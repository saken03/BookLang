from google.cloud import translate_v2 as translate
from google.api_core import retry
import os
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class TranslationService:
    def __init__(self):
        try:
            # Check if credentials file exists
            credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'google_cred.json')
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    "Google credentials file not found. Please place google_cred.json in the project root."
                )
            
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            self.client = translate.Client()
        except Exception as e:
            logger.error(f"Failed to initialize translation service: {str(e)}")
            raise

    @retry.Retry(predicate=retry.if_exception_type(Exception))
    def translate_text(self, text: str, target_language: str = 'ru') -> Optional[str]:
        """
        Translate text to target language with retry logic for API failures.
        """
        try:
            if not text or text.isspace():
                return None

            result = self.client.translate(
                text,
                target_language=target_language,
                source_language='en'
            )
            return result['translatedText']
        except Exception as e:
            logger.error(f"Translation error for text '{text}': {str(e)}")
            return None

    def batch_translate(self, texts: List[str], 
                       target_language: str = 'ru') -> List[Optional[str]]:
        """
        Translate a batch of texts with rate limiting consideration.
        Returns a list of translated texts or None for failed translations.
        """
        if not texts:
            return []

        translations = []
        batch_size = 100  # Google Translate API batch size limit
        
        try:
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_translations = [
                    self.translate_text(text, target_language) 
                    for text in batch
                ]
                translations.extend(batch_translations)
                
            return translations
        except Exception as e:
            logger.error(f"Batch translation error: {str(e)}")
            # Return None for all texts in case of batch failure
            return [None] * len(texts) 