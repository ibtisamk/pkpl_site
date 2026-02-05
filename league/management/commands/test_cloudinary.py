from django.core.management.base import BaseCommand
from django.conf import settings
import cloudinary
import cloudinary.uploader

class Command(BaseCommand):
    help = 'Test Cloudinary configuration'

    def handle(self, *args, **options):
        self.stdout.write('=' * 50)
        self.stdout.write('CLOUDINARY CONFIGURATION TEST')
        self.stdout.write('=' * 50)
        
        # Check settings
        self.stdout.write(f'\nDEFAULT_FILE_STORAGE: {settings.DEFAULT_FILE_STORAGE}')
        
        # Check cloudinary config
        config = cloudinary.config()
        self.stdout.write(f'\nCloudinary Cloud Name: {config.cloud_name}')
        self.stdout.write(f'Cloudinary API Key: {config.api_key[:10]}...' if config.api_key else 'Not set')
        self.stdout.write(f'Cloudinary API Secret: {"Set" if config.api_secret else "Not set"}')
        
        # Check if cloudinary_storage is in INSTALLED_APPS
        if 'cloudinary_storage' in settings.INSTALLED_APPS:
            self.stdout.write('\n✓ cloudinary_storage is in INSTALLED_APPS')
        else:
            self.stdout.write('\n✗ cloudinary_storage is NOT in INSTALLED_APPS')
        
        self.stdout.write('\n' + '=' * 50)
