#!/usr/bin/env python
"""Test script for word translation using OpenAI."""

import os
import django
import logging

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookland.settings')
django.setup()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from pdftranslate.openai_service import OpenAIService

def test_word_translation():
    """Test basic word translation functionality."""
    try:
        # Initialize the service
        service = OpenAIService()
        
        # Test single words
        test_words = ["hello", "world", "book", "language", "computer"]
        
        # Test individual translations
        print("\nTesting individual word translations:")
        for word in test_words:
            translation = service.translate_text(word)
            print(f"{word} -> {translation}")
        
        # Test batch translation
        print("\nTesting batch translation:")
        translations = service.batch_translate(test_words)
        for word, translation in zip(test_words, translations):
            print(f"{word} -> {translation}")
            
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")

if __name__ == "__main__":
    test_word_translation() 