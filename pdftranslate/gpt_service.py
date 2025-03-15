import os
import logging
import time
import re
from typing import List, Optional, Dict, Any
from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)


class GPTService:
    """Service for interacting with OpenAI API for text processing and translation."""
    
    def __init__(self):
        try:
            api_key = getattr(
                settings, 
                'OPENAI_API_KEY', 
                os.getenv('OPENAI_API_KEY')
            )
            
            if not api_key:
                raise ValueError("OpenAI API key not found")
            
            self.client = OpenAI(api_key=api_key)
            self.last_request_time = 0
            self.min_request_interval = 5  # Reduced to 5 seconds
            logger.info("GPT service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize GPT service: {str(e)}")
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

    def extract_text(self, pdf_text: str) -> Dict[str, Any]:
        """
        Extract words from text using simple regex.
        Returns a dictionary containing words and their immediate context.
        """
        try:
            logger.debug("Extracting words from text")
            
            # Split text into sentences
            sentences = re.split(r'[.!?]+', pdf_text)
            words = {}
            contexts = {}
            
            # Extract words and their context
            for sentence in sentences:
                # Clean the sentence
                clean_sentence = sentence.strip()
                if not clean_sentence:
                    continue
                    
                # Extract words (3+ characters)
                found_words = re.findall(r'\b\w{3,}\b', clean_sentence.lower())
                
                # Store unique words with their context
                for word in found_words:
                    if word not in words:
                        words[word] = True
                        contexts[word] = clean_sentence
            
            return {
                'important_words': list(words.keys()),
                'context': contexts,
            }
            
        except Exception as e:
            logger.error(f"Text extraction error: {str(e)}")
            return {
                "important_words": [],
                "context": {},
            }

    def translate_text(self, text: str, target_language: str = 'Russian') -> Optional[str]:
        """Translate text using GPT."""
        if not text or text.isspace():
            return None
        
        try:
            logger.debug(f"Translating: '{text}' to {target_language}")
            self._wait_for_rate_limit()
            
            prompt = (
                f"Translate this English text to {target_language}. "
                f"Return ONLY the translation:\n{text}"
            )
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{
                    "role": "system",
                    "content": "You are a translator. Respond only with translations."
                }, {
                    "role": "user",
                    "content": prompt
                }],
                temperature=0.1,
                max_tokens=200
            )
            
            translation = response.choices[0].message.content.strip()
            logger.debug(f"Translation result: {translation}")
            
            return translation
            
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            if 'rate_limit' in str(e).lower():
                logger.info("Rate limit hit, retrying after delay")
                time.sleep(self.min_request_interval)
                return self.translate_text(text, target_language)
            return None

    def batch_translate(self, texts: List[str], 
                       target_language: str = 'Russian',
                       contexts: Optional[Dict[str, str]] = None) -> List[Optional[str]]:
        """
        Translate a batch of texts efficiently.
        Optionally includes context for better translation accuracy.
        """
        if not texts:
            return []
        
        logger.info(f"Batch translating {len(texts)} items")
        
        try:
            # For small batches, combine in one prompt
            if len(texts) <= 5:
                self._wait_for_rate_limit()
                
                # Create list of texts with context if available
                items = []
                for i, text in enumerate(texts):
                    context = contexts.get(text, "") if contexts else ""
                    item = f"{i+1}. {text}"
                    if context:
                        item += f" (Context: {context})"
                    items.append(item)
                
                word_list = "\n".join(items)
                prompt = (
                    f"Translate these English words to {target_language}.\n"
                    "If context is provided, use it for accurate translation.\n"
                    f"Return ONLY the numbered translations:\n{word_list}"
                )
                
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{
                        "role": "system",
                        "content": "You are a translator. Respond with numbered translations."
                    }, {
                        "role": "user",
                        "content": prompt
                    }],
                    temperature=0.1,
                    max_tokens=200
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
                        translations[i] = self.translate_text(
                            texts[i], 
                            target_language
                        )
                
                return translations
            
            # For larger batches, process in smaller chunks
            translations = []
            batch_size = 5
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_contexts = None
                if contexts:
                    batch_contexts = {
                        text: contexts[text] 
                        for text in batch 
                        if text in contexts
                    }
                batch_trans = self.batch_translate(
                    batch, 
                    target_language,
                    batch_contexts
                )
                translations.extend(batch_trans)
            
            return translations
            
        except Exception as e:
            logger.error(f"Batch translation error: {str(e)}")
            if 'rate_limit' in str(e).lower():
                logger.info("Rate limit hit, retrying after delay")
                time.sleep(self.min_request_interval)
                return self.batch_translate(texts, target_language, contexts)
            return [None] * len(texts) 