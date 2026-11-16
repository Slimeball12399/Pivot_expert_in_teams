from django.core.exceptions import ValidationError
from django.utils import timezone

# Error codes (ValidationError.code) the web views and the API react to.
INVALID_SCHEDULE = "invalid_schedule"


def validate_scheduled_at(value):
    """A session's scheduled time: with a time zone, and in the future."""
    if timezone.is_naive(value):
        raise ValidationError("The scheduled time needs a time zone.", code=INVALID_SCHEDULE)
    if value <= timezone.now():
        raise ValidationError("The scheduled time must be in the future.", code=INVALID_SCHEDULE)
