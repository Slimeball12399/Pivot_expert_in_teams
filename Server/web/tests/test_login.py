from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
URL = reverse("web:login")
PASSWORD = "Str0ng-test-pass!"
LOGIN_FAILED = "Wrong email or password."
LOGIN_MISSING_FIELDS = "Enter your email and password."


class LoginViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "admin@example.com", PASSWORD, first_name="Anna", last_name="Hansen",
            role=User.Role.ADMIN)
        User.objects.create_user(
            "speaker@example.com", PASSWORD, first_name="Mikkel", last_name="Jensen",
            role=User.Role.SPEAKER)

    def post(self, **data):
        return self.client.post(URL, {"email": "admin@example.com", "password": PASSWORD, **data})

    def assertLoggedIn(self, user):
        self.assertEqual(self.client.session.get(SESSION_KEY), str(user.pk))

    def assertNotLoggedIn(self):
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_shows_the_form(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="password"')

    def test_admin_logs_in(self):
        with self.subTest("redirects to LOGIN_REDIRECT_URL"):
            response = self.post()
            self.assertRedirects(response, settings.LOGIN_REDIRECT_URL, fetch_redirect_response=False)
            self.assertLoggedIn(self.admin)

        with self.subTest("without 'keep me logged in' the session ends with the browser"):
            self.assertTrue(self.client.session.get_expire_at_browser_close())

        with self.subTest("with 'keep me logged in' the session is kept"):
            self.client.logout()
            self.post(remember_me="on")
            self.assertLoggedIn(self.admin)
            self.assertFalse(self.client.session.get_expire_at_browser_close())

    def test_follows_next_only_on_this_site(self):
        with self.subTest("same-site next is followed"):
            response = self.post(next="/somewhere/")
            self.assertRedirects(response, "/somewhere/", fetch_redirect_response=False)

        with self.subTest("other sites are ignored"):
            self.client.logout()
            response = self.post(next="https://evil.example.com/")
            self.assertRedirects(response, settings.LOGIN_REDIRECT_URL, fetch_redirect_response=False)

        with self.subTest("next from the URL is kept in the form"):
            self.client.logout()
            response = self.client.get(URL, {"next": "/somewhere/"})
            self.assertContains(response, 'name="next" value="/somewhere/"')

    def test_rejects_invalid_logins(self):
        cases = [
            ("wrong password", {"password": "wrong-password"}, LOGIN_FAILED),
            ("unknown email", {"email": "nobody@example.com"}, LOGIN_FAILED),
            ("speakers can't use the web app", {"email": "speaker@example.com"}, LOGIN_FAILED),
            ("empty password", {"password": ""}, LOGIN_MISSING_FIELDS),
        ]
        for label, data, message in cases:
            with self.subTest(label):
                response = self.post(**data)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, message)
                self.assertNotLoggedIn()

        with self.subTest("the email is kept, the password is not"):
            response = self.post(password="wrong-password")
            self.assertContains(response, 'value="admin@example.com"')
            self.assertNotContains(response, "wrong-password")
