import math
from unittest import mock

from django.test import SimpleTestCase

from core.models import FullVoiceResult, PartialVoiceResult
from core.services import ScoresService
from core.services.ScoresService import score_measure, score_result, signed_score

# ScoresService: a measure's score from its bands (100 in good, 50 at the
# medium edge, a bell curve in between and beyond), and a result's overall
# score. With bands of their own, so the tests don't depend on the values in
# core/voice_ranges.json.

RANGES = {
    # Two-sided, per sex.
    "mean_f1": {
        "men": {"good": {"low": 500, "high": 600}, "medium": {"low": 200, "high": 800}},
        "women": {"good": {"low": 550, "high": 700}, "medium": {"low": 400, "high": 850}},
    },
    # One-sided (higher is better), with other bands for windows.
    "f0_range_q90_q10": {
        "both": {"good": {"low": 60, "high": None}, "medium": {"low": 30, "high": None}},
        "partial": {"both": {"good": {"low": 40, "high": None}, "medium": {"low": 20, "high": None}}},
    },
    # One-sided (lower is better), only on the full result.
    "mean_pause_duration": {
        "both": {"good": {"low": None, "high": 0.8}, "medium": {"low": None, "high": 1.2}},
    },
}


@mock.patch.object(ScoresService, "RANGES", RANGES)
class ScoreMeasureTests(SimpleTestCase):
    def test_two_sided(self):
        cases = [
            ("inside good", 550, 100),
            ("on the good edge", 500, 100),
            ("the medium edge, low side", 200, 50),
            ("the medium edge, high side", 800, 50),
            ("twice as far as the medium edge", 1000, 6.25),
            ("halfway to the medium edge", 350, 100 * 0.5 ** 0.25),
        ]
        for label, value, expected in cases:
            with self.subTest(label):
                self.assertAlmostEqual(score_measure("mean_f1", value, "men"), expected, places=6)

    def test_one_sided(self):
        with self.subTest("higher is better: never less than 100 above good"):
            self.assertEqual(score_measure("f0_range_q90_q10", 500), 100)
            self.assertAlmostEqual(score_measure("f0_range_q90_q10", 30), 50)
        with self.subTest("lower is better"):
            self.assertEqual(score_measure("mean_pause_duration", 0.1), 100)
            self.assertAlmostEqual(score_measure("mean_pause_duration", 1.2), 50)
            self.assertLess(score_measure("mean_pause_duration", 2.0), 50)

    def test_the_bands_for_windows(self):
        # 30 Hz: the full result's medium edge, but past the window's good one.
        self.assertAlmostEqual(score_measure("f0_range_q90_q10", 30), 50)
        self.assertEqual(score_measure("f0_range_q90_q10", 40, partial=True), 100)
        self.assertAlmostEqual(score_measure("f0_range_q90_q10", 20, partial=True), 50)

    def test_per_sex(self):
        self.assertEqual(score_measure("mean_f1", 690, "women"), 100)
        self.assertLess(score_measure("mean_f1", 690, "men"), 100)

    def test_what_cant_be_scored(self):
        cases = [
            ("no value", ("mean_f1", None, "men")),
            ("a measure without bands", ("mean_f2", 1500, "men")),
            ("bands per sex, no sex given", ("mean_f1", 550, None)),
        ]
        for label, args in cases:
            with self.subTest(label):
                self.assertIsNone(score_measure(*args))


@mock.patch.object(ScoresService, "RANGES", RANGES)
class ScoreResultTests(SimpleTestCase):
    def test_a_full_result(self):
        result = FullVoiceResult(mean_f1=550, f0_range_q90_q10=30, mean_pause_duration=0.5)
        scores = score_result(result, sex="men")
        self.assertEqual(scores["measures"], {"mean_f1": 100.0, "f0_range_q90_q10": mock.ANY,
                                              "mean_pause_duration": 100.0})
        self.assertAlmostEqual(scores["voice_score"], (100 + 50 + 100) / 3)

    def test_a_window(self):
        # A window has no pauses; its F0 range uses the window's bands.
        result = PartialVoiceResult(mean_f1=550, f0_range_q90_q10=40)
        scores = score_result(result, sex="men")
        self.assertNotIn("mean_pause_duration", scores["measures"])
        self.assertEqual(scores["measures"]["f0_range_q90_q10"], 100)
        self.assertEqual(scores["voice_score"], 100)

    def test_without_the_sex_only_the_shared_measures(self):
        result = FullVoiceResult(mean_f1=550, f0_range_q90_q10=60, mean_pause_duration=2.0)
        scores = score_result(result)
        self.assertIsNone(scores["measures"]["mean_f1"])
        expected_pause = 100 * math.exp(-0.5 * ((2.0 - 0.8) / (0.4 / ScoresService.SPREAD)) ** 2)
        self.assertAlmostEqual(scores["voice_score"], (100 + expected_pause) / 2)

    def test_nothing_scored(self):
        self.assertIsNone(score_result(PartialVoiceResult(), sex="men")["voice_score"])


@mock.patch.object(ScoresService, "RANGES", RANGES)
class SignedScoreTests(SimpleTestCase):
    """-10 to +10 for the live graph: 0 in good, 5 at the medium edge, the sign
    for which side."""

    def test_two_sided(self):
        cases = [
            ("inside good", 550, 0),
            ("the low medium edge", 200, -5),
            ("the high medium edge", 800, 5),
            ("far below", 0, -10 * (1 - 0.5 ** ((500 / 300) ** 2))),
        ]
        for label, value, expected in cases:
            with self.subTest(label):
                self.assertAlmostEqual(signed_score("mean_f1", value, "men"), expected, places=6)

    def test_one_sided_and_partial(self):
        self.assertEqual(signed_score("f0_range_q90_q10", 500), 0)
        self.assertAlmostEqual(signed_score("f0_range_q90_q10", 30), -5)
        self.assertAlmostEqual(signed_score("f0_range_q90_q10", 20, partial=True), -5)
        self.assertAlmostEqual(signed_score("mean_pause_duration", 1.2), 5)

    def test_what_cant_be_scored(self):
        self.assertIsNone(signed_score("mean_f1", None, "men"))
        self.assertIsNone(signed_score("mean_f1", 550))
