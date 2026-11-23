import hashlib
import uuid

from django.core.exceptions import ValidationError
# Django's file wrapper (has .chunks(), .seek(), .read()); UploadedFile from a
# request is a subclass. Renamed so it doesn't clash with the File model.
from django.core.files import File as DjangoFile
from django.core.files.storage import Storage, storages
from django.utils import timezone

from core.models import File

# Error codes (ValidationError.code) the web views and the API react to.
UNSUPPORTED_TYPE = "unsupported_type"
EMPTY_FILE = "empty_file"

# Content types accepted per kind, with the extension used in the key. Audio:
# WAV (the live process's recording, converted), and what browsers record
# with MediaRecorder: WebM or Ogg with Opus (Chrome, Firefox), MP4 (Safari).
ALLOWED_TYPES = {
    File.Kind.AUDIO: {
        "audio/wav": "wav", "audio/x-wav": "wav", "audio/wave": "wav",
        "audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a",
    },
}


class FilesService:
    """CRUD for stored files. Every operation keeps both halves together: the
    bytes in the storage (S3) and the metadata row (core.models.File). The
    service builds the keys; callers pass the file and its context.

    Goes through django.core.files.storage.storages only, never boto3, so the
    storage backend can be swapped in settings.STORAGES."""

    def __init__(self, storage_name: str = "files") -> None:
        self.storage_name: str = storage_name
        self.storage: Storage = storages[storage_name]

    # --- Create ---

    def create(
        self,
        uploaded: DjangoFile,
        kind: File.Kind,
        content_type: str,
        session_id: uuid.UUID,
        talk_id: uuid.UUID,
    ) -> File:
        """Stores `uploaded` and its File row, and returns the row.

        Key: sessions/<session_id>/<talk_id>/<file_id>.<ext>
        Both or neither: nothing is stored if the checks fail, no row is made
        if the upload fails, and the uploaded object is deleted again if the
        row can't be saved.

        `uploaded` is any Django File (an UploadedFile from a request, or
        django.core.files.File around an open file). The size and SHA-256
        checksum are computed here from the bytes.
        """
        extension, size, checksum = self._check(uploaded, kind, content_type)

        file_id = uuid.uuid4()
        uploaded.seek(0)
        # The storage may change the name, so the returned one is recorded.
        key = self.storage.save(
            f"sessions/{session_id}/{talk_id}/{file_id}.{extension}", uploaded)
        try:
            return File.objects.create(
                id=file_id,
                # S3 bucket name; empty for backends without buckets.
                bucket=getattr(self.storage, "bucket_name", "") or "",
                key=key,
                kind=kind,
                content_type=content_type,
                size_bytes=size,
                checksum_sha256=checksum,
                uploaded_at=timezone.now(),
            )
        except Exception:
            self.storage.delete(key)
            raise

    # --- Read ---

    def get(self, file_id: uuid.UUID) -> File:
        """The File row (metadata). Raises File.DoesNotExist."""
        return File.objects.get(pk=file_id)

    def open(self, file: File) -> DjangoFile:
        """The stored bytes, opened for reading (binary). Close it after use,
        best with `with service.open(file) as f:`."""
        return self.storage.open(file.key, "rb")

    def url(self, file: File) -> str:
        """Link to the stored bytes. On S3 a signed link that expires
        (querystring_expire in settings), so the bucket stays private. Check
        that the user may see the file before handing this out."""
        return self.storage.url(file.key)

    # --- Update ---

    def update(self, file: File, uploaded: DjangoFile, content_type: str | None = None) -> File:
        """Replaces the content of `file`: stores the new bytes under a new key
        in the same folder, points the row at them, then deletes the old
        object. The row never points at missing or half-written bytes.
        `content_type` defaults to the current one and must fit the kind."""
        content_type = content_type or file.content_type
        extension, size, checksum = self._check(uploaded, file.kind, content_type)

        old_key = file.key
        folder = old_key.rsplit("/", 1)[0]
        uploaded.seek(0)
        file.key = self.storage.save(f"{folder}/{uuid.uuid4()}.{extension}", uploaded)
        file.content_type = content_type
        file.size_bytes = size
        file.checksum_sha256 = checksum
        file.uploaded_at = timezone.now()
        try:
            file.save(update_fields=["key", "content_type", "size_bytes", "checksum_sha256", "uploaded_at"])
        except Exception:
            # Row still points at the old object: drop the new one.
            self.storage.delete(file.key)
            file.key = old_key
            raise
        self.storage.delete(old_key)
        return file

    # --- Delete ---

    def delete(self, file: File) -> None:
        """Deletes the stored object, then the row. If the object can't be
        deleted, the row stays so the file isn't forgotten and the delete can
        be retried. A key that doesn't exist is not an error."""
        self.storage.delete(file.key)
        file.delete()

    # --- Shared by create and update ---

    def _check(self, uploaded: DjangoFile, kind: File.Kind, content_type: str) -> tuple[str, int, str]:
        """Validates the type and the content and returns
        (extension, size in bytes, SHA-256 hex). One pass over the bytes;
        Django already keeps large uploads in a temp file, not in memory."""
        extension = ALLOWED_TYPES.get(kind, {}).get(content_type)
        if extension is None:
            raise ValidationError(
                f"Files of type '{content_type}' can't be stored as {kind}.",
                code=UNSUPPORTED_TYPE)

        digest = hashlib.sha256()
        size = 0
        for chunk in uploaded.chunks():
            digest.update(chunk)
            size += len(chunk)
        if size == 0:
            raise ValidationError("The file is empty.", code=EMPTY_FILE)

        return extension, size, digest.hexdigest()
