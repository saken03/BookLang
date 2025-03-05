from google.cloud import translate_v2 as translate
from google.api_core import retry
import os
import traceback
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class TranslationService:
    def __init__(self):
        try:
            # Check if credentials file exists
            credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'google_cred.json')
            logger.info(f"Looking for credentials at: {credentials_path}")
            
            if not os.path.exists(credentials_path):
                error_msg = "Google credentials file not found. Please place google_cred.json in the project root."
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
            
            # Check if the credentials file is valid
            with open(credentials_path, 'r') as f:
                cred_content = f.read()
                if not cred_content or len(cred_content) < 10:
                    error_msg = "Google credentials file is empty or invalid."
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            
            logger.info("Setting Google credentials environment variable")
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            
            logger.info("Initializing Google Translate client")
            self.client = translate.Client()
            logger.info("Google Translate client initialized successfully")
            
            # Test the client with a simple translation
            test_result = self.client.translate("test", target_language='ru')
            logger.info(f"Test translation successful: {test_result}")
            
        except Exception as e:
            logger.error(f"Failed to initialize translation service: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    @retry.Retry(predicate=retry.if_exception_type(Exception))
    def translate_text(self, text: str, target_language: str = 'ru') -> Optional[str]:
        """
        Translate text to target language with retry logic for API failures.
        """
        try:
            if not text or text.isspace():
                return None

            logger.debug(f"Translating text: '{text}'")
            result = self.client.translate(
                text,
                target_language=target_language,
                source_language='en'
            )
            logger.debug(f"Translation result: {result}")
            return result['translatedText']
        except Exception as e:
            logger.error(f"Translation error for text '{text}': {str(e)}")
            logger.error(traceback.format_exc())
            return None

    def batch_translate(self, texts: List[str], 
                       target_language: str = 'ru') -> List[Optional[str]]:
        """
        Translate a batch of texts with rate limiting consideration.
        Returns a list of translated texts or None for failed translations.
        """
        if not texts:
            logger.warning("Empty batch provided for translation")
            return []

        logger.info(f"Batch translating {len(texts)} texts")
        translations = []
        batch_size = 100  # Google Translate API batch size limit
        
        try:
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                logger.info(f"Processing sub-batch of {len(batch)} texts")
                
                batch_translations = []
                for text in batch:
                    try:
                        translation = self.translate_text(text, target_language)
                        batch_translations.append(translation)
                    except Exception as e:
                        logger.error(f"Error translating text '{text}': {str(e)}")
                        batch_translations.append(None)
                
                translations.extend(batch_translations)
                logger.info(f"Completed sub-batch translation")
                
            logger.info(f"Batch translation completed. Translated {len(translations)} texts.")
            return translations
        except Exception as e:
            logger.error(f"Batch translation error: {str(e)}")
            logger.error(traceback.format_exc())
            # Return None for all texts in case of batch failure
            return [None] * len(texts) 