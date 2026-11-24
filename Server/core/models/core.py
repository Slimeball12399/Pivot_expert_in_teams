import uuid

from django.db import models


class UUIDModel(models.Model):
    """Abstract base for every model: the primary key is a random UUID
    instead of an incrementing number, so ids can't be guessed or counted."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class File(UUIDModel):
    """Metadata for one object in the object store (MinIO). The bytes live in
    MinIO; this row is the source of truth for what exists and who owns it.

    The row is created before the upload; size, checksum and uploaded_at are
    filled in once the upload is confirmed, so a null uploaded_at marks a
    failed or orphaned upload. Deleting a row does NOT delete the object in
    MinIO, that has to be done explicitly."""

    class Kind(models.TextChoices):
        AUDIO = "AUDIO", "Audio"

    bucket = models.CharField(max_length=63)
    key = models.CharField(max_length=512, unique=True)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    # SHA-256 of the content, hex. Proves the stored file is byte for byte the
    # recorded one (MinIO's ETag is not a plain MD5 for multipart uploads).
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    uploaded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.kind} {self.key}"
