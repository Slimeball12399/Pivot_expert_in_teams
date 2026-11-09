"""Send or preview one of Pivot's emails with a made-up code.

    python manage.py send_test_email you@example.com
    python manage.py send_test_email you@example.com --kind password_reset_code
    python manage.py send_test_email --preview email.html

With SEND_EMAILS=True the email really goes out through Resend; with False it
is printed in the terminal. --preview sends nothing: it writes the HTML
version to a file you can open in a browser.
"""

import secrets
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.emails import (
    CODE_EMAILS,
    build_email,
    code_email_context,
    render_preview_html,
)


class Command(BaseCommand):
    help = "Send (or preview) a Pivot email with a made-up code."

    def add_arguments(self, parser):
        parser.add_argument("to", nargs="?", help="Address to send the test email to.")
        parser.add_argument(
            "--kind", choices=sorted(CODE_EMAILS), default="verification_code",
            help="Which email to send (default: verification_code).")
        parser.add_argument("--name", default="Test", help="First name in the greeting.")
        parser.add_argument(
            "--preview", metavar="FILE",
            help="Write the HTML to FILE instead of sending anything.")

    def handle(self, *args, to, kind, name, preview, **options):
        if not to and not preview:
            raise CommandError("Give an address to send to, or --preview FILE.")

        length = settings.EMAIL_CODE_LENGTH
        code = "".join(secrets.choice("0123456789") for _ in range(length))
        context = code_email_context(first_name=name, code=code)

        if preview:
            path = Path(preview).resolve()
            html = render_preview_html(kind, context, to_email=to or "you@example.com")
            path.write_text(html, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Preview written to {path}"))
            return

        build_email(to=to, subject=CODE_EMAILS[kind], template=kind, context=context).send()
        where = "through Resend" if settings.SEND_EMAILS else "to the terminal (SEND_EMAILS=False)"
        self.stdout.write(self.style.SUCCESS(f"Sent {kind} to {to} {where}."))
