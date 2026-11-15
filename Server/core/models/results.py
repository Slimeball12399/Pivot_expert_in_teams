from django.db import models

from .core import UUIDModel
from .sessions import Talk


class VoiceMeasures(UUIDModel):
    """Raw voice measures that are reliable on a 30 s window. Shared by the
    partial (window) and full (whole talk) results. Comments give the key in
    the extractor output and the unit. Null when the extractor gives no value."""

    # --- F0 (pitch) ---
    mean_f0 = models.FloatField(null=True, blank=True)  # meanF0, Hz
    f0_q10 = models.FloatField(null=True, blank=True)  # F0q10, Hz
    f0_q90 = models.FloatField(null=True, blank=True)  # F0q90, Hz
    f0_std = models.FloatField(null=True, blank=True)  # F0std, Hz

    # --- Formants ---
    mean_f1 = models.FloatField(null=True, blank=True)  # meanF1, Hz
    mean_f2 = models.FloatField(null=True, blank=True)  # meanF2, Hz
    mean_f3 = models.FloatField(null=True, blank=True)  # meanF3, Hz

    # --- Spectral tilt ---
    h1_h2 = models.FloatField(null=True, blank=True)  # H1-H2, dB
    h1_a1 = models.FloatField(null=True, blank=True)  # H1-A1, dB
    h1_a2 = models.FloatField(null=True, blank=True)  # H1-A2, dB
    h1_a3 = models.FloatField(null=True, blank=True)  # H1-A3, dB

    # --- Rate and pauses ---
    mean_speaking_rate = models.FloatField(null=True, blank=True)  # meanSpeakingRate, syllables/s
    mean_pause_duration = models.FloatField(null=True, blank=True)  # meanPauseDuration, s

    # --- Intensity ---
    rms_mean = models.FloatField(null=True, blank=True)  # RMSmean, 0..1 full scale
    rms_std = models.FloatField(null=True, blank=True)  # RMSstd, 0..1 full scale

    # Calculated from the measures above; null until scored.
    voice_score = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class PartialVoiceResult(VoiceMeasures):
    """Measures for one window of a talk (e.g. 30 s window, 5 s step), for the
    live graph and lining voice up against stability."""

    talk = models.ForeignKey(Talk, on_delete=models.CASCADE, related_name="partial_voice_results")
    # Absolute UTC time the window starts, same time base as the stability data.
    start_at = models.DateTimeField()
    window_length = models.DurationField()
    # Seconds of voiced speech in the window, to filter or down-weight thin windows.
    voiced_seconds = models.FloatField(null=True, blank=True)

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
    """Measures for a whole talk. Adds the ones that only hold up on the full
    recording."""

    talk = models.OneToOneField(Talk, on_delete=models.CASCADE, related_name="full_voice_result")

    min_f0 = models.FloatField(null=True, blank=True)  # minF0, Hz
    max_f0 = models.FloatField(null=True, blank=True)  # maxF0, Hz
    f0_range = models.FloatField(null=True, blank=True)  # F0range, semitones
    mean_f2_f3 = models.FloatField(null=True, blank=True)  # meanF2+3, Hz
    h1_h2_std = models.FloatField(null=True, blank=True)  # H1-H2std, dB
    h1_a1_std = models.FloatField(null=True, blank=True)  # H1-A1std, dB
    h1_a2_std = models.FloatField(null=True, blank=True)  # H1-A2std, dB
    h1_a3_std = models.FloatField(null=True, blank=True)  # H1-A3std, dB
    pause_count = models.PositiveIntegerField(null=True, blank=True)  # pauseCount

    def __str__(self):
        return f"Full voice {self.talk_id}"
