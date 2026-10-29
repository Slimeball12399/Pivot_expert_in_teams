from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

URL = reverse("web:home")


class HomeViewTests(TestCase):
    def test_home_page(self):
        self.assertEqual(URL, "/")

        with self.subTest("logged out: redirected to the login page"):
            response = self.client.get(URL)
            self.assertRedirects(
                response, f"{reverse(settings.LOGIN_URL)}?next={URL}", fetch_redirect_response=False)

        with self.subTest("logged in: shows the page"):
            admin = User.objects.create_user(
                "admin@example.com", "Str0ng-test-pass!", first_name="Anna", last_name="Hansen",
                role=User.Role.ADMIN)
            self.client.force_login(admin)
            response = self.client.get(URL)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Hello world")
