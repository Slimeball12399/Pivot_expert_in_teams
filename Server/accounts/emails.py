"""Every email Pivot sends.

Services decide when an email goes out and pass in what it needs (a user, a
code); this module only decides what the email looks like. Each email has a
plain-text and an HTML template in accounts/templates/.

The HTML version shows two Pivot logos from web/static/web/img: the light one
(paper) on the navy header and the navy one on the white info card. They are
PNGs because Gmail and Outlook don't show SVG. By default they travel inside
the email as inline attachments, so they work without a public server. Set
EMAIL_STATIC_URL (the public https address of your static files) to load them
from there instead.

Where it goes (terminal or Resend) is decided by SEND_EMAILS in settings, and
how long a code works by EMAIL_CODE_LIFETIME (settings, "Security").
The codes themselves are made by the verification and password reset services.
"""

import base64
import email.utils
import uuid
from email.message import MIMEPart
from functools import cache
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

# Template variable -> static path, found like {% static %} finds files.
LOGOS = {
    "logo_on_dark_src": "web/img/pivot-logo-on-dark.png",  # navy header
    "logo_src": "web/img/pivot-logo.png",                  # white card
}

# The emails that show a one-time code: template name -> subject.
CODE_EMAILS = {
    "verification_code": "Your Pivot verification code",
    "password_reset_code": "Your Pivot password reset code",
}


@cache
def _static_png(static_path) -> bytes:
    path = finders.find(static_path)
    if path is None:
        raise FileNotFoundError(f"Email image not found in static files: {static_path}")
    return Path(path).read_bytes()


def _static_url(static_path):
    return settings.EMAIL_STATIC_URL.rstrip("/") + "/" + static_path


def _render(template, context, *, images, to_email):
    context = {
        **context,
        **images,
        "to_email": to_email,
        # Different in every email, hidden in the footer. Gmail collapses parts
        # that repeat earlier emails in a thread ("Show trimmed content");
        # something unique there stops it from hiding the footer.
        "email_id": uuid.uuid4().hex,
    }
    text = render_to_string(f"{template}.txt", context)
    html = render_to_string(f"{template}.html", context)
    return text, html


def build_email(*, to, subject, template, context) -> EmailMultiAlternatives:
    """An email with a text body, an HTML alternative and the logos.
    Not sent yet: call .send() on the result."""
    if settings.EMAIL_STATIC_URL:
        images = {name: _static_url(path) for name, path in LOGOS.items()}
        attachments = []
    else:
        images, attachments = {}, []
        for name, path in LOGOS.items():
            cid = email.utils.make_msgid(domain="pivot.email")  # "<...@pivot.email>"
            images[name] = f"cid:{cid[1:-1]}"
            part = MIMEPart()
            part.set_content(
                _static_png(path), maintype="image", subtype="png",
                disposition="inline", cid=cid)
            attachments.append(part)

    text, html = _render(template, context, images=images, to_email=to)
    message = EmailMultiAlternatives(subject=subject, body=text, to=[to])
    message.attach_alternative(html, "text/html")
    for part in attachments:
        message.attach(part)
    return message


def render_preview_html(template, context, *, to_email="you@example.com") -> str:
    """The HTML version, for opening in a browser. Without EMAIL_STATIC_URL the
    logos are embedded as data: URLs, which browsers show but mail apps block."""
    if settings.EMAIL_STATIC_URL:
        images = {name: _static_url(path) for name, path in LOGOS.items()}
    else:
        images = {
            name: "data:image/png;base64," + base64.b64encode(_static_png(path)).decode()
            for name, path in LOGOS.items()
        }
    _, html = _render(template, context, images=images, to_email=to_email)
    return html


def format_code(code: str) -> str:
    """Groups of four for reading: "12345678" -> "1234 5678"."""
    return " ".join(code[i:i + 4] for i in range(0, len(code), 4))


def code_lifetime_minutes() -> int:
    return int(settings.EMAIL_CODE_LIFETIME.total_seconds() // 60)


def code_email_context(*, first_name, code):
    return {
        "first_name": first_name,
        "code": code,
        "code_display": format_code(code),
        "minutes": code_lifetime_minutes(),
    }


def send_verification_code_email(user, code):
    """The code that confirms a new account's email address."""
    build_email(
        to=user.email,
        subject=CODE_EMAILS["verification_code"],
        template="verification_code",
        context=code_email_context(first_name=user.first_name, code=code),
    ).send()


def send_password_reset_code_email(user, code):
    """The code that lets a user choose a new password."""
    build_email(
        to=user.email,
        subject=CODE_EMAILS["password_reset_code"],
        template="password_reset_code",
        context=code_email_context(first_name=user.first_name, code=code),
    ).send()
