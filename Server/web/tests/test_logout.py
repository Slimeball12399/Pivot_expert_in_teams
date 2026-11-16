from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

URL = reverse("web:logout")
LOGIN = reverse(settings.LOGIN_URL)


class LogoutViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "admin@example.com", "Str0ng-test-pass!", first_name="Anna", last_name="Hansen",
            role=User.Role.ADMIN)

    def test_logout(self):
        self.assertEqual(URL, "/logout/")
        self.client.force_login(self.admin)

        with self.subTest("the header shows the logout button when logged in"):
            self.assertContains(self.client.get(reverse("web:home")), f'action="{URL}"')

        with self.subTest("POST logs out and goes to the login page"):
            response = self.client.post(URL)
            self.assertRedirects(response, LOGIN, fetch_redirect_response=False)
            self.assertNotIn("_auth_user_id", self.client.session)
            self.assertEqual(self.client.get(reverse("web:home")).status_code, 302)

    def test_get_is_refused(self):
        """A plain link, image or prefetch (GET) must not log anyone out."""
        self.client.force_login(self.admin)
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_no_button_when_logged_out(self):
        self.assertNotContains(self.client.get(LOGIN), f'action="{URL}"')
