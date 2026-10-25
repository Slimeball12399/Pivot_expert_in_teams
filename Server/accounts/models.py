from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
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

# Invite model as a next step later
