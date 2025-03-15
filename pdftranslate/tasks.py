import threading
from PyPDF2 import PdfReader
import re
import logging
import traceback
from .gpt_service import GPTService
from .models import PDFDocument, WordEntry
import time

logger = logging.getLogger(__name__)


def clean_text(text):
    """Clean and normalize text."""
    # Remove extra whitespace
    text = ' '.join(text.split())
    # Remove special characters but keep sentence structure
    text = re.sub(r'[^\w\s.,!?-]', '', text)
    return text


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
            
            # Initialize GPT service
            logger.info("Initializing GPT service")
            try:
                gpt_service = GPTService()
                logger.info("GPT service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize GPT service: {str(e)}")
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
            
            # Extract and process text page by page
            all_words = []
            all_contexts = {}
            extracted_text = []
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                try:
                    # Extract text from page
                    text = page.extract_text()
                    cleaned_text = clean_text(text)
                    extracted_text.append(cleaned_text)
                    
                    # Extract words and context
                    analysis = gpt_service.extract_text(cleaned_text)
                    
                    # Store words and their context
                    words = analysis.get('important_words', [])
                    contexts = analysis.get('context', {})
                    
                    # Add page number to context
                    for word in words:
                        if word in contexts:
                            contexts[word] = f"Page {page_num}: {contexts[word]}"
                    
                    all_words.extend(words)
                    all_contexts.update(contexts)
                    
                    logger.info(f"Page {page_num}: Found {len(words)} words")
                    
                except Exception as e:
                    logger.error(f"Error processing page {page_num}: {str(e)}")
            
            if not all_words:
                logger.error("No words found for translation")
                document.translation_status = 'failed'
                document.save()
                return
            
            # Update document with total words
            document.total_words = len(all_words)
            document.save()
            
            # Translate words with context
            translated_words = 0
            batch_size = 5
            
            for i in range(0, len(all_words), batch_size):
                batch = all_words[i:i + batch_size]
                try:
                    translations = gpt_service.batch_translate(
                        batch,
                        target_language='Russian',
                        contexts={word: all_contexts.get(word, '') for word in batch}
                    )
                    
                    # Create WordEntry instances
                    word_entries = []
                    for word, trans in zip(batch, translations):
                        if trans:
                            word_entries.append(
                                WordEntry(
                                    document=document,
                                    original_text=word,
                                    translated_text=trans,
                                    context=all_contexts.get(word, ''),
                                    page_number=int(
                                        re.search(
                                            r'Page (\d+):',
                                            all_contexts.get(word, 'Page 1:')
                                        ).group(1)
                                    )
                                )
                            )
                            translated_words += 1
                    
                    if word_entries:
                        WordEntry.objects.bulk_create(word_entries)
                    
                    # Update progress
                    progress = int((translated_words / len(all_words)) * 100)
                    document.translation_progress = min(progress, 99)
                    document.translated_words = translated_words
                    document.save()
                    
                except Exception as e:
                    logger.error(f"Error translating batch: {str(e)}")
            
            # Save the complete extracted text
            document.extracted_text = '\n'.join(extracted_text)
            
            # Update final status
            if translated_words == 0:
                logger.error("No words were translated")
                document.translation_status = 'failed'
            else:
                logger.info(f"Translation completed. Translated {translated_words} words")
                document.translation_status = 'completed'
                document.translation_progress = 100
            
            document.save()
            
        except Exception as e:
            error_message = f"Translation task error: {str(e)}"
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