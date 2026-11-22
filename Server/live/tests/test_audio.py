import tempfile
import uuid
from datetime import timedelta
from fractions import Fraction
from pathlib import Path

import av
from aiortc.mediastreams import MediaStreamError
from asgiref.sync import async_to_sync
from django.test import SimpleTestCase
from django.utils import timezone

from live.models import Connection, Recording
from live.Services.AudioService import BYTES_PER_SAMPLE, SAMPLE_RATE, AudioService

# Recording (the file and the rolling window) and AudioService (reading a
# track into the session's recording). No WebRTC: real av frames from a fake
# track, as aiortc delivers them. Wiring to the talk commands comes later.


def audio_frame(index, samples=960, rate=48000):
    """One 20 ms frame of 48 kHz mono s16, like aiortc's Opus decoder gives."""
    frame = av.AudioFrame(format="s16", layout="mono", samples=samples)
    frame.planes[0].update(b"\x10\x00" * samples)
    frame.sample_rate = rate
    frame.pts = index * samples
    frame.time_base = Fraction(1, rate)
    return frame


class FakeTrack:
    """Hands out the given frames, then ends like a closed track."""

    def __init__(self, frames):
        self.frames = list(frames)
        self.readyState = "live"

    async def recv(self):
        if not self.frames:
            self.readyState = "ended"
            raise MediaStreamError
        return self.frames.pop(0)


class FilesTestCase(SimpleTestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.files_dir = Path(folder.name)


class RecordingTests(FilesTestCase):
    def make_recording(self, window_bytes=100):
        recording = Recording(uuid.uuid4(), self.files_dir / "talk.pcm", window_bytes, timezone.now())
        self.addCleanup(lambda: recording.file.closed or recording.close())
        return recording

    def test_writes_only_while_recording(self):
        recording = self.make_recording()
        now = timezone.now()
        recording.write(b"ab", now)

        with self.subTest("paused: nothing written, the window emptied"):
            recording.pause()
            recording.write(b"cd", now)
            self.assertIsNone(recording.current_window())
        with self.subTest("resumed: the same file goes on"):
            recording.resume()
            recording.write(b"ef", now)
            recording.close()
            self.assertEqual(recording.path.read_bytes(), b"abef")
        with self.subTest("last_frame_at: the last written frame"):
            self.assertEqual(recording.last_frame_at, now)

    def test_a_new_recording_appends_to_the_same_file(self):
        """After a live restart the talk continues the file it had."""
        first = self.make_recording()
        first.write(b"ab", timezone.now())
        first.close()
        second = self.make_recording()
        second.write(b"cd", timezone.now())
        second.close()
        self.assertEqual(second.path.read_bytes(), b"abcd")

    def test_the_window_keeps_the_last_window_bytes(self):
        recording = self.make_recording(window_bytes=6)
        start = timezone.now()
        for second, pcm in enumerate([b"aa", b"bb", b"cc", b"dd"]):
            recording.write(pcm, start + timedelta(seconds=second))
        # 8 bytes written, 6 kept: the oldest frame dropped, the window starts at the second one.
        self.assertEqual(recording.current_window(), (start + timedelta(seconds=1), b"bbccdd"))
        recording.close()
        self.assertEqual(recording.path.read_bytes(), b"aabbccdd")  # the file keeps everything


class AudioServiceTests(FilesTestCase):
    def setUp(self):
        super().setUp()
        self.service = AudioService(self.files_dir)
        self.addCleanup(self.service.close)
        self.session_id = uuid.uuid4()
        self.connection = Connection(session_id=self.session_id, user_id=uuid.uuid4(),
                                     kind=Connection.Kind.TRAINER_AUDIO, peer=None, channel=None,
                                     now=timezone.now())

    def read(self, frames):
        async_to_sync(self.service.read)(self.connection, FakeTrack(frames))

    def test_start_and_finish(self):
        talk_id = uuid.uuid4()
        recording = self.service.start_recording(self.session_id, talk_id)

        with self.subTest("a file per talk under recordings/"):
            self.assertEqual(recording.path, self.files_dir / "recordings" / f"{talk_id}.pcm")
            self.assertIs(self.service.recordings[self.session_id], recording)
            self.assertEqual(self.service.window_bytes, 30 * SAMPLE_RATE * BYTES_PER_SAMPLE)
        with self.subTest("starting the next talk closes the previous one"):
            following = self.service.start_recording(self.session_id, uuid.uuid4())
            self.assertTrue(recording.file.closed)
            self.assertIs(self.service.recordings[self.session_id], following)
        with self.subTest("finishing an older talk: the current one goes on"):
            self.assertIsNone(self.service.finish_recording(talk_id))
            self.assertIs(self.service.recordings[self.session_id], following)
        with self.subTest("finish by its talk: closed, handed back, gone"):
            self.assertIs(self.service.finish_recording(following.talk_id), following)
            self.assertTrue(following.file.closed)
            self.assertNotIn(self.session_id, self.service.recordings)
            self.assertIsNone(self.service.finish_recording(following.talk_id))

    def test_reads_the_track_into_the_recording(self):
        recording = self.service.start_recording(self.session_id, uuid.uuid4())
        self.read(audio_frame(index) for index in range(50))  # 1 s at 48 kHz
        self.service.finish_recording(recording.talk_id)

        written = recording.path.read_bytes()
        # Resampled to 16 kHz mono s16: about a second's worth (the resampler
        # may hold back a few samples at the end).
        self.assertAlmostEqual(len(written), SAMPLE_RATE * BYTES_PER_SAMPLE, delta=200)
        self.assertEqual(len(written) % BYTES_PER_SAMPLE, 0)

    def test_frames_are_dropped_unless_recording(self):
        with self.subTest("no recording: read and dropped"):
            self.read(audio_frame(index) for index in range(10))
            self.assertFalse((self.files_dir / "recordings").exists())

        with self.subTest("paused: read and dropped"):
            recording = self.service.start_recording(self.session_id, uuid.uuid4())
            recording.pause()
            self.read(audio_frame(index) for index in range(10))
            self.service.finish_recording(recording.talk_id)
            self.assertEqual(recording.path.read_bytes(), b"")

    def test_an_ended_track_isnt_read(self):
        track = FakeTrack([audio_frame(0)])
        track.readyState = "ended"
        async_to_sync(self.service.read)(self.connection, track)
        self.assertEqual(len(track.frames), 1)  # never asked for a frame
