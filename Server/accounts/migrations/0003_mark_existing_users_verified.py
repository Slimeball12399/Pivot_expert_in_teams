from django.db import migrations
from django.utils import timezone


def mark_existing_users_verified(apps, schema_editor):
    """Accounts made before email verification existed count as verified,
    so the new login check doesn't lock them out."""
    User = apps.get_model("accounts", "User")
    User.objects.filter(email_verified_at__isnull=True).update(email_verified_at=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_user_email_verified_at_emailcode"),
    ]

    # Going back leaves the timestamps alone: unmarking them would lock users out.
    operations = [
        migrations.RunPython(mark_existing_users_verified, migrations.RunPython.noop),
    ]
