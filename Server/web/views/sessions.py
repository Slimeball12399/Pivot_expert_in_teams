"""Session pages: the live/replay session screen (for now served at /demo/ with fake data)."""

import math
import random

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def demo(request):
    """Chart playground: the timeline chart component with fake stability data."""
    # Fake stability values: one every 0.5 s for a 60 s talk.
    points = []
    for step in range(121):
        seconds = step * 0.5
        points.append(
            [seconds, round(60 + 15 * math.sin(seconds / 5) + random.random() * 6)])

    stability_config = {
        "measure": "stability",
        "x": {"min": 0, "max": 60, "interval": 10},
        "y": {"min": 0, "max": 100, "interval": 20},
        "target": {"low": 50, "high": 60},
        "points": points,
        # later: peaks and minimums from between talks
        "markers": sorted(random.sample(points, 8)),
        "time": 35,
    }
    return render(request, "web/session.html", {
        "stability_config": stability_config,
        "stability_score": 64,  # fake; later from the stability analysis
    })
