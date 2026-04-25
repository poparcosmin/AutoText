import re

from rest_framework import serializers

from .models import Shortcut, ShortcutSet, UserVariable
from .validators import sanitize_html, validate_shortcut_key


VARIABLE_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


class UserVariableSerializer(serializers.ModelSerializer):
    """CRUD shape for /api/user-variables/. user_id is set from the request,
    never accepted from the client, so a token-bearer cannot edit someone
    else's variables by spoofing the user field.
    """

    class Meta:
        model = UserVariable
        fields = ['id', 'name', 'value', 'updated_at']
        read_only_fields = ['id', 'updated_at']

    def validate_name(self, value):
        if not VARIABLE_NAME_RE.match(value):
            raise serializers.ValidationError(
                'Name must start with a letter or underscore and contain only '
                'letters, digits, or underscores.'
            )
        return value


class ShortcutSetSerializer(serializers.ModelSerializer):
    """Serializer for ShortcutSet model"""
    shortcut_count = serializers.SerializerMethodField()
    owner_username = serializers.SerializerMethodField()
    visible_to_usernames = serializers.SerializerMethodField()

    class Meta:
        model = ShortcutSet
        fields = ["id", "name", "set_type", "description", "owner_username", "visible_to_usernames", "shortcut_count", "created_at"]

    def get_shortcut_count(self, obj):
        # Use annotated value when available to avoid extra queries
        return getattr(obj, "shortcut_count", obj.shortcuts.count())

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
    # `aliases` is read-only here — additional trigger keys for the same
    # body. Editing happens via `aliases_input` (write-only list of
    # strings) so the wire format stays simple for both the extension
    # cheatsheet and the manage UI.
    aliases = serializers.SerializerMethodField()
    aliases_input = serializers.ListField(
        child=serializers.CharField(max_length=50, allow_blank=False),
        write_only=True,
        required=False,
    )
    # Allow writing sets via PrimaryKeyRelatedField
    sets = serializers.PrimaryKeyRelatedField(
        queryset=ShortcutSet.objects.all(),
        many=True,
        required=False
    )

    class Meta:
        model = Shortcut
        fields = [
            "id", "key", "content_type", "value", "html_value",
            "owner_username", "sets", "set_names", "set_types",
            "aliases", "aliases_input",
            "updated_at", "usage_count", "last_used_at",
        ]
        read_only_fields = ["usage_count", "last_used_at"]

    def get_aliases(self, obj):
        return [a.alias_key for a in obj.aliases.all()]

    def _sync_aliases(self, instance, alias_list):
        """Replace this shortcut's aliases with the given list.

        Validation collisions (alias already used by ANOTHER shortcut)
        bubble as ValidationError, mapped onto the `aliases_input` field
        so the manage UI can render them next to the textarea.
        """
        from .models import ShortcutAlias  # local import: avoid cycles

        cleaned = []
        seen_local = set()
        for raw in alias_list:
            key = raw.strip()
            if not key:
                continue
            ok, err = validate_shortcut_key(key)
            if not ok:
                raise serializers.ValidationError({'aliases_input': [f"'{key}': {err}"]})
            if key == instance.key:
                # Don't store the primary key as an alias of itself.
                continue
            if key in seen_local:
                continue
            seen_local.add(key)
            cleaned.append(key)

        # Detect conflicts with aliases owned by OTHER shortcuts.
        existing_other = ShortcutAlias.objects.filter(
            alias_key__in=cleaned,
        ).exclude(shortcut=instance)
        if existing_other.exists():
            conflicts = list(existing_other.values_list('alias_key', flat=True))
            raise serializers.ValidationError({
                'aliases_input': [f"Aliases already used by other shortcuts: {', '.join(conflicts)}"]
            })

        # Replace set: drop removed, add new, leave existing untouched.
        current = set(instance.aliases.values_list('alias_key', flat=True))
        target = set(cleaned)
        instance.aliases.filter(alias_key__in=(current - target)).delete()
        ShortcutAlias.objects.bulk_create([
            ShortcutAlias(shortcut=instance, alias_key=k)
            for k in (target - current)
        ])

    def create(self, validated_data):
        alias_list = validated_data.pop('aliases_input', None)
        instance = super().create(validated_data)
        if alias_list is not None:
            self._sync_aliases(instance, alias_list)
        return instance

    def update(self, instance, validated_data):
        alias_list = validated_data.pop('aliases_input', None)
        instance = super().update(instance, validated_data)
        if alias_list is not None:
            self._sync_aliases(instance, alias_list)
        return instance

    def get_set_names(self, obj):
        """Return list of set names this shortcut belongs to"""
        return [s.name for s in obj.sets.all()]

    def get_set_types(self, obj):
        """Return list of set types (for conflict resolution in extension)"""
        return [s.set_type for s in obj.sets.all()]

    def get_owner_username(self, obj):
        """Return owner username if exists"""
        return obj.owner.username if obj.owner else None

    def validate_html_value(self, value):
        """Server-side defence-in-depth peste DOMPurify din extension.
        Strips disallowed tags (script/iframe/etc.), normalizes attribute
        encoding, and keeps the bleach allowlist from textsync.validators.
        """
        return sanitize_html(value) if value else value

    def validate_key(self, value):
        ok, err = validate_shortcut_key(value)
        if not ok:
            raise serializers.ValidationError(err)
        return value
