"""Trainer invites.

A trainer (admin) invites an email to train with them. The person registers
in the app with that email, verifies it, and accepts the invite there, which
links them to the trainer (SpeakerProfile.admin). A speaker has one trainer
at a time, so accepting replaces their current one. There is no secret
token: the verified email is the proof that an invite is theirs.
"""

from functools import partial

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import (
    Case,
    CharField,
    DateField,
    DateTimeField,
    Exists,
    F,
    OuterRef,
    Q,
    Value,
    When,
)
from django.utils import timezone

from .. import emails
from ..models import AdminProfile, SpeakerProfile, User, UserInvite

INVITE_NOT_FOUND = "invite_not_found"
INVITE_NOT_FOUND_MESSAGE = "This invitation doesn't exist or is no longer open."

# The filters of the trainer's user list (get_users).
USER_FILTERS = ("speakers", "invites", "active", "inactive", "all")

# suggest_invite_emails() looks at every speaker in Pivot, not only the
# trainer's own, so it only answers long enough prefixes, with a few emails.
SUGGEST_MIN_LENGTH = 3
SUGGEST_LIMIT = 5


@transaction.atomic
def create_invite(trainer, email) -> tuple[UserInvite, bool]:
    """Invite `email` to train with `trainer` (an AdminProfile) and email them.

    Inviting an email this trainer already invited is the resend: the older
    open invite is revoked, so only the newest one counts. Returns the invite
    and whether the email already has a Pivot account, for the trainer's
    confirmation ("they'll see it in the app" or "they'll get an email").

    Raises ValidationError({"email": [...]}) when the email is already one of
    the trainer's speakers, or belongs to a trainer account.
    """
    email = User.objects.normalize_email(email.strip())
    existing = User.objects.filter(email__iexact=email, is_active=True).first()
    if existing is not None and existing.role != User.Role.SPEAKER:
        raise ValidationError({"email": ["This email belongs to a trainer account."]})
    if existing is not None and existing.speaker_profile.admin_id == trainer.pk:
        raise ValidationError({"email": ["This person is already one of your users."]})

    now = timezone.now()
    UserInvite.objects.pending().filter(
        invited_by=trainer, email__iexact=email).update(revoked_at=now)
    invite = UserInvite.objects.create(
        invited_by=trainer, email=email, expires_at=now + settings.INVITE_LIFETIME)
    # After the commit, so a failed invite sends nothing. robust: a failed
    # email doesn't undo the invite; the trainer can send it again.
    transaction.on_commit(partial(emails.send_invite_email, invite), robust=True)
    return invite, existing is not None


def revoke_invite(user, invite_id) -> UserInvite:
    """Close an open invite. The trainer who sent it cancels it (revoked_at);
    the speaker it was sent to declines it (declined_at), which needs their
    email to be verified, like accepting.

    Anyone else, and an invite that is no longer open, gets the same
    ValidationError(code=INVITE_NOT_FOUND), so nobody learns which invites exist.
    """
    invite = (UserInvite.objects.pending().select_related("invited_by")
              .filter(pk=invite_id).first())
    if (invite is not None and user.role == User.Role.ADMIN
            and invite.invited_by.user_id == user.pk):
        invite.revoked_at = timezone.now()
        invite.save(update_fields=["revoked_at"])
    elif (invite is not None and user.role == User.Role.SPEAKER
          and user.email_verified_at is not None
          and invite.email.lower() == user.email.lower()):
        invite.declined_at = timezone.now()
        invite.save(update_fields=["declined_at"])
    else:
        raise ValidationError(INVITE_NOT_FOUND_MESSAGE, code=INVITE_NOT_FOUND)
    return invite


@transaction.atomic
def accept_invite(user, invite_id) -> AdminProfile | None:
    """Accept an open invite sent to the speaker's verified email.

    The speaker moves to the inviting trainer, replacing their current one,
    the invite is marked accepted, and their other open invites are revoked,
    so accepting another one later can't move them again by accident.
    Returns the previous trainer (an AdminProfile) when it changed, else None.

    Raises ValidationError(code=INVITE_NOT_FOUND) like revoke_invite().
    """
    invite = UserInvite.objects.pending().select_for_update().filter(pk=invite_id).first()
    if (invite is None or user.role != User.Role.SPEAKER
            or user.email_verified_at is None
            or invite.email.lower() != user.email.lower()):
        raise ValidationError(INVITE_NOT_FOUND_MESSAGE, code=INVITE_NOT_FOUND)

    now = timezone.now()
    profile = SpeakerProfile.objects.select_for_update().get(user=user)
    previous_admin_id = profile.admin_id
    profile.admin_id = invite.invited_by_id
    profile.save(update_fields=["admin"])
    invite.accepted_at, invite.accepted_by = now, user
    invite.save(update_fields=["accepted_at", "accepted_by"])
    UserInvite.objects.pending().filter(
        email__iexact=user.email).exclude(pk=invite.pk).update(revoked_at=now)

    if previous_admin_id in (None, invite.invited_by_id):
        return None
    return AdminProfile.objects.get(pk=previous_admin_id)


def pending_invites_for(user):
    """Open invites sent to the user's verified email, newest first, with the
    trainer loaded: the invitations screen in the app. Empty for trainers and
    for unverified accounts, since only a verified email proves they're theirs."""
    if user.role != User.Role.SPEAKER or user.email_verified_at is None:
        return UserInvite.objects.none()
    return (UserInvite.objects.pending().filter(email__iexact=user.email)
            .select_related("invited_by__user"))


def get_users(trainer, status="speakers", query=""):
    """The trainer's user list: their speakers and/or their invites as one
    queryset of rows with the same columns, so the view can page through
    them together (Paginator works on it directly).

    status, one of USER_FILTERS:
      speakers  their speakers (the default)
      invites   open invites
      active    speakers and open invites
      inactive  revoked, declined and expired invites
      all       speakers and every invite that wasn't accepted

    Each email shows only its most recent invite, and none at all once the
    person is one of the trainer's speakers. Deactivated accounts are left
    out. `query` searches the name and email (any part).

    Rows are dicts, newest first, with the keys: row_id, kind ("speaker" or
    "invite"), email_address, first_name, last_name, born_on, phone, state,
    since and expires. Speaker rows carry the profile; invite rows only the
    email, state and dates. Raises ValueError for an unknown status.
    """
    if status not in USER_FILTERS:
        raise ValueError(f"Unknown status: {status}")
    query = query.strip()
    now = timezone.now()
    # Both parts annotate the same names in the same order, so union() lines
    # the columns up; only annotations are selected, no model fields.
    columns = ["row_id", "kind", "email_address", "first_name", "last_name",
               "born_on", "phone", "state", "since", "expires"]
    parts = []

    if status in ("speakers", "active", "all"):
        speakers = SpeakerProfile.objects.filter(admin=trainer, user__is_active=True)
        if query:
            speakers = speakers.filter(
                Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(user__email__icontains=query))
        parts.append(speakers.annotate(
            row_id=F("pk"),
            kind=Value("speaker"),
            email_address=F("user__email"),
            first_name=F("user__first_name"),
            last_name=F("user__last_name"),
            born_on=F("birth_date"),
            phone=F("user__phone_number"),
            state=Value("active"),
            since=F("user__date_joined"),
            expires=Value(None, output_field=DateTimeField()),
        ).values(*columns))

    if status != "speakers":
        invites = UserInvite.objects.filter(invited_by=trainer).filter(
            # Only the most recent invite for each email...
            ~Exists(UserInvite.objects.filter(
                invited_by=trainer, email__iexact=OuterRef("email"),
                created_at__gt=OuterRef("created_at"))),
            # ...and none for people who are already this trainer's speakers.
            ~Exists(SpeakerProfile.objects.filter(
                admin=trainer, user__email__iexact=OuterRef("email"))),
        )
        if status in ("invites", "active"):
            invites = invites.pending()
        elif status == "inactive":
            invites = invites.inactive()
        else:  # all
            invites = invites.filter(accepted_at__isnull=True)
        if query:
            invites = invites.filter(email__icontains=query)
        parts.append(invites.annotate(
            row_id=F("pk"),
            kind=Value("invite"),
            email_address=F("email"),
            first_name=Value(None, output_field=CharField()),
            last_name=Value(None, output_field=CharField()),
            born_on=Value(None, output_field=DateField()),
            phone=Value(None, output_field=CharField()),
            # UserInvite.status in SQL (accepted invites are never listed).
            state=Case(
                When(declined_at__isnull=False, then=Value(UserInvite.Status.DECLINED)),
                When(revoked_at__isnull=False, then=Value(UserInvite.Status.REVOKED)),
                When(expires_at__lte=now, then=Value(UserInvite.Status.EXPIRED)),
                default=Value(UserInvite.Status.PENDING),
            ),
            since=F("created_at"),
            expires=F("expires_at"),
        ).values(*columns))

    rows = parts[0].union(*parts[1:], all=True) if len(parts) > 1 else parts[0]
    return rows.order_by("-since")


def suggest_invite_emails(trainer, query) -> list[dict]:
    """Registered speaker emails starting with `query`, for the invite form,
    so the trainer sees an email is typed right and already in Pivot.

    It looks at every speaker in Pivot, not only the trainer's own, so it
    stays small on purpose: it matches from the start of the email (a domain
    like "@gmail.com" finds nothing), answers only from SUGGEST_MIN_LENGTH
    characters, and returns at most SUGGEST_LIMIT emails and nothing else
    about the person. already_linked marks the trainer's own speakers.
    """
    query = query.strip()
    if len(query) < SUGGEST_MIN_LENGTH:
        return []
    rows = (User.objects
            .filter(role=User.Role.SPEAKER, is_active=True,
                    email_verified_at__isnull=False, email__istartswith=query)
            .order_by("email")
            .values_list("email", "speaker_profile__admin")[:SUGGEST_LIMIT])
    return [{"email": email, "already_linked": admin_id == trainer.pk}
            for email, admin_id in rows]
