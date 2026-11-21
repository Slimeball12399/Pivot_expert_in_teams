from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.tests.utils import make_speaker, make_trainer
from core.models import FullVoiceResult, PartialVoiceResult, Session, Talk
from core.services.GraphsService import USUAL_RANGE, get_talk_graphs
from core.services.TalksService import get_talk

# get_talk_graphs(): a talk's graph config and its metadata. The session page
# and the JSON endpoint using it are tested in web/tests/test_sessions.py and
# web/tests/test_talks.py.


class GetTalkGraphsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        cls.speaker = make_speaker("mikkel@example.com", cls.trainer).speaker_profile
        cls.now = timezone.now()
        cls.session = Session.objects.create(
            trainer=cls.trainer, speaker=cls.speaker, status=Session.Status.FINISHED,
            started_at=cls.now - timedelta(hours=1), ended_at=cls.now - timedelta(minutes=30))

    def make_talk(self, minutes_ago, seconds, score=None, windows=(), status=Talk.Status.COMPLETED):
        """A talk of `seconds` recorded seconds; with `score`, a full voice
        result; `windows` are (seconds in, window score) partial results."""
        talk = Talk.objects.create(
            session=self.session, status=status,
            started_at=self.now - timedelta(minutes=minutes_ago), duration=timedelta(seconds=seconds))
        if score is not None:
            FullVoiceResult.objects.create(talk=talk, voice_score=score)
        for second, window_score in windows:
            PartialVoiceResult.objects.create(
                talk=talk, start_at=talk.started_at + timedelta(seconds=second),
                window_length=timedelta(seconds=30), voice_score=window_score)
        return talk

    def graphs(self, talk):
        return get_talk_graphs(get_talk(user=self.trainer.user, talk_id=talk.id))

    def test_graphs_and_metadata(self):
        self.make_talk(58, 60, score=50)
        self.make_talk(56, 60, status=Talk.Status.DISCARDED)  # not counted in the number
        talk = self.make_talk(50, 400, score=72.6, windows=[(5, 3.5), (0, -2.0)])
        talk.pauses.create(paused_at=talk.started_at + timedelta(seconds=100),
                           resumed_at=talk.started_at + timedelta(seconds=120))
        graphs = self.graphs(talk)

        with self.subTest("metadata: the second talk, its start and real length"):
            self.assertEqual(graphs["talk"], {
                "id": talk.id, "number": 2, "started_at": talk.started_at, "length": 420})
        with self.subTest("each window's score at its start, in time order, on 0 to 100"):
            self.assertEqual(graphs["voice_config"]["points"], [[0.0, 40.0], [5.0, 67.5]])
            self.assertEqual(graphs["voice_config"]["y"], {"min": 0, "max": 100, "interval": 20})
            self.assertEqual(graphs["voice_config"]["target"], USUAL_RANGE)
        with self.subTest("the axis: the real length, pauses included, a minute at a time"):
            self.assertEqual(graphs["voice_config"]["x"],
                             {"min": 0, "max": 420, "interval": 10, "window": 60})
            self.assertEqual(graphs["stability_config"]["x"], graphs["voice_config"]["x"])
        with self.subTest("the speech score, rounded; no stability yet"):
            self.assertEqual(graphs["speech_score"], 73)
            self.assertIsNone(graphs["stability_score"])
            self.assertEqual(graphs["stability_config"]["points"], [])

    def test_marker_dots_where_the_line_leaves_the_usual_range(self):
        # On 0 to 100: 25 and 75 are the band's edges (inside), 20 below, 80 above.
        talk = self.make_talk(50, 120, score=60,
                              windows=[(0, 0.0), (5, -5.0), (10, -6.0), (15, 5.0), (20, 6.0)])
        self.assertEqual(self.graphs(talk)["voice_config"]["markers"], [[10.0, 20.0], [20.0, 80.0]])

    def test_a_talk_without_results(self):
        graphs = self.graphs(self.make_talk(50, 90))
        self.assertEqual(graphs["voice_config"]["points"], [])
        self.assertIsNone(graphs["speech_score"])
        self.assertEqual(graphs["voice_config"]["x"]["max"], 90)

    def test_no_talk(self):
        graphs = get_talk_graphs(None)
        self.assertIsNone(graphs["talk"])
        self.assertEqual(graphs["voice_config"]["points"], [])
        self.assertEqual(graphs["voice_config"]["x"], {"min": 0, "max": 60, "interval": 10, "window": 60})
        self.assertIsNone(graphs["speech_score"])
