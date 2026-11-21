"""Forms for the web pages.

They only check the input's shape (an email, the right number of digits,
two matching passwords). The rules themselves (is the code right, is the
password strong enough, is the speaker yours) live in the services
(accounts.services, core.services), shared with the API.
"""

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError


class LoginForm(forms.Form):
    """Login: both fields filled in. Whether they're right is login_user()'s job."""

    email = forms.CharField(error_messages={"required": "Enter your email and password."})
    password = forms.CharField(
        strip=False, error_messages={"required": "Enter your email and password."})


class EmailForm(forms.Form):
    """Forgot password: the email to send the reset code to."""

    email = forms.EmailField(error_messages={
        "required": "Enter your email.",
        "invalid": "Enter a valid email address.",
    })


class CodeForm(forms.Form):
    """The one-time code from the email. The page has one box per digit; the
    view joins them: CodeForm({"code": "".join(request.POST.getlist("code"))})."""

    code = forms.CharField(strip=True, error_messages={"required": "Enter the code from the email."})

    def clean_code(self):
        code = "".join(self.cleaned_data["code"].split())  # "1234 5678" works too
        if len(code) != settings.EMAIL_CODE_LENGTH or not code.isdigit():
            raise ValidationError(
                f"Enter the {settings.EMAIL_CODE_LENGTH}-digit code from the email.")
        return code


class NewPasswordForm(forms.Form):
    """New password, typed twice. Strength is checked by reset_password()."""

    new_password = forms.CharField(
        strip=False, error_messages={"required": "Enter a new password."})
    confirm_password = forms.CharField(
        strip=False, error_messages={"required": "Enter the new password again."})

    def clean(self):
        cleaned = super().clean()
        new, confirm = cleaned.get("new_password"), cleaned.get("confirm_password")
        if new and confirm and new != confirm:
            self.add_error("confirm_password", "The passwords don't match.")
        return cleaned


class SessionCreateForm(forms.Form):
    """New session dialog: who the session is with, whether the live feedback
    also goes to their phone, and whether it starts now or later (then with a
    time, sent as UTC by new-session-dialog.js). Whether the speaker is yours
    and the time is in the future is create_session()'s job."""

    speaker_id = forms.UUIDField(error_messages={
        "required": "Choose a user.",
        "invalid": "Choose a user.",
    })
    stream_on_phone = forms.BooleanField(required=False)
    start = forms.ChoiceField(
        choices=[("now", "Now"), ("later", "Later")],
        error_messages={"required": "Choose now or later.", "invalid_choice": "Choose now or later."})
    scheduled_at = forms.DateTimeField(
        required=False, error_messages={"invalid": "Enter a valid date and time."})

    def clean(self):
        cleaned = super().clean()
        if (cleaned.get("start") == "later" and cleaned.get("scheduled_at") is None
                and "scheduled_at" not in self.errors):
            self.add_error("scheduled_at", "Choose a date and time.")
        return cleaned
