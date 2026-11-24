"""Runs the voice analysis tool (VoiceMock/FeatureExtractor.py for now, the
real extractor later) and turns its output into the voice result models in
core/models/results.py (PartialVoiceResult, FullVoiceResult).

How the tool works, FeatureExtractor.ProcessSingleFile(path, log_name, setup):
- input: the path of one audio file (WAV). log_name and setup are unused.
- output: a text file next to the input, named `<path>.txt`, with two
  tab-separated lines:
      features:<TAB>minF0<TAB>maxF0<TAB>...
      values:<TAB>81.2<TAB>243.7<TAB>...
- a missing or empty input writes nothing; the tool only prints "skipped"
  and returns None.

The tool runs in its own Python process, so a crash or a hang in it can't
take the server down, and its error output ends up in the raised error.
Every failure raises VoiceAnalysisError; nothing fails silently.
"""
import math
import shutil
import subprocess
import tempfile
import wave
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings

from core.models import FullVoiceResult, PartialVoiceResult, Talk

# Runs inside the tool's Python process: imports the tool and analyses one
# file. argv: the tool's folder, its module name, the audio path.
# Exit code 2: the tool skipped the file (missing or empty).
RUNNER = (
    "import importlib, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "tool = importlib.import_module(sys.argv[2])\n"
    "sys.exit(0 if tool.ProcessSingleFile(sys.argv[3], None, None) is not None else 2)\n"
)

# Tool output keys each analysis needs.
SHORT_KEYS = ("meanF0", "F0q10", "F0q90", "meanF1", "meanF2", "meanF3", "H1-H2", "H1-A3",
              "meanSpeakingRate")
LONG_KEYS = SHORT_KEYS + ("meanPauseDuration", "pauseCount", "RMSmean")

# How much of the tool's error output goes into the error message.
STDERR_TAIL = 2000


class VoiceAnalysisError(Exception):
    """The voice analysis couldn't produce results. The message says why."""


class VoiceAnalysis:
    def __init__(self, script: str | None = None, python: str | None = None,
                 timeout: int = 300) -> None:
        """`script`: the tool's .py file; `python`: the Python that runs it
        (default: settings.VOICE_ANALYSIS_SCRIPT and VOICE_ANALYSIS_PYTHON);
        `timeout`: seconds before a run is stopped and counts as failed."""
        self.script = Path(script or settings.VOICE_ANALYSIS_SCRIPT)
        self.python = python or settings.VOICE_ANALYSIS_PYTHON
        self.timeout = timeout

    def get_short_analysis(self, wav_path: str | Path, talk: Talk,
                           start_at: datetime) -> PartialVoiceResult:
        """One window of `talk` that starts at `start_at` (UTC), as an unsaved
        PartialVoiceResult; the caller saves it. window_length is the length
        of the WAV. voiced_seconds stays empty: the tool doesn't report it."""
        raw = self._run(wav_path, SHORT_KEYS)
        return PartialVoiceResult(
            talk=talk,
            start_at=start_at,
            window_length=self._length(wav_path),
            **self._shared_measures(raw),
        )

    def get_long_analysis(self, wav_path: str | Path, talk: Talk) -> FullVoiceResult:
        """The whole of `talk`, as an unsaved FullVoiceResult; the caller saves
        it. The short measures plus pauses and loudness."""
        raw = self._run(wav_path, LONG_KEYS)
        minutes = self._length(wav_path).total_seconds() / 60
        if raw["RMSmean"] <= 0:
            raise VoiceAnalysisError(f"{Path(wav_path).name} is silent (RMS 0), so there is no loudness.")

        return FullVoiceResult(
            talk=talk,
            **self._shared_measures(raw),
            mean_pause_duration=raw["meanPauseDuration"],
            pause_frequency=raw["pauseCount"] / minutes,
            # RMS is relative to full scale (0..1), so this is dBFS, not calibrated dB SPL.
            spl_dbfs=20 * math.log10(raw["RMSmean"]),
        )

    def _length(self, wav_path: str | Path) -> timedelta:
        """How long the WAV is. Raises VoiceAnalysisError if it can't be read
        or has no audio."""
        try:
            with wave.open(str(wav_path), "rb") as audio:
                seconds = audio.getnframes() / audio.getframerate()
        except (wave.Error, EOFError, OSError) as exc:
            raise VoiceAnalysisError(f"Can't read the length of {Path(wav_path).name}: {exc}") from exc
        if seconds <= 0:
            raise VoiceAnalysisError(f"{Path(wav_path).name} has no audio.")
        return timedelta(seconds=seconds)

    def _shared_measures(self, raw: dict[str, float]) -> dict[str, float]:
        """The tool's keys turned into the fields both result models share."""
        return {
            "mean_f0": raw["meanF0"],
            "f0_range_q90_q10": raw["F0q90"] - raw["F0q10"],
            "mean_f1": raw["meanF1"],
            "mean_f2": raw["meanF2"],
            "mean_f3": raw["meanF3"],
            # The mock gives the uncorrected H1-H2 and H1-A3. The real tool
            # should give the formant-corrected ones (H1*-H2*, H1*-A3*).
            "h1_h2_corrected": raw["H1-H2"],
            "h1_a3_corrected": raw["H1-A3"],
            "mean_speaking_rate": raw["meanSpeakingRate"],
        }

    def _run(self, wav_path: str | Path, required: tuple[str, ...]) -> dict[str, float]:
        """Runs the tool on `wav_path` and returns its output as {key: number}.
        Raises VoiceAnalysisError when the tool is missing, fails, hangs,
        skips the file, writes nothing, or writes something unreadable or
        without the `required` keys."""
        wav_path = Path(wav_path)
        if not self.script.is_file():
            raise VoiceAnalysisError(f"The voice analysis tool isn't there: {self.script}")
        if not wav_path.is_file():
            raise VoiceAnalysisError(f"The audio file isn't there: {wav_path}")

        with tempfile.TemporaryDirectory() as work:
            # The tool writes its .txt next to its input, so it gets a copy in
            # a folder of our own; the output never lands next to the original.
            audio = Path(work) / wav_path.name
            shutil.copyfile(wav_path, audio)

            try:
                result = subprocess.run(
                    [self.python, "-c", RUNNER, str(self.script.parent), self.script.stem, str(audio)],
                    capture_output=True, text=True, timeout=self.timeout, cwd=work)
            except subprocess.TimeoutExpired as exc:
                raise VoiceAnalysisError(
                    f"The voice analysis of {wav_path.name} took longer than {self.timeout} s.") from exc
            except OSError as exc:
                raise VoiceAnalysisError(f"Can't start {self.python}: {exc}") from exc

            if result.returncode == 2:
                raise VoiceAnalysisError(
                    f"The voice analysis skipped {wav_path.name} (missing or empty file).")
            if result.returncode != 0:
                raise VoiceAnalysisError(
                    f"The voice analysis of {wav_path.name} failed (exit code {result.returncode}):\n"
                    f"{result.stderr[-STDERR_TAIL:]}")

            output = Path(f"{audio}.txt")
            if not output.is_file():
                raise VoiceAnalysisError(f"The voice analysis of {wav_path.name} wrote no output.")
            lines = output.read_text(encoding="utf-8").splitlines()

        if (len(lines) < 2 or not lines[0].startswith("features:")
                or not lines[1].startswith("values:")):
            raise VoiceAnalysisError(
                f"Unexpected output for {wav_path.name}: needs a 'features:' and a 'values:' line.")
        keys = lines[0].split("\t")[1:]
        values = lines[1].split("\t")[1:]
        if len(keys) != len(values):
            raise VoiceAnalysisError(
                f"Unexpected output for {wav_path.name}: {len(keys)} features but {len(values)} values.")

        raw = {}
        for key, value in zip(keys, values):
            try:
                number = float(value)
            except ValueError:
                raise VoiceAnalysisError(
                    f"Unexpected output for {wav_path.name}: {key} is {value!r}, not a number.") from None
            if not math.isfinite(number):
                raise VoiceAnalysisError(f"Unexpected output for {wav_path.name}: {key} is {value}.")
            raw[key] = number

        missing = [key for key in required if key not in raw]
        if missing:
            raise VoiceAnalysisError(
                f"The voice analysis of {wav_path.name} is missing: {', '.join(missing)}.")
        return raw
