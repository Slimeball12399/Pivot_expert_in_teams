import json
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path

from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.tests.utils import make_speaker, make_trainer
from core.models import Session, Talk
from core.services.TalksService import TALK_ALREADY_OPEN
from live.models import Connection, Recording
from live.Services.AudioService import AudioService
from live.Services.CommandsService import (
    INVALID_COMMAND,
    NO_OPEN_TALK,
    NOT_ALLOWED,
    Command,
    CommandsService,
)

# CommandsService: the control channel's commands and replies, and the
# recording following them. No WebRTC: a fake channel records what is sent,
# the recordings go to a temporary folder. A dropped connection pausing the talk is
# in test_connections.py.
# The talk rules themselves are tested in core/tests/test_talk_crud.py.


class FakeChannel:
    """Stands in for the aiortc data channel: keeps what is sent."""

    def __init__(self, ready_state="open"):
        self.readyState = ready_state
        self.sent = []

    def send(self, message):
        self.sent.append(json.loads(message))


class CommandsServiceTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        cls.speaker = make_speaker("mikkel@example.com", trainer=cls.trainer)

    def setUp(self):
        self.session = Session.objects.create(
            trainer=self.trainer, speaker=self.speaker.speaker_profile, status=Session.Status.LIVE,
            started_at=timezone.now() - timedelta(minutes=5))
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.audio = AudioService(Path(folder.name))
        self.addCleanup(self.audio.close)
        self.service = CommandsService(self.audio)
        self.connection = self.make_connection(self.trainer.user, Connection.Kind.TRAINER_AUDIO)

    def make_connection(self, user, kind, channel=None):
        return Connection(session_id=self.session.id, user_id=user.id, kind=kind, peer=None,
                          channel=channel or FakeChannel(), now=timezone.now())

    def command(self, type: Command, command_id=1, connection=None):
        """Sends one command, as the browser does, and returns the reply."""
        connection = connection or self.connection
        async_to_sync(self.service.handle)(connection, json.dumps({"id": command_id, "type": type}))
        return connection.channel.sent[-1]


class CommandTests(CommandsServiceTestCase):
    def test_start_pause_resume(self):
        # What the browser sends; finish and discard are HTTP.
        self.assertEqual(list(Command), ["start_talk", "pause_talk", "resume_talk"])

        with self.subTest("start: a recording talk, number 1, the reply with the browser's id"):
            reply = self.command(Command.START_TALK, command_id=7)
            talk = Talk.objects.get(session=self.session)
            self.assertEqual(reply, {"id": 7, "type": "ok", "talk": {
                "id": str(talk.id), "number": 1, "status": "RECORDING"}})
        with self.subTest("pause: the open talk, no talk id needed"):
            self.assertEqual(self.command(Command.PAUSE_TALK)["talk"]["status"], "PAUSED")
            self.assertEqual(talk.pauses.filter(resumed_at=None).count(), 1)
        with self.subTest("resume"):
            self.assertEqual(self.command(Command.RESUME_TALK)["talk"]["status"], "RECORDING")
            self.assertEqual(talk.pauses.filter(resumed_at=None).count(), 0)
        with self.subTest("a second start while one is open: TalksService's error"):
            reply = self.command(Command.START_TALK, command_id=8)
            self.assertEqual((reply["id"], reply["type"], reply["code"]), (8, "error", TALK_ALREADY_OPEN))

    def test_the_recording_follows_the_commands(self):
        talk_id = uuid.UUID(self.command(Command.START_TALK)["talk"]["id"])
        recording = self.audio.recordings[self.session.id]

        with self.subTest("start: the talk's recording, writing"):
            self.assertEqual(recording.talk_id, talk_id)
            self.assertEqual(recording.state, Recording.State.RECORDING)
        with self.subTest("pause"):
            self.command(Command.PAUSE_TALK)
            self.assertEqual(recording.state, Recording.State.PAUSED)
        with self.subTest("resume"):
            self.command(Command.RESUME_TALK)
            self.assertEqual(recording.state, Recording.State.RECORDING)
        with self.subTest("a refused command leaves it as it was"):
            self.command(Command.START_TALK)  # talk_already_open
            self.assertIs(self.audio.recordings[self.session.id], recording)
            self.assertFalse(recording.file.closed)

        # Last, because it forgets the recording.
        with self.subTest("resume after a live restart: the talk's file carries on"):
            self.command(Command.PAUSE_TALK)
            self.audio.close()  # the restart: no recordings in memory any more
            self.command(Command.RESUME_TALK)
            again = self.audio.recordings[self.session.id]
            self.assertEqual((again.talk_id, again.path), (talk_id, recording.path))
            self.assertEqual(again.state, Recording.State.RECORDING)

    def test_the_next_talk_gets_the_next_number(self):
        Talk.objects.create(session=self.session, status=Talk.Status.COMPLETED,
                            started_at=timezone.now() - timedelta(minutes=3))
        Talk.objects.create(session=self.session, status=Talk.Status.DISCARDED,
                            started_at=timezone.now() - timedelta(minutes=2))  # doesn't count
        self.assertEqual(self.command(Command.START_TALK)["talk"]["number"], 2)

    def test_rejects(self):
        with self.subTest("pause or resume without an open talk"):
            for command in (Command.PAUSE_TALK, Command.RESUME_TALK):
                self.assertEqual(self.command(command)["code"], NO_OPEN_TALK)

        cases = [
            ("not JSON", "pause please", None),
            ("no id", json.dumps({"type": "pause_talk"}), None),
            ("an id that isn't a number", json.dumps({"id": "7", "type": "pause_talk"}), None),
            ("finish goes over HTTP", json.dumps({"id": 3, "type": "finish_talk"}), 3),
            ("an unknown command", json.dumps({"id": 4, "type": "dance"}), 4),
        ]
        for label, message, command_id in cases:
            with self.subTest(label):
                async_to_sync(self.service.handle)(self.connection, message)
                reply = self.connection.channel.sent[-1]
                self.assertEqual((reply["id"], reply["code"]), (command_id, INVALID_COMMAND))

        with self.subTest("run_command (used by ConnectionService too) refuses anything else"):
            # With a talk going on, so it gets past the open talk check.
            Talk.objects.create(session=self.session, status=Talk.Status.RECORDING,
                                started_at=timezone.now())
            with self.assertRaises(ValidationError) as caught:
                async_to_sync(self.service.run_command)(self.connection, "finish_talk")
            self.assertEqual(caught.exception.code, INVALID_COMMAND)
            Talk.objects.all().delete()

        with self.subTest("the speaker's connection can't control talks"):
            phone = self.make_connection(self.speaker, Connection.Kind.SPEAKER_FEEDBACK)
            self.assertEqual(self.command(Command.START_TALK, connection=phone)["code"], NOT_ALLOWED)

        with self.subTest("a session that isn't live: TalksService's error"):
            Session.objects.filter(pk=self.session.pk).update(status=Session.Status.FINISHED)
            self.assertEqual(self.command(Command.START_TALK)["code"], "session_not_live")
        self.assertFalse(Talk.objects.exists())

    def test_a_closed_channel_gets_no_reply(self):
        closed = self.make_connection(self.trainer.user, Connection.Kind.TRAINER_AUDIO,
                                      FakeChannel(ready_state="closed"))
        async_to_sync(self.service.handle)(closed, json.dumps({"id": 1, "type": "start_talk"}))
        self.assertEqual(closed.channel.sent, [])
        # The command still ran.
        self.assertTrue(Talk.objects.filter(session=self.session, status=Talk.Status.RECORDING).exists())
