from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField

from .manager import UserManager
from .validators import (
    MAX_HEIGHT_CM,
    MIN_HEIGHT_CM,
    validate_danish_phone_number,
    validate_min_age,
)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        SPEAKER = "speaker", "Speaker"

    username = None
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    # Optional on the model so createsuperuser doesn't ask for it;
    # register_speaker() requires it for speakers.
    phone_number = PhoneNumberField(
        region="DK", blank=True, validators=[validate_danish_phone_number])
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.SPEAKER)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    def __str__(self):
        return f"{self.email} {self.role}"


class AdminProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="admin_profile")


class SpeakerProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="speaker_profile")
    admin = models.ForeignKey(
        AdminProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="speakers",
    )
    birth_date = models.DateField(validators=[validate_min_age])
    height_cm = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(MIN_HEIGHT_CM),
            MaxValueValidator(MAX_HEIGHT_CM),
        ]
    )
    improvement_goals = models.TextField(blank=True)


class Consent(models.Model):
    """One row each time a user gives a consent, so there is proof of what was
    agreed to and when (GDPR art. 7(1)). Withdrawing sets withdrawn_at instead
    of deleting the row."""

    class Purpose(models.TextChoices):
        PRIVACY_NOTICE = "privacy_notice", "Privacy notice"
        AUDIO_STORAGE = "audio_storage", "Storing raw audio recordings"
        RESEARCH = "research", "Using data for Pivot research"

    # Purposes a speaker must accept to register; the rest are optional.
    REQUIRED_FOR_SPEAKERS = frozenset({Purpose.PRIVACY_NOTICE})

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="consents")
    purpose = models.CharField(max_length=40, choices=Purpose.choices)
    # Version of this purpose's text the user agreed to (settings.CONSENT_VERSIONS).
    notice_version = models.CharField(max_length=20)
    granted_at = models.DateTimeField(default=timezone.now)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-granted_at"]
        constraints = [
            # A user accepts a given version of a given consent only once.
            models.UniqueConstraint(
                fields=["user", "purpose", "notice_version"],
                name="unique_consent_per_version",
            ),
        ]

    def __str__(self):
        return f"{self.user.email} {self.purpose} v{self.notice_version}"

    @staticmethod
    def current_version(purpose):
        """Current version of `purpose` from settings.CONSENT_VERSIONS."""
        try:
            return settings.CONSENT_VERSIONS[purpose]
        except KeyError:
            raise ImproperlyConfigured(
                f"settings.CONSENT_VERSIONS has no version for '{purpose}'.")

# Invite model as a next step later
