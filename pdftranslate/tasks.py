import threading
from PyPDF2 import PdfReader
import io
import re
import logging
from .translation_service import TranslationService
from .models import PDFDocument, WordEntry
from django.db import transaction

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
        try:
            document = PDFDocument.objects.select_for_update().get(id=self.document_id)
            
            # Set status to in_progress
            document.translation_status = 'in_progress'
            document.save()
            
            # Initialize translation service
            translation_service = TranslationService()
            
            # Read PDF content
            pdf_reader = PdfReader(document.pdf_file)
            
            # First pass: count total words
            total_words = 0
            for page in pdf_reader.pages:
                text = page.extract_text()
                words = clean_text(text)
                total_words += len(words)
            
            document.total_words = total_words
            document.save()
            
            # Second pass: translate words
            translated_words = 0
            extracted_text = []
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                text = page.extract_text()
                extracted_text.append(text)
                
                words = clean_text(text)
                if words:
                    translations = translation_service.batch_translate(words)
                    
                    # Create WordEntry instances
                    word_entries = []
                    for pos, (word, trans) in enumerate(zip(words, translations)):
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
                    
                    # Update progress
                    progress = int((translated_words / total_words) * 100)
                    document.translation_progress = min(progress, 99)  # Keep at 99% until fully complete
                    document.translated_words = translated_words
                    document.save()
            
            # Save the complete extracted text
            document.extracted_text = '\n'.join(extracted_text)
            
            # Update final status
            if translated_words == 0:
                document.translation_status = 'failed'
            else:
                document.translation_status = 'completed'
                document.translation_progress = 100
            
            document.save()
            
        except Exception as e:
            logger.error(f"Translation task error for document {self.document_id}: {str(e)}")
            try:
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