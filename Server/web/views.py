from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_not_required, login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render, resolve_url
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.debug import sensitive_post_parameters

from accounts.models import User
from accounts.services import login_user

from .decorators import role_required


def page_not_found(request, exception):
    """Pivot's 404 page. Used for any unknown URL when DEBUG is off (see handler404)."""
    return render(request, "web/404.html", status=404)


@login_required  # also covered by LoginRequiredMiddleware; kept so the view says it
def home(request):
    """Placeholder home page; also where a login goes without ?next=."""
    return render(request, "web/home.html")


@login_not_required
@sensitive_post_parameters("password")
def login(request):
    """Trainer (admin) login with a session cookie. Speakers use the mobile app."""
    next_url = request.POST.get("next") or request.GET.get("next", "")

    if request.method != "POST":
        return render(request, "web/login.html", {"next": next_url})

    email = request.POST.get("email", "").strip()
    try:
        user = login_user(request, email, request.POST.get("password", ""),
                          role=User.Role.ADMIN)
    except ValidationError as e:
        # Keep the email so it doesn't have to be typed again; never the password.
        return render(request, "web/login.html", {
            "email": email,
            "error": e.messages[0],
            "next": next_url,
        })

    auth_login(request, user)
    if not request.POST.get("remember_me"):
        request.session.set_expiry(0)  # session ends when the browser closes

    # Only follow ?next= when it points back to this site.
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = resolve_url(settings.LOGIN_REDIRECT_URL)
    return redirect(next_url)
