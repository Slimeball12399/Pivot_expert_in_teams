"""Scores from the voice measures, with the bands in core/voice_ranges.json.

One measure: 100 anywhere inside its good band. Outside it the score falls
along a normal (bell) curve with the distance from the good band, scaled so
it is MEDIUM_EDGE_SCORE (50) exactly at the edge of the medium band: 100 good,
50 to 100 medium, under 50 bad, nearing 0 further out (twice as far as the
medium edge: 6.25). A one-sided band (a null limit) only falls on its open
side: half a bell. The overall score is the mean of the measures scored.

The same for both kinds of result: a PartialVoiceResult (one window) is
scored on the measures it has, with a measure's "partial" bands if the file
gives them, else its usual ones; a FullVoiceResult also has pauses and
loudness. Measures with bands per sex (men, women) need the speaker's sex;
without it they are left out, and only the measures the same for everyone
(both) count.

signed_score gives the same as -10 to +10 for the live voice graph's lines
(PartialVoiceResult.pace_score, pitch_variation_score): 0 inside good, -5 or
+5 at the medium edge, nearing -10 or +10 further out; minus below the good
band (too slow, too flat), plus above it.

Nothing is saved here: the caller puts the scores where they belong.
"""
import json
import math
from pathlib import Path

from core.models import PartialVoiceResult

RANGES_FILE = Path(__file__).resolve().parent.parent / "voice_ranges.json"
# The bands, read once when the module loads. Change the file, restart the process.
RANGES = {key: entry for key, entry in json.loads(RANGES_FILE.read_text(encoding="utf-8")).items()
          if not key.startswith("_")}

# The score at the edge of the medium band.
MEDIUM_EDGE_SCORE = 50
# How many standard deviations the medium edge is from the good band, so that
# 100 * exp(-spread² / 2) is MEDIUM_EDGE_SCORE there.
SPREAD = math.sqrt(2 * math.log(100 / MEDIUM_EDGE_SCORE))


def score_measure(key: str, value: float | None, sex: str | None = None, partial: bool = False) -> float | None:
    """One measure's score, 0 to 100, or None when it can't be scored: no value,
    no bands for it, or bands per sex and no `sex` ("men" or "women") given.
    `partial`: a window's measure, scored with the measure's "partial" bands
    if it has them."""
    entry = RANGES.get(key)
    if entry is None or value is None:
        return None
    bands = entry.get("partial", entry) if partial else entry
    band = bands.get("both") or (bands.get(sex) if sex else None)
    if band is None:
        return None
    good, medium = band["good"], band["medium"]

    if good["low"] is not None and value < good["low"]:
        distance, edge = good["low"] - value, good["low"] - medium["low"]
    elif good["high"] is not None and value > good["high"]:
        distance, edge = value - good["high"], medium["high"] - good["high"]
    else:
        return 100.0
    if edge <= 0:
        # No medium band on this side: straight from good to bad.
        return 0.0
    sigma = edge / SPREAD
    return 100 * math.exp(-0.5 * (distance / sigma) ** 2)


def score_result(result, sex: str | None = None) -> dict:
    """The scores of a PartialVoiceResult or FullVoiceResult:
    {"measures": {field: score or None}, "voice_score": the mean of the
    measures scored, or None if none could be}. Only the measures the result
    has (a window has no pauses or loudness)."""
    partial = isinstance(result, PartialVoiceResult)
    measures = {key: score_measure(key, getattr(result, key), sex, partial)
                for key in RANGES if hasattr(result, key)}
    scored = [score for score in measures.values() if score is not None]
    return {"measures": measures, "voice_score": sum(scored) / len(scored) if scored else None}


def signed_score(key: str, value: float | None, sex: str | None = None, partial: bool = False) -> float | None:
    """score_measure as -10 to +10: 0 inside good, 10 * (1 - score / 100)
    outside it (5 at the medium edge), negative below the good band and
    positive above it. None when the measure can't be scored."""
    score = score_measure(key, value, sex, partial)
    if score is None or score == 100:
        return None if score is None else 0.0
    bands = RANGES[key].get("partial", RANGES[key]) if partial else RANGES[key]
    good = (bands.get("both") or bands[sex])["good"]
    below = good["low"] is not None and value < good["low"]
    return (-1 if below else 1) * 10 * (1 - score / 100)
