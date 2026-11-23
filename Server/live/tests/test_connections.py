from asgiref.sync import async_to_sync

from core.models import Session, Talk
from live.models import Connection, Recording
from live.Services.CommandsService import Command
from live.Services.ConnectionService import ConnectionService

from .test_commands import CommandsServiceTestCase

# ConnectionService.connection_dropped: what a lost connection does, and the
# reconnect timeout (time_out). No WebRTC: the connection has no peer, a fake
# channel stands in for the data channel. Offers and answers need aiortc and a
# browser; they are tried by hand.


class ConnectionDroppedTests(CommandsServiceTestCase):
    def setUp(self):
        super().setUp()
        self.connections = ConnectionService(ice_servers=[], commands=self.service, audio=self.audio)

    def drop(self, connection=None):
        async_to_sync(self.connections.connection_dropped)(connection or self.connection)

    def test_pauses_a_recording_talk(self):
        self.command(Command.START_TALK)
        self.drop()
        talk = Talk.objects.get(session=self.session)

        with self.subTest("the connection: disconnected, with the time"):
            self.assertEqual(self.connection.state, Connection.State.DISCONNECTED)
            self.assertIsNotNone(self.connection.disconnected_at)
        with self.subTest("the talk: paused, through the pause command"):
            self.assertEqual(talk.status, Talk.Status.PAUSED)
            self.assertEqual(talk.pauses.count(), 1)
        with self.subTest("the recording: paused with it"):
            self.assertEqual(self.audio.recordings[self.session.id].state, Recording.State.PAUSED)
        with self.subTest("dropping again: still one pause"):
            self.drop()
            self.assertEqual(talk.pauses.count(), 1)

    def test_without_a_talk_nothing_happens(self):
        self.drop()
        self.assertEqual(self.connection.state, Connection.State.DISCONNECTED)
        self.assertFalse(Talk.objects.exists())

    def test_the_speakers_connection_leaves_the_talk(self):
        self.command(Command.START_TALK)
        phone = self.make_connection(self.speaker, Connection.Kind.SPEAKER_FEEDBACK)
        self.drop(phone)
        self.assertEqual(phone.state, Connection.State.DISCONNECTED)
        self.assertEqual(Talk.objects.get(session=self.session).status, Talk.Status.RECORDING)


class ReconnectTimeoutTests(CommandsServiceTestCase):
    """The trainer's connection drops and doesn't come back: after
    reconnect_timeout the session is finished, its open talk failed."""

    def setUp(self):
        super().setUp()
        # Long while dropping, so the timer a drop starts doesn't fire in the test.
        self.connections = ConnectionService(ice_servers=[], commands=self.service, audio=self.audio,
                                             reconnect_timeout=60)

    def time_out(self):
        """Runs the timer itself, without its wait."""
        self.connections.reconnect_timeout = 0
        async_to_sync(self.connections.time_out)(self.session.id, self.trainer.user.id)

    def test_a_drop_starts_the_timer_once(self):
        async_to_sync(self.connections.connection_dropped)(self.connection)
        self.assertIn(self.connection.key, self.connections.timeouts)
        timer = self.connections.timeouts[self.connection.key]
        async_to_sync(self.connections.connection_dropped)(self.connection)
        self.assertIs(self.connections.timeouts[self.connection.key], timer)

    def test_the_speakers_drop_starts_none(self):
        phone = self.make_connection(self.speaker, Connection.Kind.SPEAKER_FEEDBACK)
        async_to_sync(self.connections.connection_dropped)(phone)
        self.assertEqual(self.connections.timeouts, {})

    def test_no_reconnect_finishes_the_session_and_fails_the_talk(self):
        self.command(Command.START_TALK)
        talk = Talk.objects.get(session=self.session)
        async_to_sync(self.connections.connection_dropped)(self.connection)
        with self.assertLogs("live.Services.ConnectionService", "INFO"):
            self.time_out()

        self.session.refresh_from_db()
        talk.refresh_from_db()
        with self.subTest("the session: finished, with its end"):
            self.assertEqual(self.session.status, Session.Status.FINISHED)
            self.assertIsNotNone(self.session.ended_at)
        with self.subTest("the talk: failed, with what it recorded"):
            self.assertEqual(talk.status, Talk.Status.FAILED)
            self.assertIsNotNone(talk.duration)
        with self.subTest("its recording: closed, the file kept"):
            self.assertNotIn(self.session.id, self.audio.recordings)
            self.assertTrue((self.audio.recordings_dir / f"{talk.id}.pcm").exists())
        with self.subTest("the timer: gone"):
            self.assertNotIn(self.connection.key, self.connections.timeouts)

    def test_a_session_ended_meanwhile_is_left_alone(self):
        Session.objects.filter(pk=self.session.pk).update(status=Session.Status.FINISHED)
        self.time_out()
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, Session.Status.FINISHED)
