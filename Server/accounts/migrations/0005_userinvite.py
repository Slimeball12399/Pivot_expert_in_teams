# Written by hand to match what makemigrations generates. Check with:
#   python manage.py makemigrations --check --dry-run

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_user_pending_email"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserInvite",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("email", models.EmailField(max_length=254)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("declined_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("accepted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="accepted_invites", to=settings.AUTH_USER_MODEL)),
                ("invited_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="invites", to="accounts.adminprofile")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["invited_by", "email"], name="accounts_us_invited_f901d4_idx")],
            },
        ),
    ]
