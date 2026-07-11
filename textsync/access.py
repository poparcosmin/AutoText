"""Centralised access-control helpers for shortcuts and shortcut sets."""

from django.db.models import Q

from .models import Shortcut, ShortcutSet


def accessible_sets_q(user):
    """Return a Q filter for ShortcutSet rows this user can see.

    A set is accessible when any of the following holds:
    - set_type == 'general'  (visible to all authenticated users)
    - owner == user          (the user's own personal set)
    - user in visible_to     (explicitly shared with this user)

    SET_TYPES are 'general' and 'personal' only — there is no 'shared' type.
    """
    return Q(set_type="general") | Q(owner=user) | Q(visible_to=user)


def accessible_shortcuts(user):
    """Return a Shortcut queryset limited to sets accessible by *user*."""
    return Shortcut.objects.filter(
        sets__in=ShortcutSet.objects.filter(accessible_sets_q(user))
    )
