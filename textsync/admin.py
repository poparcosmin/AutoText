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
    list_display = ["key", "content_type", "value_preview", "get_sets", "updated_at", "updated_by"]
    list_filter = ["content_type", "updated_at", "sets"]
    search_fields = ["key", "value"]
    readonly_fields = ["updated_at"]
    filter_horizontal = ["sets"]  # Nice UI for ManyToMany selection

    fieldsets = (
        ('Content Type', {
            'fields': ('key', 'content_type'),
            'description': 'Choose between Plain Text or Rich Text (HTML)'
        }),
        ('Plain Text Content', {
            'fields': ('value',),
            'classes': ('content-type-section', 'text-section'),
        }),
        ('Rich Text Content', {
            'fields': ('html_value',),
            'classes': ('content-type-section', 'html-section'),
            'description': 'Use the WYSIWYG editor for rich text formatting.'
        }),
        ('Organization', {
            'fields': ('sets',)
        }),
        ('Metadata', {
            'fields': ('updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

    class Media:
        js = ('textsync/admin/js/shortcut_toggle.js',)
        css = {
            'all': ('textsync/admin/css/shortcut_toggle.css',)
        }

    def content_type(self, obj):
        """Display content type with icon"""
        if obj.content_type == 'text':
            return format_html('<span style="color: #666;">📝 Text</span>')
        else:
            return format_html('<span style="color: #4285f4;">🎨 HTML</span>')

    content_type.short_description = "Type"

    def value_preview(self, obj):
        """Show first 50 chars of value or html_value"""
        if obj.content_type == 'text':
            if not obj.value:
                return format_html('<em style="color: #999;">-</em>')
            return obj.value[:50] + "..." if len(obj.value) > 50 else obj.value
        else:
            if not obj.html_value:
                return format_html('<em style="color: #999;">-</em>')
            # Strip HTML tags for preview
            import re
            text = re.sub('<[^<]+?>', '', obj.html_value)
            return text[:50] + "..." if len(text) > 50 else text

    value_preview.short_description = "Preview"

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
