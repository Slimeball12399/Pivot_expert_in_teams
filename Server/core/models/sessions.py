from datetime import timedelta

from django.db import models
from django.db.models import F, Q

from core.validators import validate_scheduled_at

from .core import File, UUIDModel


class Session(UUIDModel):
    class Status(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not started"
        LIVE = "LIVE", "Live"
        FINISHED = "FINISHED", "Finished"
        CANCELLED = "CANCELLED", "Cancelled"  # ended before it ever went live, no data
        ABORTED = "ABORTED", "Aborted"  # went live but did not end cleanly, partial data
        DELETED = "DELETED", "Deleted"  # finished, then taken out by the trainer; the row stays

    class Display(models.TextChoices):
        WEB = "WEB", "Browser only"
        MOBILE = "MOBILE", "Mobile only"
        BOTH = "BOTH", "Browser and mobile"

    # SET_NULL: deleting a trainer account keeps the speaker's history.
    trainer = models.ForeignKey(
        "accounts.AdminProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
    )
    # CASCADE: deleting a speaker account deletes their sessions (files in the
    # object store need their own cleanup).
    speaker = models.ForeignKey(
        "accounts.SpeakerProfile",
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NOT_STARTED)
    # Where the live feedback is shown to the speaker.
    display = models.CharField(max_length=8, choices=Display.choices, default=Display.WEB)

    # Null when the session is started on the spot without scheduling.
    scheduled_at = models.DateTimeField(null=True, blank=True, validators=[validate_scheduled_at])
    started_at = models.DateTimeField(null=True, blank=True)
    # Set for finished and aborted sessions.
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Only one LIVE session per speaker at a time.
            models.UniqueConstraint(
                fields=["speaker"],
                condition=Q(status="LIVE"),
                name="one_live_session_per_speaker",
            ),
            # Can't end before it started (null passes: unfinished sessions have no end).
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True) | Q(ended_at__gte=F("started_at")),
                name="session_ends_after_start",
            ),
        ]

    def __str__(self):
        return f"Session {self.id} {self.status}"

class Talk(UUIDModel):
    class Status(models.TextChoices):
        RECORDING = "RECORDING", "Recording"
        PAUSED = "PAUSED", "Paused"  # each pause is a TalkPause row
        PROCESSING = "PROCESSING", "Processing"  # audio uploaded, STT/analysis running
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"  # upload lost or analysis crashed
        DISCARDED = "DISCARDED", "Discarded"  # trainer threw the talk away

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="talks")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECORDING)
    # The row is created when recording starts.
    started_at = models.DateTimeField()
    # Null while recording, set when recording stops.
    duration = models.DurationField(null=True, blank=True)
    # Automatic retries of the current processing step; FAILED after the limit.
    analysis_attempts = models.PositiveSmallIntegerField(default=0)
    # SET_NULL: the File row goes away only together with its MinIO object.
    audio = models.OneToOneField(
        File,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="talk",
    )

    class Meta:
        ordering = ["started_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(duration__isnull=True) | Q(duration__gte=timedelta(0)),
                name="talk_duration_not_negative",
            ),
            # One talk at a time per session: at most one RECORDING or PAUSED.
            models.UniqueConstraint(
                fields=["session"],
                condition=Q(status__in=["RECORDING", "PAUSED"]),
                name="one_open_talk_per_session",
            ),
        ]

    def close(self, status, now):
        """Ends this talk at `now` with `status` and saves it: a pause going on
        ends now, and duration becomes the time recorded, without the pauses.
        Only sets the talk's own data; the services decide when a talk may be
        closed and with which status."""
        self.pauses.filter(resumed_at__isnull=True).update(resumed_at=now)
        paused = sum((p.resumed_at - p.paused_at for p in self.pauses.all()), start=timedelta(0))
        self.status = status
        self.duration = now - self.started_at - paused
        self.save(update_fields=["status", "duration"])

    def __str__(self):
        return f"Talk {self.id} {self.status}"


class TalkPause(UUIDModel):
    """One pause in a talk. Kept as intervals (not just a total), so the
    audio, which has no pauses in it, can be mapped back to real time and
    lined up with the stability data."""

    talk = models.ForeignKey(Talk, on_delete=models.CASCADE, related_name="pauses")
    paused_at = models.DateTimeField()
    # Null while the pause is going on.
    resumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["paused_at"]
        constraints = [
            # At most one pause going on per talk.
            models.UniqueConstraint(
                fields=["talk"],
                condition=Q(resumed_at__isnull=True),
                name="one_open_pause_per_talk",
            ),
            models.CheckConstraint(
                condition=Q(resumed_at__isnull=True) | Q(resumed_at__gte=F("paused_at")),
                name="pause_resumes_after_it_starts",
            ),
        ]

    def __str__(self):
        return f"Pause of talk {self.talk_id} at {self.paused_at}"
