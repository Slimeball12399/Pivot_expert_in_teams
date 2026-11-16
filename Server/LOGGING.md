# Logging

## Getting a logger

Create one logger per module under the `pivot` namespace:

```python
import logging

log = logging.getLogger("pivot.<area>")   # e.g. pivot.auth, pivot.sessions, pivot.telemetry
```

Only loggers under `pivot.*` use our log level and handlers. Logging setup lives in `LOGGING` in `settings.py`, so you don't configure anything in your own module.

## Levels

| Level   | Use for                                                    |
|---------|------------------------------------------------------------|
| DEBUG   | Detail useful while developing (values, branches taken)    |
| INFO    | Normal events worth a record (login, session started)      |
| WARNING | Something unexpected but handled (failed login, retry)     |
| ERROR   | Something failed and the user is affected                  |

Use `log.exception("...")` inside an `except` block to include the stack trace.

The level is DEBUG in dev and INFO in production. Override it with the `LOG_LEVEL` environment variable.

## Rules

- **Log IDs, never personal data.** Write `user_id=42`, not an email, name or phone number (GDPR).
- **Never log secrets:** passwords, tokens, cookies, `Authorization` headers or Wi-Fi credentials. A redaction filter masks common ones, but it is only a safety net.
- **Don't log request bodies or form data** wholesale.
- **Use `%s` arguments, not f-strings:**
  ```python
  log.info("session started session_id=%s", session.pk)   # good
  log.info(f"session started session_id={session.pk}")    # avoid
  ```
  Formatting only happens if the line is actually written.
- **Use `key=value` pairs** in messages so lines are easy to search.

## Request IDs

Every request gets an ID, added to each log line in square brackets and returned in the `X-Request-ID` response header:

```
2026-11-02 21:15:03 INFO [3f9c1a...] pivot.auth: login success user_id=42 channel=web
```

To trace one request, search the logs for its ID. Code running outside a request (management commands, background services) shows `[-]`.

## Where logs go

- **Console:** the main output, and what `docker logs` shows.
- **File:** `logs/pivot.log`, rotated at 5 MB with 5 old files kept. Mount `logs/` as a volume in Docker so it survives restarts.

## Auth events

Login, logout and failed logins are logged automatically under `pivot.auth` by `accounts/signals.py`. Registration, email verification and password reset are logged in their views.

## Tests

`core/tests/test_logging.py` checks auth events, request IDs and redaction. Run it with:

```
python manage.py test core
```

When you add logging to a feature, check it with `self.assertLogs("pivot.<area>", "INFO")` and assert that no personal data appears in the output.
