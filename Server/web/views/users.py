"""The trainer's Users page and its actions: the users table (speakers and
invites, with search and filters), the invite dialog with its email
suggestions, and resending or cancelling an invite.

Sessions don't exist yet, so the session columns (sessions, last session,
speech and stability scores) stay empty for now.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.models import User, UserInvite
from accounts.services.invites import (
    HAS_TRAINER,
    USER_FILTERS,
    create_invite,
    get_users,
    revoke_invite,
    suggest_invite_emails,
)

from ..decorators import role_required

# The status values of the filter menu are the keys of USER_FILTERS.
STATUS_OPTIONS = [
    {"value": "all", "label": "All"},
    {"value": "active", "label": "Active"},
    {"value": "speakers", "label": "Speakers"},
    {"value": "invites", "label": "Invites"},
    {"value": "inactive", "label": "Inactive"},
]
DEFAULT_STATUS = "speakers"
# Most speakers invite_suggestions returns with own=1 (new session dialog).
OWN_SUGGEST_LIMIT = 5


def filter_groups(status):
    """The filter menu: groups of tags. "multiple": False means one tag per
    group. The group name is also the query parameter (?status=speakers)."""
    return [
        {"name": "status", "label": "Status", "multiple": False,
         "options": STATUS_OPTIONS, "selected": [status]},
    ]


@role_required(User.Role.ADMIN)
def user_list(request):
    """Users page: the trainer's numbers, search (?q=), filters (?status=,
    default "speakers", which also switches to the speaker columns), the
    users table and the invite dialog."""
    trainer = request.user.admin_profile
    status = request.GET.get("status", DEFAULT_STATUS)
    if status not in USER_FILTERS:
        status = DEFAULT_STATUS
    query = request.GET.get("q", "").strip()

    rows = list(get_users(trainer, status, query))
    for row in rows:
        # Until there are sessions: the speaker columns stay empty.
        row.sessions, row.last_session = 0, None
        row.speech = row.speech_change = row.stability = row.stability_change = None

    return render(request, "web/users.html", {
        "speaker_count": get_users(trainer, "speakers").count(),
        "sessions_this_week": 0,  # until there are sessions
        "status": status,
        "query": query,
        "filter_groups": filter_groups(status),
        "rows": rows,
        "layout": "speakers" if status == "speakers" else "mixed",
    })


@role_required(User.Role.ADMIN)
def invite_suggestions(request):
    """Emails for the invite dialog's dropdown, as JSON:
    {"suggestions": [{"email": ..., "already_linked": true, "already_invited": false}, ...]}.
    suggest_invite_emails() decides what is shown (from 3 characters, start
    of the email, at most 5): already_linked marks the trainer's own speakers,
    already_invited the emails with an open invite from them.

    With own=1 (the new session dialog): only the trainer's own speakers, from
    get_users() (name or email, any part; only active accounts), at most
    OWN_SUGGEST_LIMIT, as {"suggestions": [{"id": ..., "first_name": ...,
    "last_name": ..., "email": ...}]}; id is the speaker's user id, what
    create_session() takes. The dialog asks from 2 characters."""
    query = request.GET.get("q", "")
    trainer = request.user.admin_profile
    if request.GET.get("own") == "1":
        rows = get_users(trainer, "speakers", query)[:OWN_SUGGEST_LIMIT]
        return JsonResponse({"suggestions": [
            {"id": row.id, "first_name": row.first_name, "last_name": row.last_name, "email": row.email}
            for row in rows
        ]})
    return JsonResponse({
        "suggestions": suggest_invite_emails(trainer, query),
    })


@require_POST
@role_required(User.Role.ADMIN)
def invite_create(request):
    """Send invite, from the invite dialog (invite-dialog.js posts the form).

    201 {"message": ...}: sent; the message also waits as a toast for the
    reload that shows the new row. 400 {"errors": {"email": [...]}}: shown
    under the email field, and the dialog stays open. 409 {"confirm": ...}:
    the speaker already trains with another trainer; nothing is sent, the
    dialog shows the warning and the next Send posts replace_confirmed=1."""
    email = request.POST.get("email", "").strip()
    replace_confirmed = request.POST.get("replace_confirmed") == "1"
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"errors": {"email": ["Enter a valid email address."]}}, status=400)
    try:
        invite, _ = create_invite(request.user.admin_profile, email, replace_confirmed)
    except ValidationError as error:
        # A field error (from a dict) has no code.
        if getattr(error, "code", None) == HAS_TRAINER:
            return JsonResponse({"confirm": error.messages[0]}, status=409)
        return JsonResponse({"errors": error.message_dict}, status=400)
    message = f"Invite sent to {invite.email}."
    messages.success(request, message)
    return JsonResponse({"message": message}, status=201)


@require_POST
@role_required(User.Role.ADMIN)
def invite_resend(request, invite_id):
    """Resend from a table row: a new invite to the same email (create_invite
    closes the older open one). Back to the page it came from (?next=)."""
    trainer = request.user.admin_profile
    invite = UserInvite.objects.filter(pk=invite_id, invited_by=trainer).first()
    if invite is None:
        raise Http404
    try:
        # Confirmed already: the trainer saw any "already trains with" warning
        # when they first sent it.
        create_invite(trainer, invite.email, True)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(request, f"Invite sent again to {invite.email}.")
    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
        next_url = reverse("web:users")
    return redirect(next_url)


@require_POST
@role_required(User.Role.ADMIN)
def invite_cancel(request, invite_id):
    """Cancel from a table row (revoke_invite). Back to the page it came from (?next=)."""
    try:
        invite = revoke_invite(request.user, invite_id)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(request, f"Invite to {invite.email} cancelled.")
    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
        next_url = reverse("web:users")
    return redirect(next_url)
