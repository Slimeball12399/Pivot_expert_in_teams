import math
import shutil
import struct
import sys
import tempfile
import uuid
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.test import SimpleTestCase

from core.models import FullVoiceResult, PartialVoiceResult, Talk
from core.services.VoiceAnalysis import VoiceAnalysis, VoiceAnalysisError

# VoiceAnalysis: running the tool in its own process, reading its output into
# the result models, and that every failure raises VoiceAnalysisError instead
# of failing silently. Small fake tools stand in for the extractor, so the
# numbers are known; one test runs the real mock when it is there.
# No database: the results are returned unsaved.

# What the fake "good" tool reports, in the tool's own keys.
GOOD_OUTPUT = {
    "meanF0": 120, "F0q10": 100, "F0q90": 150, "meanF1": 500, "meanF2": 1500, "meanF3": 2500,
    "H1-H2": 4, "H1-A3": 20, "meanSpeakingRate": 5, "meanPauseDuration": 0.5,
    "pauseCount": 6, "RMSmean": 0.1,
}
AUDIO_SECONDS = 30

# Fake tools: ProcessSingleFile(path, log_name, setup) like the real one.
WRITE_OUTPUT = (
    "def write(path, keys, values):\n"
    "    with open(path + '.txt', 'w', encoding='utf-8', newline='') as f:\n"
    "        f.write('features:\\t' + '\\t'.join(keys) + '\\r\\n' + 'values:\\t' + '\\t'.join(values))\n"
)
TOOLS = {
    "Good": WRITE_OUTPUT + (
        f"OUTPUT = {GOOD_OUTPUT!r}\n"
        "def ProcessSingleFile(path, log_name, setup):\n"
        "    write(path, list(OUTPUT), [str(v) for v in OUTPUT.values()])\n"
        "    return True\n"),
    "Silent": WRITE_OUTPUT + (
        f"OUTPUT = {dict(GOOD_OUTPUT, RMSmean=0)!r}\n"
        "def ProcessSingleFile(path, log_name, setup):\n"
        "    write(path, list(OUTPUT), [str(v) for v in OUTPUT.values()])\n"
        "    return True\n"),
    "Skips": "def ProcessSingleFile(path, log_name, setup):\n    print('skipped'); return None\n",
    "Crashes": "def ProcessSingleFile(path, log_name, setup):\n    raise RuntimeError('tool exploded')\n",
    "WritesNothing": "def ProcessSingleFile(path, log_name, setup):\n    return True\n",
    "WritesAWord": WRITE_OUTPUT + (
        "def ProcessSingleFile(path, log_name, setup):\n"
        "    write(path, ['meanF0'], ['abc']); return True\n"),
    "WritesNan": WRITE_OUTPUT + (
        "def ProcessSingleFile(path, log_name, setup):\n"
        "    write(path, ['meanF0'], ['nan']); return True\n"),
    "Uneven": WRITE_OUTPUT + (
        "def ProcessSingleFile(path, log_name, setup):\n"
        "    write(path, ['meanF0', 'meanF1'], ['120']); return True\n"),
    "LeavesOutKeys": WRITE_OUTPUT + (
        "def ProcessSingleFile(path, log_name, setup):\n"
        "    write(path, ['meanF0'], ['120']); return True\n"),
    "Hangs": "import time\ndef ProcessSingleFile(path, log_name, setup):\n    time.sleep(30)\n",
}


class VoiceAnalysisTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.folder = Path(tempfile.mkdtemp())
        for name, code in TOOLS.items():
            (cls.folder / f"{name}.py").write_text(code, encoding="utf-8")

        cls.audio = cls.folder / "talk.wav"
        with wave.open(str(cls.audio), "wb") as audio:  # 30 s of a quiet tone
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(1000)
            audio.writeframes(b"".join(
                struct.pack("<h", int(3000 * math.sin(i / 5))) for i in range(1000 * AUDIO_SECONDS)))
        cls.not_audio = cls.folder / "notes.txt"
        cls.not_audio.write_text("not a recording", encoding="utf-8")

        cls.talk = Talk(id=uuid.uuid4())
        cls.start_at = datetime(2026, 11, 16, 17, 0, tzinfo=timezone.utc)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.folder, ignore_errors=True)
        super().tearDownClass()

    def analysis(self, tool="Good", **kwargs):
        """A VoiceAnalysis running one of the fake tools with this Python."""
        return VoiceAnalysis(**{"script": self.folder / f"{tool}.py", "python": sys.executable, **kwargs})

    def assertFails(self, expected, func, *args):
        """func(*args) raises VoiceAnalysisError, with `expected` in its message."""
        with self.assertRaises(VoiceAnalysisError) as ctx:
            func(*args)
        self.assertIn(expected, str(ctx.exception))
        return ctx.exception

    def test_short_analysis(self):
        result = self.analysis().get_short_analysis(self.audio, self.talk, self.start_at)

        self.assertIsInstance(result, PartialVoiceResult)
        self.assertEqual(result.talk, self.talk)
        self.assertEqual(result.start_at, self.start_at)
        self.assertEqual(result.window_length, timedelta(seconds=AUDIO_SECONDS))
        expected = {
            "mean_f0": 120, "f0_range_q90_q10": 50, "mean_f1": 500, "mean_f2": 1500,
            "mean_f3": 2500, "h1_h2_corrected": 4, "h1_a3_corrected": 20, "mean_speaking_rate": 5,
        }
        for field, value in expected.items():
            with self.subTest(field):
                self.assertEqual(getattr(result, field), value)
        with self.subTest("left for later: the score, and voiced seconds the tool doesn't give"):
            self.assertIsNone(result.voice_score)
            self.assertIsNone(result.voiced_seconds)

    def test_long_analysis(self):
        result = self.analysis().get_long_analysis(self.audio, self.talk)

        self.assertIsInstance(result, FullVoiceResult)
        self.assertEqual(result.talk, self.talk)
        cases = [
            ("a shared measure", "f0_range_q90_q10", 50),
            ("speaking rate", "mean_speaking_rate", 5),
            ("mean pause", "mean_pause_duration", 0.5),
            ("pauses per minute: 6 in 30 s", "pause_frequency", 12),
            ("loudness: 20 * log10(0.1)", "spl_dbfs", -20),
        ]
        for label, field, value in cases:
            with self.subTest(label):
                self.assertAlmostEqual(getattr(result, field), value)
        self.assertIsNone(result.voice_score)

    def test_output_never_lands_next_to_the_audio(self):
        self.analysis().get_long_analysis(self.audio, self.talk)
        self.assertFalse(Path(f"{self.audio}.txt").exists())

    def test_failures_raise(self):
        missing_audio = self.folder / "missing.wav"
        cases = [
            ("the audio file is missing", "Good", {}, missing_audio, "audio file isn't there"),
            ("the tool is missing", "NoSuchTool", {}, self.audio, "tool isn't there"),
            ("the tool skips the file", "Skips", {}, self.audio, "skipped"),
            ("the tool crashes", "Crashes", {}, self.audio, "failed (exit code 1)"),
            ("the tool writes nothing", "WritesNothing", {}, self.audio, "wrote no output"),
            ("the tool writes a word", "WritesAWord", {}, self.audio, "not a number"),
            ("the tool writes nan", "WritesNan", {}, self.audio, "meanF0 is nan"),
            ("features and values don't match", "Uneven", {}, self.audio, "2 features but 1 values"),
            ("the tool leaves out keys", "LeavesOutKeys", {}, self.audio, "is missing: F0q10"),
            ("the tool hangs", "Hangs", {"timeout": 1}, self.audio, "took longer than 1 s"),
            ("the Python can't start", "Good", {"python": str(self.folder / "no-python")},
             self.audio, "Can't start"),
        ]
        for label, tool, options, audio, expected in cases:
            with self.subTest(label):
                self.assertFails(expected, self.analysis(tool, **options).get_short_analysis,
                                 audio, self.talk, self.start_at)

        with self.subTest("a crash brings the tool's own error along"):
            error = self.assertFails("tool exploded", self.analysis("Crashes").get_long_analysis,
                                     self.audio, self.talk)
            self.assertIn("RuntimeError", str(error))

    def test_long_analysis_failures_raise(self):
        cases = [
            ("not a WAV", "Good", self.not_audio, "Can't read the length"),
            ("silent audio has no loudness", "Silent", self.audio, "is silent"),
        ]
        for label, tool, audio, expected in cases:
            with self.subTest(label):
                self.assertFails(expected, self.analysis(tool).get_long_analysis, audio, self.talk)

    @skipUnless(Path(settings.VOICE_ANALYSIS_SCRIPT).is_file(), "the voice analysis tool isn't there")
    def test_the_configured_tool(self):
        """The tool from settings (the mock for now), end to end."""
        result = VoiceAnalysis().get_long_analysis(self.audio, self.talk)
        for field in ("mean_f0", "f0_range_q90_q10", "mean_speaking_rate", "pause_frequency", "spl_dbfs"):
            with self.subTest(field):
                self.assertTrue(math.isfinite(getattr(result, field)))
