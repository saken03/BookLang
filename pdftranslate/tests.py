from django.test import TestCase
from django.core.cache import cache
from .translation_service import TranslationService


class CacheTest(TestCase):
    def setUp(self):
        self.translation_service = TranslationService()

    def test_cache_connection(self):
        """Test that Redis cache is working"""
        # Test basic cache operations
        test_key = 'test_key'
        test_value = 'test_value'
        
        # Set a value
        cache.set(test_key, test_value, timeout=60)
        
        # Get the value
        retrieved_value = cache.get(test_key)
        
        # Verify
        self.assertEqual(retrieved_value, test_value)
        
    def test_translation_cache(self):
        """Test that translations are being cached"""
        words = ['hello', 'world']
        
        # First translation (should hit API)
        translations1 = self.translation_service.batch_translate(words)
        
        # Second translation (should hit cache)
        translations2 = self.translation_service.batch_translate(words)
        
        # Verify we got the same translations
        self.assertEqual(translations1, translations2)
        
        # Verify the translations are not None
        self.assertNotIn(None, translations1)
        self.assertNotIn(None, translations2)
