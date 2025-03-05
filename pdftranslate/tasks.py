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

logger = logging.getLogger(__name__)


def clean_text(text):
    """Clean and split text into words."""
    words = re.findall(r'\b\w+\b', text.lower())
    return [w for w in words if len(w) > 1]


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
            
            # Set status to in_progress
            document.translation_status = 'in_progress'
            document.save()
            
            # Initialize translation service
            logger.info(f"Initializing translation service for document {self.document_id}")
            try:
                translation_service = TranslationService()
                logger.info(f"Translation service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize translation service: {str(e)}")
                document.translation_status = 'failed'
                document.save()
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
                return
                
            document.total_words = total_words
            document.save()
            logger.info(f"Total words in document: {total_words}")
            
            # Second pass: translate words with progress updates
            translated_words = 0
            extracted_text = []
            
            for page_num, words in enumerate(words_by_page, 1):
                text = pdf_reader.pages[page_num - 1].extract_text()
                extracted_text.append(text)
                
                if words:
                    # Translate in smaller batches for more frequent updates
                    batch_size = 5  # Translate 5 words at a time
                    for i in range(0, len(words), batch_size):
                        batch = words[i:i + batch_size]
                        logger.info(f"Translating batch of {len(batch)} words from page {page_num}")
                        
                        try:
                            translations = translation_service.batch_translate(batch)
                            logger.info(f"Successfully translated batch: {translations}")
                            
                            # Create WordEntry instances for this batch
                            word_entries = []
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
                            
                            if word_entries:
                                WordEntry.objects.bulk_create(word_entries)
                            
                            # Update progress more frequently
                            progress = int((translated_words / total_words) * 100)
                            document.translation_progress = min(progress, 99)
                            document.translated_words = translated_words
                            document.save()
                            
                            # Add a small delay to make progress visible
                            time.sleep(0.5)
                        except Exception as e:
                            logger.error(f"Error translating batch: {str(e)}")
                            logger.error(traceback.format_exc())
            
            # Save the complete extracted text
            document.extracted_text = '\n'.join(extracted_text)
            
            # Update final status
            if translated_words == 0:
                logger.error(f"No words were translated for document {self.document_id}")
                document.translation_status = 'failed'
            else:
                logger.info(f"Translation completed for document {self.document_id}. Translated {translated_words} words.")
                document.translation_status = 'completed'
                document.translation_progress = 100
            
            document.save()
            
        except Exception as e:
            error_message = f"Translation task error for document {self.document_id}: {str(e)}"
            logger.error(error_message)
            logger.error(traceback.format_exc())
            try:
                if document:
                    document.translation_status = 'failed'
                    document.save()
                else:
                    document = PDFDocument.objects.get(id=self.document_id)
                    document.translation_status = 'failed'
                    document.save()
            except Exception as inner_e:
                logger.error(f"Failed to update document status: {str(inner_e)}")


def start_translation(document_id):
    """Start the translation process in a background thread."""
    task = TranslationTask(document_id)
    task.start()
    return task 