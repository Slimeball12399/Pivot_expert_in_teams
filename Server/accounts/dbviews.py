"""Read-only models over database views.

Each class describes a view's columns so it can be queried with the normal
ORM (filter, order_by, Paginator). managed = False: Django never creates,
changes or drops these. The view's SQL lives in its migration; changing it
means a new migration with CREATE OR REPLACE VIEW (which can only add columns
at the end), or DROP VIEW and CREATE VIEW to change existing ones.

models.py imports this module, because Django only knows about models that
are imported when the app loads.
"""

from django.db import models
from django.utils import timezone

from .validators import age_on


class TrainerUser(models.Model):
    """A row of a trainer's user list: one of their speakers or one of their
    invites (view accounts_trainer_user, migration 0006_trainer_user_view).

    The view already applies the list's rules: only speakers with an active
    account; for invites only the most recent one per email, never accepted
    ones, and none for people who are already the trainer's speakers.
    state is "active" for speakers and the invite's status for invites
    (pending, declined, revoked or expired), worked out in SQL the same way
    as UserInvite.status, so change both together. Invite rows have no
    names, birth date or phone.

    Read-only: never save or delete these.
    """

    class Kind(models.TextChoices):
        SPEAKER = "speaker", "Speaker"
        INVITE = "invite", "Invite"

    # The speaker's SpeakerProfile id, or the invite's id (UUIDs don't collide).
    id = models.UUIDField(primary_key=True)
    trainer = models.ForeignKey(
        "accounts.AdminProfile", on_delete=models.DO_NOTHING, related_name="+")
    kind = models.CharField(max_length=10)
    email = models.EmailField()
    first_name = models.CharField(max_length=150, null=True)
    last_name = models.CharField(max_length=150, null=True)
    birth_date = models.DateField(null=True)
    phone = models.CharField(max_length=128, null=True)
    state = models.CharField(max_length=10)
    # When the speaker joined, or when the invite was sent.
    since = models.DateTimeField()
    expires = models.DateTimeField(null=True)

    class Meta:
        managed = False
        db_table = "accounts_trainer_user"
        ordering = ["-since"]

    def __str__(self):
        return f"{self.kind} {self.email} ({self.state})"

    @property
    def age(self):
        """Full years today, or None for invites."""
        if self.birth_date is None:
            return None
        return age_on(self.birth_date, timezone.now().date())
