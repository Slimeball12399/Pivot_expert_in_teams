from datetime import datetime, timezone

from django.core.exceptions import ValidationError

# Youngest age a speaker can register at. Denmark's GDPR digital age of
# consent is 15 (since 2024); we use a higher limit to stay clear of it.
MIN_AGE = 16

# Accepted body height range for speakers, in centimetres.
MIN_HEIGHT_CM = 100
MAX_HEIGHT_CM = 250


def validate_danish_phone_number(value):
    """Only accept Danish numbers (+45) for now."""
    if value and getattr(value, "country_code", None) != 45:
        raise ValidationError(
            "Only Danish phone numbers (+45) are supported for now.",
            code="not_danish_phone_number",
        )


def age_on(birth_date, today):
    """Full years between birth_date and today (one less if the birthday hasn't happened yet)."""
    had_birthday = (today.month, today.day) >= (birth_date.month, birth_date.day)
    return today.year - birth_date.year - (0 if had_birthday else 1)


def validate_min_age(birth_date):
    # Always compare against today's date in UTC, whatever TIME_ZONE is set to.
    today = datetime.now(timezone.utc).date()
    if birth_date > today:
        raise ValidationError("Birth date can't be in the future.", code="future_birth_date")
    if age_on(birth_date, today) < MIN_AGE:
        raise ValidationError(
            "You must be at least %(min_age)s years old.",
            code="too_young",
            params={"min_age": MIN_AGE},
        )
