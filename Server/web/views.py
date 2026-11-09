from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_not_required, login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_POST

from accounts import services
from accounts.emails import code_lifetime_minutes
from accounts.models import EmailCode, User

from .decorators import role_required
from .forms import CodeForm, EmailForm, LoginForm, NewPasswordForm

# Session keys for the logged-out flows.
# CODE_FLOW: who the code page is for and what a right code does:
#   {"purpose": EmailCode.Purpose value, "email": ...}, plus "next" and
#   "remember_me" from the login form when it's email verification
# RESET: the password reset token from a right reset code: {"uid": ..., "token": ...}
CODE_FLOW = "code_flow"
RESET = "password_reset"

SENT_NEW_CODE = "If that account needs a code, we sent a new one."


def page_not_found(request, exception):
    """Pivot's 404 page. Used for any unknown URL when DEBUG is off (see handler404)."""
    return render(request, "web/404.html", status=404)


@login_required  # also covered by LoginRequiredMiddleware; kept so the view says it
def home(request):
    """Placeholder home page; also where a login goes without ?next=."""
    return render(request, "web/home.html")


@login_not_required
@require_POST  # a GET logout could be triggered by any link, image or prefetch
def logout(request):
    """End the session and go to the login page. Sent by the logout button in the header."""
    auth_logout(request)
    return redirect(settings.LOGIN_URL)


@login_not_required
@sensitive_post_parameters("password")
def login(request):
    """Trainer (admin) login with a session cookie. Speakers use the mobile app.

    Right password but unverified email: a code is emailed and the code page
    opens; entering it logs the admin in.
    """
    next_url = request.POST.get("next") or request.GET.get("next", "")

    if request.method != "POST":
        return render(request, "web/login.html", {"next": next_url})

    email = request.POST.get("email", "").strip()
    remember_me = bool(request.POST.get("remember_me"))
    form = LoginForm(request.POST)
    if not form.is_valid():
        # Keep the email so it doesn't have to be typed again; never the password.
        return render(request, "web/login.html", {
            "email": email,
            "error": next(iter(form.errors.values()))[0],
            "next": next_url,
        })
    try:
        user = services.login_user(request, form.cleaned_data["email"],
                                   form.cleaned_data["password"], role=User.Role.ADMIN)
    except ValidationError as e:
        if getattr(e, "code", None) == services.EMAIL_NOT_VERIFIED:
            # Only reached with the right password. The code page reads who it's
            # for and where to go afterwards from the session.
            request.session[CODE_FLOW] = {
                "purpose": EmailCode.Purpose.VERIFY_EMAIL, "email": email,
                "next": next_url, "remember_me": remember_me,
            }
            return redirect("web:verify_code")
        # Keep the email so it doesn't have to be typed again; never the password.
        return render(request, "web/login.html", {
            "email": email,
            "error": e.messages[0],
            "next": next_url,
        })

    auth_login(request, user)
    if not remember_me:
        request.session.set_expiry(0)  # session ends when the browser closes

    # Only follow ?next= when it points back to this site.
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = resolve_url(settings.LOGIN_REDIRECT_URL)
    return redirect(next_url)


@login_not_required
def forgot_password(request):
    """Step 1 of the password reset: the email to send the reset code to."""
    form = EmailForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        # The same next step whether or not the email has an account.
        services.request_password_reset(email)
        request.session[CODE_FLOW] = {"purpose": EmailCode.Purpose.RESET_PASSWORD, "email": email}
        return redirect("web:verify_code")
    return render(request, "web/forgot_password.html", {
        "email": request.POST.get("email", ""),
        "error": form.errors.get("email", [""])[0],
    })


@login_not_required
def verify_code(request):
    """The one-time code from the email, for email verification (after a
    login) or password reset (after forgot password). Which one is in the
    session (CODE_FLOW); without it there is nothing to verify."""
    flow = request.session.get(CODE_FLOW)
    if not flow:
        return redirect("web:login")
    is_reset = flow["purpose"] == EmailCode.Purpose.RESET_PASSWORD

    error = ""
    if request.method == "POST":
        form = CodeForm({"code": "".join(request.POST.getlist("code"))})
        if not form.is_valid():
            error = form.errors["code"][0]
        elif is_reset:
            try:
                uid, token = services.verify_password_reset_code(
                    flow["email"], form.cleaned_data["code"])
            except ValidationError as e:
                error = e.messages[0]
            else:
                del request.session[CODE_FLOW]
                request.session[RESET] = {"uid": uid, "token": token}
                return redirect("web:password_reset")
        else:
            try:
                user = services.verify_email(flow["email"], form.cleaned_data["code"])
            except ValidationError as e:
                error = e.messages[0]
            else:
                del request.session[CODE_FLOW]
                if user.role != User.Role.ADMIN:
                    # Only admins log in here. Verified now, so the mobile app works.
                    messages.success(request, "Your email is verified. Log in in the Pivot app.")
                    return redirect("web:login")
                # The password was checked in this session before the code
                # page opened (login above), so the right code completes the login.
                auth_login(request, user)
                if not flow["remember_me"]:
                    request.session.set_expiry(0)
                next_url = flow["next"]
                if not url_has_allowed_host_and_scheme(
                    next_url, allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    next_url = resolve_url(settings.LOGIN_REDIRECT_URL)
                return redirect(next_url)

    return render(request, "web/verify_code.html", {
        "heading": "Reset your password" if is_reset else "Verify your email",
        "email": flow["email"],
        "digits": range(settings.EMAIL_CODE_LENGTH),
        "minutes": code_lifetime_minutes(),
        "error": error,
    })


@login_not_required
@require_POST
def resend_code(request):
    """"Send a new code" on the code page. Shows the same message whether or
    not anything was sent (cooldown, unknown email)."""
    flow = request.session.get(CODE_FLOW)
    if not flow:
        return redirect("web:login")
    if flow["purpose"] == EmailCode.Purpose.RESET_PASSWORD:
        services.request_password_reset(flow["email"])
    else:
        services.resend_verification_code(flow["email"])
    messages.info(request, SENT_NEW_CODE)
    return redirect("web:verify_code")


@login_not_required
@sensitive_post_parameters("new_password", "confirm_password")
def password_reset(request):
    """Step 3 of the password reset: choose a new password. Needs the reset
    token from a right reset code (step 2, verify_code)."""
    reset = request.session.get(RESET)
    if not reset:
        return redirect("web:forgot_password")

    form = NewPasswordForm(request.POST if request.method == "POST" else None)
    errors = {}
    if request.method == "POST":
        if form.is_valid():
            try:
                services.reset_password(
                    reset["uid"], reset["token"], form.cleaned_data["new_password"])
            except ValidationError as e:
                if not hasattr(e, "error_dict"):  # token expired or already used
                    del request.session[RESET]
                    messages.error(request, e.messages[0])
                    return redirect("web:forgot_password")
                errors = e.message_dict  # weak password; the token still works
            else:
                del request.session[RESET]
                messages.success(request, "Your password is changed. Log in with your new password.")
                return redirect("web:login")
        else:
            errors = form.errors

    return render(request, "web/password_reset.html", {
        "new_password_error": errors.get("new_password", [""])[0],
        "confirm_password_error": errors.get("confirm_password", [""])[0],
    })
