"""Session pages. For now only /demo/: the screen while a talk is going on
(empty for now). The session screen (session.html) gets its view later."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def talk_demo(request):
    """The screen while a talk is going on. Empty for now."""
    return render(request, "web/talk.html")
