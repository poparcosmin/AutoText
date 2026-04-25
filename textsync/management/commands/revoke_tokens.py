"""Revoke all ExpiringToken records for one or more users.

Use case: laptop / device lost. Run this from the OVH shell when a user
reports a stolen device — they'll be prompted to log in again on the
next sync from any other browser, and the lost device's cached token
becomes useless.

Examples:
    uv run python manage.py revoke_tokens cosmin
    uv run python manage.py revoke_tokens cosmin bogdan aura
    uv run python manage.py revoke_tokens --all   # nuclear: every user
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from textsync.models import ExpiringToken


class Command(BaseCommand):
    help = "Revoke ExpiringToken(s) for the specified users (or --all)."

    def add_arguments(self, parser):
        parser.add_argument(
            "usernames",
            nargs="*",
            help="One or more usernames whose tokens should be revoked.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            dest="revoke_all",
            help="Revoke tokens for ALL users (use with care).",
        )

    def handle(self, *args, **options):
        revoke_all = options["revoke_all"]
        usernames = options["usernames"]

        if not revoke_all and not usernames:
            raise CommandError(
                "Specify usernames or pass --all. Nothing was revoked."
            )

        if revoke_all:
            qs = ExpiringToken.objects.all()
            label = "all users"
        else:
            users = User.objects.filter(username__in=usernames)
            found = set(users.values_list("username", flat=True))
            missing = set(usernames) - found
            if missing:
                self.stderr.write(
                    self.style.WARNING(
                        f"Skipping unknown usernames: {', '.join(sorted(missing))}"
                    )
                )
            if not users.exists():
                raise CommandError("No matching users found.")
            qs = ExpiringToken.objects.filter(user__in=users)
            label = ", ".join(sorted(found))

        count = qs.count()
        if count == 0:
            self.stdout.write(self.style.WARNING(
                f"No active tokens for {label}."
            ))
            return

        qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f"Revoked {count} token(s) for {label}."
        ))
