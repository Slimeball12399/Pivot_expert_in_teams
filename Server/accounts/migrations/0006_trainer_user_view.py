# The trainer's user list as a database view, read through the unmanaged
# model accounts.dbviews.TrainerUser. Written by hand (makemigrations doesn't
# write views). To change the view, add a new migration; don't edit this one.

import django.db.models.deletion
from django.db import migrations, models

# One row per speaker or invite, with the same columns. now() is evaluated
# when the view is queried, so "expired" is always current. The invite rules
# (latest per email first, then drop accepted ones and existing speakers)
# must stay in that order: if the latest invite was accepted, an older one
# must not show up instead.
CREATE_VIEW = """
CREATE VIEW accounts_trainer_user AS
SELECT
    sp.id                   AS id,
    sp.admin_id             AS trainer_id,
    'speaker'::varchar(10)  AS kind,
    u.email                 AS email,
    u.first_name            AS first_name,
    u.last_name             AS last_name,
    sp.birth_date           AS birth_date,
    u.phone_number          AS phone,
    'active'::varchar(10)   AS state,
    u.date_joined           AS since,
    NULL::timestamptz       AS expires
FROM accounts_speakerprofile sp
JOIN accounts_user u ON u.id = sp.user_id
WHERE sp.admin_id IS NOT NULL
  AND u.is_active

UNION ALL

SELECT
    i.id,
    i.invited_by_id,
    'invite'::varchar(10),
    i.email,
    NULL::varchar,
    NULL::varchar,
    NULL::date,
    NULL::varchar,
    (CASE
        WHEN i.declined_at IS NOT NULL THEN 'declined'
        WHEN i.revoked_at IS NOT NULL THEN 'revoked'
        WHEN i.expires_at <= now() THEN 'expired'
        ELSE 'pending'
    END)::varchar(10),
    i.created_at,
    i.expires_at
FROM (
    -- Only the most recent invite per trainer and email.
    SELECT DISTINCT ON (invited_by_id, lower(email)) *
    FROM accounts_userinvite
    ORDER BY invited_by_id, lower(email), created_at DESC
) AS i
WHERE i.accepted_at IS NULL
  -- None for people who are already this trainer's speakers.
  AND NOT EXISTS (
      SELECT 1
      FROM accounts_speakerprofile sp2
      JOIN accounts_user u2 ON u2.id = sp2.user_id
      WHERE sp2.admin_id = i.invited_by_id
        AND lower(u2.email) = lower(i.email)
  );
"""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_userinvite"),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE_VIEW, reverse_sql="DROP VIEW IF EXISTS accounts_trainer_user;"),
        # State only: managed=False, so this creates nothing in the database.
        migrations.CreateModel(
            name="TrainerUser",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False)),
                ("kind", models.CharField(max_length=10)),
                ("email", models.EmailField(max_length=254)),
                ("first_name", models.CharField(max_length=150, null=True)),
                ("last_name", models.CharField(max_length=150, null=True)),
                ("birth_date", models.DateField(null=True)),
                ("phone", models.CharField(max_length=128, null=True)),
                ("state", models.CharField(max_length=10)),
                ("since", models.DateTimeField()),
                ("expires", models.DateTimeField(null=True)),
                ("trainer", models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name="+", to="accounts.adminprofile")),
            ],
            options={
                "db_table": "accounts_trainer_user",
                "ordering": ["-since"],
                "managed": False,
            },
        ),
    ]
