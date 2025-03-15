import os
import logging
import time
from typing import List, Optional
from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)

class OpenAIService:
    """Service for interacting with OpenAI API for translation."""
    
    def __init__(self):
        """Initialize the OpenAI client with API key from settings."""
        try:
            api_key = getattr(
                settings, 
                'OPENAI_API_KEY', 
                os.getenv('OPENAI_API_KEY')
            )
            
            if not api_key:
                raise ValueError("OpenAI API key not found")
            
            # Initialize the client
            self.client = OpenAI(api_key=api_key)
            self.last_request_time = 0
            self.min_request_interval = 20  
            logger.info("OpenAI service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI service: {str(e)}")
            raise
    
    def _wait_for_rate_limit(self):
        """Wait if needed to respect rate limits."""
        now = time.time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.debug(f"Rate limit: sleeping for {sleep_time:.1f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def translate_text(self, text: str, target_language: str = 'Russian') -> Optional[str]:
        """Translate a single word using GPT-3.5."""
        if not text or text.isspace():
            return None
        
        try:
            logger.debug(f"Translating word: '{text}' to {target_language}")
            self._wait_for_rate_limit()
            
            prompt = (
                f"You are a precise translator. Translate this English word "
                f"to {target_language}. Return ONLY the translation:\n{text}"
            )
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",  # Using GPT-3.5 model
                messages=[{
                    "role": "system",
                    "content": "You are a translator. Respond only with translations."
                }, {
                    "role": "user",
                    "content": prompt
                }],
                temperature=0.1,  # Very low temperature for consistent translations
                max_tokens=10     # Short response for single words
            )
            
            translation = response.choices[0].message.content.strip()
            logger.debug(f"Translation result: {translation}")
            
            return translation
            
        except Exception as e:
            logger.error(f"Translation error for word '{text}': {str(e)}")
            if 'rate_limit' in str(e).lower():
                logger.info("Rate limit hit, retrying after delay")
                time.sleep(self.min_request_interval)
                return self.translate_text(text, target_language)
            return None
    
    def batch_translate(self, texts: List[str], target_language: str = 'Russian') -> List[Optional[str]]:
        """Translate a batch of words efficiently."""
        if not texts:
            return []
        
        logger.info(f"Batch translating {len(texts)} words")
        
        try:
            # For small batches, combine in one prompt
            if len(texts) <= 5:  # Reduced batch size
                self._wait_for_rate_limit()
                word_list = "\n".join(f"{i+1}. {text}" for i, text in enumerate(texts))
                prompt = (
                    f"Translate these English words to {target_language}.\n"
                    f"Return ONLY the numbered translations:\n{word_list}"
                )
                
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",  # Using GPT-3.5 model
                    messages=[{
                        "role": "system",
                        "content": "You are a translator. Respond with numbered translations."
                    }, {
                        "role": "user",
                        "content": prompt
                    }],
                    temperature=0.1,
                    max_tokens=100
                )
                
                result = response.choices[0].message.content.strip()
                translations = [""] * len(texts)
                
                # Parse numbered responses
                for line in result.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    
                    parts = line.split('.', 1)
                    if len(parts) == 2 and parts[0].strip().isdigit():
                        idx = int(parts[0].strip()) - 1
                        if 0 <= idx < len(texts):
                            translations[idx] = parts[1].strip()
                
                # Fill any missing translations
                for i, trans in enumerate(translations):
                    if not trans and i < len(texts):
                        translations[i] = self.translate_text(texts[i], 
                                                           target_language)
                
                return translations
            
            translations = []
            batch_size = 5  # Smaller batch size
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_trans = self.batch_translate(batch, target_language)
                translations.extend(batch_trans)
            
            return translations
            
        except Exception as e:
            logger.error(f"Batch translation error: {str(e)}")
            if 'rate_limit' in str(e).lower():
                logger.info("Rate limit hit, retrying after delay")
                time.sleep(self.min_request_interval)
                return self.batch_translate(texts, target_language)
            return [None] * len(texts) 