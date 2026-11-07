# Test style

How the Server's tests are written, so new ones look like the existing ones.
Run them with `python manage.py test` (or one app or file, e.g.
`python manage.py test accounts.tests.test_invites`).

## Where tests go

- `<app>/tests/test_<area>.py`, one file per area: a service, an endpoint group, a page.
- **The rules live in `accounts/tests`**, tested directly on the services
  (`accounts.services.accounts`, `accounts.services.invites`), validators and models.
- **`api/tests` and `web/tests` test only the HTTP layer**: status codes, response
  shape, redirects, which template is used. Every class there has a docstring
  saying what it covers, and where the rules are tested when they live elsewhere:
  ```python
  class InviteEndpointTests(APITestCase):
      """The HTTP layer. The rules are tested in accounts/tests/test_invites.py."""
  ```
- A comment at the top of a file says what it covers and what is tested elsewhere,
  e.g. `# get_users() is tested in test_trainer_user_view.py, together with the view it reads.`

## Base classes

| Class | When |
|---|---|
| `TestCase` | Needs the database (most tests) |
| `SimpleTestCase` | No database (validators, email rendering, formatting) |
| `APITestCase` | API endpoints (`self.client` is DRF's `APIClient`) |

## File layout

In this order:

1. Imports in three groups separated by a blank line: standard library, third party
   (`django`, `rest_framework`, ...), then project (`accounts...`, `api...`), with
   relative imports (`from .utils import ...`) last.
2. One blank line, then module constants in `UPPER_CASE`:
   ```python
   PASSWORD = "Str0ng-test-pass!"
   NEW_PASSWORD = "An0ther-str0ng-pass!"
   URL = reverse("api:me")
   LOGIN_URL = reverse("api:login")
   LOGIN_FAILED = "Wrong email or password."   # messages the tests compare against
   ```
3. Small module-level helpers used only by this file, e.g. `make_user()`,
   `speaker_data(**overrides)`, `payload(**overrides)`. Helpers needed by more than
   one file go in `accounts/tests/utils.py` (see below).
4. The test classes.

## Classes and methods

- One class per unit, named `<Thing>Tests` (`RegisterSpeakerTests`,
  `PasswordResetEndpointTests`). A file can hold several classes when it tests
  several units (`test_emails.py`, `test_validators.py`, `test_invites.py`).
- **Few methods, each a whole topic.** A typical class has the happy path, the
  rejections and maybe a special case, not one method per assertion:
  `test_creates_...` / `test_full_reset`, `test_rejects` / `test_not_found`,
  `test_only_post_is_allowed`.
- Method names say what is checked in plain words: `test_resend_replaces_the_open_invite`,
  `test_public_endpoints_ignore_a_bad_token`.
- A docstring on a method only when the reason for the test isn't obvious from its
  name, e.g. why reading every column catches a broken database view.

## Sub-cases with `subTest`

Group related checks inside one method with `subTest`, so a failure names the
exact case and the other cases still run.

**Case tables** for the same check with different inputs: a list of tuples whose
first item is a readable label, looped over:

```python
cases = [
    ("too short", "mi", []),
    ("a domain finds nothing", "@gmail.com", []),
]
for label, query, expected in cases:
    with self.subTest(label, query=query):
        self.assertEqual(suggest_invite_emails(self.trainer, query), expected)
```

**Named steps** for a flow, each with a sentence that reads like a spec:

```python
with self.subTest("right password: not verified, and a code"):
    ...
with self.subTest("after the code, login works"):
    ...
```

When the cases must cover every option of something, assert that too, so adding
an option without a test fails:

```python
self.assertEqual(set(cases), set(USER_FILTERS))  # a new filter needs a case here
```

Sub-cases that change shared state go last, with a comment:

```python
# Last, because it changes the speaker.
with self.subTest("deactivated speakers are left out"):
```

## Assertion helpers

Repeated "this must fail in this way" checks become `assert...` methods on the
class, named like unittest's own: `assertRejected(field, **overrides)`,
`assertRaisesCode(code, func, *args)`, `assertLoginFails(...)`,
`assertNotFound(user, invite_id=None)`. They also check that nothing was saved
when that matters.

## Test data

- `setUpTestData` (class-level, created once) for data the tests only read.
  `setUp` when tests change it.
- Create data through the real services where possible (`register_speaker`,
  `User.objects.create_superuser`), so tests use the same rules as the app.
- Shared helpers in `accounts/tests/utils.py`:

  | Helper | Gives |
  |---|---|
  | `code_in(message)` | The one-time code from a sent email |
  | `frozen_now()`, `FIXED_NOW` | A fixed "today" for age checks |
  | `make_trainer(email)` | A trainer (admin) named Anne Trainer; returns their `AdminProfile` |
  | `make_speaker(email, trainer=None, **user_fields)` | A verified speaker named Mikkel Jensen, optionally linked to a trainer; `user_fields` e.g. `email_verified_at=None`, `is_active=False` |
  | `make_invite(trainer, email, days_old=0, **fields)` | An invite sent `days_old` days ago, expiring 7 days later (`days_old=10` is expired) |

- Example addresses use `@example.com`. The names stay the same across tests
  (Anne, Mikkel, Bo for a second trainer), so failures are easy to read.

## Time

- Everything is UTC. Use `django.utils.timezone.now()`, never `datetime.now()`
  without a time zone or `date.today()`.
- Move timestamps with an `update()` after creating, e.g. for `auto_now_add` fields
  (`make_invite` does this for `created_at`), or push them past a limit
  (`let_cooldown_pass()` in the verification tests).
- Use `frozen_now()` when a rule depends on today's date.

## Emails and `on_commit`

- Sent emails are in `django.core.mail.outbox`; check the recipients and subject
  (`[m.to for m in mail.outbox]`).
- Services send emails with `transaction.on_commit`, which never fires inside a
  `TestCase` by itself. Wrap the call to run it:
  ```python
  with self.captureOnCommitCallbacks(execute=True):
      invite, registered = create_invite(self.trainer, "new@example.com")
  ```

## API tests

- Log in with `self.client.force_authenticate(user)` (and `force_authenticate(None)`
  to log out). Real tokens only in tests about tokens themselves (`test_jwt_auth.py`).
- Compare status codes with DRF's constants and pass the body as the failure
  message, so a failure shows why:
  `self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)`
- Check the shape with the set of keys (`self.assertEqual(set(body), {"detail"})`)
  and coded errors by their code (`response.json()["code"] == "invite_not_found"`).
- Check who may call an endpoint: not logged in (401), wrong role (403), and that
  nothing changed afterwards.

## Mocks

Avoid them; test through the real database and services. Use `unittest.mock`
only for what a test can't produce for real:

| Case | Example |
|---|---|
| A failure, to prove the rollback | `mock.patch.object(SpeakerProfile, "save", side_effect=RuntimeError("db down"))` |
| Time passing inside a library | `mock.patch.object(default_token_generator, "_now", return_value=later)` |
| The environment of a command | `mock.patch.dict(os.environ, {"DJANGO_SUPERUSER_PASSWORD": PASSWORD})` |
| Typed input to a command | `mock.patch("builtins.input", side_effect=["maybe", "no"])` |

## Tests that guard against drift

- `accounts/tests/test_migrations.py` runs `makemigrations --check`: any model
  change without a migration fails.
- `accounts/tests/test_trainer_user_view.py` reads every column of the
  `accounts_trainer_user` database view and compares its invite states with
  `UserInvite.status`, so the hand-written SQL and the models can't silently drift
  apart.
