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
    level=logging.DEBUG,
    format='%(levelname)s %(asctime)s %(module)s %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
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
        
        # Test words
        test_words = ["hello", "world", "book", "language", "translation"]
        
        # Test individual translations
        logger.info("Testing individual translations")
        for word in test_words:
            try:
                translation = translation_service.translate_text(word)
                logger.info(f"'{word}' -> '{translation}'")
                if not translation:
                    logger.error(f"Translation failed for '{word}'")
            except Exception as e:
                logger.error(f"Error translating '{word}': {str(e)}")
        
        # Test batch translation
        logger.info("Testing batch translation")
        try:
            translations = translation_service.batch_translate(test_words)
            for word, translation in zip(test_words, translations):
                logger.info(f"Batch: '{word}' -> '{translation}'")
                if not translation:
                    logger.error(f"Batch translation failed for '{word}'")
        except Exception as e:
            logger.error(f"Error in batch translation: {str(e)}")
        
        logger.info("Translation service test completed")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    test_translation() 