import json
from datetime import timedelta
from unittest import mock
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.serializers.json import DjangoJSONEncoder
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.utils import make_speaker, make_trainer
from core.models import FullVoiceResult, PartialVoiceResult, Session, Talk
from core.services.TalksService import finish_talk
from live.client import LIVE_UNAVAILABLE, LiveError
from live.models import Connection

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


class SessionCardTests(TestCase):
    """The session cards above the table (session_card.html): the live
    session to reconnect to, else the next two upcoming ones."""

    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        cls.speakers = [make_speaker(f"speaker{i}@example.com", trainer=cls.trainer) for i in range(4)]

    def setUp(self):
        self.client.force_login(self.trainer.user)

    def session(self, index, **fields):
        return Session.objects.create(trainer=self.trainer, speaker=self.speakers[index].speaker_profile, **fields)

    def test_no_cards(self):
        response = self.client.get(URL)
        self.assertIsNone(response.context["live"])
        self.assertEqual(response.context["upcoming"], [])
        self.assertContains(response, '<div class="sessions-top"></div>', html=False)

    def test_the_next_two_upcoming(self):
        now = timezone.now()
        later = self.session(0, scheduled_at=now + timedelta(days=2))
        unscheduled = self.session(1)
        soon = self.session(2, scheduled_at=now + timedelta(minutes=30))
        self.session(3, status=Session.Status.FINISHED, started_at=now, ended_at=now)
        response = self.client.get(URL)
        with self.subTest("the soonest first, without a time after them, two at most"):
            self.assertEqual(response.context["upcoming"], [soon, later])
            self.assertNotIn(unscheduled, response.context["upcoming"])
        with self.subTest("each with Start, posting to its live screen"):
            self.assertContains(response, "Up next")
            self.assertContains(response, "session-card-upcoming", count=2)
            self.assertContains(response, f'action="{reverse("web:session_live", args=[soon.id])}"')
            self.assertContains(response, "minutes")  # "in 29 minutes" or so, for the soon one

    def test_the_live_session_instead(self):
        now = timezone.now()
        live = self.session(0, status=Session.Status.LIVE, started_at=now - timedelta(minutes=12))
        Talk.objects.create(session=live, status=Talk.Status.COMPLETED, started_at=now)
        Talk.objects.create(session=live, status=Talk.Status.DISCARDED, started_at=now)
        self.session(1, scheduled_at=now + timedelta(minutes=30))
        response = self.client.get(URL)
        self.assertEqual(response.context["live"], live)
        self.assertEqual(response.context["upcoming"], [])
        self.assertContains(response, "session-card-live", count=1)
        self.assertNotContains(response, "session-card-upcoming")
        with self.subTest("its talks without discarded ones, its clock, Reconnect to its live screen"):
            self.assertEqual(response.context["live"].talk_count, 1)
            self.assertContains(response, f'data-started-at="{live.started_at.isoformat()}"')
            self.assertContains(response, f'href="{reverse("web:session_live", args=[live.id])}"')
            self.assertContains(response, "Reconnect")


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
            # Start in the dialog goes on to its live screen.
            self.assertEqual(response.json()["live_url"], reverse("web:session_live", args=[session.id]))
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
            voice_score=40.0)
        # Still processing: in the card, not in the graphs.
        Talk.objects.create(
            session=cls.session, status=Talk.Status.PROCESSING,
            started_at=now - timedelta(minutes=52), duration=timedelta(seconds=30))
        cls.url = reverse("web:session", args=[cls.session.id])

    def get_json(self, url):
        return self.client.get(url, HTTP_ACCEPT="application/json")

    def test_session_json(self):
        self.client.force_login(self.trainer.user)
        response = self.get_json(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("Accept", response["Vary"])
        data = response.json()

        with self.subTest("the session"):
            self.assertEqual(data["session"], {
                "id": str(self.session.id), "status": "FINISHED",
                # As Django's JSON writes times: ISO 8601, milliseconds, Z.
                "started_at": DjangoJSONEncoder().default(self.session.started_at),
                "ended_at": DjangoJSONEncoder().default(self.session.ended_at),
            })

        with self.subTest("every talk, oldest first, numbered, with its length and score"):
            self.assertEqual([talk["number"] for talk in data["talks"]], [1, 2, 3])
            self.assertEqual([talk["duration"] for talk in data["talks"]], [125.0, 40.0, 30.0])
            self.assertEqual([talk["speech"] for talk in data["talks"]], [60.2, 72.6, None])
            self.assertEqual(data["talks"][0]["url"], reverse("web:talk", args=[self.first.id]))

        with self.subTest("the graphs of the latest talk with results, not the one still processing"):
            self.assertEqual(data["talk"]["id"], str(self.talk.id))
            self.assertEqual(data["voice_config"]["points"], [[0.0, 40.0]])
            self.assertEqual(data["speech_score"], 73)

    def test_the_talk_going_on_has_its_pauses(self):
        now = timezone.now()
        live = Session.objects.create(trainer=self.trainer, speaker=self.speaker.speaker_profile,
                                      status=Session.Status.LIVE, started_at=now - timedelta(minutes=5))
        talk = Talk.objects.create(session=live, status=Talk.Status.PAUSED, started_at=now - timedelta(minutes=3))
        talk.pauses.create(paused_at=now - timedelta(minutes=2), resumed_at=now - timedelta(seconds=90))
        talk.pauses.create(paused_at=now - timedelta(seconds=20))
        self.client.force_login(self.trainer.user)
        data = self.get_json(reverse("web:session", args=[live.id])).json()
        row = data["talks"][0]
        self.assertEqual(row["paused_seconds"], 30.0)
        self.assertEqual(row["paused_at"], DjangoJSONEncoder().default(now - timedelta(seconds=20)))
        self.assertEqual(row["finish_url"], reverse("web:talk_finish", args=[talk.id]))

    def test_session_page(self):
        self.assertEqual(self.url, f"/sessions/{self.session.id}/")
        self.client.force_login(self.trainer.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "web/session.html")
        self.assertTemplateUsed(response, "web/content/session_content.html")
        self.assertEqual(response.context["session"], self.session)

        with self.subTest("the same JSON in the page, for session.js"):
            page = response.content.decode()
            start = page.index('<script id="session-data" type="application/json">')
            embedded = page[page.index(">", start) + 1:page.index("</script>", start)]
            self.assertEqual(json.loads(embedded), self.get_json(self.url).json())
        with self.subTest("the frame session.js fills in: rows, row template, charts without config"):
            self.assertContains(response, "data-talk-rows", count=1)
            self.assertContains(response, '<template id="talk-row-template">', html=False)
            self.assertContains(response, '<template id="talk-empty-template">', html=False)
            self.assertNotContains(response, "voice-chart-config")
            self.assertContains(response, "web/js/session.js")

    def test_header(self):
        self.client.force_login(self.trainer.user)

        with self.subTest("finished: name, board, talks, length start to end; Delete session"):
            response = self.client.get(self.url)
            self.assertTemplateUsed(response, "web/components/session_header.html")
            self.assertContains(response, "Mikkel Jensen &middot; Session")
            # How long it ran: session-header.js shows it from these.
            self.assertContains(response, "<span data-session-talk-count>3 talks</span>", html=False)
            self.assertContains(response, "data-session-elapsed")
            self.assertContains(response, f'data-ended-at="{self.session.ended_at.isoformat()}"')
            self.assertContains(response, "web/js/session-header.js")
            self.assertContains(response, "session-header-status-finished")
            self.assertContains(response, 'id="session-delete"')
            self.assertNotContains(response, 'id="session-finish"')
            self.assertNotContains(response, "Start talk")

        now = timezone.now()
        live = Session.objects.create(
            trainer=self.trainer, speaker=self.speaker.speaker_profile, status=Session.Status.LIVE,
            started_at=now - timedelta(minutes=5))
        Talk.objects.create(session=live, status=Talk.Status.COMPLETED,
                            started_at=now - timedelta(minutes=4), duration=timedelta(seconds=60))

        with self.subTest("live: no end yet (it counts to now); Start talk 2 twice, Finish session"):
            response = self.client.get(reverse("web:session", args=[live.id]))
            self.assertContains(response, f'data-started-at="{live.started_at.isoformat()}"')
            self.assertNotContains(response, "data-ended-at")
            self.assertContains(response, "Start talk 2", count=2)  # header and talks card
            self.assertContains(response, 'id="session-finish"')

    def test_a_session_without_talks(self):
        empty = Session.objects.create(trainer=self.trainer, speaker=self.speaker.speaker_profile)
        self.client.force_login(self.trainer.user)
        data = self.get_json(reverse("web:session", args=[empty.id])).json()
        self.assertEqual(data["talks"], [])
        self.assertIsNone(data["talk"])
        self.assertEqual(data["voice_config"]["points"], [])
        response = self.client.get(reverse("web:session", args=[empty.id]))
        self.assertEqual(response.status_code, 200)
        # Not started: no length yet, and Start session.
        self.assertNotContains(response, "data-session-elapsed")
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


class LiveScreenTests(TestCase):
    """/sessions/<id>/live/: GET the live screen of a live session, POST start
    the session. start_session's rules are in core/tests; the connection
    itself is live.js, in the browser (its endpoint: ConnectTests)."""

    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        cls.speaker = make_speaker("mikkel@example.com", trainer=cls.trainer)
        cls.live = Session.objects.create(
            trainer=cls.trainer, speaker=cls.speaker.speaker_profile, status=Session.Status.LIVE,
            started_at=timezone.now() - timedelta(minutes=5))

    def setUp(self):
        self.client.force_login(self.trainer.user)

    def url(self, session):
        return reverse("web:session_live", args=[session.id])

    def test_the_live_screen(self):
        self.assertEqual(self.url(self.live), f"/sessions/{self.live.id}/live/")
        response = self.client.get(self.url(self.live))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "web/live.html")
        self.assertTemplateUsed(response, "web/components/session_header.html")
        self.assertEqual(response.context["session"], self.live)
        with self.subTest("the session and its connect URL are in the page, for live.js"):
            self.assertContains(response, f'data-session-id="{self.live.id}"', html=False)
            self.assertContains(response, f'data-connect-url="{reverse("web:session_connect", args=[self.live.id])}"',
                                html=False)
            self.assertContains(response, "data-csrf-token=", html=False)
        with self.subTest("it starts on the loading screen, connecting"):
            self.assertContains(response, "data-live-loading", count=1)
            self.assertContains(response, 'data-state="connecting"', html=False)
        with self.subTest("the session content, hidden and without its JSON: live.js fetches it once connected"):
            self.assertTemplateUsed(response, "web/content/session_content.html")
            self.assertContains(response, "data-live-content hidden", html=False)
            self.assertNotContains(response, 'id="session-data"')
            self.assertContains(response, f'data-session-url="{reverse("web:session", args=[self.live.id])}"',
                                html=False)
        with self.subTest("Start talk, for live.js to send on the channel"):
            self.assertContains(response, 'id="session-start-talk"')
        with self.subTest("the talk header and view too, hidden: live.js shows them while a talk goes on"):
            self.assertTemplateUsed(response, "web/components/talk_header.html")
            self.assertTemplateUsed(response, "web/content/talk_content.html")
            self.assertContains(response, "data-talk-header hidden", html=False)
            self.assertContains(response, 'data-live-view="talk" hidden', html=False)
            for button in ["talk-pause", "talk-end", "talk-finish-session"]:
                self.assertContains(response, f'id="{button}"')
        with self.subTest("Finish session asks first, then posts"):
            self.assertTemplateUsed(response, "web/components/confirm_dialog.html")
            self.assertContains(response, f'data-confirm-url="{reverse("web:session_finish", args=[self.live.id])}"',
                                count=2)  # the session header's and the talk header's

    def test_get_not_live_goes_to_the_session_page(self):
        for status in [Session.Status.NOT_STARTED, Session.Status.FINISHED, Session.Status.CANCELLED]:
            with self.subTest(status):
                session = Session.objects.create(
                    trainer=self.trainer, speaker=self.speaker.speaker_profile, status=status)
                response = self.client.get(self.url(session))
                self.assertRedirects(response, reverse("web:session", args=[session.id]),
                                     fetch_redirect_response=False)

    def test_post_starts_it(self):
        other = make_speaker("sofie@example.com", trainer=self.trainer)
        upcoming = Session.objects.create(trainer=self.trainer, speaker=other.speaker_profile)
        response = self.client.post(self.url(upcoming))
        self.assertRedirects(response, self.url(upcoming), fetch_redirect_response=False)
        upcoming.refresh_from_db()
        self.assertEqual(upcoming.status, Session.Status.LIVE)
        self.assertIsNotNone(upcoming.started_at)

    def test_post_that_cant_start(self):
        with self.subTest("already live: on to its live screen, no message"):
            response = self.client.post(self.url(self.live))
            self.assertRedirects(response, self.url(self.live), fetch_redirect_response=False)
            self.assertEqual(list(get_messages(response.wsgi_request)), [])

        with self.subTest("the speaker has another live session: the session page says why"):
            second = Session.objects.create(trainer=self.trainer, speaker=self.speaker.speaker_profile)
            response = self.client.post(self.url(second), follow=True)
            self.assertRedirects(response, reverse("web:session", args=[second.id]))
            self.assertEqual([str(m) for m in get_messages(response.wsgi_request)],
                             ["This speaker already has a live session."])
            second.refresh_from_db()
            self.assertEqual(second.status, Session.Status.NOT_STARTED)

    def test_rejects(self):
        upcoming = Session.objects.create(trainer=self.trainer, speaker=self.speaker.speaker_profile)
        with self.subTest("someone else's session: 404"):
            self.client.force_login(make_trainer("bo@example.com").user)
            self.assertEqual(self.client.get(self.url(self.live)).status_code, 404)
            self.assertEqual(self.client.post(self.url(upcoming)).status_code, 404)
        with self.subTest("a speaker: not allowed"):
            self.client.force_login(self.speaker)
            self.assertEqual(self.client.get(self.url(self.live)).status_code, 403)
            self.assertEqual(self.client.post(self.url(upcoming)).status_code, 403)
        with self.subTest("only GET and POST"):
            self.client.force_login(self.trainer.user)
            self.assertEqual(self.client.put(self.url(self.live)).status_code, 405)

        with self.subTest("the old /talk/ is gone"):
            self.assertEqual(self.client.get("/talk/").status_code, 404)


class ConnectTests(TestCase):
    """/sessions/<id>/connect/: GET the live process's offer, POST the
    browser's answer. The live process is mocked (LiveClient); the client,
    with the ICE servers it adds to the offer, is tested in
    live/tests/test_client.py, the live process in live/tests."""

    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        cls.speaker = make_speaker("mikkel@example.com", trainer=cls.trainer)
        cls.live = Session.objects.create(
            trainer=cls.trainer, speaker=cls.speaker.speaker_profile, status=Session.Status.LIVE,
            started_at=timezone.now())

    def setUp(self):
        self.client.force_login(self.trainer.user)
        patcher = mock.patch("web.views.sessions.LiveClient")
        self.live_client = patcher.start().return_value
        self.addCleanup(patcher.stop)
        # Nothing recorded by default (the real one gives the PCM's path).
        self.live_client.stop_recording.return_value = None
        self.offer = {"sdp": "v=0\r\n", "ice_servers": [{"urls": "stun:203.0.113.7:3478"}],
                      "ice_transport_policy": "all"}
        self.live_client.offer.return_value = self.offer
        self.url = reverse("web:session_connect", args=[self.live.id])

    def post_answer(self, body):
        return self.client.post(self.url, json.dumps(body), content_type="application/json")

    def test_get_the_offer(self):
        self.assertEqual(self.url, f"/sessions/{self.live.id}/connect/")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.offer)  # the client's offer, as it is
        self.live_client.offer.assert_called_once_with(
            self.live.id, self.trainer.user.id, Connection.Kind.TRAINER_AUDIO)

    def test_post_the_answer(self):
        response = self.post_answer({"sdp": "v=0\r\n"})
        self.assertEqual(response.status_code, 204)
        self.live_client.answer.assert_called_once_with(
            self.live.id, self.trainer.user.id, Connection.Kind.TRAINER_AUDIO, "v=0\r\n")

    def test_post_a_bad_body(self):
        cases = [("not JSON", "nope"), ("no sdp", {}), ("empty", {"sdp": " "}), ("not text", {"sdp": 3})]
        for label, body in cases:
            with self.subTest(label):
                response = (self.client.post(self.url, body, content_type="application/json")
                            if isinstance(body, str) else self.post_answer(body))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["code"], "invalid_body")
        self.live_client.answer.assert_not_called()

    def test_the_live_process_errors(self):
        with self.subTest("its 404 and 409 as they are"):
            for status, code in [(404, "connection_not_found"), (409, "connection_replaced")]:
                self.live_client.answer.side_effect = LiveError(code, "Detail.", status)
                response = self.post_answer({"sdp": "v=0\r\n"})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json(), {"code": code, "errors": {"__all__": ["Detail."]}})
        with self.subTest("not reachable: 503"):
            self.live_client.offer.side_effect = LiveError(LIVE_UNAVAILABLE, "The live process can't be reached.")
            with self.assertLogs("web.views.sessions", "WARNING"):
                response = self.client.get(self.url)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["code"], "live_unavailable")

    def test_rejects(self):
        with self.subTest("not live: 409, the live process isn't asked"):
            finished = Session.objects.create(
                trainer=self.trainer, speaker=self.speaker.speaker_profile, status=Session.Status.FINISHED)
            response = self.client.get(reverse("web:session_connect", args=[finished.id]))
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["code"], "not_live")
            self.live_client.offer.assert_not_called()
        with self.subTest("someone else's session: 404"):
            self.client.force_login(make_trainer("bo@example.com").user)
            self.assertEqual(self.client.get(self.url).status_code, 404)
        with self.subTest("a speaker: not allowed"):
            self.client.force_login(self.speaker)
            self.assertEqual(self.client.get(self.url).status_code, 403)
        with self.subTest("only GET and POST"):
            self.client.force_login(self.trainer.user)
            self.assertEqual(self.client.put(self.url).status_code, 405)


class SessionFinishTests(TestCase):
    """POST /sessions/<id>/finish/: Finish session (the confirm dialog).
    end_session's rules are in core/tests; the live process is mocked."""

    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        cls.speaker = make_speaker("mikkel@example.com", trainer=cls.trainer)

    def setUp(self):
        self.client.force_login(self.trainer.user)
        patcher = mock.patch("web.views.sessions.LiveClient")
        self.live_client = patcher.start().return_value
        self.addCleanup(patcher.stop)
        # Nothing recorded by default (the real one gives the PCM's path).
        self.live_client.stop_recording.return_value = None
        self.live = Session.objects.create(
            trainer=self.trainer, speaker=self.speaker.speaker_profile, status=Session.Status.LIVE,
            started_at=timezone.now() - timedelta(minutes=5))
        self.url = reverse("web:session_finish", args=[self.live.id])

    def test_finishes_it_with_its_talk(self):
        talk = Talk.objects.create(session=self.live, status=Talk.Status.PAUSED, started_at=timezone.now())
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.live.refresh_from_db()
        talk.refresh_from_db()
        self.assertEqual(self.live.status, Session.Status.FINISHED)
        self.assertEqual(talk.status, Talk.Status.PROCESSING)
        with self.subTest("the live process: the recording stopped, the connections closed"):
            self.live_client.stop_recording.assert_called_once_with(talk.id)
            self.live_client.close_session.assert_called_once_with(self.live.id)
        with self.subTest("a toast for the reload"):
            self.assertEqual([str(m) for m in get_messages(response.wsgi_request)],
                             ["Session with Mikkel Jensen finished."])

    def test_end_talk_first_then_the_session(self):
        # The same order as the End talk button, then the session: the
        # recording stopped, finish_talk (it will upload it), the connections
        # closed, end_session.
        talk = Talk.objects.create(session=self.live, status=Talk.Status.RECORDING, started_at=timezone.now())
        seen = []
        self.live_client.stop_recording.side_effect = lambda talk_id: seen.append(
            ("stop_recording", Talk.objects.get(pk=talk_id).status))
        self.live_client.close_session.side_effect = lambda session_id: seen.append(
            ("close_session", Talk.objects.get(pk=talk.pk).status, Session.objects.get(pk=session_id).status))
        with mock.patch("web.views.sessions.finish_talk", wraps=finish_talk) as finishing:
            self.client.post(self.url)
        # No browser file, and the mocked live process gave no PCM path.
        finishing.assert_called_once_with(trainer=self.trainer.user, talk_id=talk.id, audio=None, recording=None)
        self.assertEqual(seen, [
            ("stop_recording", Talk.Status.RECORDING),
            # The talk finished by finish_talk, the session not yet.
            ("close_session", Talk.Status.PROCESSING, Session.Status.LIVE),
        ])
        self.live.refresh_from_db()
        self.assertEqual(self.live.status, Session.Status.FINISHED)

    def test_the_browsers_recording_goes_to_the_talk_going_on(self):
        talk = Talk.objects.create(session=self.live, status=Talk.Status.RECORDING, started_at=timezone.now())
        audio = SimpleUploadedFile("talk.webm", b"webm", content_type="audio/webm")
        seen = {}
        # Read during the call: Django closes the upload once the request is done.
        with mock.patch("web.views.sessions.finish_talk",
                        side_effect=lambda **kwargs: seen.update(kwargs, content=kwargs["audio"].read())):
            response = self.client.post(self.url, {"audio": audio})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(seen["talk_id"], talk.id)
        self.assertEqual(seen["content"], b"webm")

    def test_a_recording_with_no_talk_going_on(self):
        audio = SimpleUploadedFile("talk.webm", b"webm", content_type="audio/webm")
        response = self.client.post(self.url, {"audio": audio})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["errors"]["__all__"], ["There's no talk going on for this recording."])
        # Refused before anything changes.
        self.live_client.close_session.assert_not_called()
        self.live.refresh_from_db()
        self.assertEqual(self.live.status, Session.Status.LIVE)

    def test_finished_even_when_the_live_process_cant_be_reached(self):
        self.live_client.close_session.side_effect = LiveError(LIVE_UNAVAILABLE, "Can't be reached.")
        with self.assertLogs("web.views.sessions", "WARNING"):
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.live.refresh_from_db()
        self.assertEqual(self.live.status, Session.Status.FINISHED)

    def test_rejects(self):
        with self.subTest("not live: 409, the live process isn't asked"):
            Session.objects.filter(pk=self.live.pk).update(status=Session.Status.FINISHED)
            self.assertEqual(self.client.post(self.url).status_code, 409)
            self.live_client.close_session.assert_not_called()
        with self.subTest("someone else's: 404"):
            self.client.force_login(make_trainer("bo@example.com").user)
            self.assertEqual(self.client.post(self.url).status_code, 404)
        with self.subTest("a speaker: not allowed"):
            self.client.force_login(self.speaker)
            self.assertEqual(self.client.post(self.url).status_code, 403)
        with self.subTest("only POST"):
            self.client.force_login(self.trainer.user)
            self.assertEqual(self.client.get(self.url).status_code, 405)
