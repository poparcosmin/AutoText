"""Create the 'birou-curators' Django group and add the requested users.

This group governs who can edit shortcuts in `general` (Birou) sets via
the API. Superusers are always exempt from the group check. Run once
after deploy.

Examples:
    uv run python manage.py setup_birou_curators            # adds cosmin (default)
    uv run python manage.py setup_birou_curators cosmin bogdan
    uv run python manage.py setup_birou_curators --list     # show current members
"""
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand

GROUP_NAME = "birou-curators"


class Command(BaseCommand):
    help = (
        "Idempotently create the 'birou-curators' group and add the named users. "
        "Default users: cosmin."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "usernames",
            nargs="*",
            default=["cosmin"],
            help="Usernames to add to the group (default: cosmin).",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            dest="list_only",
            help="Just print the current members and exit.",
        )

    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(name=GROUP_NAME)
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created group '{GROUP_NAME}'."))
        else:
            self.stdout.write(f"Group '{GROUP_NAME}' already exists.")

        if options["list_only"]:
            members = group.user_set.values_list("username", flat=True)
            if members:
                self.stdout.write("Members: " + ", ".join(sorted(members)))
            else:
                self.stdout.write("Members: (none)")
            return

        usernames = options["usernames"] or ["cosmin"]
        added, missing = [], []
        for username in usernames:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                missing.append(username)
                continue
            if not user.groups.filter(pk=group.pk).exists():
                user.groups.add(group)
                added.append(username)

        if added:
            self.stdout.write(self.style.SUCCESS(
                f"Added to '{GROUP_NAME}': {', '.join(added)}"
            ))
        else:
            self.stdout.write("No new members added (all targets were already members).")

        if missing:
            self.stdout.write(self.style.WARNING(
                f"Skipped (no such user): {', '.join(missing)}"
            ))
