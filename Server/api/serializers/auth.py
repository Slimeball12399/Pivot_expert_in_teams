"""Logging in, tokens, email codes and password reset."""

from rest_framework import serializers


# Input


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


# Output


class TokenPairSerializer(serializers.Serializer):
    """Response of POST /api/auth/login/."""

    access = serializers.CharField()
    refresh = serializers.CharField()
