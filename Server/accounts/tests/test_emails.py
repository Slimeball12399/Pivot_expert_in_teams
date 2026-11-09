import tempfile
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from django.core import mail
from django.core.management import call_command
from datetime import timedelta

from django.test import SimpleTestCase, override_settings

from accounts.emails import (
    format_code,
    send_password_reset_code_email,
    send_verification_code_email,
)

USER = SimpleNamespace(email="anna@example.com", first_name="Anna")


class FormatCodeTests(SimpleTestCase):
    def test_groups_of_four(self):
        self.assertEqual(format_code("12345678"), "1234 5678")
        self.assertEqual(format_code("123456"), "1234 56")


@override_settings(EMAIL_CODE_LIFETIME=timedelta(minutes=15), EMAIL_STATIC_URL="")
class CodeEmailTests(SimpleTestCase):
    def assert_code_email(self, subject):
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["anna@example.com"])
        self.assertEqual(message.subject, subject)

        with self.subTest("plain text"):
            self.assertIn("1234 5678", message.body)
            self.assertIn("Hi Anna", message.body)
            self.assertIn("15 minutes", message.body)

        with self.subTest("HTML"):
            html, mimetype = message.alternatives[0]
            self.assertEqual(mimetype, "text/html")
            self.assertIn("1234 5678", html)
            self.assertIn("Hi Anna", html)
            # Template syntax that didn't render (e.g. a multi-line {# #} comment).
            for leftover in ("{#", "#}", "{%", "%}", "{{", "}}"):
                self.assertNotIn(leftover, html)

        with self.subTest("both logos inline, referenced from the HTML"):
            self.assertEqual(len(message.attachments), 2)
            for logo in message.attachments:
                self.assertEqual(logo.get_content_type(), "image/png")
                self.assertEqual(logo.get_content_disposition(), "inline")
                cid = logo["Content-ID"].strip("<>")
                self.assertIn(f'src="cid:{cid}"', html)

    def test_footer_names_recipient_and_differs_per_email(self):
        send_verification_code_email(USER, "12345678")
        send_verification_code_email(USER, "12345678")
        first, second = (m.alternatives[0][0] for m in mail.outbox)
        self.assertIn("sent by Pivot to anna@example.com", first)
        self.assertIn("&copy;&nbsp;2026&nbsp;SDU", first)
        self.assertNotEqual(first, second)  # unique id, so Gmail doesn't trim it

    def test_verification_code_email(self):
        send_verification_code_email(USER, "12345678")
        self.assert_code_email("Your Pivot verification code")

    def test_password_reset_code_email(self):
        send_password_reset_code_email(USER, "12345678")
        self.assert_code_email("Your Pivot password reset code")
        self.assertIn("Never share this code", mail.outbox[0].body)

    def test_name_is_escaped_in_html(self):
        user = SimpleNamespace(email="x@example.com", first_name="<b>Eve</b>")
        send_verification_code_email(user, "12345678")
        html, _ = mail.outbox[0].alternatives[0]
        self.assertNotIn("<b>Eve</b>", html)
        self.assertIn("&lt;b&gt;Eve&lt;/b&gt;", html)

    @override_settings(EMAIL_STATIC_URL="https://example.com/static/")
    def test_logos_from_url(self):
        send_verification_code_email(USER, "12345678")
        message = mail.outbox[0]
        html, _ = message.alternatives[0]
        self.assertIn('src="https://example.com/static/web/img/pivot-logo-on-dark.png"', html)
        self.assertIn('src="https://example.com/static/web/img/pivot-logo.png"', html)
        self.assertEqual(message.attachments, [])

    @override_settings(EMAIL_CODE_LIFETIME=timedelta(minutes=30))
    def test_lifetime_comes_from_settings(self):
        send_verification_code_email(USER, "12345678")
        self.assertIn("30 minutes", mail.outbox[0].body)


@override_settings(EMAIL_STATIC_URL="")
class SendTestEmailCommandTests(SimpleTestCase):
    @override_settings(EMAIL_CODE_LENGTH=8)
    def test_code_has_configured_length(self):
        call_command("send_test_email", "me@example.com", stdout=StringIO())
        # The code is on its own indented line, e.g. "    1234 5678".
        self.assertRegex(mail.outbox[0].body, r"(?m)^    \d{4} \d{4}$")

    def test_sends_each_kind(self):
        for kind in ("verification_code", "password_reset_code"):
            with self.subTest(kind):
                mail.outbox.clear()
                call_command("send_test_email", "me@example.com", kind=kind, stdout=StringIO())
                self.assertEqual(len(mail.outbox), 1)
                self.assertEqual(mail.outbox[0].to, ["me@example.com"])

    def test_preview_writes_html_and_sends_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preview.html"
            call_command("send_test_email", preview=str(path), stdout=StringIO())
            html = path.read_text(encoding="utf-8")
        self.assertIn("data:image/png;base64,", html)
        self.assertIn("Confirm your email", html)
        self.assertEqual(mail.outbox, [])
