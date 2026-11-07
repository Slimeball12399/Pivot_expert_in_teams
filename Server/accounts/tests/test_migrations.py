from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class MigrationsTests(TestCase):
    def test_models_and_migrations_match(self):
        """Like `makemigrations --check`: a model change without a migration
        fails here, including the hand-written ones (0005_userinvite and the
        TrainerUser model in 0006_trainer_user_view)."""
        out = StringIO()
        try:
            call_command("makemigrations", check=True, dry_run=True, stdout=out, stderr=out)
        except SystemExit:
            self.fail(f"Models have changes without a migration:\n{out.getvalue()}")
