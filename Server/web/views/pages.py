"""General pages: the home page, the users page and the 404 page."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def page_not_found(request, exception):
    """Pivot's 404 page. Used for any unknown URL when DEBUG is off (see handler404)."""
    return render(request, "web/404.html", status=404)


@login_required  # also covered by LoginRequiredMiddleware; kept so the view says it
def home(request):
    """Placeholder home page; also where a login goes without ?next=."""
    return render(request, "web/home.html")



@login_required
def users(request):
    """Placeholder users page."""
    return render(request, "web/users.html")
