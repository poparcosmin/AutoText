from rest_framework import serializers

from .models import Shortcut, ShortcutSet


class ShortcutSetSerializer(serializers.ModelSerializer):
    """Serializer for ShortcutSet model"""
    shortcut_count = serializers.SerializerMethodField()
    owner_username = serializers.SerializerMethodField()
    visible_to_usernames = serializers.SerializerMethodField()

    class Meta:
        model = ShortcutSet
        fields = ["id", "name", "set_type", "description", "owner_username", "visible_to_usernames", "shortcut_count", "created_at"]

    def get_shortcut_count(self, obj):
        return obj.shortcuts.count()

    def get_owner_username(self, obj):
        """Return owner username if exists"""
        return obj.owner.username if obj.owner else None

    def get_visible_to_usernames(self, obj):
        """Return list of usernames who can see this set"""
        return [u.username for u in obj.visible_to.all()]


class ShortcutSerializer(serializers.ModelSerializer):
    """Serializer for Shortcut model with set information"""
    set_names = serializers.SerializerMethodField()
    set_types = serializers.SerializerMethodField()
    owner_username = serializers.SerializerMethodField()

    class Meta:
        model = Shortcut
        fields = ["id", "key", "value", "html_value", "owner_username", "set_names", "set_types", "updated_at"]

    def get_set_names(self, obj):
        """Return list of set names this shortcut belongs to"""
        return [s.name for s in obj.sets.all()]

    def get_set_types(self, obj):
        """Return list of set types (for conflict resolution in extension)"""
        return [s.set_type for s in obj.sets.all()]

    def get_owner_username(self, obj):
        """Return owner username if exists"""
        return obj.owner.username if obj.owner else None
