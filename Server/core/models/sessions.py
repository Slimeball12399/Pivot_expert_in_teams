from datetime import timedelta

from django.db import models
from django.db.models import F, Q

from .core import File, UUIDModel


class Session(UUIDModel):
    class Status(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not started"
        LIVE = "LIVE", "Live"
        FINISHED = "FINISHED", "Finished"
        CANCELLED = "CANCELLED", "Cancelled"  # ended before it ever went live, no data
        ABORTED = "ABORTED", "Aborted"  # went live but did not end cleanly, partial data

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
    scheduled_at = models.DateTimeField(null=True, blank=True)
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
        ]

    def __str__(self):
        return f"Talk {self.id} {self.status}"
