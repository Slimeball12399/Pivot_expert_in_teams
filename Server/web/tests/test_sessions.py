from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.utils import make_speaker, make_trainer
from core.models import FullVoiceResult, PartialVoiceResult, Session, Talk

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


class SessionPageTests(TestCase):
    """GET /sessions/<id>/: one session, with the graphs of its latest talk
    that has a full voice result and the talks card. The graphs are tested in
    core/tests/test_graphs_service.py (get_talk_graphs), get_session() in
    core/tests/test_session_crud.py, the eye's JSON in test_talks.py."""

    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        cls.speaker = make_speaker("mikkel@example.com", trainer=cls.trainer)
        now = timezone.now()
        cls.session = Session.objects.create(
            trainer=cls.trainer, speaker=cls.speaker.speaker_profile, status=Session.Status.FINISHED,
            started_at=now - timedelta(hours=1), ended_at=now - timedelta(minutes=50))
        cls.first = Talk.objects.create(
            session=cls.session, status=Talk.Status.COMPLETED,
            started_at=now - timedelta(minutes=58), duration=timedelta(seconds=125))
        FullVoiceResult.objects.create(talk=cls.first, voice_score=60.2)
        cls.talk = Talk.objects.create(
            session=cls.session, status=Talk.Status.COMPLETED,
            started_at=now - timedelta(minutes=55), duration=timedelta(seconds=40))
        FullVoiceResult.objects.create(talk=cls.talk, voice_score=72.6)
        PartialVoiceResult.objects.create(
            talk=cls.talk, start_at=cls.talk.started_at, window_length=timedelta(seconds=30),
            voice_score=-2.0)
        # Still processing: in the card, not in the graphs.
        Talk.objects.create(
            session=cls.session, status=Talk.Status.PROCESSING,
            started_at=now - timedelta(minutes=52), duration=timedelta(seconds=30))
        cls.url = reverse("web:session", args=[cls.session.id])

    def test_session_page(self):
        self.assertEqual(self.url, f"/sessions/{self.session.id}/")
        self.client.force_login(self.trainer.user)
        response = self.client.get(self.url)

        with self.subTest("the page, with the latest talk that has results in the graphs"):
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "web/session.html")
            self.assertEqual(response.context["session"], self.session)
            self.assertEqual(response.context["talk"]["id"], self.talk.id)
            self.assertEqual(response.context["voice_config"]["points"], [[0.0, 40.0]])
            self.assertEqual(response.context["speech_score"], 73)
            # The graph config is in the page for timeline-chart.js.
            self.assertContains(response, 'id="voice-chart-config"')

        with self.subTest("the talks card: every talk, numbered, the shown one marked"):
            talks = response.context["talks"]
            self.assertEqual([row.number for row in talks], [1, 2, 3])
            self.assertEqual([row.length for row in talks], ["2:05", "0:40", "0:30"])
            self.assertEqual([row.speech for row in talks], [60, 73, None])
            self.assertContains(response, f'data-talk-url="{reverse("web:talk", args=[self.first.id])}"')
            self.assertContains(response, f'data-talk-row="{self.talk.id}" aria-current="true"')
            self.assertContains(response, 'aria-current="true"', count=1)

    def test_header(self):
        self.client.force_login(self.trainer.user)

        with self.subTest("finished: name, board, talks, length start to end; Delete session"):
            response = self.client.get(self.url)
            self.assertTemplateUsed(response, "web/components/session_header.html")
            self.assertEqual(response.context["elapsed"], "10:00")
            self.assertContains(response, "Mikkel Jensen &middot; Session")
            self.assertRegex(response.content.decode(), r"3 talks\s+&middot; 10:00\s")
            self.assertContains(response, "session-header-status-finished")
            self.assertContains(response, 'id="session-delete"')
            self.assertNotContains(response, 'id="session-finish"')
            self.assertFalse(response.context["can_start_talk"])

        now = timezone.now()
        live = Session.objects.create(
            trainer=self.trainer, speaker=self.speaker.speaker_profile, status=Session.Status.LIVE,
            started_at=now - timedelta(minutes=5))
        Talk.objects.create(session=live, status=Talk.Status.COMPLETED,
                            started_at=now - timedelta(minutes=4), duration=timedelta(seconds=60))

        with self.subTest("live with no open talk: so far; Start talk 2 twice, Finish session"):
            response = self.client.get(reverse("web:session", args=[live.id]))
            self.assertTrue(response.context["can_start_talk"])
            self.assertEqual(response.context["next_talk"], 2)
            self.assertContains(response, " so far")
            self.assertContains(response, "Start talk 2", count=2)  # header and talks card
            self.assertContains(response, 'id="session-finish"')

        # Last, because it opens a talk.
        with self.subTest("live with a talk recording: no Start talk"):
            Talk.objects.create(session=live, status=Talk.Status.RECORDING, started_at=now)
            response = self.client.get(reverse("web:session", args=[live.id]))
            self.assertFalse(response.context["can_start_talk"])
            self.assertNotContains(response, "Start talk")

    def test_a_session_without_talks(self):
        empty = Session.objects.create(trainer=self.trainer, speaker=self.speaker.speaker_profile)
        self.client.force_login(self.trainer.user)
        response = self.client.get(reverse("web:session", args=[empty.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["talk"])
        self.assertEqual(response.context["voice_config"]["points"], [])
        self.assertContains(response, "No talks yet.")
        # Not started: no length yet, and Start session.
        self.assertIsNone(response.context["elapsed"])
        self.assertContains(response, 'id="session-start"')

    def test_not_found(self):
        other_trainer = make_trainer("bo@example.com")
        cases = [
            ("another trainer's session", other_trainer.user, self.session.id),
            ("a session that doesn't exist", self.trainer.user, "00000000-0000-0000-0000-000000000000"),
        ]
        for label, user, session_id in cases:
            with self.subTest(label):
                self.client.force_login(user)
                response = self.client.get(reverse("web:session", args=[session_id]))
                self.assertEqual(response.status_code, 404)


class SessionEditDeleteTests(TestCase):
    """PATCH and DELETE /sessions/<id>/: the edit dialog and the confirm
    dialog from the Sessions table. The HTTP layer only: the rules are tested
    in core/tests/test_session_crud.py (update_session, delete_session)."""

    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        cls.speaker = make_speaker("mikkel@example.com", trainer=cls.trainer)

    def setUp(self):
        self.client.force_login(self.trainer.user)
        now = timezone.now()
        self.planned = Session.objects.create(
            trainer=self.trainer, speaker=self.speaker.speaker_profile,
            scheduled_at=now + timedelta(days=1))
        self.finished = Session.objects.create(
            trainer=self.trainer, speaker=self.speaker.speaker_profile, status=Session.Status.FINISHED,
            started_at=now - timedelta(hours=1), ended_at=now - timedelta(minutes=30))

    def patch(self, session, **fields):
        return self.client.patch(
            reverse("web:session", args=[session.id]), urlencode(fields),
            content_type="application/x-www-form-urlencoded")

    def test_edit(self):
        when = (timezone.now() + timedelta(days=2)).replace(microsecond=0)

        with self.subTest("later, also on the phone: saved, with a toast"):
            response = self.patch(self.planned, start="later", stream_on_phone="on",
                                  scheduled_at=when.isoformat().replace("+00:00", "Z"))
            self.assertEqual(response.status_code, 200)
            self.planned.refresh_from_db()
            self.assertEqual(self.planned.display, Session.Display.BOTH)
            self.assertEqual(self.planned.scheduled_at, when)
            self.assertEqual([str(m) for m in get_messages(response.wsgi_request)],
                             ["Session with Mikkel Jensen saved."])

        with self.subTest("now, browser only: the schedule is removed"):
            self.assertEqual(self.patch(self.planned, start="now").status_code, 200)
            self.planned.refresh_from_db()
            self.assertEqual(self.planned.display, Session.Display.WEB)
            self.assertIsNone(self.planned.scheduled_at)

    def test_edit_rejects(self):
        past = (timezone.now() - timedelta(hours=1)).isoformat()
        cases = [
            ("later without a time", self.planned, {"start": "later"}, 400, "scheduled_at"),
            ("later, in the past", self.planned, {"start": "later", "scheduled_at": past}, 400, "scheduled_at"),
            ("a session that has started", self.finished, {"start": "now"}, 409, "__all__"),
        ]
        for label, session, fields, status, field in cases:
            with self.subTest(label):
                response = self.patch(session, **fields)
                self.assertEqual(response.status_code, status)
                self.assertIn(field, response.json()["errors"])
        with self.subTest("another trainer's session: not found"):
            self.client.force_login(make_trainer("bo@example.com").user)
            self.assertEqual(self.patch(self.planned, start="now").status_code, 404)

    def test_delete(self):
        url = reverse("web:session", args=[self.finished.id])

        with self.subTest("finished: moves to Discarded, with a toast"):
            response = self.client.delete(url)
            self.assertEqual(response.status_code, 200)
            self.finished.refresh_from_db()
            self.assertEqual(self.finished.status, Session.Status.DELETED)
            self.assertEqual([str(m) for m in get_messages(response.wsgi_request)],
                             ["Session with Mikkel Jensen deleted. It is under Discarded now."])
            listed = self.client.get(reverse("web:sessions"), {"status": "discarded"})
            self.assertEqual(listed.context["rows"], [self.finished])

        with self.subTest("not finished: refused"):
            response = self.client.delete(reverse("web:session", args=[self.planned.id]))
            self.assertEqual(response.status_code, 409)
            self.assertIn("__all__", response.json()["errors"])

        with self.subTest("another trainer's session: not found"):
            self.client.force_login(make_trainer("bo@example.com").user)
            self.assertEqual(self.client.delete(url).status_code, 404)

    def test_post_is_not_allowed(self):
        # Creating goes to /sessions/ (session_list).
        response = self.client.post(reverse("web:session", args=[self.planned.id]))
        self.assertEqual(response.status_code, 405)

    def test_table_buttons_open_the_dialogs(self):
        with self.subTest("upcoming: the pencil carries the edit dialog's data"):
            response = self.client.get(reverse("web:sessions"), {"status": "upcoming"})
            self.assertContains(response, f'data-edit-session="{reverse("web:session", args=[self.planned.id])}"')
            self.assertContains(response, 'data-display="WEB"')
            self.assertTemplateUsed(response, "web/components/confirm_dialog.html")
        with self.subTest("past: the bin asks first, then DELETE"):
            response = self.client.get(reverse("web:sessions"))
            self.assertContains(response, f'data-confirm-url="{reverse("web:session", args=[self.finished.id])}"')
            self.assertContains(response, 'data-confirm-method="DELETE"')
