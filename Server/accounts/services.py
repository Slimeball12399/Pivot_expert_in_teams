from functools import partial

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.debug import sensitive_variables

from . import emails, verification
from .models import Consent, EmailCode, SpeakerProfile, User

# Error codes (ValidationError.code) the web views and the API react to.
INVALID_LOGIN = "invalid_login"
EMAIL_NOT_VERIFIED = "email_not_verified"
INVALID_CODE = "invalid_code"
INVALID_RESET_TOKEN = "invalid_token"
EMAIL_TAKEN = "email_taken"

EMAIL_NOT_VERIFIED_MESSAGE = "Verify your email to log in. We sent you a code."
INVALID_CODE_MESSAGE = "That code is wrong or has expired. Check the email or ask for a new code."
INVALID_RESET_TOKEN_MESSAGE = "This password reset has expired. Start again to get a new code."
EMAIL_TAKEN_MESSAGE = "An account with this email already exists."


def email_in_use(email, *, exclude=None) -> bool:
    """True if an account other than `exclude` holds `email`, in any letter
    case: as its own email, or as a pending new email it can still confirm
    (it has a usable verification code, the same rules as EmailCode.is_usable).

    A pending email whose codes are all used, replaced, expired or out of
    attempts holds nothing, so nobody can block an address by never
    confirming it. Its owner can revive it with "send a new code" until
    another account takes the address.
    """
    holders = User.objects.filter(
        Q(email__iexact=email)
        | Q(pending_email__iexact=email,
            email_codes__purpose=EmailCode.Purpose.VERIFY_EMAIL,
            email_codes__used_at__isnull=True,
            email_codes__invalidated_at__isnull=True,
            email_codes__expires_at__gt=timezone.now(),
            email_codes__attempts__lt=settings.EMAIL_CODE_MAX_ATTEMPTS)
    )
    if exclude is not None:
        holders = holders.exclude(pk=exclude.pk)
    return holders.exists()


@transaction.atomic
def register_speaker(*, email, password, first_name, last_name, phone_number,
                     birth_date, height_cm, consents, improvement_goals=""):

    errors = {}

    consents = set(consents)
    unknown = consents - set(Consent.Purpose.values)
    missing = Consent.REQUIRED_FOR_SPEAKERS - consents
    if unknown:
        errors.setdefault("consents", []).append(
            f"Unknown consent: {', '.join(sorted(unknown))}.")
    if missing:
        labels = ", ".join(sorted(Consent.Purpose(p).label for p in missing))
        errors.setdefault("consents", []).append(
            f"You must accept: {labels}.")

    user = None
    try:
        user = User.objects.build_user(
            email,
            password,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            role=User.Role.SPEAKER,
        )
    except ValidationError as e:
        e.update_error_dict(errors)

    # The unique constraint only catches the exact same spelling. This also
    # catches other letter case and a new email another account is confirming.
    # Skipped when full_clean already reported a problem with the email.
    if "email" not in errors and email_in_use(User.objects.normalize_email(email)):
        errors.setdefault("email", []).append(EMAIL_TAKEN_MESSAGE)

    # Optional on the model (so createsuperuser doesn't ask), required for speakers.
    if not phone_number:
        errors.setdefault("phone_number", []).append(
            "Phone number is required.")

    profile = SpeakerProfile(
        birth_date=birth_date,
        height_cm=height_cm,
        improvement_goals=improvement_goals,
    )
    try:
        profile.full_clean(exclude=["user"])
    except ValidationError as e:
        e.update_error_dict(errors)

    if errors:
        raise ValidationError(errors)

    user.save()
    # Other accounts' pending changes to this email had no usable code left
    # (email_in_use above), so they can't be confirmed any more.
    User.objects.filter(pending_email__iexact=user.email).exclude(pk=user.pk).update(
        pending_email="")
    profile.user = user
    profile.save()
    Consent.objects.bulk_create([
        Consent(user=user, purpose=purpose,
                notice_version=Consent.current_version(purpose))
        for purpose in sorted(consents)
    ])
    # After the commit, so a failed registration sends nothing. robust: a
    # failed email doesn't undo the account; logging in sends a new code.
    transaction.on_commit(partial(send_verification_code, user), robust=True)
    return user


@sensitive_variables("password")
def login_user(request, email, password, role=None) -> AbstractUser:
    """The login rules, for the web (sessions) and the API (tokens).

    Raises ValidationError with code INVALID_LOGIN (wrong email or password,
    inactive account, or not `role`), or EMAIL_NOT_VERIFIED after emailing a
    new code. The caller logs the returned user in its own way.
    """
    user = authenticate(request, email=email, password=password)
    if user is None or (role is not None and user.role != role):
        raise ValidationError("Wrong email or password.", code=INVALID_LOGIN)
    # Only after the password check, so "not verified" never tells a
    # stranger that an email has an account.
    if user.email_verified_at is None:
        send_verification_code(user)
        raise ValidationError(EMAIL_NOT_VERIFIED_MESSAGE, code=EMAIL_NOT_VERIFIED)
    return user


# Fields a user may change about themselves (PATCH /api/me/). Email and role
# are left out on purpose: email needs re-verification, role is admin-only.
EDITABLE_USER_FIELDS = frozenset({"first_name", "last_name", "phone_number"})
EDITABLE_SPEAKER_FIELDS = frozenset(
    {"birth_date", "height_cm", "improvement_goals"})


@transaction.atomic
def update_profile(user, *, profile=None, email=None, current_password=None, **fields):
    """Change the given fields of `user` and, for speakers, of their
    SpeakerProfile (`profile`, a dict). Only the fields passed are touched.

    A new `email` needs `current_password` and isn't switched here: it is
    saved as pending_email and a code is sent to it. verify_email() switches
    it once that code is entered. Sending the current email cancels a
    pending change.

    Runs the same model validators as registration and raises one
    ValidationError with every error found; nothing is saved then.
    """
    profile = profile or {}
    unknown = (set(fields) - EDITABLE_USER_FIELDS) | (set(profile) -
                                                      EDITABLE_SPEAKER_FIELDS)
    if unknown:
        raise ValueError(f"Not editable: {', '.join(sorted(unknown))}")

    errors = {}
    old_pending_email = user.pending_email

    if email is not None:
        email = User.objects.normalize_email(email.strip())
        if email.lower() == user.email.lower():
            fields["pending_email"] = ""  # cancels a pending change
        elif not user.check_password(current_password or ""):
            errors.setdefault("current_password", []).append("Wrong password.")
        elif email_in_use(email, exclude=user):
            errors.setdefault("email", []).append(EMAIL_TAKEN_MESSAGE)
        else:
            fields["pending_email"] = email

    for name, value in fields.items():
        setattr(user, name, value)

    if "phone_number" in fields and not fields["phone_number"] and user.role == User.Role.SPEAKER:
        errors.setdefault("phone_number", []).append(
            "Phone number is required.")
    try:
        user.full_clean(exclude=["password"])
    except ValidationError as e:
        e.update_error_dict(errors)

    speaker_profile = None
    if profile:
        if user.role != User.Role.SPEAKER:
            errors.setdefault("profile", []).append(
                "Only speakers have profile details to change.")
        else:
            try:
                speaker_profile = user.speaker_profile
            except SpeakerProfile.DoesNotExist:
                errors.setdefault("profile", []).append(
                    "This account has no speaker profile.")
            else:
                for name, value in profile.items():
                    setattr(speaker_profile, name, value)
                try:
                    speaker_profile.full_clean(exclude=["user", "admin"])
                except ValidationError as e:
                    e.update_error_dict(errors)

    if errors:
        # Undo the in-memory changes so the caller's objects stay as saved.
        user.refresh_from_db()
        raise ValidationError(errors)

    if fields:
        user.save(update_fields=list(fields))
    if "pending_email" in fields and fields["pending_email"] != old_pending_email:
        # A code sent to the earlier pending email must not confirm this one.
        # Inside the resend cooldown no new code goes out below; the user
        # asks for one ("send a new code") once it has passed.
        user.email_codes.filter(
            purpose=EmailCode.Purpose.VERIFY_EMAIL, used_at__isnull=True,
            invalidated_at__isnull=True,
        ).update(invalidated_at=timezone.now())
    if fields.get("pending_email"):
        # Other accounts' pending changes to this email had no usable code
        # left (email_in_use above), so they can't be confirmed any more.
        User.objects.filter(pending_email__iexact=user.pending_email).exclude(
            pk=user.pk).update(pending_email="")
        transaction.on_commit(partial(send_verification_code, user), robust=True)
    if speaker_profile is not None:
        speaker_profile.save(update_fields=list(profile))
    return user



# Email verification
# A new account can't log in until its email is verified with a code. The
# code goes out on registering (speakers) or on creation (admins), and again
# whenever an unverified user logs in with the right password.


def send_verification_code(user) -> bool:
    """Email a new verification code to the address that still needs one:
    the pending new email if there is one, else the account's email while
    unverified. False when nothing was sent: nothing to verify, or the last
    code is still inside the resend cooldown."""
    to = user.pending_email or (user.email if user.email_verified_at is None else "")
    if not to:
        return False
    code = verification.create_code(user, EmailCode.Purpose.VERIFY_EMAIL)
    if code is None:  # resend cooldown
        return False
    emails.send_verification_code_email(user, code, to=to)
    return True


def resend_verification_code(email) -> None:
    """The "send a new code" button, for an unverified account's email or a
    pending new email. Does the same whether or not the email has an
    account, so it can't be used to find out which emails do."""
    user = User.objects.filter(
        Q(email__iexact=email) | Q(pending_email__iexact=email), is_active=True).first()
    if user is not None and (
            user.pending_email.lower() == email.lower() or user.email_verified_at is None):
        send_verification_code(user)


def verify_email(email, code) -> AbstractUser:
    """Verify `email` with `code` and return the user. Either an unverified
    account's own email, or a pending new email, which then replaces the
    old one (User.save then logs the app out everywhere).

    Raises ValidationError(code=INVALID_CODE) for any wrong, expired or used
    code, and for unknown or already verified emails; EMAIL_TAKEN if another
    account took the new email in the meantime.
    """
    # email_in_use() keeps an email on one account at most, so this finds one.
    user = User.objects.filter(
        Q(email__iexact=email) | Q(pending_email__iexact=email), is_active=True).first()
    changing = user is not None and user.pending_email.lower() == email.lower()
    if (user is None or (not changing and user.email_verified_at is not None)
            or not verification.validate_code(user, EmailCode.Purpose.VERIFY_EMAIL, code)):
        raise ValidationError(INVALID_CODE_MESSAGE, code=INVALID_CODE)
    if changing:
        if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            raise ValidationError(EMAIL_TAKEN_MESSAGE, code=EMAIL_TAKEN)
        # The spelling saved in update_profile, not however it was typed here.
        user.email, user.pending_email = user.pending_email, ""
    user.email_verified_at = timezone.now()
    user.save()
    return user


# Password reset
# 1. request_password_reset(email) emails a reset code.
# 2. verify_password_reset_code(email, code) swaps a right code for a reset
#    token (Django's PasswordResetTokenGenerator, PASSWORD_RESET_TIMEOUT).
# 3. reset_password(uid, token, new_password) sets the new password.
# The token is signed with SECRET_KEY and includes the password hash, so it
# can't be forged and stops working once the password has changed.


def request_password_reset(email) -> None:
    """Email a reset code. Does the same whether or not the email has an
    account, so it can't be used to find out which emails do."""
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is None:
        return
    code = verification.create_code(user, EmailCode.Purpose.RESET_PASSWORD)
    if code is not None:  # None: resend cooldown
        emails.send_password_reset_code_email(user, code)


def verify_password_reset_code(email, code) -> tuple[str, str]:
    """Swap a right reset code for (uid, token), which reset_password() needs.
    Raises ValidationError(code=INVALID_CODE) like verify_email()."""
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is None or not verification.validate_code(
            user, EmailCode.Purpose.RESET_PASSWORD, code):
        raise ValidationError(INVALID_CODE_MESSAGE, code=INVALID_CODE)
    return urlsafe_base64_encode(force_bytes(user.pk)), default_token_generator.make_token(user)


@sensitive_variables("new_password")
@transaction.atomic
def reset_password(uid, token, new_password) -> AbstractUser:
    """Set a new password with the token from verify_password_reset_code().

    Raises ValidationError(code=INVALID_RESET_TOKEN) for a wrong or expired
    token, and ValidationError({"new_password": [...]}) for a password the
    AUTH_PASSWORD_VALIDATORS reject. A weak password doesn't use up the
    token, so the user can try another one.
    """
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)), is_active=True)
    except (ValueError, ValidationError, User.DoesNotExist):  # bad base64, not a UUID, no user
        user = None
    if user is None or not default_token_generator.check_token(user, token):
        raise ValidationError(INVALID_RESET_TOKEN_MESSAGE, code=INVALID_RESET_TOKEN)
    try:
        validate_password(new_password, user)
    except ValidationError as e:
        raise ValidationError({"new_password": e.messages})

    user.set_password(new_password)
    fields = ["password"]
    # Getting the code proved they own the email.
    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        fields.append("email_verified_at")
    user.save(update_fields=fields)  # also logs the app out everywhere (User.save)
    # Reset codes asked for in the meantime stop working.
    user.email_codes.filter(
        purpose=EmailCode.Purpose.RESET_PASSWORD, used_at__isnull=True, invalidated_at__isnull=True,
    ).update(invalidated_at=timezone.now())
    return user
