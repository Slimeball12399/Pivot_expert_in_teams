from asgiref.sync import async_to_sync

from core.models import Talk
from live.models import Connection, Recording
from live.Services.CommandsService import Command
from live.Services.ConnectionService import ConnectionService

from .test_commands import CommandsServiceTestCase

# ConnectionService.connection_dropped: what a lost connection does. No
# WebRTC: the connection has no peer, a fake channel stands in for the data
# channel. Offers and answers need aiortc and a browser; they are tried by hand.


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
