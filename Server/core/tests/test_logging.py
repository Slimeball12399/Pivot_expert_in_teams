"""Tests for SCRUM-112 Basic logging setup.

Login is not implemented yet, so auth events are tested by sending Django's
auth signals directly with mock users and requests instead of going through
real views. SimpleTestCase is used because no database is needed.
"""
import logging
from unittest import mock

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from core.log_filters import RedactSensitiveFilter
from core.request_id import RequestIDFilter, RequestIDMiddleware, request_id_var

FAKE_EMAIL = "anna.test@example.com"
FAKE_PASSWORD = "Sup3rSecret!pw"


def make_user(pk=42, email=FAKE_EMAIL):
    """Stand-in for a real user until the user model and login exist.

    `save` is included because Django's own update_last_login handler also
    listens to user_logged_in and calls user.save().
    """
    return mock.Mock(pk=pk, email=email, spec=["pk", "email", "save"])


class AuthEventLoggingTests(SimpleTestCase):
    """SCRUM-119: auth events are logged without sensitive data."""

    def setUp(self):
        self.request = RequestFactory().post("/login/")

    def test_login_success_logs_user_id_and_channel(self):
        user = make_user()
        with self.assertLogs("pivot.auth", level="INFO") as logs:
            user_logged_in.send(sender=user.__class__, request=self.request, user=user)

        self.assertEqual(len(logs.records), 1)
        record = logs.records[0]
        self.assertEqual(record.levelno, logging.INFO)
        self.assertIn("login success", record.getMessage())
        self.assertIn("user_id=42", record.getMessage())
        self.assertIn("channel=web", record.getMessage())

    def test_login_success_does_not_log_email(self):
        user = make_user()
        with self.assertLogs("pivot.auth", level="INFO") as logs:
            user_logged_in.send(sender=user.__class__, request=self.request, user=user)

        self.assertNotIn(FAKE_EMAIL, "\n".join(logs.output))

    def test_logout_logs_user_id(self):
        user = make_user(pk=7)
        with self.assertLogs("pivot.auth", level="INFO") as logs:
            user_logged_out.send(sender=user.__class__, request=self.request, user=user)

        self.assertIn("logout", logs.records[0].getMessage())
        self.assertIn("user_id=7", logs.records[0].getMessage())

    def test_logout_without_user_does_not_crash(self):
        # Django sends user=None when an anonymous session logs out.
        with self.assertLogs("pivot.auth", level="INFO") as logs:
            user_logged_out.send(sender=None, request=self.request, user=None)

        self.assertIn("user_id=None", logs.records[0].getMessage())

    def test_login_failed_is_a_warning(self):
        credentials = {"email": FAKE_EMAIL, "password": FAKE_PASSWORD}
        with self.assertLogs("pivot.auth", level="INFO") as logs:
            user_login_failed.send(
                sender=__name__, credentials=credentials, request=self.request
            )

        self.assertEqual(logs.records[0].levelno, logging.WARNING)
        self.assertIn("login failed", logs.records[0].getMessage())

    def test_login_failed_does_not_log_credentials(self):
        credentials = {"email": FAKE_EMAIL, "password": FAKE_PASSWORD}
        with self.assertLogs("pivot.auth", level="INFO") as logs:
            user_login_failed.send(
                sender=__name__, credentials=credentials, request=self.request
            )

        output = "\n".join(logs.output)
        self.assertNotIn(FAKE_EMAIL, output)
        self.assertNotIn(FAKE_PASSWORD, output)


class RequestIDMiddlewareTests(SimpleTestCase):
    """SCRUM-118: each request gets an ID that appears in its log lines."""

    def setUp(self):
        self.factory = RequestFactory()
        self.seen_ids = []

        def view(request):
            # Record what the logging filter would see during the request.
            self.seen_ids.append(request_id_var.get())
            return HttpResponse("ok")

        self.middleware = RequestIDMiddleware(view)

    def test_generates_id_and_returns_it_in_header(self):
        response = self.middleware(self.factory.get("/"))

        rid = response["X-Request-ID"]
        self.assertRegex(rid, r"^[0-9a-f]{32}$")
        self.assertEqual(self.seen_ids, [rid])

    def test_each_request_gets_a_different_id(self):
        first = self.middleware(self.factory.get("/"))["X-Request-ID"]
        second = self.middleware(self.factory.get("/"))["X-Request-ID"]

        self.assertNotEqual(first, second)

    def test_reuses_valid_incoming_id(self):
        incoming = "abc12345-client-id"
        response = self.middleware(
            self.factory.get("/", HTTP_X_REQUEST_ID=incoming)
        )

        self.assertEqual(response["X-Request-ID"], incoming)
        self.assertEqual(self.seen_ids, [incoming])

    def test_replaces_invalid_incoming_id(self):
        bad = "bad id\nFAKE LOG LINE"
        response = self.middleware(self.factory.get("/", HTTP_X_REQUEST_ID=bad))

        self.assertNotEqual(response["X-Request-ID"], bad)
        self.assertRegex(response["X-Request-ID"], r"^[0-9a-f]{32}$")

    def test_id_is_cleared_after_request(self):
        self.middleware(self.factory.get("/"))

        self.assertEqual(request_id_var.get(), "-")

    def test_id_is_cleared_even_if_view_raises(self):
        def broken_view(request):
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            RequestIDMiddleware(broken_view)(self.factory.get("/"))

        self.assertEqual(request_id_var.get(), "-")

    def test_filter_adds_current_id_to_log_records(self):
        record = logging.LogRecord("pivot.test", logging.INFO, __file__, 1, "hi", (), None)
        token = request_id_var.set("req-123456")
        try:
            RequestIDFilter().filter(record)
        finally:
            request_id_var.reset(token)

        self.assertEqual(record.request_id, "req-123456")

    def test_filter_uses_dash_outside_requests(self):
        record = logging.LogRecord("pivot.test", logging.INFO, __file__, 1, "hi", (), None)
        RequestIDFilter().filter(record)

        self.assertEqual(record.request_id, "-")


class RedactSensitiveFilterTests(SimpleTestCase):
    """Safety net: secrets are masked if someone logs them by mistake."""

    def redact(self, msg, *args):
        record = logging.LogRecord("pivot.test", logging.INFO, __file__, 1, msg, args, None)
        RedactSensitiveFilter().filter(record)
        return record.getMessage()

    def test_masks_password(self):
        result = self.redact("password=%s", FAKE_PASSWORD)

        self.assertNotIn(FAKE_PASSWORD, result)
        self.assertIn("[REDACTED]", result)

    def test_masks_tokens_in_json_like_text(self):
        result = self.redact('{"access": "eyJhbGciOi.abc", "refresh": "eyJ.def"}')

        self.assertNotIn("eyJhbGciOi.abc", result)
        self.assertNotIn("eyJ.def", result)

    def test_masks_authorization_header(self):
        result = self.redact("authorization: Bearer-xyz123")

        self.assertNotIn("Bearer-xyz123", result)

    def test_leaves_normal_messages_alone(self):
        self.assertEqual(
            self.redact("login success user_id=%s", 42),
            "login success user_id=42",
        )

    def test_is_case_insensitive(self):
        result = self.redact("PASSWORD=%s", FAKE_PASSWORD)

        self.assertNotIn(FAKE_PASSWORD, result)