import logging
import os
import json
from openai import OpenAI
from django.core.cache import cache
from tenacity import retry, stop_after_attempt, wait_exponential


# Add an extra blank line here to satisfy the linter requirement


logger = logging.getLogger(__name__)


class TranslationService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        if self.client.api_key:
            logger.info("Successfully initialized OpenAI API")
        else:
            msg = "OpenAI API key not found in environment variables"
            logger.error(f"Failed to initialize OpenAI API: {msg}")
            raise ValueError(msg)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def batch_translate(self, texts, source_lang='en', target_lang='ru'):
        """
        Translate a batch of texts using OpenAI's API with optimized batching
        and caching. Only translates valid words (alphabetic).
        """
        try:
            # Filter out invalid words
            valid_texts = [
                text for text in texts
                if text and isinstance(text, str) and text.isalpha()
            ]
            
            if not valid_texts:
                logger.warning("No valid words to translate in batch")
                return [None] * len(texts)
            
            # Check cache first
            key_parts = [
                'translation',
                source_lang,
                target_lang,
                str(hash(tuple(valid_texts)))
            ]
            cache_key = '_'.join(key_parts)
            cached = cache.get(cache_key)
            if cached:
                logger.info("Retrieved translations from cache")
                # Map cached translations back to original texts
                result = []
                valid_idx = 0
                for text in texts:
                    if (text and isinstance(text, str) and text.isalpha()):
                        result.append(cached[valid_idx])
                        valid_idx += 1
                    else:
                        result.append(None)
                return result

            logger.info("Batch translating %d words", len(valid_texts))
            
            # Prepare optimized prompt
            prompt = (
                f"Translate these {len(valid_texts)} words from {source_lang} "
                f"to {target_lang}. Return translations in JSON format: "
                "{'translations': ['word1', 'word2', ...]}\n\n"
                f"Words: {', '.join(valid_texts)}"
            )

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )

            # Parse response
            try:
                content = response.choices[0].message.content
                result = json.loads(content)
                translations = result.get('translations', [])
                
                # Ensure we have the same number of translations as valid texts
                if len(translations) < len(valid_texts):
                    logger.warning(
                        "Received fewer translations than expected. "
                        "Padding with None."
                    )
                    translations.extend(
                        [None] * (len(valid_texts) - len(translations))
                    )
                elif len(translations) > len(valid_texts):
                    logger.warning("Received extra translations. Truncating.")
                    translations = translations[:len(valid_texts)]

                # Cache successful translations
                cache.set(cache_key, translations, timeout=3600)
                
                # Map translations back to original texts
                result = []
                valid_idx = 0
                for text in texts:
                    if (text and isinstance(text, str) and text.isalpha()):
                        result.append(translations[valid_idx])
                        valid_idx += 1
                    else:
                        result.append(None)
                return result

            except (json.JSONDecodeError, KeyError, AttributeError) as e:
                logger.error(
                    "Failed to parse translation response: %s", e
                )
                raise ValueError(
                    "Invalid response format from translation API"
                )

        except Exception as e:
            logger.error("Translation failed: %s", e)
            raise 