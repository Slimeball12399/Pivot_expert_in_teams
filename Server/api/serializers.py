from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import Consent
from accounts.services import register_speaker

# Base serializers: each field is defined once here, and the input and output
# serializers below extend them. Change a field here and every serializer that
# uses it follows.


class UserBaseSerializer(serializers.Serializer):
    """Fields of the User that are both sent in and returned."""

    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField()


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


# Output


class RegisteredUserSerializer(UserBaseSerializer):
    """Response of POST /api/auth/register/."""

    id = serializers.UUIDField()
    role = serializers.CharField()


class HealthSerializer(serializers.Serializer):
    """Response of GET /api/health/."""

    status = serializers.CharField()
    database = serializers.ChoiceField(choices=["ok", "down"])
