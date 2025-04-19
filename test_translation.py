#!/usr/bin/env python
"""
Test script for the translation service.
Run this script to verify that the translation service is working correctly.
"""

import os
import sys
import django
import logging

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookland.settings')
django.setup()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Import the translation service
from pdftranslate.translation_service import TranslationService

def test_translation():
    """Test the translation service with a few simple words."""
    logger.info("Starting translation service test")
    
    try:
        # Initialize the translation service
        logger.info("Initializing translation service")
        translation_service = TranslationService()
        
        # Test languages and words
        test_cases = [
            ("en", "ru", ["hello", "world", "book"]),
            ("en", "es", ["computer", "programming", "language"]),
            ("en", "fr", ["artificial", "intelligence", "learning"])
        ]
        
        # Test translations
        for source_lang, target_lang, words in test_cases:
            logger.info(f"\nTesting translation from {source_lang} to {target_lang}")
            
            # Test batch translation
            try:
                translations = translation_service.batch_translate(words, target_lang)
                for word, translation in zip(words, translations):
                    logger.info(f"'{word}' -> '{translation}'")
                    if not translation:
                        logger.error(f"Translation failed for '{word}'")
            except Exception as e:
                logger.error(f"Error in batch translation: {str(e)}")
        
        logger.info("\nTranslation service test completed")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    test_translation() 