import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create an optional first admin from DJANGO_SUPERUSER_* environment variables.'

    def handle(self, *args, **options):
        names = (
            'DJANGO_SUPERUSER_USERNAME',
            'DJANGO_SUPERUSER_EMAIL',
            'DJANGO_SUPERUSER_PASSWORD',
        )
        username, email, password = (os.getenv(name, '') for name in names)
        if not any((username, email, password)):
            return
        if not all((username, email, password)):
            raise CommandError('Set all three DJANGO_SUPERUSER_* variables, or leave all three empty.')

        User = get_user_model()
        existing = User.objects.filter(username=username).first()
        if existing is not None:
            if not (existing.is_active and existing.is_staff and existing.is_superuser):
                raise CommandError('The bootstrap username already belongs to a user who is not an active superuser.')
            self.stdout.write('The bootstrap superuser already exists; credentials were not changed.')
            return

        user = User(username=username, email=email)
        try:
            user.full_clean(exclude=['password'])
            if password == 'change-me-now':
                raise ValidationError('The old example password is not allowed. Choose a new password.')
            validate_password(password, user=user)
        except ValidationError as exc:
            raise CommandError('Cannot create the bootstrap admin: ' + '; '.join(exc.messages)) from exc

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write('Created the bootstrap superuser. Remove the bootstrap variables after first use.')
