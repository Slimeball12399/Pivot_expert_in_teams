from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import transaction
from django.contrib.auth.models import AbstractUser
from django.views.decorators.debug import sensitive_variables

from .models import Consent, SpeakerProfile, User


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
    profile.user = user
    profile.save()
    Consent.objects.bulk_create([
        Consent(user=user, purpose=purpose,
                notice_version=Consent.current_version(purpose))
        for purpose in sorted(consents)
    ])
    return user


@sensitive_variables("password")
def login_user(request, email, password, role=None) -> AbstractUser:
    if not email or not password:
        raise ValidationError("Enter your email and password.", code="missing")

    user = authenticate(request, email=email, password=password)
    if user is None or (role is not None and user.role != role):
        raise ValidationError("Wrong email or password.", code="invalid_login")
    return user


# Fields a user may change about themselves (PATCH /api/me/). Email and role
# are left out on purpose: email needs re-verification, role is admin-only.
EDITABLE_USER_FIELDS = frozenset({"first_name", "last_name", "phone_number"})
EDITABLE_SPEAKER_FIELDS = frozenset(
    {"birth_date", "height_cm", "improvement_goals"})


@transaction.atomic
def update_profile(user, *, profile=None, **fields):
    """Change the given fields of `user` and, for speakers, of their
    SpeakerProfile (`profile`, a dict). Only the fields passed are touched.

    Runs the same model validators as registration and raises one
    ValidationError with every error found; nothing is saved then.
    """
    profile = profile or {}
    unknown = (set(fields) - EDITABLE_USER_FIELDS) | (set(profile) -
                                                      EDITABLE_SPEAKER_FIELDS)
    if unknown:
        raise ValueError(f"Not editable: {', '.join(sorted(unknown))}")

    errors = {}

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
    if speaker_profile is not None:
        speaker_profile.save(update_fields=list(profile))
    return user
