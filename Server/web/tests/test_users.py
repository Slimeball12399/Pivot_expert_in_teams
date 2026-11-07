from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from accounts.tests.utils import make_speaker, make_trainer

URL = reverse("web:users")
SUGGESTIONS_URL = reverse("web:invite_suggestions")


class UsersViewTests(TestCase):
    """The Users page. UI only for now; the invite rules are tested in
    accounts/tests/test_invites.py."""

    def test_users_page(self):
        self.assertEqual(URL, "/users/")
        trainer = make_trainer("anne@example.com")
        speaker = make_speaker("mikkel@example.com", trainer=trainer)
        make_speaker("other@example.com")  # not this trainer's

        with self.subTest("logged out: redirected to the login page"):
            response = self.client.get(URL)
            self.assertRedirects(
                response, f"{reverse(settings.LOGIN_URL)}?next={URL}", fetch_redirect_response=False)

        with self.subTest("a speaker: not allowed"):
            self.client.force_login(speaker)
            self.assertEqual(self.client.get(URL).status_code, 403)

        with self.subTest("the trainer: their numbers, the search and the invite dialog"):
            self.client.force_login(trainer.user)
            response = self.client.get(URL, {"q": "mik"})
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "web/users.html")
            self.assertEqual(response.context["speaker_count"], 1)
            self.assertContains(response, "1 speaker</span>")
            self.assertContains(response, "0 sessions this week")
            self.assertContains(response, 'value="mik"')
            self.assertContains(response, 'id="invite-dialog"')
            self.assertContains(response, f'data-suggestions-url="{SUGGESTIONS_URL}"')

        with self.subTest("by default: only speakers, with their session columns"):
            self.assertEqual(response.context["layout"], "speakers")
            self.assertEqual([row["kind"] for row in response.context["rows"]], ["speaker"] * 3)
            self.assertContains(response, 'role="table"')
            self.assertContains(response, ">Stability</div>")
            self.assertNotContains(response, "Not joined yet")
            self.assertContains(response, "data-filter-menu")
            self.assertRegex(response.content.decode(), r'data-value="speakers"\s+aria-pressed="true"')

        with self.subTest("?status=all: speakers and invites, with status and activity"):
            all_users = self.client.get(URL, {"status": "all"})
            self.assertEqual(all_users.context["layout"], "mixed")
            self.assertEqual(len(all_users.context["rows"]), 7)
            self.assertContains(all_users, "Not joined yet", count=4)
            self.assertContains(all_users, '<span class="badge badge-warning">Pending</span>', html=True)
            self.assertNotContains(all_users, ">Stability</div>")

        with self.subTest("an unknown status falls back to speakers"):
            self.assertEqual(self.client.get(URL, {"status": "nope"}).context["layout"], "speakers")

        with self.subTest("marked as the current page in the nav"):
            self.assertContains(response, f'href="{URL}" aria-current="page"')


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
             [{"email": "mikkel.jensen@example.com", "already_linked": True}]),
            ("someone else's speaker", "mil",
             [{"email": "milla.berg@example.com", "already_linked": False}]),
            ("nothing matches", "zzz", []),
        ]
        for label, query, expected in cases:
            with self.subTest(label, query=query):
                response = self.client.get(SUGGESTIONS_URL, {"q": query})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"suggestions": expected})

