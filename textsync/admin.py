from django import forms
from django.contrib import admin
from django.db.models import Q
from django.utils.html import format_html
from tinymce.widgets import TinyMCE
from .models import Shortcut, ShortcutSet, ExpiringToken


@admin.register(ShortcutSet)
class ShortcutSetAdmin(admin.ModelAdmin):
    list_display = ["name", "set_type", "owner", "get_visible_to", "get_shortcut_count", "created_at"]
    list_filter = ["set_type", "created_at", "owner"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at"]
    filter_horizontal = ["visible_to"]

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'set_type', 'description')
        }),
        ('Ownership & Sharing', {
            'fields': ('owner', 'visible_to'),
            'description': 'Set owner and share with specific users. Only superusers can modify these fields.'
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def get_shortcut_count(self, obj):
        return obj.shortcuts.count()

    get_shortcut_count.short_description = "Shortcuts"

    def get_visible_to(self, obj):
        """Display users who can see this set"""
        users = obj.visible_to.all()
        if not users:
            return "-"
        return ", ".join([u.username for u in users])

    get_visible_to.short_description = "Shared With"

    def get_readonly_fields(self, request, obj=None):
        """Make owner and visible_to readonly for staff users"""
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            readonly.extend(['owner', 'visible_to'])
        return readonly

    def get_queryset(self, request):
        """Filter queryset: staff users see their own sets + sets shared with them, superusers see all"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Staff users see: sets they own OR sets they're in visible_to
        return qs.filter(Q(owner=request.user) | Q(visible_to=request.user)).distinct()

    def save_model(self, request, obj, form, change):
        """Auto-assign owner to current user if not set"""
        if not obj.pk and not obj.owner:
            obj.owner = request.user
        super().save_model(request, obj, form, change)


class ShortcutAdminForm(forms.ModelForm):
    """Custom form for Shortcut with TinyMCE editor for html_value"""

    class Meta:
        model = Shortcut
        fields = '__all__'
        widgets = {
            'html_value': TinyMCE(),
        }


class ShortcutSetFilter(admin.SimpleListFilter):
    """Custom filter to filter shortcuts by set with better display"""
    title = 'Shortcut Set'
    parameter_name = 'set'

    def lookups(self, request, model_admin):
        """Return list of sets available to current user"""
        if request.user.is_superuser:
            sets = ShortcutSet.objects.all()
        else:
            sets = ShortcutSet.objects.filter(
                Q(owner=request.user) | Q(visible_to=request.user)
            ).distinct()

        return [(s.id, f"{s.name} ({s.get_set_type_display()})") for s in sets.order_by('set_type', 'name')]

    def queryset(self, request, queryset):
        """Filter queryset by selected set"""
        if self.value():
            return queryset.filter(sets__id=self.value()).distinct()
        return queryset


@admin.register(Shortcut)
class ShortcutAdmin(admin.ModelAdmin):
    form = ShortcutAdminForm
    list_display = ["key", "content_type", "value_preview", "owner", "get_sets", "updated_at", "updated_by"]
    list_filter = [ShortcutSetFilter, "content_type", "owner", "updated_at"]
    search_fields = ["key", "value", "sets__name"]
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
        """Display which sets this shortcut belongs to with color coding"""
        sets = obj.sets.all()
        if not sets:
            return format_html('<em style="color: #999;">No sets</em>')

        # Color code by set type
        set_badges = []
        for s in sets:
            if s.set_type == 'general':
                color = '#4CAF50'  # Green for general
                icon = '🏢'
            else:
                color = '#2196F3'  # Blue for personal
                icon = '👤'

            badge = f'<span style="background: {color}; color: white; padding: 2px 8px; border-radius: 3px; margin-right: 4px; font-size: 11px;">{icon} {s.name}</span>'
            set_badges.append(badge)

        return format_html(''.join(set_badges))

    get_sets.short_description = "Sets"

    def get_queryset(self, request):
        """Filter queryset: staff users see only their own shortcuts, superusers see all"""
        qs = super().get_queryset(request)

        # Prefetch sets for better performance
        qs = qs.prefetch_related('sets', 'sets__owner')

        # Filter by user permissions
        if request.user.is_superuser:
            return qs.order_by('key')
        return qs.filter(owner=request.user).order_by('key')

    def save_model(self, request, obj, form, change):
        """Auto-assign owner and updated_by to current user"""
        if not obj.pk:
            # New object - set both owner and updated_by
            if not obj.owner:
                obj.owner = request.user
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
