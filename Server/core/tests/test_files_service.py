import hashlib
import uuid
from unittest import mock

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase, override_settings

from core.models import File
from core.services.FilesService import EMPTY_FILE, UNSUPPORTED_TYPE, FilesService

# FilesService against Django's InMemoryStorage instead of MinIO, so these run
# without the object store. What's checked: the stored bytes and the File row
# always exist together, the key layout, and that failures leave nothing behind.

IN_MEMORY_STORAGES = {
    **settings.STORAGES,
    "files": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
}

AUDIO = b"RIFF fake wav bytes for the tests"
NEW_AUDIO = b"RIFF other wav bytes, a bit longer than the first ones"


def wav(content=AUDIO, content_type="audio/wav"):
    return SimpleUploadedFile("talk.wav", content, content_type=content_type)


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class FilesServiceTests(TestCase):
    def setUp(self):
        self.service = FilesService()
        self.session_id = uuid.uuid4()
        self.talk_id = uuid.uuid4()

    def create(self, content=AUDIO, content_type="audio/wav"):
        return self.service.create(
            wav(content, content_type),
            kind=File.Kind.AUDIO,
            content_type=content_type,
            session_id=self.session_id,
            talk_id=self.talk_id,
        )

    # --- Create ---

    def test_create_stores_bytes_and_row(self):
        file = self.create()

        self.assertEqual(file.key, f"sessions/{self.session_id}/{self.talk_id}/{file.id}.wav")
        self.assertEqual(file.kind, File.Kind.AUDIO)
        self.assertEqual(file.content_type, "audio/wav")
        self.assertEqual(file.size_bytes, len(AUDIO))
        self.assertEqual(file.checksum_sha256, hashlib.sha256(AUDIO).hexdigest())
        self.assertIsNotNone(file.uploaded_at)
        self.assertTrue(File.objects.filter(pk=file.pk).exists())
        self.assertTrue(self.service.storage.exists(file.key))

    def test_create_accepts_every_wav_spelling(self):
        for content_type in ("audio/wav", "audio/x-wav", "audio/wave"):
            with self.subTest(content_type=content_type):
                file = self.create(content_type=content_type)
                self.assertTrue(file.key.endswith(".wav"))

    def test_create_rejects_unsupported_type(self):
        with self.assertRaises(ValidationError) as ctx:
            self.create(content_type="audio/mpeg")

        self.assertEqual(ctx.exception.code, UNSUPPORTED_TYPE)
        self.assertFalse(File.objects.exists())

    def test_create_rejects_empty_file(self):
        with self.assertRaises(ValidationError) as ctx:
            self.create(content=b"")

        self.assertEqual(ctx.exception.code, EMPTY_FILE)
        self.assertFalse(File.objects.exists())

    def test_create_stores_nothing_when_rejected(self):
        file_id = uuid.uuid4()
        with mock.patch("core.services.FilesService.uuid.uuid4", return_value=file_id):
            with self.assertRaises(ValidationError):
                self.create(content=b"")

        key = f"sessions/{self.session_id}/{self.talk_id}/{file_id}.wav"
        self.assertFalse(self.service.storage.exists(key))

    def test_create_deletes_object_when_row_fails(self):
        file_id = uuid.uuid4()
        with mock.patch("core.services.FilesService.uuid.uuid4", return_value=file_id), \
                mock.patch.object(File.objects, "create", side_effect=IntegrityError("boom")):
            with self.assertRaises(IntegrityError):
                self.create()

        key = f"sessions/{self.session_id}/{self.talk_id}/{file_id}.wav"
        self.assertFalse(self.service.storage.exists(key))
        self.assertFalse(File.objects.exists())

    def test_create_makes_no_row_when_upload_fails(self):
        with mock.patch.object(self.service.storage, "save", side_effect=OSError("storage down")):
            with self.assertRaises(OSError):
                self.create()

        self.assertFalse(File.objects.exists())

    # --- Read ---

    def test_get_returns_row(self):
        file = self.create()
        self.assertEqual(self.service.get(file.id), file)

    def test_get_unknown_id_raises(self):
        with self.assertRaises(File.DoesNotExist):
            self.service.get(uuid.uuid4())

    def test_open_returns_stored_bytes(self):
        file = self.create()
        with self.service.open(file) as f:
            self.assertEqual(f.read(), AUDIO)

    def test_url_points_at_key(self):
        file = self.create()
        self.assertIn(file.key, self.service.url(file))

    # --- Update ---

    def test_update_replaces_content_and_deletes_old_object(self):
        file = self.create()
        old_key = file.key

        updated = self.service.update(file, wav(NEW_AUDIO))

        self.assertEqual(updated.pk, file.pk)
        self.assertNotEqual(updated.key, old_key)
        self.assertEqual(updated.key.rsplit("/", 1)[0], old_key.rsplit("/", 1)[0])
        self.assertFalse(self.service.storage.exists(old_key))
        self.assertTrue(self.service.storage.exists(updated.key))
        with self.service.open(updated) as f:
            self.assertEqual(f.read(), NEW_AUDIO)

        row = File.objects.get(pk=file.pk)
        self.assertEqual(row.key, updated.key)
        self.assertEqual(row.size_bytes, len(NEW_AUDIO))
        self.assertEqual(row.checksum_sha256, hashlib.sha256(NEW_AUDIO).hexdigest())

    def test_update_rejects_unsupported_type_and_keeps_old(self):
        file = self.create()
        old_key = file.key

        with self.assertRaises(ValidationError) as ctx:
            self.service.update(file, wav(NEW_AUDIO, "audio/mpeg"), content_type="audio/mpeg")

        self.assertEqual(ctx.exception.code, UNSUPPORTED_TYPE)
        self.assertEqual(file.key, old_key)
        self.assertTrue(self.service.storage.exists(old_key))
        self.assertEqual(File.objects.get(pk=file.pk).checksum_sha256, hashlib.sha256(AUDIO).hexdigest())

    def test_update_keeps_old_when_row_save_fails(self):
        file = self.create()
        old_key = file.key
        new_id = uuid.uuid4()
        new_key = f"{old_key.rsplit('/', 1)[0]}/{new_id}.wav"

        with mock.patch("core.services.FilesService.uuid.uuid4", return_value=new_id), \
                mock.patch.object(File, "save", side_effect=IntegrityError("boom")):
            with self.assertRaises(IntegrityError):
                self.service.update(file, wav(NEW_AUDIO))

        self.assertEqual(file.key, old_key)
        self.assertTrue(self.service.storage.exists(old_key))
        self.assertFalse(self.service.storage.exists(new_key))
        self.assertEqual(File.objects.get(pk=file.pk).key, old_key)

    # --- Delete ---

    def test_delete_removes_object_and_row(self):
        file = self.create()
        key = file.key

        self.service.delete(file)

        self.assertFalse(self.service.storage.exists(key))
        self.assertFalse(File.objects.filter(key=key).exists())

    def test_delete_keeps_row_when_storage_fails(self):
        file = self.create()

        with mock.patch.object(self.service.storage, "delete", side_effect=OSError("storage down")):
            with self.assertRaises(OSError):
                self.service.delete(file)

        self.assertTrue(File.objects.filter(pk=file.pk).exists())
