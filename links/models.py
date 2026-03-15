from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.crypto import get_random_string

ALPHABET = 'abcdefghijklmnopqrstuvwxyz0123456789'
RESERVED_CODES = {'admin'}


class ShortLink(models.Model):
    short_code = models.SlugField(
        max_length=32,
        unique=True,
        blank=True,
        help_text='Optional. Leave blank to generate a random code.',
    )
    target_url = models.URLField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.short_code} -> {self.target_url}'

    def clean(self):
        super().clean()
        if self.short_code:
            self.short_code = self.short_code.lower()
            if self.short_code in RESERVED_CODES:
                raise ValidationError({'short_code': 'This short code is reserved.'})

    def save(self, *args, **kwargs):
        if self.short_code:
            self.short_code = self.short_code.lower()
        else:
            self.short_code = self.generate_unique_code()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('links:redirect', kwargs={'code': self.short_code})

    @classmethod
    def generate_unique_code(cls, length=6):
        while True:
            code = get_random_string(length, allowed_chars=ALPHABET)
            if code not in RESERVED_CODES and not cls.objects.filter(short_code=code).exists():
                return code
