"""The analysis of a finished talk, run in the background by the worker
(core/tasks.py, python manage.py db_worker), never in a request.

The long analysis of the whole talk: its stored audio (Talk.audio: the
browser's WebM, Ogg or MP4, or the server's WAV) is fetched from the file
storage, converted to a WAV the voice analysis tool reads (16 kHz, mono,
16-bit: the same as the live process's recording), analysed as a whole and
scored (ScoresService); the FullVoiceResult is saved and the talk is
COMPLETED. The windows (PartialVoiceResult) come from the live process while
the talk is recorded (live/Services/FeedbackService.py), not from here.
Still to come: the converted WAV kept, retries.
"""
import shutil
import tempfile
import uuid
import wave
from pathlib import Path

import av
from django.db import transaction

from core.models import FullVoiceResult, Talk
from core.services.FilesService import FilesService
from core.services.ScoresService import score_result
from core.services.VoiceAnalysis import VoiceAnalysis, VoiceAnalysisError

# The WAV the voice analysis tool gets.
WAV_SAMPLE_RATE = 16000
WAV_SAMPLE_WIDTH = 2  # bytes: 16-bit


def analyse_talk(talk_id: uuid.UUID, sex: str | None = None) -> FullVoiceResult | None:
    """Analyses and scores the talk's stored audio as a whole, saves the
    FullVoiceResult (replacing one from an earlier attempt) and sets the talk
    COMPLETED; returns the result. `sex` ("men" or "women") picks the bands of
    the measures that have them (ScoresService). None, with nothing saved,
    when the talk isn't PROCESSING any more (discarded meanwhile). Raises
    VoiceAnalysisError when the talk has no audio, the audio can't be decoded,
    or the tool fails (see VoiceAnalysis); Talk.DoesNotExist for a talk that
    isn't there."""
    talk = Talk.objects.select_related("audio").get(pk=talk_id)
    if talk.audio is None:
        raise VoiceAnalysisError(f"Talk {talk.id} has no stored audio.")

    with tempfile.TemporaryDirectory() as work:
        # A local copy first: PyAV reads it by path, the storage's file object
        # may not seek the way it needs.
        original = Path(work) / Path(talk.audio.key).name
        with FilesService().open(talk.audio) as stored, original.open("wb") as copy:
            shutil.copyfileobj(stored, copy)

        wav_path = Path(work) / f"{talk.id}.wav"
        try:
            with av.open(str(original)) as container, wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(WAV_SAMPLE_WIDTH)
                wav.setframerate(WAV_SAMPLE_RATE)
                resampler = av.AudioResampler(format="s16", layout="mono", rate=WAV_SAMPLE_RATE)
                for frame in container.decode(audio=0):
                    for resampled in resampler.resample(frame):
                        wav.writeframes(bytes(resampled.planes[0])[:resampled.samples * WAV_SAMPLE_WIDTH])
                # What the resampler still holds at the end.
                for resampled in resampler.resample(None):
                    wav.writeframes(bytes(resampled.planes[0])[:resampled.samples * WAV_SAMPLE_WIDTH])
        except av.FFmpegError as error:
            raise VoiceAnalysisError(f"The audio of talk {talk.id} can't be decoded: {error}") from error

        result = VoiceAnalysis().get_long_analysis(wav_path, talk)

    result.voice_score = score_result(result, sex=sex)["voice_score"]
    with transaction.atomic():
        talk = Talk.objects.select_for_update().get(pk=talk.pk)
        if talk.status != Talk.Status.PROCESSING:
            return None
        FullVoiceResult.objects.filter(talk=talk).delete()
        result.talk = talk
        result.save()
        talk.status = Talk.Status.COMPLETED
        talk.save(update_fields=["status"])
    return result
