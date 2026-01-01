import csv
import io
from django import forms
from django.contrib import admin, messages
from django.db.models import Q, Count
from django.urls import path
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html
from datetime import timedelta
from tinymce.widgets import TinyMCE
from .models import Shortcut, ShortcutSet, ExpiringToken, ShortcutUsageLog


@admin.register(ShortcutSet)
class ShortcutSetAdmin(admin.ModelAdmin):
    list_display = [
        "name", "set_type", "owner", "get_visible_to",
        "get_shortcut_count", "created_at"
    ]
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
            'description': (
                'Set owner and share with specific users. '
                'Only superusers can modify these fields.'
            )
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
        """Filter: staff see own sets + shared, superusers see all."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Staff users see: sets they own OR sets they're in visible_to
        return qs.filter(Q(owner=request.user) | Q(visible_to=request.user)).distinct()

    def save_model(self, request, obj, form, change):
        """Auto-assign owner to current user if not set"""
        # For new objects or objects without owner, set owner to current user
        if not obj.owner:
            obj.owner = request.user
        super().save_model(request, obj, form, change)

    # ========== Restrict visibility for staff users ==========

    def has_module_permission(self, request):
        """Only superusers can see ShortcutSet in admin sidebar"""
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


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
            # Staff see: their sets + general sets (Birou) + sets shared with them
            sets = ShortcutSet.objects.filter(
                Q(owner=request.user) |
                Q(set_type='general') |
                Q(visible_to=request.user)
            ).distinct()

        return [
            (s.id, f"{s.name} ({s.get_set_type_display()})")
            for s in sets.order_by('set_type', 'name')
        ]

    def queryset(self, request, queryset):
        """Filter queryset by selected set"""
        if self.value():
            return queryset.filter(sets__id=self.value()).distinct()
        return queryset


@admin.register(Shortcut)
class ShortcutAdmin(admin.ModelAdmin):
    form = ShortcutAdminForm
    list_display = [
        "key", "content_type", "value_preview", "owner", "get_sets",
        "usage_count", "last_used_at", "updated_at"
    ]
    list_filter = [ShortcutSetFilter, "content_type", "owner", "updated_at"]
    search_fields = ["key", "value", "sets__name"]
    readonly_fields = ["updated_at", "usage_count", "last_used_at"]
    filter_horizontal = ["sets"]  # Nice UI for ManyToMany selection
    ordering = ["-usage_count", "key"]  # Most used shortcuts first

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
        ('Usage Statistics', {
            'fields': ('usage_count', 'last_used_at'),
            'classes': ('collapse',),
            'description': 'Tracked when the shortcut is used.'
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

            style = (
                f"background: {color}; color: white; padding: 2px 8px; "
                "border-radius: 3px; margin-right: 4px; font-size: 11px;"
            )
            badge = f'<span style="{style}">{icon} {s.name}</span>'
            set_badges.append(badge)

        return format_html(''.join(set_badges))

    get_sets.short_description = "Sets"

    def get_queryset(self, request):
        """Filter: staff see own shortcuts + general set shortcuts, superusers see all."""
        qs = super().get_queryset(request)

        # Prefetch sets for better performance
        qs = qs.prefetch_related('sets', 'sets__owner')

        # Filter by user permissions
        if request.user.is_superuser:
            return qs.order_by('key')

        # Staff users see:
        # 1. Their own shortcuts
        # 2. Shortcuts in general sets (like Birou)
        # 3. Shortcuts in sets shared with them
        return qs.filter(
            Q(owner=request.user) |
            Q(sets__set_type='general') |
            Q(sets__visible_to=request.user)
        ).distinct().order_by('key')

    def save_model(self, request, obj, form, change):
        """Auto-assign owner, updated_by, and auto-detect content_type"""
        # Set owner to current user if not set (new objects or without owner)
        if not obj.owner:
            obj.owner = request.user

        # Always set updated_by to current user on any save
        obj.updated_by = request.user

        # Auto-detect content_type based on which field has data
        # Priority: html_value > value (if html is filled, use html type)
        if obj.html_value and obj.html_value.strip():
            obj.content_type = 'html'
        elif obj.value and obj.value.strip():
            obj.content_type = 'text'
        # If neither has content, default to 'text'
        else:
            obj.content_type = 'text'

        super().save_model(request, obj, form, change)

    def get_personal_set(self, user):
        """Get or create the user's personal set"""
        personal_set, created = ShortcutSet.objects.get_or_create(
            owner=user,
            set_type='personal',
            defaults={
                'name': user.username,
                'description': f'Personal shortcuts for {user.username}'
            }
        )
        return personal_set

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """
        Customize the 'sets' field:
        - Filter to show only sets the user can access
        - Staff can see: their personal sets + general sets (Birou) + sets shared with them
        """
        if db_field.name == 'sets':
            if request.user.is_superuser:
                # Superusers see all sets
                kwargs['queryset'] = ShortcutSet.objects.all().order_by('set_type', 'name')
            else:
                # Staff users see:
                # 1. Their own sets (personal)
                # 2. General sets like Birou (set_type='general')
                # 3. Sets shared with them via visible_to
                kwargs['queryset'] = ShortcutSet.objects.filter(
                    Q(owner=request.user) |
                    Q(set_type='general') |
                    Q(visible_to=request.user)
                ).distinct().order_by('set_type', 'name')

        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_changeform_initial_data(self, request):
        """Pre-select personal set for new shortcuts"""
        initial = super().get_changeform_initial_data(request)
        personal_set = self.get_personal_set(request.user)
        initial['sets'] = [personal_set.pk]
        return initial

    def get_fieldsets(self, request, obj=None):
        """Simplified fieldsets for staff users"""
        if request.user.is_superuser:
            return self.fieldsets

        # Staff users get a simpler view - no content_type dropdown (auto-detected)
        return (
            ('Shortcut Key', {
                'fields': ('key',),
                'description': 'Enter the shortcut key (e.g., /sig, /addr)'
            }),
            ('Plain Text Content', {
                'fields': ('value',),
                'classes': ('content-type-section', 'text-section'),
                'description': 'For simple text without formatting.'
            }),
            ('Rich Text Content', {
                'fields': ('html_value',),
                'classes': ('content-type-section', 'html-section'),
                'description': 'Use the editor for rich text with formatting. If both fields have content, rich text takes priority.'
            }),
            ('Save to Set', {
                'fields': ('sets',),
                'description': 'Select which set(s) to save this shortcut to. Your personal set is pre-selected.'
            }),
        )

    def get_list_display(self, request):
        """Simplified list for staff users"""
        if request.user.is_superuser:
            return self.list_display
        # Staff don't need to see owner (it's always them)
        return ["key", "content_type", "value_preview", "get_sets", "updated_at"]

    def get_list_filter(self, request):
        """Simplified filters for staff users"""
        if request.user.is_superuser:
            return self.list_filter
        # Staff don't need owner filter
        return [ShortcutSetFilter, "content_type", "updated_at"]

    # ========== Bulk Operations: Import/Export CSV ==========

    actions = ['export_as_csv']
    change_list_template = 'admin/textsync/shortcut/change_list.html'

    def get_urls(self):
        """Add custom URL for CSV import"""
        urls = super().get_urls()
        custom_urls = [
            path(
                'import-csv/',
                self.admin_site.admin_view(self.import_csv_view),
                name='textsync_shortcut_import_csv'
            ),
        ]
        return custom_urls + urls

    def export_as_csv(self, request, queryset):
        """Export selected shortcuts as CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="shortcuts_export.csv"'
        response.write('\ufeff')  # UTF-8 BOM for Excel compatibility

        writer = csv.writer(response)
        writer.writerow(['key', 'content_type', 'value', 'html_value', 'sets'])

        for shortcut in queryset:
            sets_str = '|'.join([s.name for s in shortcut.sets.all()])
            writer.writerow([
                shortcut.key,
                shortcut.content_type,
                shortcut.value or '',
                shortcut.html_value or '',
                sets_str
            ])

        msg = f"Exported {queryset.count()} shortcuts to CSV."
        self.message_user(request, msg, messages.SUCCESS)
        return response

    export_as_csv.short_description = "Export selected shortcuts as CSV"

    def import_csv_view(self, request):
        """Handle CSV import"""
        if request.method == 'POST':
            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                self.message_user(request, "Please select a CSV file.", messages.ERROR)
                return redirect('..')

            if not csv_file.name.endswith('.csv'):
                self.message_user(request, "File must be a CSV.", messages.ERROR)
                return redirect('..')

            try:
                # Read and decode CSV
                decoded_file = csv_file.read().decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(decoded_file))

                created_count = 0
                updated_count = 0
                errors = []

                for row_num, row in enumerate(reader, start=2):
                    try:
                        key = row.get('key', '').strip()
                        if not key:
                            errors.append(f"Row {row_num}: Missing key")
                            continue

                        content_type = row.get('content_type', 'text').strip()
                        if content_type not in ['text', 'html']:
                            content_type = 'text'

                        value = row.get('value', '')
                        html_value = row.get('html_value', '')
                        sets_str = row.get('sets', '')

                        # Create or update shortcut
                        shortcut, created = Shortcut.objects.update_or_create(
                            key=key,
                            owner=request.user,
                            defaults={
                                'content_type': content_type,
                                'value': value,
                                'html_value': html_value,
                                'updated_by': request.user,
                            }
                        )

                        # Handle sets
                        if sets_str:
                            names = [s.strip() for s in sets_str.split('|')]
                            set_names = [n for n in names if n]
                            for set_name in set_names:
                                defaults = {
                                    'owner': request.user,
                                    'set_type': 'personal'
                                }
                                shortcut_set, _ = ShortcutSet.objects.get_or_create(
                                    name=set_name, defaults=defaults
                                )
                                shortcut.sets.add(shortcut_set)

                        if created:
                            created_count += 1
                        else:
                            updated_count += 1

                    except Exception as e:
                        errors.append(f"Row {row_num}: {str(e)}")

                # Report results
                msg = (
                    f"Import complete: {created_count} created, "
                    f"{updated_count} updated."
                )
                if errors:
                    msg += f" {len(errors)} errors."
                    for error in errors[:5]:
                        messages.warning(request, error)
                    if len(errors) > 5:
                        remaining = len(errors) - 5
                        messages.warning(request, f"...and {remaining} more")

                level = messages.SUCCESS if not errors else messages.WARNING
                self.message_user(request, msg, level)

            except Exception as e:
                err_msg = f"Error processing CSV: {str(e)}"
                self.message_user(request, err_msg, messages.ERROR)

            return redirect('..')

        # GET request - show import form
        context = {
            **self.admin_site.each_context(request),
            'title': 'Import Shortcuts from CSV',
            'opts': self.model._meta,
        }
        return render(request, 'admin/textsync/shortcut/import_csv.html', context)


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

    # ========== Restrict visibility for staff users ==========

    def has_module_permission(self, request):
        """Only superusers can see ExpiringToken in admin"""
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(ShortcutUsageLog)
class ShortcutUsageLogAdmin(admin.ModelAdmin):
    """Admin for viewing shortcut usage logs with analytics."""
    list_display = ["shortcut_key", "user", "domain", "used_at"]
    list_filter = ["used_at", "user", "shortcut__sets"]
    search_fields = ["shortcut__key", "user__username", "domain"]
    readonly_fields = ["shortcut", "user", "used_at", "domain"]
    date_hierarchy = "used_at"
    ordering = ["-used_at"]

    def shortcut_key(self, obj):
        return obj.shortcut.key
    shortcut_key.short_description = "Shortcut"
    shortcut_key.admin_order_field = "shortcut__key"

    # ========== Restrict visibility for staff users ==========

    def has_module_permission(self, request):
        """Only superusers can see ShortcutUsageLog in admin"""
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        """Usage logs are created automatically, not manually."""
        return False

    def has_change_permission(self, request, obj=None):
        """Usage logs are read-only."""
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def changelist_view(self, request, extra_context=None):
        """Add analytics summary to the changelist view."""
        extra_context = extra_context or {}

        # Get date range for analytics
        now = timezone.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # Today's usage
        today_count = ShortcutUsageLog.objects.filter(used_at__gte=today).count()

        # This week's usage
        week_count = ShortcutUsageLog.objects.filter(used_at__gte=week_ago).count()

        # This month's usage
        month_count = ShortcutUsageLog.objects.filter(used_at__gte=month_ago).count()

        # Top shortcuts (last 30 days)
        top_shortcuts = (
            ShortcutUsageLog.objects
            .filter(used_at__gte=month_ago)
            .values('shortcut__key')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        # Top users (last 30 days)
        top_users = (
            ShortcutUsageLog.objects
            .filter(used_at__gte=month_ago)
            .values('user__username')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        # Top domains (last 30 days)
        top_domains = (
            ShortcutUsageLog.objects
            .filter(used_at__gte=month_ago)
            .exclude(domain__isnull=True)
            .exclude(domain='')
            .values('domain')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

        extra_context.update({
            'today_count': today_count,
            'week_count': week_count,
            'month_count': month_count,
            'top_shortcuts': list(top_shortcuts),
            'top_users': list(top_users),
            'top_domains': list(top_domains),
            'show_analytics': True,
        })

        return super().changelist_view(request, extra_context=extra_context)
