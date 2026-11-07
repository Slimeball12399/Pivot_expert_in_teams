from django.conf import settings
from django.contrib.messages import get_messages
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now

from accounts.models import UserInvite
from accounts.tests.utils import make_invite, make_speaker, make_trainer

URL = reverse("web:users")
SUGGESTIONS_URL = reverse("web:invite_suggestions")
CREATE_URL = reverse("web:invite_create")


class UsersViewTests(TestCase):
    """The Users page. Which rows each filter and search returns is tested in
    accounts/tests/test_trainer_user_view.py (get_users)."""

    def setUp(self):
        self.trainer = make_trainer("anne@example.com")
        self.speaker = make_speaker("mikkel@example.com", trainer=self.trainer)
        make_speaker("other@example.com")  # not this trainer's
        make_invite(self.trainer, "mette@example.com")
        make_invite(self.trainer, "anders@example.com", days_old=10)  # expired

    def test_users_page(self):
        self.assertEqual(URL, "/users/")

        with self.subTest("logged out: redirected to the login page"):
            response = self.client.get(URL)
            self.assertRedirects(
                response, f"{reverse(settings.LOGIN_URL)}?next={URL}", fetch_redirect_response=False)

        with self.subTest("a speaker: not allowed"):
            self.client.force_login(self.speaker)
            self.assertEqual(self.client.get(URL).status_code, 403)

        self.client.force_login(self.trainer.user)
        response = self.client.get(URL)

        with self.subTest("by default: the trainer's speakers, with the session columns"):
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "web/users.html")
            self.assertEqual(response.context["layout"], "speakers")
            self.assertEqual([row.email for row in response.context["rows"]], ["mikkel@example.com"])
            self.assertEqual(response.context["speaker_count"], 1)
            self.assertContains(response, "1 speaker</span>")
            self.assertContains(response, ">Stability</div>")
            self.assertRegex(response.content.decode(), r'data-value="speakers"\s+aria-pressed="true"')
            self.assertContains(response, f'data-suggestions-url="{SUGGESTIONS_URL}"')

        with self.subTest("?status=all: speakers and invites, with status and activity"):
            response = self.client.get(URL, {"status": "all"})
            self.assertEqual(response.context["layout"], "mixed")
            self.assertEqual(len(response.context["rows"]), 3)
            self.assertContains(response, "Not joined yet", count=2)
            self.assertContains(response, '<span class="badge badge-warning">Pending</span>', html=True)
            self.assertContains(response, '<span class="badge">Expired</span>', html=True)

        with self.subTest("?q= searches, and the search keeps the filter"):
            response = self.client.get(URL, {"status": "all", "q": "mette"})
            self.assertEqual([row.email for row in response.context["rows"]], ["mette@example.com"])
            self.assertContains(response, '<input type="hidden" name="status" value="all">', html=True)

        with self.subTest("nothing matches: an empty state"):
            response = self.client.get(URL, {"q": "nobody"})
            self.assertContains(response, "No one matches")

        with self.subTest("an unknown status falls back to speakers"):
            self.assertEqual(self.client.get(URL, {"status": "nope"}).context["layout"], "speakers")

        with self.subTest("marked as the current page in the nav"):
            self.assertContains(response, f'href="{URL}" aria-current="page"')


class InviteCreateViewTests(TestCase):
    """Send invite in the invite dialog. The invite rules are tested in
    accounts/tests/test_invites.py (create_invite)."""

    def setUp(self):
        self.trainer = make_trainer("anne@example.com")
        self.client.force_login(self.trainer.user)

    def test_sends_an_invite(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(CREATE_URL, {"email": " mette@example.com "})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"message": "Invite sent to mette@example.com."})
        self.assertEqual(UserInvite.objects.get().email, "mette@example.com")
        self.assertEqual([message.to for message in mail.outbox], [["mette@example.com"]])
        self.assertEqual([str(m) for m in get_messages(response.wsgi_request)],
                         ["Invite sent to mette@example.com."])

    def test_rejects(self):
        make_speaker("mikkel@example.com", trainer=self.trainer)
        cases = [
            ("not an email", "mette", "Enter a valid email address."),
            ("empty", "", "Enter a valid email address."),
            ("already their speaker", "mikkel@example.com", "This person is already one of your users."),
            ("a trainer account", "anne@example.com", "This email belongs to a trainer account."),
        ]
        for label, email, message in cases:
            with self.subTest(label, email=email):
                response = self.client.post(CREATE_URL, {"email": email})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {"errors": {"email": [message]}})
        self.assertFalse(UserInvite.objects.exists())

        with self.subTest("only POST"):
            self.assertEqual(self.client.get(CREATE_URL).status_code, 405)


class InviteRowActionTests(TestCase):
    """Resend and Cancel on a users table row."""

    def setUp(self):
        self.trainer = make_trainer("anne@example.com")
        self.invite = make_invite(self.trainer, "mette@example.com")
        self.client.force_login(self.trainer.user)

    def test_resend(self):
        url = reverse("web:invite_resend", args=[self.invite.pk])
        next_url = f"{URL}?status=invites"
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, {"next": next_url})
        self.assertRedirects(response, next_url, fetch_redirect_response=False)

        with self.subTest("a new open invite replaces the old one, and is emailed"):
            self.invite.refresh_from_db()
            self.assertEqual(self.invite.status, UserInvite.Status.REVOKED)
            self.assertEqual(UserInvite.objects.pending().get().email, "mette@example.com")
            self.assertEqual(len(mail.outbox), 1)

        with self.subTest("a next to another site goes to the users page instead"):
            response = self.client.post(url, {"next": "https://evil.example.com/"})
            self.assertRedirects(response, URL, fetch_redirect_response=False)

    def test_cancel(self):
        url = reverse("web:invite_cancel", args=[self.invite.pk])
        response = self.client.post(url, {"next": URL})
        self.assertRedirects(response, URL, fetch_redirect_response=False)
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.status, UserInvite.Status.REVOKED)

        with self.subTest("cancelling it again: an error message, nothing changes"):
            response = self.client.post(url, {"next": URL})
            self.assertEqual([m.level_tag for m in get_messages(response.wsgi_request)], ["error"])

    def test_another_trainers_invite(self):
        other = make_trainer("bo@example.com")
        invite = make_invite(other, "lars@example.com")
        with self.subTest("resend: not found"):
            response = self.client.post(reverse("web:invite_resend", args=[invite.pk]))
            self.assertEqual(response.status_code, 404)
        with self.subTest("cancel: an error message, the invite stays open"):
            self.client.post(reverse("web:invite_cancel", args=[invite.pk]))
            invite.refresh_from_db()
            self.assertEqual(invite.status, UserInvite.Status.PENDING)


class InviteSuggestionsViewTests(TestCase):
    """The JSON for the invite dialog's dropdown. Which emails are suggested is
    tested in accounts/tests/test_invites.py (suggest_invite_emails)."""

    def test_invite_suggestions(self):
        self.assertEqual(SUGGESTIONS_URL, "/users/invite/suggestions/")
        trainer = make_trainer("anne@example.com")
        own = make_speaker("mikkel.jensen@example.com", trainer=trainer)
        make_speaker("milla.berg@example.com")  # another trainer's or nobody's

        with self.subTest("logged out: redirected to the login page"):
            response = self.client.get(SUGGESTIONS_URL, {"q": "mik"})
            self.assertRedirects(
                response, f"{reverse(settings.LOGIN_URL)}?next={SUGGESTIONS_URL}%3Fq%3Dmik",
                fetch_redirect_response=False)

        with self.subTest("a speaker: not allowed"):
            self.client.force_login(own)
            self.assertEqual(self.client.get(SUGGESTIONS_URL, {"q": "mik"}).status_code, 403)

        self.client.force_login(trainer.user)
        cases = [
            ("too short", "mi", []),
            ("the trainer's own speaker", "mik",
             [{"email": "mikkel.jensen@example.com", "already_linked": True, "already_invited": False}]),
            ("someone else's speaker", "mil",
             [{"email": "milla.berg@example.com", "already_linked": False, "already_invited": False}]),
            ("nothing matches", "zzz", []),
        ]
        for label, query, expected in cases:
            with self.subTest(label, query=query):
                response = self.client.get(SUGGESTIONS_URL, {"q": query})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"suggestions": expected})

