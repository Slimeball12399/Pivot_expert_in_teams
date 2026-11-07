"""The trainer's Users page, and the invite dialog's email suggestions.

The page is UI only for now: the table shows sample rows, and the search,
the row actions and Send invite are not connected to the invite services
yet. The suggestions are real (invite_suggestions)."""

from datetime import timedelta

from django.http import JsonResponse
from django.shortcuts import render
from django.utils.timezone import now

from accounts.models import User
from accounts.services.invites import USER_FILTERS, get_users, suggest_invite_emails

from ..decorators import role_required


# The status values of the filter menu are the keys of USER_FILTERS.
STATUS_OPTIONS = [
    {"value": "all", "label": "All"},
    {"value": "active", "label": "Active"},
    {"value": "speakers", "label": "Speakers"},
    {"value": "invites", "label": "Invites"},
    {"value": "inactive", "label": "Inactive"},
]


def filter_groups(status):
    """The filter menu: groups of tags. "multiple": False means one tag per
    group. The group name is also the query parameter (?status=speakers)."""
    return [
        {"name": "status", "label": "Status", "multiple": False,
         "options": STATUS_OPTIONS, "selected": [status]},
    ]


def sample_rows():
    """Placeholder rows, shaped like accounts.dbviews.TrainerUser (kind,
    state, names, email, since, expires), one invite of each state. Speakers
    also have the session numbers the table will show once sessions exist
    (sessions, last_session, speech and stability scores out of 100, and how
    much each score changed over the last month)."""
    today = now()
    speaker = {"kind": "speaker", "state": "active", "expires": None}
    invite = {"kind": "invite", "first_name": "", "last_name": ""}
    return [
        {**speaker, "first_name": "Anna", "last_name": "Hansen",
         "email": "anna.hansen@example.com", "since": today - timedelta(days=30),
         "sessions": 12, "last_session": today - timedelta(days=2),
         "speech": 78, "speech_change": 14, "stability": 64, "stability_change": -3},
        {**invite, "state": "pending", "email": "mette.poulsen@example.com",
         "since": today - timedelta(days=2), "expires": today + timedelta(days=5)},
        {**speaker, "first_name": "Sofie", "last_name": "Madsen",
         "email": "sofie.madsen@example.com", "since": today - timedelta(days=21),
         "sessions": 5, "last_session": today - timedelta(days=6),
         "speech": 61, "speech_change": -23, "stability": 82, "stability_change": 0},
        {**speaker, "first_name": "Mikkel", "last_name": "Jensen",
         "email": "mikkel.jensen@example.com", "since": today - timedelta(days=12),
         "sessions": 0, "last_session": None,
         "speech": None, "speech_change": None, "stability": None, "stability_change": None},
        {**invite, "state": "expired", "email": "anders.nielsen@example.com",
         "since": today - timedelta(days=10), "expires": today - timedelta(days=3)},
        {**invite, "state": "declined", "email": "andrea.larsen@example.com",
         "since": today - timedelta(days=4), "expires": today + timedelta(days=3)},
        {**invite, "state": "revoked", "email": "lars.berg@example.com",
         "since": today - timedelta(days=6), "expires": today + timedelta(days=1)},
    ]


@role_required(User.Role.ADMIN)
def user_list(request):
    """Users page: the trainer's numbers, search, filters, the users table
    and the invite dialog. ?status= (default "speakers") picks the rows (sample rows for now,
    narrowed the way USER_FILTERS will narrow get_users()) and, for
    "speakers", the speaker columns (sessions and scores)."""
    trainer = request.user.admin_profile
    status = request.GET.get("status", "speakers")
    if status not in USER_FILTERS:
        status = "speakers"
    states = USER_FILTERS[status]
    rows = [row for row in sample_rows() if states is None or row["state"] in states]
    return render(request, "web/users.html", {
        "speaker_count": get_users(trainer, "speakers").count(),
        "sessions_this_week": 0,  # placeholder until there are sessions
        "query": request.GET.get("q", "").strip(),
        "filter_groups": filter_groups(status),
        "rows": rows,
        "layout": "speakers" if status == "speakers" else "mixed",
    })


@role_required(User.Role.ADMIN)
def invite_suggestions(request):
    """Emails for the invite dialog's dropdown, as JSON:
    {"suggestions": [{"email": ..., "already_linked": true}, ...]}.
    suggest_invite_emails() decides what is shown (from 3 characters, start
    of the email, at most 5); already_linked marks the trainer's own speakers."""
    query = request.GET.get("q", "")
    return JsonResponse({
        "suggestions": suggest_invite_emails(request.user.admin_profile, query),
    })
