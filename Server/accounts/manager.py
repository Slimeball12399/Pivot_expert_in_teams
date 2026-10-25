from django.contrib.auth.models import BaseUserManager
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction


class UserManager(BaseUserManager):
    use_in_migrations = True

    def build_user(self, email, password=None, **extra_fields):
        """Return a validated, unsaved user.

        Runs the AUTH_PASSWORD_VALIDATORS and every model field validator
        (full_clean), and raises one ValidationError with all errors found.
        """
        user = self.model(email=self.normalize_email(email), **extra_fields)

        errors = {}
        if password is not None:
            try:
                validate_password(password, user)
            except ValidationError as e:
                errors["password"] = e.messages
        user.set_password(password)  # None gives an unusable password

        try:
            user.full_clean()
        except ValidationError as e:
            e.update_error_dict(errors)

        if errors:
            raise ValidationError(errors)
        return user

    def create_user(self, email, password=None, **extra_fields):
        user = self.build_user(email, password, **extra_fields)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("role") != "admin":
            raise ValueError("Superuser must have role='admin'.")
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        # Imported here because models.py imports this file (avoids a circular import).
        from .models import AdminProfile

        # Create the user and its admin profile together, or neither.
        with transaction.atomic(using=self._db):
            user = self.create_user(email, password, **extra_fields)
            AdminProfile.objects.using(self._db).create(user=user)
        return user
