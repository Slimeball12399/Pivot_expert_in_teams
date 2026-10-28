import os

from django.contrib.auth.management.commands import createsuperuser
from django.core.management import CommandError

from accounts.models import Consent

YES = {"y", "yes"}
NO = {"n", "no"}
ENV_VAR = "DJANGO_SUPERUSER_ACCEPT_CONSENTS"


class Command(createsuperuser.Command):
    """Django's createsuperuser, plus a required yes/no for the consents.

    Interactive: asks "Do you accept ...? [yes/no]" before anything else.
    With --noinput: pass --accept-consents, or set DJANGO_SUPERUSER_ACCEPT_CONSENTS=yes.
    Answering no (or not accepting with --noinput) stops without creating anything.
    """

    help = "Create an admin, who must accept the privacy notice and all consents."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--accept-consents",
            action="store_true",
            help="Accept the privacy notice and all consents (needed with --noinput).",
        )

    def handle(self, *args, **options):
        if not self.consents_accepted(options):
            raise CommandError(
                "A superuser must accept the privacy notice and all consents. "
                "Nothing was created."
            )
        super().handle(*args, **options)

    def consents_accepted(self, options):
        if options["accept_consents"]:
            return True
        if os.environ.get(ENV_VAR, "").strip().lower() in YES | {"1", "true"}:
            return True
        if not options["interactive"]:
            return False
        return self.ask_yes_no()

    def ask_yes_no(self):
        consents = "\n".join(
            f"  - {purpose.label} (version {Consent.current_version(purpose.value)})"
            for purpose in Consent.Purpose
        )
        question = (
            f"Admins must accept all of these:\n{consents}\n"
            f"Do you accept? [yes/no]: "
        )
        while True:
            answer = input(question).strip().lower()
            if answer in YES:
                return True
            if answer in NO:
                return False
            self.stderr.write("Please answer yes or no.")
