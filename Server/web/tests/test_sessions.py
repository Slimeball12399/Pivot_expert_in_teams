from datetime import timedelta

from django.conf import settings
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.utils import make_speaker, make_trainer
from core.models import Session

URL = reverse("web:sessions")

# The Sessions page and creating a session from the new session dialog: the
# HTTP layer only. The rules (your own speaker, active account, a future
# time) are tested in core/tests/test_session_crud.py (create_session). The
# dialog's user search (web:invite_suggestions with own=1) is in test_users.py.


class SessionsPageTests(TestCase):
    """GET /sessions/: the page, for trainers only."""

    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        cls.speaker = make_speaker("mikkel@example.com", trainer=cls.trainer)

    def test_sessions_page(self):
        self.assertEqual(URL, "/sessions/")

        with self.subTest("logged out: redirected to the login page"):
            response = self.client.get(URL)
            self.assertRedirects(
                response, f"{reverse(settings.LOGIN_URL)}?next={URL}", fetch_redirect_response=False)

        with self.subTest("a speaker: not allowed"):
            self.client.force_login(self.speaker)
            self.assertEqual(self.client.get(URL).status_code, 403)

        with self.subTest("a trainer: the page, with the head and the new session dialog"):
            self.client.force_login(self.trainer.user)
            response = self.client.get(URL, {"q": " maja "})
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "web/sessions.html")
            self.assertTemplateUsed(response, "web/components/new_session_dialog.html")
            self.assertEqual(response.context["query"], "maja")
            self.assertContains(response, "0 this week</span>")
            self.assertContains(response, 'id="new-session-open"')
            self.assertContains(response, 'No session matches &ldquo;maja&rdquo;.')
            self.assertContains(
                response, f'data-speakers-url="{reverse("web:invite_suggestions")}"')

    def test_status_filter(self):
        self.client.force_login(self.trainer.user)
        cases = [
            ("by default: past", {}, "past"),
            ("upcoming", {"status": "upcoming"}, "upcoming"),
            ("discarded", {"status": "discarded"}, "discarded"),
            ("unknown: past", {"status": "live"}, "past"),
        ]
        for label, params, expected in cases:
            with self.subTest(label):
                response = self.client.get(URL, params)
                self.assertEqual(response.context["status"], expected)
                self.assertRegex(response.content.decode(),
                                 rf'data-value="{expected}"\s+aria-pressed="true"')
                # The search keeps the filter.
                self.assertContains(response, f'name="status" value="{expected}"')

        cases = [
            ("time, by default: all", {}, "all"),
            ("this week", {"period": "week"}, "week"),
            ("this month", {"period": "month"}, "month"),
            ("this year", {"period": "year"}, "year"),
            ("unknown: all", {"period": "today"}, "all"),
        ]
        for label, params, expected in cases:
            with self.subTest(label):
                response = self.client.get(URL, params)
                self.assertEqual(response.context["period"], expected)
                self.assertRegex(response.content.decode(),
                                 rf'data-value="{expected}"\s+aria-pressed="true"')
                self.assertContains(response, f'name="period" value="{expected}"')

    def test_lists_sessions_by_filter_and_search(self):
        """Which sessions get_sessions() returns is tested in
        core/tests/test_session_crud.py; here, that the page passes the filter
        and the search on and shows the rows."""
        maja = make_speaker("maja@example.com", trainer=self.trainer, first_name="Maja", last_name="Holm")
        now = timezone.now()
        finished = Session.objects.create(
            trainer=self.trainer, speaker=self.speaker.speaker_profile, status=Session.Status.FINISHED,
            started_at=now - timedelta(hours=2), ended_at=now - timedelta(hours=1, minutes=36))
        planned = Session.objects.create(
            trainer=self.trainer, speaker=maja.speaker_profile, status=Session.Status.NOT_STARTED,
            scheduled_at=now + timedelta(days=1))
        cancelled = Session.objects.create(
            trainer=self.trainer, speaker=maja.speaker_profile, status=Session.Status.CANCELLED)
        aborted = Session.objects.create(
            trainer=self.trainer, speaker=self.speaker.speaker_profile, status=Session.Status.ABORTED,
            started_at=now - timedelta(days=1))
        Session.objects.create(  # live: in none of the tabs
            trainer=self.trainer, speaker=maja.speaker_profile, status=Session.Status.LIVE, started_at=now)
        self.client.force_login(self.trainer.user)

        cases = [
            ("past", {}, [finished]),
            ("upcoming", {"status": "upcoming"}, [planned]),
            ("discarded: cancelled and aborted", {"status": "discarded"}, [aborted, cancelled]),
            ("a search within the filter", {"status": "discarded", "q": "maja"}, [cancelled]),
        ]
        for label, params, expected in cases:
            with self.subTest(label):
                response = self.client.get(URL, params)
                self.assertEqual(response.context["rows"], expected)
                self.assertTemplateUsed(response, "web/components/session_row.html")

        with self.subTest("a row: date, name, length and status"):
            response = self.client.get(URL)
            self.assertEqual(response.context["rows"][0].minutes, 24)
            self.assertContains(response, "Mikkel Jensen")
            self.assertContains(response, "24 min")
            self.assertContains(response, '<span class="badge badge-success">Finished</span>', html=True)

    def test_only_get_and_post_are_allowed(self):
        self.client.force_login(self.trainer.user)
        self.assertEqual(self.client.put(URL).status_code, 405)


class SessionCreateViewTests(TestCase):
    """POST /sessions/: the form the new session dialog posts."""

    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        cls.speaker = make_speaker("mikkel@example.com", trainer=cls.trainer)
        cls.other = make_speaker("other@example.com")  # not this trainer's

    def setUp(self):
        self.client.force_login(self.trainer.user)

    def post(self, **overrides):
        return self.client.post(URL, {"speaker_id": self.speaker.id, "start": "now", **overrides})

    def assertRejected(self, field, **overrides):
        """400 with an error for `field`, and no session saved."""
        response = self.post(**overrides)
        self.assertEqual(response.status_code, 400)
        self.assertIn(field, response.json()["errors"])
        self.assertFalse(Session.objects.exists())

    def test_creates_a_session(self):
        with self.subTest("now, browser only: no schedule, a toast for the reload"):
            response = self.post()
            self.assertEqual(response.status_code, 201)
            session = Session.objects.get(pk=response.json()["id"])
            self.assertEqual(session.speaker.user, self.speaker)
            self.assertEqual(session.status, Session.Status.NOT_STARTED)
            self.assertEqual(session.display, Session.Display.WEB)
            self.assertIsNone(session.scheduled_at)
            self.assertEqual([str(m) for m in get_messages(response.wsgi_request)],
                             ["Session with Mikkel Jensen saved."])

        with self.subTest("later, also on the phone: the UTC time and BOTH"):
            when = (timezone.now() + timedelta(days=1)).replace(microsecond=0)
            response = self.post(start="later", stream_on_phone="on",
                                 scheduled_at=when.isoformat().replace("+00:00", "Z"))
            self.assertEqual(response.status_code, 201)
            session = Session.objects.get(pk=response.json()["id"])
            self.assertEqual(session.display, Session.Display.BOTH)
            self.assertEqual(session.scheduled_at, when)

        with self.subTest("now: a time sent anyway is ignored"):
            response = self.post(scheduled_at=when.isoformat())
            self.assertIsNone(Session.objects.get(pk=response.json()["id"]).scheduled_at)

    def test_rejects(self):
        past = (timezone.now() - timedelta(hours=1)).isoformat()
        cases = [
            ("no user", "speaker_id", {"speaker_id": ""}),
            ("not a user id", "speaker_id", {"speaker_id": "abc"}),
            ("another trainer's speaker", "speaker_id", {"speaker_id": self.other.id}),
            ("neither now nor later", "start", {"start": "soon"}),
            ("later without a time", "scheduled_at", {"start": "later"}),
            ("later, not a time", "scheduled_at", {"start": "later", "scheduled_at": "tomorrow"}),
            ("later, in the past", "scheduled_at", {"start": "later", "scheduled_at": past}),
        ]
        for label, field, overrides in cases:
            with self.subTest(label):
                self.assertRejected(field, **overrides)
