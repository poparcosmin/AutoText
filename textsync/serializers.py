from rest_framework import serializers

from .models import Shortcut, ShortcutSet


class ShortcutSetSerializer(serializers.ModelSerializer):
    """Serializer for ShortcutSet model"""
    shortcut_count = serializers.SerializerMethodField()

    class Meta:
        model = ShortcutSet
        fields = ["id", "name", "set_type", "description", "shortcut_count", "created_at"]

    def get_shortcut_count(self, obj):
        return obj.shortcuts.count()


class ShortcutSerializer(serializers.ModelSerializer):
    """Serializer for Shortcut model with set information"""
    set_names = serializers.SerializerMethodField()
    set_types = serializers.SerializerMethodField()

    class Meta:
        model = Shortcut
        fields = ["id", "key", "value", "html_value", "set_names", "set_types", "updated_at"]

    def get_set_names(self, obj):
        """Return list of set names this shortcut belongs to"""
        return [s.name for s in obj.sets.all()]

    def get_set_types(self, obj):
        """Return list of set types (for conflict resolution in extension)"""
        return [s.set_type for s in obj.sets.all()]
