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
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver

from .cache import invalidate_user_cache
from .models import Shortcut, ShortcutSet


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
        set_type='shared',
    ).values_list('visible_to__id', flat=True)
    user_ids.update(shared_user_ids)
    _bulk_invalidate(user_ids)


@receiver([post_save, post_delete], sender=ShortcutSet)
def invalidate_on_set_change(sender, instance, **kwargs):
    user_ids = set()
    if instance.owner_id:
        user_ids.add(instance.owner_id)
    user_ids.update(instance.visible_to.values_list('id', flat=True))
    _bulk_invalidate(user_ids)


@receiver(m2m_changed, sender=ShortcutSet.visible_to.through)
def invalidate_on_visibility_change(sender, instance, action, pk_set, reverse, **kwargs):
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
        ).values_list('owner_id', flat=True)
        user_ids.update(owner_ids)
    else:
        # Set-side: instance is ShortcutSet; pk_set are User IDs being added/removed
        user_ids = set(pk_set)
        if instance.owner_id:
            user_ids.add(instance.owner_id)

    _bulk_invalidate(user_ids)
