from django.core.management.base import BaseCommand

from apps.members.models import Role

ROLE_NAMES = ["influencer", "koc"]


class Command(BaseCommand):
    help = "Seed the default member roles (Influencer, KOC)"

    def handle(self, *args, **kwargs):
        for name in ROLE_NAMES:
            role, created = Role.objects.get_or_create(name=name, defaults={"status": 1})
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created role: {name}"))
            else:
                self.stdout.write(f"Role already exists: {name}")
