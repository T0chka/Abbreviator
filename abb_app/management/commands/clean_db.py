from django.core.management.base import BaseCommand
from abb_app.models import AbbreviationEntry

class Command(BaseCommand):
    help = "Clean abbreviation table in the database"

    def handle(self, *args, **kwargs):
        self.stdout.write("Clearing existing abbreviation entries...")
        AbbreviationEntry.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("Successfully cleaned abbreviation table."))