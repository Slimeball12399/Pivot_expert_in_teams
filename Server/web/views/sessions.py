"""Session pages. For now only the talk screen (talk.html, the screen while a
talk is going on), with no URL yet. The session screen (session.html) gets
its view later."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


# The voice graph on the talk screen: pace (the solid line) and pitch
# variation (the dashed one, second_points) as scores from -10 to +10, with the
# optimal band from -5 to +5. Live: it shows the minute the newest score is in
# and moves on to the next minute as the data gets there. No data until there
# is a live talk; talk.js writes demo data into it for now.
VOICE_CHART = {
    "measure": "speech",
    "live": True,
    "x": {"min": 0, "interval": 10, "window": 60},
    "y": {"min": -10, "max": 10, "interval": 5},
    "target": {"low": -5, "high": 5},
    "points": [],
    "second_points": [],
}


@login_required
def talk_demo(request):
    """The screen while a talk is going on. Demo data only for now."""
    return render(request, "web/talk.html", {"voice_config": VOICE_CHART})
