from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import Consent
from accounts.services.accounts import register_speaker, update_profile

# Base serializers: each field is defined once here, and the input and output
# serializers below extend them. Change a field here and every serializer that
# uses it follows.


class UserEditableSerializer(serializers.Serializer):
    """Fields of the User that users can change themselves (PATCH /api/me/)."""

    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField()


class UserBaseSerializer(UserEditableSerializer):
    """Fields of the User that are both sent in and returned."""

    email = serializers.EmailField()


class SpeakerProfileBaseSerializer(serializers.Serializer):
    """Fields of the SpeakerProfile."""

    birth_date = serializers.DateField()
    height_cm = serializers.IntegerField()
    improvement_goals = serializers.CharField(required=False, allow_blank=True, default="")


# Input


class SpeakerRegistrationSerializer(UserBaseSerializer, SpeakerProfileBaseSerializer):
    """Input for POST /api/auth/register/.

    Only parses types and checks fields are present. The real rules (age,
    height, Danish phone, password strength, unique email, consents) live in
    accounts and run inside register_speaker().
    """

    password = serializers.CharField(write_only=True, trim_whitespace=False)
    consents = serializers.MultipleChoiceField(choices=Consent.Purpose.choices)

    def create(self, validated_data):
        try:
            return register_speaker(**validated_data)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)

    def to_representation(self, user):
        """What the endpoint returns after registering."""
        return RegisteredUserSerializer(user).data


class EmailSerializer(serializers.Serializer):
    """Input for the endpoints that only need an email (resend, forgot password)."""

    email = serializers.EmailField()


class LoginSerializer(EmailSerializer):
    """Input for POST /api/auth/login/. The rules run in login_user()."""

    password = serializers.CharField(write_only=True, trim_whitespace=False)


class EmailCodeSerializer(EmailSerializer):
    """Input for the endpoints that check a code from an email."""

    # Spaces are allowed, so "1234 5678" copied from the email works.
    code = serializers.CharField(max_length=32)


class PasswordResetTokenSerializer(serializers.Serializer):
    """Proof of a right reset code: returned by POST /api/auth/password-reset/verify/
    and sent back to PUT /api/auth/password-reset/confirm/."""

    uid = serializers.CharField()
    reset_token = serializers.CharField()


class PasswordResetConfirmSerializer(PasswordResetTokenSerializer):
    """Input for PUT /api/auth/password-reset/confirm/. Password strength is
    checked inside reset_password(), with the AUTH_PASSWORD_VALIDATORS."""

    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class MeUpdateBaseSerializer(UserBaseSerializer):
    """Shared part of the PATCH /api/me/ input: the user's own details.

    Send only the fields to change. A new email also needs current_password;
    it becomes pending_email and is switched only after the code sent to it
    is entered (PUT /api/auth/verify-email/). Role can't be changed here;
    fields a serializer doesn't declare are ignored. The rules (Danish
    phone, age, height, password, email taken) run inside update_profile().
    """

    current_password = serializers.CharField(
        write_only=True, required=False, trim_whitespace=False)

    def update(self, user, validated_data):
        try:
            return update_profile(user, **validated_data)
        except DjangoValidationError as e:
            # Put profile field errors under "profile", like the request.
            errors = dict(e.message_dict)
            profile_errors = {
                name: errors.pop(name)
                for name in list(errors)
                if name in SpeakerProfileBaseSerializer._declared_fields
            }
            if profile_errors:
                errors["profile"] = profile_errors
            raise serializers.ValidationError(errors)


class AdminMeUpdateSerializer(MeUpdateBaseSerializer):
    """Input for PATCH /api/me/ for an admin: own details only.

    AdminProfile has nothing to edit, so there is no "profile" field;
    one sent anyway is ignored.
    """


class SpeakerMeUpdateSerializer(MeUpdateBaseSerializer):
    """Input for PATCH /api/me/ for a speaker: own details plus profile."""

    profile = SpeakerProfileBaseSerializer(required=False)


ME_UPDATE_SERIALIZERS = {"speaker": SpeakerMeUpdateSerializer, "admin": AdminMeUpdateSerializer}


# Output


class RegisteredUserSerializer(UserBaseSerializer):
    """Response of POST /api/auth/register/."""

    id = serializers.UUIDField()
    role = serializers.CharField()


class SpeakerProfileSerializer(SpeakerProfileBaseSerializer):
    """The "profile" part of GET /api/me/ for a speaker."""

    id = serializers.UUIDField()


class AdminProfileSerializer(serializers.Serializer):
    """The "profile" part of GET /api/me/ for an admin."""

    id = serializers.UUIDField()


class MeBaseSerializer(RegisteredUserSerializer):
    """Shared part of GET /api/me/: the user, plus a new email waiting for
    its code ("" when there is none)."""

    pending_email = serializers.CharField()


class SpeakerMeSerializer(MeBaseSerializer):
    """GET /api/me/ for a speaker: the user plus their speaker profile."""

    profile = SpeakerProfileSerializer(source="speaker_profile", allow_null=True)


class AdminMeSerializer(MeBaseSerializer):
    """GET /api/me/ for an admin: the user plus their admin profile."""

    profile = AdminProfileSerializer(source="admin_profile", allow_null=True)


ME_SERIALIZERS = {"speaker": SpeakerMeSerializer, "admin": AdminMeSerializer}


def me_data(user):
    """The GET /api/me/ body for `user`, shaped by their role."""
    return ME_SERIALIZERS[user.role](user).data


class TokenPairSerializer(serializers.Serializer):
    """Response of POST /api/auth/login/."""

    access = serializers.CharField()
    refresh = serializers.CharField()


class DetailSerializer(serializers.Serializer):
    """A plain message, e.g. "If that account exists, we sent a code."."""

    detail = serializers.CharField()


class CodedErrorSerializer(DetailSerializer):
    """Errors the app reacts to by `code`: email_not_verified, invalid_code,
    invalid_token. `detail` is a message that can be shown as it is."""

    code = serializers.CharField()


class HealthSerializer(serializers.Serializer):
    """Response of GET /api/health/."""

    status = serializers.CharField()
    database = serializers.ChoiceField(choices=["ok", "down"])
