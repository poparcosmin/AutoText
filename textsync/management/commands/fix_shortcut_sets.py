"""
Management command to link shortcuts to sets based on their intended set.
This fixes shortcuts that exist but aren't linked to any sets.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count

from textsync.models import Shortcut, ShortcutSet


class Command(BaseCommand):
    help = "Link unlinked shortcuts to appropriate sets"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )
        parser.add_argument(
            "--set-name",
            type=str,
            default="Birou",
            help="Set name to link shortcuts to (default: Birou)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        set_name = options["set_name"]

        self.stdout.write(f"\n🔍 Checking for shortcuts without sets...\n")

        # Find shortcuts that have no sets
        unlinked_shortcuts = Shortcut.objects.annotate(
            set_count=Count('sets')
        ).filter(set_count=0)

        unlinked_count = unlinked_shortcuts.count()

        if unlinked_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ All shortcuts are already linked to sets!"))
            return

        self.stdout.write(
            self.style.WARNING(f"⚠️  Found {unlinked_count} shortcuts not linked to any sets")
        )

        # Find target set
        try:
            target_set = ShortcutSet.objects.get(name=set_name)
            self.stdout.write(f"📁 Target set: '{target_set.name}' ({target_set.get_set_type_display()})\n")
        except ShortcutSet.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Set '{set_name}' not found!"))
            self.stdout.write("   Available sets:")
            for s in ShortcutSet.objects.all():
                self.stdout.write(f"   - {s.name} ({s.get_set_type_display()})")
            return

        # Show sample of shortcuts to be linked
        self.stdout.write("Sample shortcuts to be linked:")
        for sc in unlinked_shortcuts[:5]:
            owner_str = f" (owner: {sc.owner.username})" if sc.owner else " (no owner)"
            preview = sc.value[:40] if sc.value else (sc.html_value[:40] if sc.html_value else "")
            self.stdout.write(f"  - {sc.key} → {preview}...{owner_str}")

        if unlinked_count > 5:
            self.stdout.write(f"  ... and {unlinked_count - 5} more\n")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n🔍 DRY RUN - No changes made"))
            self.stdout.write(f"   Would link {unlinked_count} shortcuts to '{target_set.name}' set")
            return

        # Link shortcuts to set
        linked_count = 0
        for shortcut in unlinked_shortcuts:
            shortcut.sets.add(target_set)
            linked_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"\n✅ Successfully linked {linked_count} shortcuts to '{target_set.name}' set")
        )
        self.stdout.write(f"   Total shortcuts in {target_set.name}: {target_set.shortcuts.count()}")
