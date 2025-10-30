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
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['key']
        verbose_name = 'Shortcut'
        verbose_name_plural = 'Shortcuts'

    def __str__(self):
        sets_str = ", ".join([s.name for s in self.sets.all()]) if self.sets.exists() else "no sets"
        preview = self.value[:30] if self.value else (self.html_value[:30] if self.html_value else "no content")
        return f"{self.key} → {preview} ({sets_str})"
