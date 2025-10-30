from django import forms
from django.contrib import admin
from django.utils.html import format_html
from tinymce.widgets import TinyMCE
from .models import Shortcut, ShortcutSet, ExpiringToken


@admin.register(ShortcutSet)
class ShortcutSetAdmin(admin.ModelAdmin):
    list_display = ["name", "set_type", "get_shortcut_count", "created_at"]
    list_filter = ["set_type", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at"]

    def get_shortcut_count(self, obj):
        return obj.shortcuts.count()

    get_shortcut_count.short_description = "Shortcuts"


class ShortcutAdminForm(forms.ModelForm):
    """Custom form for Shortcut with TinyMCE editor for html_value"""

    class Meta:
        model = Shortcut
        fields = '__all__'
        widgets = {
            'html_value': TinyMCE(),
        }


@admin.register(Shortcut)
class ShortcutAdmin(admin.ModelAdmin):
    form = ShortcutAdminForm
    list_display = ["key", "value_preview", "get_sets", "updated_at", "updated_by"]
    list_filter = ["updated_at", "sets"]
    search_fields = ["key", "value"]
    readonly_fields = ["updated_at", "html_preview"]
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

    def html_preview(self, obj):
        """Display rendered HTML preview of html_value field"""
        if not obj.html_value:
            return format_html('<em style="color: #999;">No HTML content</em>')
        return format_html(
            '<div style="border: 1px solid #ddd; padding: 10px; '
            'background: #f9f9f9; border-radius: 4px;">{}</div>',
            obj.html_value
        )

    html_preview.short_description = "HTML Preview"

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ExpiringToken)
class ExpiringTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "key_preview", "created", "expires_at", "is_valid"]
    list_filter = ["created", "expires_at"]
    search_fields = ["user__username", "key"]
    readonly_fields = ["key", "created", "expires_at"]

    def key_preview(self, obj):
        """Show first 10 chars of token"""
        return f"{obj.key[:10]}..."

    key_preview.short_description = "Token"

    def is_valid(self, obj):
        """Check if token is still valid"""
        return not obj.is_expired()

    is_valid.boolean = True
    is_valid.short_description = "Valid"
