import threading
from PyPDF2 import PdfReader
import io
import re
import logging
import traceback
from .translation_service import TranslationService
from .models import PDFDocument, WordEntry
from django.db import transaction
import time
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from celery import shared_task

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()


def clean_text(text):
    """Clean and split text into words.
    
    Filters out:
    - Numbers and special characters
    - Non-alphabetic strings
    """
    # Convert to lowercase and split into words
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    
    # Filter words and remove duplicates while preserving order
    filtered_words = []
    seen = set()
    for word in words:
        if (word.isalpha() and  # Only keep alphabetic words
            not any(c.isdigit() for c in word) and  # Remove words with numbers
            word not in seen):  # Remove duplicates
            filtered_words.append(word)
            seen.add(word)
    
    return filtered_words


def send_progress_update(document_id, progress, translated_words, total_words):
    """Send progress update through WebSocket."""
    async_to_sync(channel_layer.group_send)(
        f'translation_{document_id}',
        {
            'type': 'translation_progress',
            'progress': progress,
            'translated_words': translated_words,
            'total_words': total_words
        }
    )


class TranslationTask(threading.Thread):
    def __init__(self, document_id):
        super().__init__()
        self.document_id = document_id
        self.daemon = True

    def run(self):
        document = None
        try:
            logger.info(f"Starting translation for document {self.document_id}")
            document = PDFDocument.objects.select_for_update().get(id=self.document_id)
            
            # Set status to in_progress and send initial progress
            document.translation_status = 'in_progress'
            document.translation_progress = 0
            document.save()
            send_progress_update(self.document_id, 0, 0, 0)
            
            # Initialize translation service
            logger.info(f"Initializing translation service for document {self.document_id}")
            try:
                from .google_translate_service import GoogleTranslateService
                translation_service = GoogleTranslateService()
                logger.info(f"Google Translation service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize translation service: {str(e)}")
                document.translation_status = 'failed'
                document.save()
                send_progress_update(self.document_id, 0, 0, 0)
                return
            
            # Read PDF content
            logger.info(f"Reading PDF content for document {self.document_id}")
            try:
                pdf_reader = PdfReader(document.pdf_file)
                logger.info(f"PDF has {len(pdf_reader.pages)} pages")
            except Exception as e:
                logger.error(f"Failed to read PDF: {str(e)}")
                document.translation_status = 'failed'
                document.save()
                send_progress_update(self.document_id, 0, 0, 0)
                return
            
            # Extract all words and remember first page/position for each unique word
            all_words = []
            word_first_location = {}
            extracted_text = []
            for page_num, page in enumerate(pdf_reader.pages, 1):
                try:
                    text = page.extract_text()
                    extracted_text.append(text)
                    words = clean_text(text)
                    for pos, word in enumerate(words):
                        if word not in word_first_location:
                            word_first_location[word] = (page_num, pos)
                            all_words.append(word)
                except Exception as e:
                    logger.error(f"Error extracting text from page {page_num}: {str(e)}")
            
            if not all_words:
                logger.error(f"No words found in document {self.document_id}")
                document.translation_status = 'failed'
                document.save()
                send_progress_update(self.document_id, 0, 0, 0)
                return
            
            document.total_words = len(all_words)
            document.save()
            logger.info(f"Total unique words in document: {len(all_words)}")
            
            # Translate unique words
            translated_words = 0
            BATCH_SIZE = 100
            word_entries = []
            for i in range(0, len(all_words), BATCH_SIZE):
                batch = all_words[i:i+BATCH_SIZE]
                try:
                    translations = [translation_service.translate_word(word, target_language=document.target_language) for word in batch]
                    logger.info(f"Successfully translated batch: {translations}")
                    for word, trans in zip(batch, translations):
                        if trans:
                            page_num, pos = word_first_location[word]
                            word_entries.append(
                                WordEntry(
                                    document=document,
                                    original_text=word,
                                    translated_text=trans,
                                    page_number=page_num,
                                    position=pos
                                )
                            )
                            translated_words += 1
                    # Bulk create entries periodically
                    if len(word_entries) >= BATCH_SIZE * 2:
                        WordEntry.objects.bulk_create(word_entries)
                        word_entries = []
                    # Update progress and send update
                    progress = int((translated_words / len(all_words)) * 100)
                    document.translation_progress = min(progress, 99)
                    document.translated_words = translated_words
                    document.save()
                    send_progress_update(
                        self.document_id,
                        document.translation_progress,
                        translated_words,
                        len(all_words)
                    )
                except Exception as e:
                    logger.error(f"Error translating batch: {str(e)}")
                    logger.error(traceback.format_exc())
            # Create any remaining word entries
            if word_entries:
                WordEntry.objects.bulk_create(word_entries)
            # Save the complete extracted text
            document.extracted_text = '\n'.join(extracted_text)
            # Update final status and progress
            document.translation_status = 'completed'
            document.translation_progress = 100
            document.translated_words = translated_words
            document.save()
            # Send final progress update
            send_progress_update(self.document_id, 100, translated_words, len(all_words))
            logger.info(f"Translation completed for document {self.document_id}")
        except Exception as e:
            error_message = f"Translation task error for document {self.document_id}: {str(e)}"
            logger.error(error_message)
            logger.error(traceback.format_exc())
            try:
                if document:
                    document.translation_status = 'failed'
                    document.save()
                    send_progress_update(self.document_id, 0, 0, 0)
                else:
                    document = PDFDocument.objects.get(id=self.document_id)
                    document.translation_status = 'failed'
                    document.save()
                    send_progress_update(self.document_id, 0, 0, 0)
            except Exception as inner_e:
                logger.error(f"Failed to update document status: {str(inner_e)}")


def start_translation(document_id):
    """Start the translation process in a background thread."""
    task = TranslationTask(document_id)
    task.start()
    return task 