import os
import re
import math
import random
from typing import Optional

PROFILES = {
    "male": {
        "f0_mean": (120, 20),     # (mean, std) of the speaker's average F0
        "f1": (500, 40),
        "f2": (1500, 100),
        "f3": (2500, 150),
    },
    "female": {
        "f0_mean": (210, 25),
        "f1": (600, 50),
        "f2": (1800, 120),
        "f3": (2900, 170),
    },
}


def _tnorm(rng: random.Random, mean: float, std: float, lo: float, hi: float) -> float:
    """Normal sample clipped to [lo, hi] (resamples a few times, then clamps)."""
    for _ in range(10):
        x = rng.gauss(mean, std)
        if lo <= x <= hi:
            return x
    return min(max(rng.gauss(mean, std), lo), hi)


def mock_features(
    duration_s: float = 120.0,
    sex: Optional[str] = None,
    seed: Optional[int] = None,
    decimals: int = 2,
) -> dict:
    """
    Return a mock feature dict.

    duration_s: length of the (pretend) recording, drives pauseCount
    sex: "male", "female" or None for random
    seed: set for reproducible output (useful in tests)
    """
    rng = random.Random(seed)
    profile = PROFILES[sex or rng.choice(list(PROFILES))]

    # --- F0 (pitch) ---
    mean_f0 = _tnorm(rng, *profile["f0_mean"], lo=70, hi=320)
    # Pitch variability in semitones; lively speakers 3-5 st std, monotone ~1.5
    std_st = _tnorm(rng, 3.0, 0.8, 1.2, 5.5)
    def st_to_hz(st): return mean_f0 * 2 ** (st / 12)

    q10 = st_to_hz(-1.28 * std_st)
    q90 = st_to_hz(1.28 * std_st)
    # Extremes sit beyond the quantiles (octave jumps, emphasis, creak)
    min_f0 = st_to_hz(-_tnorm(rng, 2.6, 0.4, 2.0, 3.5) * std_st)
    max_f0 = st_to_hz(_tnorm(rng, 3.0, 0.5, 2.0, 4.0) * std_st)
    f0_std_hz = mean_f0 * (2 ** (std_st / 12) - 1)
    f0_range_st = 12 * math.log2(max_f0 / min_f0)

    # --- Formants (voice color) ---
    f1 = _tnorm(rng, *profile["f1"], lo=300, hi=900)
    f2 = _tnorm(rng, *profile["f2"], lo=f1 + 400, hi=2600)
    f3 = _tnorm(rng, *profile["f3"], lo=f2 + 500, hi=3600)

    # --- Spectral tilt measures (dB) ---
    # Breathier voices have higher H1-H2; pressed voices lower
    # shared factor keeps the tilt measures correlated
    breathiness = rng.gauss(0, 1)
    h1h2 = _tnorm(rng, 4 + 2 * breathiness, 1.5, -4, 14)
    h1a1 = _tnorm(rng, 5 + 3 * breathiness, 3.0, -10, 22)
    h1a2 = _tnorm(rng, 12 + 3 * breathiness, 3.5, -2, 30)
    h1a3 = _tnorm(rng, 20 + 4 * breathiness, 4.5, 3, 40)

    def tilt_std(mean_val: float) -> float:
        return _tnorm(rng, 3 + 0.15 * abs(mean_val), 1.0, 1.0, 9.0)

    # --- Pauses and rate ---
    pauses_per_min = _tnorm(rng, 12, 4, 3, 28)
    pause_count = max(0, round(pauses_per_min * duration_s / 60))
    mean_pause = _tnorm(rng, 0.65, 0.2, 0.25, 1.6)        # seconds
    articulation_rate = _tnorm(
        rng, 5.0, 0.6, 3.5, 6.8)   # syllables per second

    # --- Intensity (normalized amplitude, 0..1 full scale) ---
    rms_mean = _tnorm(rng, 0.06, 0.02, 0.015, 0.15)
    rms_std = rms_mean * _tnorm(rng, 0.55, 0.12, 0.25, 0.9)

    def r(x): return round(x, decimals)
    return {
        "minF0": r(min_f0),
        "maxF0": r(max_f0),
        "meanF0": r(mean_f0),
        "F0range": r(f0_range_st),
        "F0std": r(f0_std_hz),
        "F0q10": r(q10),
        "F0q90": r(q90),
        "meanF1": r(f1),
        "meanF2": r(f2),
        "meanF3": r(f3),
        "meanF2+3": r(f2 + f3),
        "H1-H2": r(h1h2),
        "H1-H2std": r(tilt_std(h1h2)),
        "H1-A1": r(h1a1),
        "H1-A1std": r(tilt_std(h1a1)),
        "H1-A2": r(h1a2),
        "H1-A2std": r(tilt_std(h1a2)),
        "H1-A3": r(h1a3),
        "H1-A3std": r(tilt_std(h1a3)),
        "pauseCount": pause_count,
        "meanPauseDuration": r(mean_pause),
        "meanSpeakingRate": r(articulation_rate),
        "RMSmean": round(rms_mean, 4),
        "RMSstd": round(rms_std, 4),
    }


def generate_features():
    keyOrder = ['minF0', 'maxF0', 'meanF0', 'F0range', 'F0std', 'F0q10', 'F0q90', 'meanF1',
                'meanF2', 'meanF3', 'meanF2+3', 'H1-H2', 'H1-H2std', 'H1-A1', 'H1-A1std', 'H1-A2', 'H1-A2std',
                'H1-A3', 'H1-A3std', 'pauseCount', 'meanPauseDuration', 'meanSpeakingRate', 'RMSmean', 'RMSstd']
    features = mock_features()
    return keyOrder, features


def ProcessDirectory(srcPath, pattern, trgPath):
    data = {}
    print('path: ', srcPath)

    for fName in os.listdir(srcPath):
        if re.match(pattern, fName):
            print('  processing:', fName)
            fIn = os.path.join(srcPath, fName)
            result = ProcessSingleFile(fIn, None, None)
            if result is not None:
                data[fName] = result

    if not data:
        print('no matching files found')
        return data

    # Write one combined table: header row, then one row per file
    keys = next(iter(data.values()))[0]
    out = ['file' + '\t' + '\t'.join(keys)]
    for fName, (_, values) in data.items():
        out.append(fName + '\t' + '\t'.join(values))

    os.makedirs(os.path.dirname(trgPath) or '.', exist_ok=True)
    with open(trgPath, 'w', encoding='utf-8', newline='') as f:
        f.write('\r\n'.join(out))

    print('written:', trgPath)
    return data


def ProcessSingleFile(fIn, logName, setupJson):
    # Check the file exists and is not empty
    if not os.path.isfile(fIn) or os.path.getsize(fIn) == 0:
        print('    skipped (missing or empty):', fIn)
        return None

    keys, dta = generate_features()

    out = ['features:' + '\t' + '\t'.join(keys)]
    featureVector = [str(dta[k]) for k in keys]
    out.append('values:' + '\t' + '\t'.join(featureVector))

    with open(fIn + '.txt', 'w', encoding='utf-8', newline='') as f:
        f.write('\r\n'.join(out))

    return keys, featureVector
