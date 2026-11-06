# accounts/signals.py  (connect in AccountsConfig.ready())
import logging
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

log = logging.getLogger("pivot.auth")

@receiver(user_logged_in)
def on_login(sender, request, user, **kw):
    log.info("login success user_id=%s channel=web", user.pk)

@receiver(user_logged_out)
def on_logout(sender, request, user, **kw):
    log.info("logout user_id=%s", getattr(user, "pk", None))

@receiver(user_login_failed)
def on_login_failed(sender, credentials, request, **kw):
    log.warning("login failed")   # never log `credentials`