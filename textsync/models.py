from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from datetime import timedelta
import binascii
import os


class ExpiringToken(models.Model):
    """
    Custom token model with expiration.
    Tokens expire after 180 days.
    """
    key = models.CharField(max_length=40, primary_key=True)
    user = models.OneToOneField(User, related_name='auth_token', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = 'Expiring Token'
        verbose_name_plural = 'Expiring Tokens'

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=180)
        return super().save(*args, **kwargs)

    @classmethod
    def generate_key(cls):
        return binascii.hexlify(os.urandom(20)).decode()

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Token for {self.user.username} (expires {self.expires_at.strftime('%Y-%m-%d')})"


class ShortcutSet(models.Model):
    """Represents a set of shortcuts (e.g., 'birou', 'cosmin', 'bogdan', 'aura')"""

    SET_TYPES = [
        ('general', 'General (Birou)'),
        ('personal', 'Personal (Utilizator)'),
    ]

    name = models.CharField(max_length=50, unique=True)
    set_type = models.CharField(max_length=10, choices=SET_TYPES, default='general')
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                              related_name='owned_sets',
                              help_text='User who owns this set. Staff can only see/edit their own sets.')
    visible_to = models.ManyToManyField(User, blank=True,
                                        related_name='visible_sets',
                                        help_text='Staff users who can see this set (in addition to the owner). Only superusers can set this.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['set_type', 'name']
        verbose_name = 'Shortcut Set'
        verbose_name_plural = 'Shortcut Sets'

    def __str__(self):
        return f"{self.name} ({self.get_set_type_display()})"


class Shortcut(models.Model):
    """Represents a text expansion shortcut"""

    CONTENT_TYPES = [
        ('text', 'Plain Text'),
        ('html', 'Rich Text (HTML)'),
    ]

    key = models.CharField(max_length=50)  # Removed unique=True - same key can be in different sets
    content_type = models.CharField(max_length=10, choices=CONTENT_TYPES, default='text')
    value = models.TextField(blank=True)
    html_value = models.TextField(blank=True, null=True)
    sets = models.ManyToManyField(ShortcutSet, related_name='shortcuts', blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                              related_name='owned_shortcuts',
                              help_text='User who owns this shortcut. Staff can only see/edit their own shortcuts.')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='updated_shortcuts')
    # Usage tracking
    usage_count = models.PositiveIntegerField(default=0, help_text='Total times this shortcut has been expanded')
    last_used_at = models.DateTimeField(null=True, blank=True, help_text='Last time this shortcut was used')

    class Meta:
        ordering = ['key']
        verbose_name = 'Shortcut'
        verbose_name_plural = 'Shortcuts'
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['updated_at']),
            models.Index(fields=['usage_count']),
            # Composite index for delta sync cursor pagination: WHERE updated_at > X
            # ORDER BY updated_at, id. Verify usage with EXPLAIN QUERY PLAN.
            models.Index(fields=['updated_at', 'id']),
        ]

    def __str__(self):
        sets_str = ", ".join([s.name for s in self.sets.all()]) if self.sets.exists() else "no sets"
        preview = self.value[:30] if self.value else (self.html_value[:30] if self.html_value else "no content")
        return f"{self.key} → {preview} ({sets_str})"


class UserVariable(models.Model):
    """Per-user custom variable, accessed in shortcuts as [[var:name]].

    A simple key→value store scoped to one user. Values resolve at expand
    time inside the extension; if a user creates `display_name = "Cosmin"`,
    the snippet `Salut, sunt [[var:display_name]]` becomes `Salut, sunt Cosmin`.

    Names are case-sensitive and must match `[a-zA-Z_][a-zA-Z0-9_]*` so they
    fit cleanly inside the [[var:...]] grammar without escaping.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='variables',
                             help_text='Owner — only this user sees + uses this variable')
    name = models.CharField(max_length=50,
                            help_text='Variable name (used as [[var:name]] in shortcuts)')
    value = models.TextField(blank=True, help_text='What the variable expands to')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = [('user', 'name')]
        verbose_name = 'User Variable'
        verbose_name_plural = 'User Variables'
        indexes = [
            models.Index(fields=['user', 'name']),
        ]

    def __str__(self):
        preview = self.value[:30] if self.value else '(empty)'
        return f"[[var:{self.name}]] = {preview} ({self.user.username})"


class ShortcutVersion(models.Model):
    """Snapshot history for general (Birou) shortcuts.

    Each save of a general-set shortcut snapshots the PREVIOUS state (key,
    value, html_value, content_type) before it is overwritten. The latest
    five snapshots per shortcut are retained; older snapshots are pruned.
    Personal shortcuts skip versioning — they are user-owned and the user
    can simply edit-undo from the manage UI.

    Restore: in Django admin, the "Restore this version" action on a
    `ShortcutVersion` writes its snapshot back into the parent `Shortcut`,
    which itself produces a new snapshot of the rolled-back state. Nothing
    is destroyed.
    """
    shortcut = models.ForeignKey(Shortcut, on_delete=models.CASCADE,
                                 related_name='versions')
    # Per-shortcut increment so the admin can list "v1, v2, v3" without
    # parsing timestamps. Computed at insert time inside the signal.
    version_number = models.PositiveIntegerField()
    key = models.CharField(max_length=50)
    content_type = models.CharField(max_length=10)
    value = models.TextField(blank=True)
    html_value = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='shortcut_versions',
                                   help_text='User whose save triggered this snapshot.')

    class Meta:
        ordering = ['-version_number']
        unique_together = [('shortcut', 'version_number')]
        verbose_name = 'Shortcut Version'
        verbose_name_plural = 'Shortcut Versions'
        indexes = [
            models.Index(fields=['shortcut', '-version_number']),
        ]

    def __str__(self):
        return f"{self.shortcut.key} v{self.version_number} ({self.created_at:%Y-%m-%d %H:%M})"


class ShortcutUsageLog(models.Model):
    """
    Detailed usage log for analytics.
    Tracks each shortcut expansion for reporting and analysis.
    """
    shortcut = models.ForeignKey(Shortcut, on_delete=models.CASCADE, related_name='usage_logs')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shortcut_usage_logs')
    used_at = models.DateTimeField(auto_now_add=True)
    # Optional: track where the shortcut was used (domain)
    domain = models.CharField(max_length=255, blank=True, null=True,
                              help_text='Domain where the shortcut was used')

    class Meta:
        ordering = ['-used_at']
        verbose_name = 'Shortcut Usage Log'
        verbose_name_plural = 'Shortcut Usage Logs'
        indexes = [
            models.Index(fields=['used_at']),
            models.Index(fields=['user', 'used_at']),
            models.Index(fields=['shortcut', 'used_at']),
        ]

    def __str__(self):
        return f"{self.user.username} used '{self.shortcut.key}' at {self.used_at}"
