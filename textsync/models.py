from django.contrib.auth.models import User
from django.db import models


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

    key = models.CharField(max_length=50)  # Removed unique=True - same key can be in different sets
    value = models.TextField()
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
        return f"{self.key} → {self.value[:30]} ({sets_str})"
