from django.core.management.base import BaseCommand
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Clears all translation caches'

    def handle(self, *args, **options):
        try:
            # Clear all caches since we're using local memory cache
            cache.clear()
            self.stdout.write(
                self.style.SUCCESS('Successfully cleared all caches')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error clearing caches: {str(e)}')
            ) 