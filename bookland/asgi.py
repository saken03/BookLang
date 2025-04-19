"""
ASGI config for bookland project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
import django

# Set up Django settings before importing other modules
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookland.settings')
django.setup()  # Initialize Django

# Import after Django setup
from django.core.asgi import get_asgi_application

application = get_asgi_application()
