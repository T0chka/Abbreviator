from django.core.management.base import BaseCommand

from abb_app.services.sessions import cleanup_expired_documents


class Command(BaseCommand):
    help = 'Delete uploaded documents inactive longer than the session timeout.'

    def handle(self, *args, **options):
        deleted = cleanup_expired_documents()
        self.stdout.write(f'Deleted documents: {deleted}')
