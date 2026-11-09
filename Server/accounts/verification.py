"""One-time email codes: making them and checking them.

Shared by email verification and password reset (EmailCode.Purpose). This
module knows nothing about either flow: services.py decides when a code is
made, what happens once it is right, and sends the emails.

Settings ("Security"): EMAIL_CODE_LENGTH, EMAIL_CODE_LIFETIME,
EMAIL_CODE_MAX_ATTEMPTS and EMAIL_CODE_RESEND_COOLDOWN.
"""

import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import EmailCode


@transaction.atomic
def create_code(user, purpose) -> str | None:
    """Make a new code for `user` and return it, for the caller to email.

    Returns None and makes nothing while the user's last code for `purpose`
    is younger than EMAIL_CODE_RESEND_COOLDOWN, so the resend buttons can't
    flood an inbox. Earlier open codes for `purpose` are invalidated (kept as
    a record, but they stop working), so only the newest email counts. Only a
    keyed hash of the code is stored, so a leaked database alone doesn't
    reveal any codes.
    """
    now = timezone.now()
    codes = EmailCode.objects.filter(user=user, purpose=purpose)
    if codes.filter(created_at__gt=now - settings.EMAIL_CODE_RESEND_COOLDOWN).exists():
        return None

    length = settings.EMAIL_CODE_LENGTH
    code = f"{secrets.randbelow(10 ** length):0{length}d}"
    codes.filter(used_at__isnull=True, invalidated_at__isnull=True).update(invalidated_at=now)
    EmailCode.objects.create(
        user=user,
        purpose=purpose,
        code_hash=hmac.new(settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest(),
        expires_at=now + settings.EMAIL_CODE_LIFETIME,
    )
    return code


@transaction.atomic
def validate_code(user, purpose, code) -> bool:
    """True if `code` is the user's current, usable code for `purpose`.

    Spaces are ignored, so "1234 5678" as shown in the email works. A right
    code is marked used, so it works once. A wrong one counts as an attempt;
    after EMAIL_CODE_MAX_ATTEMPTS the code stops working and the user has to
    ask for a new one.
    """
    current = (
        EmailCode.objects.select_for_update()
        .filter(user=user, purpose=purpose, used_at__isnull=True, invalidated_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if current is None or not current.is_usable:
        return False

    code = "".join(str(code or "").split())
    # The same keyed hash as in create_code().
    code_hash = hmac.new(settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(current.code_hash, code_hash):
        current.attempts += 1
        current.save(update_fields=["attempts"])
        return False

    current.used_at = timezone.now()
    current.save(update_fields=["used_at"])
    return True
