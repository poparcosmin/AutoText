"""
Management command to load shortcuts from fixture into Birou set.
Automatically finds the Birou set by name, regardless of ID.
"""

import json
import os

from django.core.management.base import BaseCommand
from django.utils import timezone

from textsync.models import Shortcut, ShortcutSet


class Command(BaseCommand):
    help = "Load shortcuts from birou_shortcuts.json into Birou set"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing shortcuts without confirmation",
        )

    def handle(self, *args, **options):
        # Find Birou set
        try:
            birou_set = ShortcutSet.objects.get(name="Birou")
            self.stdout.write(f"✅ Found 'birou' set with ID: {birou_set.id}")
        except ShortcutSet.DoesNotExist:
            self.stdout.write(self.style.ERROR("❌ Set 'birou' not found!"))
            self.stdout.write("   Create it first in Django admin")
            return

        # Load fixture
        fixture_path = os.path.join(
            os.path.dirname(__file__), "../../fixtures/birou_shortcuts.json"
        )

        if not os.path.exists(fixture_path):
            self.stdout.write(self.style.ERROR(f"❌ Fixture not found: {fixture_path}"))
            return

        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Delete existing shortcuts in birou set (optional)
        old_count = birou_set.shortcuts.count()
        if old_count > 0:
            if options["force"]:
                birou_set.shortcuts.all().delete()
                self.stdout.write(f"🗑️  Deleted {old_count} old shortcuts")
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️  Birou set already has {old_count} shortcuts. "
                        f"Use --force to delete them first."
                    )
                )
                return

        # Load shortcuts
        created = 0
        for item in data:
            if item["model"] != "textsync.Shortcut":
                continue

            fields = item["fields"]

            # Create or update shortcut, scoped to birou_set to avoid
            # MultipleObjectsReturned when the same key exists in multiple sets
            shortcut = birou_set.shortcuts.filter(key=fields["key"]).first()
            if shortcut is None:
                shortcut = Shortcut.objects.create(
                    key=fields["key"],
                    value=fields["value"],
                    html_value=fields["html_value"],
                    updated_at=timezone.now(),
                )
                shortcut.sets.add(birou_set)
                is_new = True
            else:
                shortcut.value = fields["value"]
                shortcut.html_value = fields["html_value"]
                shortcut.updated_at = timezone.now()
                shortcut.save(update_fields=["value", "html_value", "updated_at"])
                is_new = False

            if is_new:
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Loaded {created} new shortcuts into 'birou' set (ID {birou_set.id})"
            )
        )
        self.stdout.write(f"   Total shortcuts in birou: {birou_set.shortcuts.count()}")
