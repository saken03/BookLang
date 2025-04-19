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

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()


def clean_text(text):
    """Clean and split text into words."""
    words = re.findall(r'\b\w+\b', text.lower())
    return [w for w in words if len(w) > 1]


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
                translation_service = TranslationService()
                logger.info(f"Translation service initialized successfully")
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
            
            # First pass: count total words
            logger.info(f"Counting words in document {self.document_id}")
            total_words = 0
            words_by_page = []
            for page_num, page in enumerate(pdf_reader.pages, 1):
                try:
                    text = page.extract_text()
                    page_words = clean_text(text)
                    words_by_page.append(page_words)
                    total_words += len(page_words)
                    logger.info(f"Page {page_num}: Found {len(page_words)} words")
                except Exception as e:
                    logger.error(f"Error extracting text from page {page_num}: {str(e)}")
            
            if total_words == 0:
                logger.error(f"No words found in document {self.document_id}")
                document.translation_status = 'failed'
                document.save()
                send_progress_update(self.document_id, 0, 0, 0)
                return
                
            document.total_words = total_words
            document.save()
            logger.info(f"Total words in document: {total_words}")
            
            # Second pass: translate words with progress updates
            translated_words = 0
            extracted_text = []
            
            # Configuration for batch processing
            BATCH_SIZE = 50  # Increased from 5 to 50
            word_entries = []  # Collect entries for bulk creation
            
            for page_num, words in enumerate(words_by_page, 1):
                text = pdf_reader.pages[page_num - 1].extract_text()
                extracted_text.append(text)
                
                if words:
                    # Process in larger batches
                    for i in range(0, len(words), BATCH_SIZE):
                        batch = words[i:i + BATCH_SIZE]
                        logger.info(
                            f"Translating batch of {len(batch)} words from page {page_num}"
                        )
                        
                        try:
                            translations = translation_service.batch_translate(
                                batch,
                                target_lang=document.target_language
                            )
                            logger.info(f"Successfully translated batch: {translations}")
                            
                            # Create WordEntry instances for this batch
                            for pos, (word, trans) in enumerate(zip(batch, translations), start=i):
                                if trans:
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
                            
                            # Update progress and send update
                            progress = int((translated_words / total_words) * 100)
                            document.translation_progress = min(progress, 99)
                            document.translated_words = translated_words
                            document.save()
                            send_progress_update(
                                self.document_id,
                                document.translation_progress,
                                translated_words,
                                total_words
                            )
                            
                            # Bulk create entries periodically
                            if len(word_entries) >= BATCH_SIZE * 5:
                                WordEntry.objects.bulk_create(word_entries)
                                word_entries = []
                            
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
            send_progress_update(self.document_id, 100, translated_words, total_words)
            
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