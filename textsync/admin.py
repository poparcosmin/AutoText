from django.contrib import admin
from .models import Shortcut, ShortcutSet


@admin.register(ShortcutSet)
class ShortcutSetAdmin(admin.ModelAdmin):
    list_display = ["name", "set_type", "get_shortcut_count", "created_at"]
    list_filter = ["set_type", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at"]

    def get_shortcut_count(self, obj):
        return obj.shortcuts.count()

    get_shortcut_count.short_description = "Shortcuts"


@admin.register(Shortcut)
class ShortcutAdmin(admin.ModelAdmin):
    list_display = ["key", "value_preview", "get_sets", "updated_at", "updated_by"]
    list_filter = ["updated_at", "sets"]
    search_fields = ["key", "value"]
    readonly_fields = ["updated_at"]
    filter_horizontal = ["sets"]  # Nice UI for ManyToMany selection

    def value_preview(self, obj):
        """Show first 50 chars of value"""
        return obj.value[:50] + "..." if len(obj.value) > 50 else obj.value

    value_preview.short_description = "Value"

    def get_sets(self, obj):
        """Display which sets this shortcut belongs to"""
        sets = obj.sets.all()
        if not sets:
            return "-"
        return ", ".join([f"{s.name} ({s.get_set_type_display()})" for s in sets])

    get_sets.short_description = "Sets"

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)
