from django.core.exceptions import ValidationError
from django.db import transaction

from .models import SpeakerProfile, User


@transaction.atomic
def register_speaker(*, email, password, first_name, last_name, phone_number,
                     birth_date, height_cm, improvement_goals=""):
    """Create a speaker: the User and its SpeakerProfile together, or nothing.

    Validates both models first and raises one ValidationError with every
    error from both.
    """
    errors = {}

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
    return user
