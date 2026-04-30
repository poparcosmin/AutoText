"""
Cache invalidation signals for AutoText.

Single source of truth for invalidating user-scoped cache entries when
shortcuts/sets change. Replaces ad-hoc `invalidate_user_cache` calls
scattered across views — covers admin edits, shell commands, bulk imports,
and signal-driven mutations that views never see.

Coalesces invalidations via `transaction.on_commit` so one save with N
related users yields one batch instead of N individual cache hits.
"""

from django.db import transaction
from django.db.models.signals import post_save, post_delete, m2m_changed, pre_save
from django.dispatch import receiver

from .cache import invalidate_user_cache
from .models import Shortcut, ShortcutSet, ShortcutVersion

# Cap on how many historical snapshots to retain per shortcut. Older ones
# are pruned in the same transaction as the new snapshot is created.
SNIPPET_HISTORY_LIMIT = 5


def _bulk_invalidate(user_ids):
    """Schedule cache invalidation for a set of users after the current
    transaction commits. Coalesces multiple calls within the same transaction
    into a single post-commit pass.
    """
    user_ids = {uid for uid in user_ids if uid}
    if not user_ids:
        return

    def _do():
        for uid in user_ids:
            invalidate_user_cache(uid)

    transaction.on_commit(_do)


@receiver([post_save, post_delete], sender=Shortcut)
def invalidate_on_shortcut_change(sender, instance, **kwargs):
    user_ids = set()
    if instance.owner_id:
        user_ids.add(instance.owner_id)
    # Single query collects all visible_to user IDs across shared sets that
    # contain this shortcut — avoids N+1 from iterating sets then visible_to.
    shared_user_ids = ShortcutSet.objects.filter(
        shortcuts=instance,
        set_type="shared",
    ).values_list("visible_to__id", flat=True)
    user_ids.update(shared_user_ids)
    _bulk_invalidate(user_ids)


@receiver([post_save, post_delete], sender=ShortcutSet)
def invalidate_on_set_change(sender, instance, **kwargs):
    user_ids = set()
    if instance.owner_id:
        user_ids.add(instance.owner_id)
    user_ids.update(instance.visible_to.values_list("id", flat=True))
    _bulk_invalidate(user_ids)


@receiver(m2m_changed, sender=ShortcutSet.visible_to.through)
def invalidate_on_visibility_change(
    sender, instance, action, pk_set, reverse, **kwargs
):
    """M2M signals fire from both directions:

    - reverse=False: instance is ShortcutSet, pk_set are User IDs
    - reverse=True:  instance is User,        pk_set are ShortcutSet IDs

    Without handling both, `user.visible_sets.add(set)` would invalidate the
    wrong cache (treating set IDs as user IDs).
    """
    if action not in ("post_add", "post_remove", "post_clear"):
        return
    if not pk_set:
        return

    if reverse:
        # User-side: instance is the User; affected = that user + each set's owner
        user_ids = {instance.pk}
        owner_ids = ShortcutSet.objects.filter(
            pk__in=pk_set,
            owner__isnull=False,
        ).values_list("owner_id", flat=True)
        user_ids.update(owner_ids)
    else:
        # Set-side: instance is ShortcutSet; pk_set are User IDs being added/removed
        user_ids = set(pk_set)
        if instance.owner_id:
            user_ids.add(instance.owner_id)

    _bulk_invalidate(user_ids)


@receiver(pre_save, sender=Shortcut)
def snapshot_shortcut_history(sender, instance, **kwargs):
    """Snapshot the PRIOR state of a general (Birou) shortcut before save.

    Why pre_save and not post_save: post_save runs after the row was
    overwritten, so we'd snapshot the *new* values, which is useless for
    rollback. Reading the old row from DB inside pre_save preserves the
    state we are about to discard.

    Skip rules:
      - new shortcut (pk is None) — no prior version to snapshot
      - personal shortcuts — versioning only matters for shared Birou
        snippets where multiple curators edit the same body
      - no actual change — saving with identical content is noise

    M2M membership in `sets` is committed AFTER pre_save in the create
    flow, but for an UPDATE we read the existing membership directly
    from DB, which already reflects the persisted state.
    """
    if not instance.pk:
        return

    try:
        old = Shortcut.objects.only("key", "content_type", "value", "html_value").get(
            pk=instance.pk
        )
    except Shortcut.DoesNotExist:
        return

    # No-op save (admin clicked save without editing) — skip noise.
    if (
        old.key == instance.key
        and old.content_type == instance.content_type
        and old.value == instance.value
        and (old.html_value or "") == (instance.html_value or "")
    ):
        return

    # Only snapshot if the shortcut belongs to at least one general set.
    # `.exists()` is cheap (LIMIT 1) and the membership is the persisted
    # state, not the in-memory one.
    is_general = old.sets.filter(set_type="general").exists()
    if not is_general:
        return

    last = (
        ShortcutVersion.objects.filter(shortcut=instance)
        .order_by("-version_number")
        .values_list("version_number", flat=True)
        .first()
    )
    next_version = (last or 0) + 1

    ShortcutVersion.objects.create(
        shortcut=instance,
        version_number=next_version,
        key=old.key,
        content_type=old.content_type,
        value=old.value,
        html_value=old.html_value,
        created_by=instance.updated_by,
    )

    # Prune older snapshots beyond the cap. We delete by PK so the
    # ordering query is deterministic even when timestamps are equal.
    keep_pks = list(
        ShortcutVersion.objects.filter(shortcut=instance)
        .order_by("-version_number")
        .values_list("pk", flat=True)[:SNIPPET_HISTORY_LIMIT]
    )
    ShortcutVersion.objects.filter(shortcut=instance).exclude(pk__in=keep_pks).delete()
