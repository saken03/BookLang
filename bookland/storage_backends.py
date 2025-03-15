"""
Storage backends for handling static and media files in production.
"""

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class StaticStorage(S3Boto3Storage):
    """Storage backend for static files."""
    location = 'static'
    default_acl = 'public-read'


class MediaStorage(S3Boto3Storage):
    """Storage backend for media files."""
    location = 'media'
    default_acl = 'public-read'
    file_overwrite = False 