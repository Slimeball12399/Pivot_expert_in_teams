from django.db import models

from .core import UUIDModel
from .sessions import Talk


class VoiceMeasures(UUIDModel):
    """The voice parameters that are scored. These follow the scoring set, not
    the extractor output: a separate adapter translates the extractor output
    into these fields. Null when a value could not be produced.

    Which parameters live here (scored live and on the full talk) and which
    only on FullVoiceResult is provisional until Oliver's feedback."""

    mean_f0 = models.FloatField(null=True, blank=True)  # Hz
    # F0 range as Q90 - Q10, not max - min.
    f0_range_q90_q10 = models.FloatField(null=True, blank=True)  # Hz
    mean_f1 = models.FloatField(null=True, blank=True)  # Hz
    mean_f2 = models.FloatField(null=True, blank=True)  # Hz
    mean_f3 = models.FloatField(null=True, blank=True)  # Hz
    # Formant-corrected spectral tilt (H1*-H2*, H1*-A3*).
    h1_h2_corrected = models.FloatField(null=True, blank=True)  # dB
    h1_a3_corrected = models.FloatField(null=True, blank=True)  # dB

    mean_speaking_rate = models.FloatField(
        null=True, blank=True)  # syllables/s

    # Calculated from the measures above; null until scored.
    voice_score = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class PartialVoiceResult(VoiceMeasures):
    """Measures for one window of a talk (e.g. 30 s window, 5 s step), for the
    live graph and lining voice up against stability."""

    talk = models.ForeignKey(
        Talk, on_delete=models.CASCADE, related_name="partial_voice_results")
    # Absolute UTC time the window starts, same time base as the stability data.
    start_at = models.DateTimeField()
    window_length = models.DurationField()
    # Seconds of voiced speech in the window, to filter or down-weight thin windows.
    voiced_seconds = models.FloatField(null=True, blank=True)
    # The two lines of the live voice graph, as scores from -10 to +10; null
    # until scored.
    pace_score = models.FloatField(null=True, blank=True)
    pitch_variation_score = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["start_at"]
        constraints = [
            # Reprocessing a talk can't create the same window twice.
            models.UniqueConstraint(
                fields=["talk", "start_at", "window_length"],
                name="unique_partial_voice_window",
            ),
        ]

    def __str__(self):
        return f"Partial voice {self.talk_id} @ {self.start_at}"


class FullVoiceResult(VoiceMeasures):
    """Measures for a whole talk. Adds the parameters that are only scored on
    the full recording (provisional, see VoiceMeasures)."""

    talk = models.OneToOneField(
        Talk, on_delete=models.CASCADE, related_name="full_voice_result")

    mean_pause_duration = models.FloatField(null=True, blank=True)  # s
    pause_frequency = models.FloatField(null=True, blank=True)  # pauses/min
    # Derived from RMS as 20*log10(rms). Relative to full scale, not calibrated
    # dB SPL, so only comparable within the same recording setup.
    spl_dbfs = models.FloatField(null=True, blank=True)  # dBFS

    def __str__(self):
        return f"Full voice {self.talk_id}"
