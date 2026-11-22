"""The commands a trainer's browser sends over a connection's "control" data
channel (live.models.Connection.channel), and the replies.

Over the channel: start_talk, pause_talk and resume_talk. Finishing and
discarding a talk go over HTTP (finishing can carry the exact WAV). The rules
stay in core.services.TalksService; this only reads the message, finds the
talk and replies.

A command, JSON:     {"id": 7, "type": "pause_talk"}
The reply:           {"id": 7, "type": "ok", "talk": {"id": "...", "number": 2, "status": "PAUSED"}}
                     {"id": 7, "type": "error", "code": "invalid_transition", "detail": "..."}

"id" is the browser's own number, so it can match the reply (feedback comes
over the same channel at any time). There is no talk id: a session has at
most one open talk (RECORDING or PAUSED), and the connection knows the session.

Each command also updates the session's recording (AudioService) once
TalksService has said yes: start opens it, pause and resume pause and resume
it. A dropped connection pauses the open talk through the same pause_talk
command (ConnectionService.connection_dropped), so its recording pauses too.
"""

import asyncio
import json
import logging
import uuid
import weakref
from enum import StrEnum

from asgiref.sync import sync_to_async
from django.core.exceptions import ValidationError

from accounts.models import User
from core.models import Talk
from core.services.TalksService import pause_talk, resume_talk, start_talk
from live.models import Connection
from live.Services.AudioService import AudioService

logger = logging.getLogger(__name__)



class Command(StrEnum):
    """The commands the channel takes, as the browser sends them in "type".
    Finishing and discarding a talk are HTTP, not here."""

    START_TALK = "start_talk"
    PAUSE_TALK = "pause_talk"
    RESUME_TALK = "resume_talk"


# Error codes in the replies, next to the ones TalksService raises
# (invalid_transition, talk_already_open, session_not_live, ...).
INVALID_COMMAND = "invalid_command"
NOT_ALLOWED = "not_allowed"
NO_OPEN_TALK = "no_open_talk"
INTERNAL_ERROR = "internal_error"


class CommandsService:
    """Runs the commands of every connection, one at a time per connection."""

    def __init__(self, audio: AudioService):
        # The recordings the commands start, pause and resume.
        self.audio = audio
        # One lock per connection, so a quick "pause, resume" runs in the order
        # it was sent: each message is handled in its own task. Weak, so a
        # closed connection's lock goes with it.
        self.locks: weakref.WeakKeyDictionary[Connection, asyncio.Lock] = weakref.WeakKeyDictionary()

    async def handle(self, connection: Connection, message: str | bytes):
        """One message from the channel: checks its shape, runs the command
        and sends the reply on the same channel."""
        try:
            data = json.loads(message)
        except (TypeError, ValueError):
            data = None
        # Only a number id is sent back: the browser matches replies to its
        # commands by it, so anything else gets null (bool is an int, but no id).
        command_id = data.get("id") if isinstance(data, dict) else None
        if not isinstance(command_id, int) or isinstance(command_id, bool):
            command_id = None

        if not isinstance(data, dict) or not isinstance(command_id, int) or data.get("type") not in Command:
            reply = {"type": "error", "code": INVALID_COMMAND,
                     "detail": f"Send JSON with a number id and a type, one of {', '.join(Command)}."}
        elif connection.kind != Connection.Kind.TRAINER_AUDIO:
            reply = {"type": "error", "code": NOT_ALLOWED,
                     "detail": "Only the trainer's connection can control the talks."}
        else:
            try:
                talk = await self.run_command(connection, Command(data["type"]))
            except ValidationError as error:
                reply = {"type": "error", "code": error.code, "detail": error.messages[0]}
            except Exception:
                # Keep the channel working; the details go to the log.
                logger.exception("Command %s on %s failed", data["type"], connection)
                reply = {"type": "error", "code": INTERNAL_ERROR,
                         "detail": "Something went wrong on the server. Try again."}
            else:
                reply = {"type": "ok", "talk": talk}

        if connection.channel.readyState == "open":
            connection.channel.send(json.dumps({"id": command_id, **reply}))

    async def run_command(self, connection: Connection, command: Command) -> dict:
        """Runs the command for the connection, after any command of the same
        connection still running, and returns the talk as the reply shows it.
        Raises ValidationError when TalksService says no. Used by handle() and
        by ConnectionService (a dropped connection pauses the talk).

        The recording follows only once the talk has changed, so a refused
        command leaves it as it was. It is changed here, on the event loop,
        not in apply_command: that runs in a worker thread, and the recordings
        belong to the loop (AudioService.read writes them)."""
        async with self.locks.setdefault(connection, asyncio.Lock()):
            talk = await sync_to_async(self.apply_command)(connection, command)
            recording = self.audio.recordings.get(connection.session_id)
            if command == Command.START_TALK:
                self.audio.start_recording(connection.session_id, uuid.UUID(talk["id"]))
            elif command == Command.PAUSE_TALK:
                if recording is not None:
                    recording.pause()
            elif command == Command.RESUME_TALK:
                if recording is not None:
                    recording.resume()
                else:
                    # None after a live restart: the talk carries on in its file.
                    self.audio.start_recording(connection.session_id, uuid.UUID(talk["id"]))
            return talk

    def apply_command(self, connection: Connection, command: Command) -> dict:
        """run_command's database part, through TalksService (synchronous: the
        ORM). Start needs no talk (TalksService refuses a second open one);
        every other command acts on the session's open talk, so that is
        checked first, then which command it is. Anything that isn't a command
        is refused, so a command added to Command without a branch here can't
        run as another one."""
        trainer = User.objects.get(pk=connection.user_id)
        if command == Command.START_TALK:
            talk = start_talk(trainer, connection.session_id)
        else:
            # At most one per session: RECORDING or PAUSED.
            open_talk = Talk.objects.filter(
                session_id=connection.session_id,
                status__in=[Talk.Status.RECORDING, Talk.Status.PAUSED]).first()
            if open_talk is None:
                raise ValidationError("There is no talk going on.", code=NO_OPEN_TALK)
            if command == Command.PAUSE_TALK:
                talk = pause_talk(trainer, open_talk.id)
            elif command == Command.RESUME_TALK:
                talk = resume_talk(trainer, open_talk.id)
            else:
                raise ValidationError(f"Unknown command: {command}.", code=INVALID_COMMAND)

        # Its place in the session, 1 to n, as on the session page: discarded talks don't count.
        number = (Talk.objects.filter(session_id=connection.session_id, started_at__lte=talk.started_at)
                  .exclude(status=Talk.Status.DISCARDED).count())
        return {"id": str(talk.id), "number": number, "status": talk.status}
