# Speaker rows of the trainer's user list carry the speaker's user id instead
# of their SpeakerProfile id, as everywhere else in the app. The old view is
# dropped and the new one created. Written by hand, like 0006.

from django.db import migrations

VIEW_WITH_USER_ID = """
DROP VIEW IF EXISTS accounts_trainer_user;
CREATE VIEW accounts_trainer_user AS
SELECT
    u.id                    AS id,
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

VIEW_WITH_PROFILE_ID = """
DROP VIEW IF EXISTS accounts_trainer_user;
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
        ("accounts", "0006_trainer_user_view"),
    ]

    operations = [
        migrations.RunSQL(sql=VIEW_WITH_USER_ID, reverse_sql=VIEW_WITH_PROFILE_ID),
    ]
