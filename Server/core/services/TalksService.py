"""Talks inside a live session, as in the talk state machine in
core/LogicGraphs.md: start, pause, resume, finish and discard.

Only the session's trainer controls talks. Whether the devices are connected
(needed before starting or resuming) is checked by the caller, which knows the
WebRTC state; these functions only look at the database.

get_talk reads one talk with all its results, for the session's trainer and
its speaker. A session's talks come with get_session.
"""
import logging
import tempfile
from functools import partial
import uuid
import wave
from pathlib import Path

import av

from django.core.exceptions import ValidationError
from django.core.files import File as DjangoFile
from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.utils import timezone

from accounts.models import User
from core.models import File, PartialVoiceResult, Session, Talk
from core.services.FilesService import FilesService
from core.services.SessionsService import INVALID_TRANSITION, NOT_ADMIN, get_session
from core.tasks import analyse_talk

# Error codes (ValidationError.code) the web views and the API react to.
# NOT_ADMIN and INVALID_TRANSITION are the same codes as for sessions.
SESSION_NOT_LIVE = "session_not_live"
TALK_ALREADY_OPEN = "talk_already_open"
TALK_NOT_YOURS = "talk_not_yours"

# The live process's recording (live/Services/AudioService.py writes it): raw
# PCM, 16 kHz, mono, 16-bit. finish_talk wraps it in a WAV header to store it.
PCM_SAMPLE_RATE = 16000
PCM_CHANNELS = 1
PCM_SAMPLE_WIDTH = 2
# The browser's recording counts as intact when it decodes all the way and is
# at most this many seconds shorter than the talk (its start and its pauses
# lag the server's a little).
INTACT_TOLERANCE_SECONDS = 5

logger = logging.getLogger(__name__)


@transaction.atomic
def start_talk(trainer: User, session_id: uuid.UUID) -> Talk:
    """Starts a talk in one of `trainer`'s live sessions and returns it
    (RECORDING, started_at set). Refused while the session already has a talk
    that is recording or paused."""
    if trainer.role != User.Role.ADMIN:
        raise ValidationError("Only admins can manage talks.", code=NOT_ADMIN)
    session = get_session(user=trainer, session_id=session_id)
    if session.status != Session.Status.LIVE:
        raise ValidationError(
            "Talks can only be started in a live session; this one is "
            f"{session.get_status_display().lower()}.",
            code=SESSION_NOT_LIVE)

    try:
        return Talk.objects.create(session=session, started_at=timezone.now())
    except IntegrityError as exc:
        if "one_open_talk_per_session" in str(exc):
            raise ValidationError(
                "This session already has a talk going on. Finish it first.",
                code=TALK_ALREADY_OPEN) from exc
        raise


@transaction.atomic
def pause_talk(trainer: User, talk_id: uuid.UUID) -> Talk:
    """Pauses a recording talk (RECORDING -> PAUSED) and records when the
    pause started, as a TalkPause."""
    talk = _trainers_talk(trainer, talk_id)
    if talk.status != Talk.Status.RECORDING:
        raise ValidationError(
            "Only a recording talk can be paused; this one is "
            f"{talk.get_status_display().lower()}.",
            code=INVALID_TRANSITION)

    talk.status = Talk.Status.PAUSED
    talk.save(update_fields=["status"])
    talk.pauses.create(paused_at=timezone.now())
    return talk


@transaction.atomic
def resume_talk(trainer: User, talk_id: uuid.UUID) -> Talk:
    """Continues a paused talk (PAUSED -> RECORDING) and closes its pause."""
    talk = _trainers_talk(trainer, talk_id)
    if talk.status != Talk.Status.PAUSED:
        raise ValidationError(
            "Only a paused talk can be resumed; this one is "
            f"{talk.get_status_display().lower()}.",
            code=INVALID_TRANSITION)

    talk.pauses.filter(resumed_at__isnull=True).update(resumed_at=timezone.now())
    talk.status = Talk.Status.RECORDING
    talk.save(update_fields=["status"])
    return talk


@transaction.atomic
def finish_talk(trainer: User, talk_id: uuid.UUID, audio: UploadedFile | None = None,
                recording: Path | None = None) -> Talk:
    """Finishes a recording or paused talk (-> PROCESSING) and sets its
    duration: the time recorded, without the pauses. Its audio is stored with
    it (FilesService, Talk.audio), for the analysis that follows separately.
    Two recordings can come with it:

    - `audio`: the browser's own recording (MediaRecorder, as it was sent:
      WebM, Ogg or MP4), the better one: recorded at the mic, with no network
      in between. It is used when intact: it decodes all the way (PyAV) and
      is as long as the talk, give or take INTACT_TOLERANCE_SECONDS;
    - `recording`: the live process's PCM file (closed by the caller first),
      stored as a WAV.

    Stored: the browser's file if intact; else the PCM as a WAV (a broken or
    short browser file is logged and dropped); else, with no PCM, the browser's
    file anyway (the only copy); else nothing (no audio). The PCM is deleted
    once its audio is safely stored: after the commit, whichever of the two
    was stored. With audio stored, the analysis is enqueued after the commit
    too (core/tasks.py, the analysis queue). Without a `recording` (the live process didn't confirm it
    closed the file) nothing is deleted.

    The caller checks the browser's file type (FilesService.ALLOWED_TYPES)
    before anything changes; a file that doesn't fit raises unsupported_type
    or empty_file here and nothing is finished."""
    talk = _trainers_talk(trainer, talk_id)
    if talk.status not in (Talk.Status.RECORDING, Talk.Status.PAUSED):
        raise ValidationError(
            "Only a recording or paused talk can be finished; this one is "
            f"{talk.get_status_display().lower()}.",
            code=INVALID_TRANSITION)

    # First: the duration the browser's recording is checked against.
    talk.close(Talk.Status.PROCESSING, timezone.now())
    pcm = recording if recording is not None and recording.exists() else None

    # Is the browser's file intact? Decoded all the way, its length added up
    # from the audio frames (MediaRecorder's WebM carries no duration).
    intact = False
    if audio is not None:
        seconds = 0.0
        try:
            audio.seek(0)
            with av.open(audio, mode="r") as container:
                for frame in container.decode(audio=0):
                    seconds += frame.samples / frame.sample_rate
            intact = seconds >= talk.duration.total_seconds() - INTACT_TOLERANCE_SECONDS
        except Exception as error:
            # Anything PyAV can't read (not audio, cut off, no audio stream).
            logger.warning("The browser's recording of talk %s doesn't decode: %s", talk.id, error)
        else:
            if not intact:
                logger.warning("The browser's recording of talk %s is %.1f s, the talk %.1f s",
                               talk.id, seconds, talk.duration.total_seconds())
        audio.seek(0)

    if audio is not None and (intact or pcm is None):
        talk.audio = FilesService().create(
            audio, File.Kind.AUDIO, audio.content_type, talk.session_id, talk.id)
    elif pcm is not None:
        with tempfile.TemporaryFile() as wav_file:
            # wave writes the header (with the length) when it is closed; the
            # temporary file stays open for the upload.
            with wave.open(wav_file, "wb") as wav, pcm.open("rb") as samples:
                wav.setnchannels(PCM_CHANNELS)
                wav.setsampwidth(PCM_SAMPLE_WIDTH)
                wav.setframerate(PCM_SAMPLE_RATE)
                while chunk := samples.read(1024 * 1024):
                    wav.writeframes(chunk)
            talk.audio = FilesService().create(
                DjangoFile(wav_file, name=f"{talk.id}.wav"), File.Kind.AUDIO, "audio/wav",
                talk.session_id, talk.id)
    if talk.audio_id is not None:
        talk.save(update_fields=["audio"])
        # Stored: the PCM isn't needed any more. After the commit, so a
        # rollback doesn't leave the talk without either.
        if pcm is not None:
            transaction.on_commit(lambda: pcm.unlink(missing_ok=True), robust=True)
        # The analysis, in the background (core/tasks.py). After the commit,
        # so the worker never looks for a talk that isn't saved yet.
        transaction.on_commit(partial(analyse_talk.enqueue, str(talk.id)))
    return talk


@transaction.atomic
def discard_talk(trainer: User, talk_id: uuid.UUID) -> Talk:
    """Throws a talk away (-> DISCARDED) and returns it. Takes the place of
    deleting: the row stays, but its audio is deleted, since a recording the
    trainer threw away isn't kept.

    The audio is deleted after the commit, so a discard that is rolled back
    never loses the recording. If that delete fails, the talk is still
    discarded and the error is logged; the file is left for a cleanup job.
    """
    talk = _trainers_talk(trainer, talk_id)
    if talk.status == Talk.Status.DISCARDED:
        raise ValidationError("This talk is already discarded.", code=INVALID_TRANSITION)

    # A talk discarded while paused: its pause ends now.
    talk.pauses.filter(resumed_at__isnull=True).update(resumed_at=timezone.now())
    talk.status = Talk.Status.DISCARDED
    talk.save(update_fields=["status"])
    if talk.audio is not None:
        audio = talk.audio
        transaction.on_commit(lambda: FilesService().delete(audio), robust=True)
    return talk


# --- Read ---

def get_talk(user: User, talk_id: uuid.UUID) -> Talk:
    """The talk with its full voice result and all its partial voice results
    (talk.partial_voice_results.all(), in time order), if `user` may see it:
    - admin: talks in the sessions they are the trainer of
    - speaker: talks in their own sessions
    Anything else, or a talk that doesn't exist, gives talk_not_yours (the
    same error, so the API doesn't reveal which talk ids exist).
    Discarded talks are returned too; callers check the status they need.
    """
    talks = (Talk.objects
             .select_related("full_voice_result")
             .prefetch_related(Prefetch(
                 "partial_voice_results",
                 queryset=PartialVoiceResult.objects.order_by("start_at"))))
    if user.role == User.Role.ADMIN:
        talk = talks.filter(pk=talk_id, session__trainer__user=user).first()
    elif user.role == User.Role.SPEAKER:
        talk = talks.filter(pk=talk_id, session__speaker__user=user).first()
    else:
        talk = None
    if talk is None:
        raise ValidationError("This talk is not one of yours.", code=TALK_NOT_YOURS)
    return talk


def _trainers_talk(trainer: User, talk_id: uuid.UUID) -> Talk:
    """The talk, if `trainer` is an admin and it is in one of their sessions;
    raises otherwise. A missing and someone else's talk give the same error,
    so the API doesn't reveal which talk ids exist."""
    if trainer.role != User.Role.ADMIN:
        raise ValidationError("Only admins can manage talks.", code=NOT_ADMIN)
    talk = (Talk.objects.select_related("audio")
            .filter(pk=talk_id, session__trainer__user=trainer).first())
    if talk is None:
        raise ValidationError("This talk is not one of yours.", code=TALK_NOT_YOURS)
    return talk
