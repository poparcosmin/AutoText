"""
Management command to fix NULL owners for ShortcutSets and Shortcuts.
Assigns a default owner to all objects without owner.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from textsync.models import Shortcut, ShortcutSet


class Command(BaseCommand):
    help = "Fix NULL owners by assigning a default owner"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
        )
        parser.add_argument(
            "--owner",
            type=str,
            default="admin",
            help="Username to assign as owner (default: admin)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        owner_username = options["owner"]

        self.stdout.write("\n🔍 Checking for objects without owners...\n")

        # Find owner user
        try:
            owner = User.objects.get(username=owner_username)
            self.stdout.write(f"✅ Using owner: {owner.username}\n")
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"❌ User '{owner_username}' not found!")
            )
            self.stdout.write("   Available users:")
            for u in User.objects.all():
                self.stdout.write(f"   - {u.username}")
            return

        # Fix ShortcutSets
        sets_without_owner = ShortcutSet.objects.filter(owner__isnull=True)
        sets_count = sets_without_owner.count()

        if sets_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  Found {sets_count} ShortcutSet(s) without owner:"
                )
            )
            for s in sets_without_owner:
                self.stdout.write(f"  - {s.name} ({s.get_set_type_display()})")

            if not dry_run:
                updated = sets_without_owner.update(owner=owner)
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Updated {updated} ShortcutSet(s)")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"🔍 DRY RUN - Would update {sets_count} ShortcutSet(s)"
                    )
                )
        else:
            self.stdout.write(self.style.SUCCESS("✅ All ShortcutSets have owners!"))

        # Fix Shortcuts
        shortcuts_without_owner = Shortcut.objects.filter(owner__isnull=True)
        shortcuts_count = shortcuts_without_owner.count()

        if shortcuts_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  Found {shortcuts_count} Shortcut(s) without owner"
                )
            )

            # Show sample
            sample = shortcuts_without_owner[:5]
            for sc in sample:
                sets_str = ", ".join([s.name for s in sc.sets.all()]) or "no sets"
                self.stdout.write(f"  - {sc.key} (in: {sets_str})")
            if shortcuts_count > 5:
                self.stdout.write(f"  ... and {shortcuts_count - 5} more")

            if not dry_run:
                updated = shortcuts_without_owner.update(owner=owner)
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Updated {updated} Shortcut(s)")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"🔍 DRY RUN - Would update {shortcuts_count} Shortcut(s)"
                    )
                )
        else:
            self.stdout.write(self.style.SUCCESS("\n✅ All Shortcuts have owners!"))

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n🔍 DRY RUN - No changes made. Run without --dry-run to apply changes."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✅ Done! All objects now have owners.")
            )
