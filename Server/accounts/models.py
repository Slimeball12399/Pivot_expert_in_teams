from functools import partial

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models, transaction
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField

from core.models import UUIDModel

from .manager import UserManager
from .validators import (
    MAX_HEIGHT_CM,
    MIN_HEIGHT_CM,
    validate_danish_phone_number,
    validate_min_age,
)


# AbstractUser first, so its Meta (verbose names) is the one inherited.
class User(AbstractUser, UUIDModel):
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

    email_verified_at = models.DateTimeField(null=True, blank=True)
    # A new email the user asked for (PATCH /api/me/). It replaces `email`
    # only once the code sent to it is entered, so a typo can't lock anyone out.
    pending_email = models.EmailField(blank=True, default="")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    def __str__(self):
        return f"{self.email} {self.role}"

    def save(self, *args, **kwargs):
        """Saves the user, with these rules wherever the email or password
        changes (admin panel, password reset, shell):

        - Email changed: it counts as unverified again (unless email_verified_at
          was changed in the same save, e.g. an admin fixing a typo), every
          open code of the user is invalidated (they went to the old address),
          and a new verification code goes to the new address.
        - Email or password changed: every refresh token is blacklisted, so
          the mobile app is logged out on all devices. Web sessions already
          end on a password change (Django checks the password hash).
        """
        update_fields = kwargs.get("update_fields")
        old = None
        if not self._state.adding and (
                update_fields is None or {"email", "password"} & set(update_fields)):
            old = User.objects.filter(pk=self.pk).values(
                "email", "password", "email_verified_at").first()
        email_changed = old is not None and old["email"] != self.email
        password_changed = old is not None and old["password"] != self.password

        if email_changed and self.email_verified_at == old["email_verified_at"]:
            self.email_verified_at = None
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "email_verified_at"}

        super().save(*args, **kwargs)

        if email_changed:
            # Imported here: services imports this module.
            from .services import send_verification_code
            self.email_codes.filter(used_at__isnull=True, invalidated_at__isnull=True).update(
                invalidated_at=timezone.now())
            transaction.on_commit(partial(send_verification_code, self), robust=True)
        if email_changed or password_changed:
            from rest_framework_simplejwt.token_blacklist.models import (
                BlacklistedToken,
                OutstandingToken,
            )
            for refresh in OutstandingToken.objects.filter(user=self, blacklistedtoken__isnull=True):
                BlacklistedToken.objects.get_or_create(token=refresh)


class AdminProfile(UUIDModel):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="admin_profile")


class SpeakerProfile(UUIDModel):
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


class Consent(UUIDModel):
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

class EmailCode(UUIDModel):
    """A one-time code emailed to a user (email verification, password reset).

    Only a hash of the code is stored. Codes are never deleted while the user
    exists, so there is a record of what was sent and what happened to it.
    Whether a code still works is worked out from the timestamps (see
    is_usable), never stored as a flag that could go stale.
    """

    class Purpose(models.TextChoices):
        VERIFY_EMAIL = "verify_email", "Verify email"
        RESET_PASSWORD = "reset_password", "Reset password"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="email_codes")
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    # Entered correctly.
    used_at = models.DateTimeField(null=True, blank=True)
    # Replaced by a newer code, or cancelled.
    invalidated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "purpose"])]

    def __str__(self):
        return f"{self.get_purpose_display()} code for {self.user.email}"

    @property
    def is_usable(self):
        """Not used, not replaced, not expired, and not out of attempts."""
        return (
            self.used_at is None
            and self.invalidated_at is None
            and self.expires_at > timezone.now()
            and self.attempts < settings.EMAIL_CODE_MAX_ATTEMPTS
        )