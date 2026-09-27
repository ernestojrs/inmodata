import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea el administrador inicial desde variables de entorno."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_ADMIN_USERNAME")
        email = os.environ.get("DJANGO_ADMIN_EMAIL")
        password = os.environ.get("DJANGO_ADMIN_PASSWORD")

        if not all([username, email, password]):
            self.stdout.write(
                "Administrador inicial omitido: faltan variables de entorno."
            )
            return

        user_model = get_user_model()

        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
            },
        )

        if created:
            user.set_password(password)
            user.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Administrador '{username}' creado correctamente."
                )
            )
            return

        self.stdout.write(
            f"El administrador '{username}' ya existe. No se hicieron cambios."
        )