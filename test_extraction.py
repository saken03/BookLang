#!/usr/bin/env python
"""Test script for GPT text extraction."""

import os
import django
import logging

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookland.settings')
django.setup()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from pdftranslate.gpt_service import GPTService

def test_extraction():
    """Test text extraction and analysis functionality."""
    try:
        # Initialize the service
        service = GPTService()
        
        # Test text
        sample_text = """
        The artificial intelligence revolution has transformed various sectors of the economy. 
        Machine learning algorithms now power recommendation systems, autonomous vehicles, 
        and natural language processing applications. Deep neural networks have achieved 
        remarkable results in image recognition and language translation tasks.
        """
        
        # Test text extraction
        print("\nTesting text extraction and analysis:")
        analysis = service.extract_text(sample_text)
        
        print("\nImportant words:")
        for word in analysis['important_words']:
            context = analysis['context'].get(word, 'No context available')
            print(f"- {word}")
            print(f"  Context: {context}")
        
        print("\nSummary:")
        print(analysis['summary'])
        
        # Test translation of extracted words
        print("\nTesting translation of important words:")
        translations = service.batch_translate(
            analysis['important_words'],
            contexts=analysis['context']
        )
        
        print("\nTranslations:")
        for word, trans in zip(analysis['important_words'], translations):
            print(f"{word} -> {trans}")
            
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")

if __name__ == "__main__":
    test_extraction() 