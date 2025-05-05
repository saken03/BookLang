from google.cloud import translate_v2 as translate
import os

class GoogleTranslateService:
    def __init__(self):
        self.client = translate.Client()

    def translate_word(self, word, target_language='ru', source_language='en'):
        result = self.client.translate(
            word,
            target_language=target_language,
            source_language=source_language,
            format_='text'
        )
        return result['translatedText'] 