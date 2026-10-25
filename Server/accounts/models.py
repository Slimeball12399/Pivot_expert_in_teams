from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
from .manager import UserManager


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        SPEAKER = "speaker", "Speaker"

    username = None
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, blank=True)
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
    birth_date = models.DateField()
    height_cm = models.PositiveSmallIntegerField()
    improvement_goals = models.TextField(blank=True)

# Invite model as a next step later
