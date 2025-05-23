from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.files.storage import default_storage
from django.http import JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.db.models import Q
from .models import PDFDocument, WordEntry, Flashcard
from .tasks import start_translation
from PyPDF2 import PdfReader
import io
import re
import logging
import os
from datetime import datetime, timedelta
from django.db import models
import json
import asyncio
import time
from django.core.paginator import Paginator

logger = logging.getLogger(__name__)

# Create your views here.

def clean_text(text):
    """Clean and split text into words."""
    # Remove special characters and split into words
    words = re.findall(r'\b\w+\b', text.lower())
    return [w for w in words if len(w) > 1]  # Filter out single characters

def logout_view(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('login')

def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('pdf_list')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    return render(request, 'pdftranslate/signup.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {username}!')
            return redirect('pdf_list')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'pdftranslate/login.html')

@login_required
def delete_pdf(request, pk):
    """Delete a PDF document and its associated files."""
    document = get_object_or_404(PDFDocument, pk=pk, user=request.user)
    
    try:
        # Delete the actual file from storage
        if document.pdf_file and os.path.exists(document.pdf_file.path):
            os.remove(document.pdf_file.path)
        
        # Delete the database record (this will cascade delete WordEntries)
        document.delete()
        messages.success(request, f'"{document.title}" has been deleted.')
    except Exception as e:
        logger.error(f"Error deleting PDF {document.title}: {str(e)}")
        messages.error(request, 'Error deleting the PDF file.')
    
    return redirect('pdf_list')

@login_required
def upload_pdf(request):
    if request.method == 'POST':
        if 'pdf_file' not in request.FILES:
            messages.error(request, 'No file was uploaded.')
            return redirect('upload_pdf')
        
        pdf_file = request.FILES['pdf_file']
        target_language = request.POST.get('target_language', 'ru')
        
        # Check if it's actually a PDF file
        if not pdf_file.name.lower().endswith('.pdf'):
            messages.error(request, 'Please upload a PDF file.')
            return redirect('upload_pdf')
        
        try:
            # Read the file content once
            file_content = pdf_file.read()
            
            # Try to parse it as PDF to validate
            try:
                pdf_reader = PdfReader(io.BytesIO(file_content))
                if len(pdf_reader.pages) == 0:
                    raise ValueError("The PDF file appears to be empty")
            except Exception as e:
                logger.error(f"Invalid PDF file: {str(e)}")
                messages.error(
                    request,
                    'The file appears to be invalid or corrupted.'
                )
                return redirect('upload_pdf')
            
            # Create PDFDocument instance
            document = PDFDocument.objects.create(
                user=request.user,
                title=pdf_file.name,
                target_language=target_language,
                translation_status='pending'
            )
            
            # Save the file using default storage
            file_name = default_storage.save(
                f'pdfs/{request.user.id}/{document.id}/{pdf_file.name}',
                io.BytesIO(file_content)
            )
            document.pdf_file.name = file_name
            document.save()
            
            # Start translation in background
            start_translation(document.id)
            
            messages.success(
                request,
                'PDF uploaded successfully. Translation in progress...'
            )
            
        except Exception as e:
            messages.error(
                request,
                'An unexpected error occurred. Please try again.'
            )
            logger.error(
                f"Unexpected error processing {pdf_file.name}: {str(e)}"
            )
        
        return redirect('pdf_list')
    
    # For GET requests, pass language choices to the template
    context = {
        'language_choices': PDFDocument.LANGUAGE_CHOICES
    }
    return render(request, 'pdftranslate/upload.html', context)

@login_required
def get_translation_progress(request, pk):
    """AJAX endpoint to get translation progress."""
    try:
        document = PDFDocument.objects.get(pk=pk, user=request.user)
        return JsonResponse({
            'status': document.translation_status,
            'progress': document.translation_progress,
            'total_words': document.total_words,
            'translated_words': document.translated_words
        })
    except PDFDocument.DoesNotExist:
        return JsonResponse({'error': 'Document not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting progress: {str(e)}")
        return JsonResponse(
            {'error': 'Failed to get progress'},
            status=500
        )

@login_required
def pdf_list(request):
    documents = PDFDocument.objects.filter(user=request.user).prefetch_related('words').all()
    context = {'documents': documents}
    return render(request, 'pdftranslate/pdf_list.html', context)

@login_required
def flashcard_list(request):
    now = timezone.now()
    document_id = request.GET.get('document_id')
    page = request.GET.get('page', 1)
    
    # Get all user's documents that have flashcards
    user_documents = PDFDocument.objects.filter(
        user=request.user,
        words__flashcard__isnull=False
    ).distinct()
    
    # Base queryset
    if document_id:
        flashcards = Flashcard.objects.filter(word_entry__document_id=document_id, user=request.user)
    else:
        # If no document selected, show the first document's flashcards
        if user_documents.exists():
            first_doc = user_documents.first()
            flashcards = Flashcard.objects.filter(word_entry__document=first_doc, user=request.user)
            document_id = first_doc.id
        else:
            flashcards = Flashcard.objects.none()
    
    # Get statistics for the selected document
    total_cards = flashcards.count()
    cards_due = flashcards.filter(next_review__lte=now).count()
    cards_learned = flashcards.filter(review_count__gt=0).count()
    cards_mastered = flashcards.filter(review_count__gte=5).count()
    
    # Pagination
    paginator = Paginator(flashcards, 12)  # Show 12 cards per page
    try:
        flashcards_page = paginator.page(page)
    except:
        flashcards_page = paginator.page(1)
    
    # Calculate progress for each flashcard
    for card in flashcards_page:
        card.progress = min(100, (card.review_count or 0) * 20)
    
    context = {
        'flashcards': flashcards_page,
        'total_cards': total_cards,
        'cards_due': cards_due,
        'cards_learned': cards_learned,
        'cards_mastered': cards_mastered,
        'paginator': paginator,
        'page_obj': flashcards_page,
        'documents': user_documents,
        'selected_document_id': document_id,
    }
    return render(request, 'pdftranslate/flashcard_list.html', context)

@login_required
def flashcard_review(request, pk=None):
    """Review a specific flashcard or get the next due card."""
    now = timezone.now()
    
    if request.method == 'POST':
        # Handle review submission
        flashcard = get_object_or_404(
            Flashcard,
            pk=request.POST.get('flashcard_id'),
            user=request.user
        )
        
        # Get the interval and determine if remembered
        interval = request.POST.get('interval', 'good')
        remembered = request.POST.get('remembered', '').lower() == 'true'
        
        # Calculate next review time based on interval
        if interval == 'again':
            next_review = now + timedelta(minutes=10)
            remembered = False
        elif interval == 'hard':
            next_review = now + timedelta(minutes=15)
            remembered = False
        elif interval == 'good':
            next_review = now + timedelta(days=1)
            remembered = True
        else:  # easy
            next_review = now + timedelta(days=2)
            remembered = True
        
        # Update flashcard
        flashcard.last_reviewed = now
        flashcard.next_review = next_review
        if remembered:
            flashcard.review_count += 1
        else:
            flashcard.review_count = max(0, flashcard.review_count - 1)
        flashcard.save()
        
        # Find the next card to review
        next_card = Flashcard.objects.filter(
            user=request.user,
            next_review__lte=now
        ).exclude(pk=flashcard.pk).first()
        
        if next_card:
            return redirect('flashcard_review', pk=next_card.pk)
        else:
            return redirect('flashcard_list')
    
    # GET request - show the next card
    if pk is None:
        # Get the next due card
        flashcard = Flashcard.objects.filter(
            user=request.user,
            next_review__lte=now
        ).first()
        if not flashcard:
            messages.info(request, 'No cards due for review at this time.')
            return redirect('flashcard_list')
    else:
        # Get the specific card
        flashcard = get_object_or_404(Flashcard, pk=pk, user=request.user)
    
    # Get progress information
    total_due = Flashcard.objects.filter(
        user=request.user,
        next_review__lte=now
    ).count()
    reviewed_today = Flashcard.objects.filter(
        user=request.user,
        last_reviewed__date=now.date()
    ).count()
    cards_remaining_today = max(0, total_due - reviewed_today)
    
    context = {
        'flashcard': flashcard,
        'total_due': total_due,
        'reviewed_today': reviewed_today,
        'cards_remaining_today': cards_remaining_today,
    }
    return render(request, 'pdftranslate/flashcard_review.html', context)

@login_required
def create_flashcards(request, document_id):
    """Create flashcards for all translated words in a document."""
    document = get_object_or_404(PDFDocument, pk=document_id, user=request.user)
    
    # Create flashcards using the new method
    created_count = document.create_all_flashcards(request.user)
    
    if created_count > 0:
        messages.success(
            request,
            f'Created {created_count} new flashcards from "{document.title}"'
        )
    else:
        messages.info(
            request,
            'No new flashcards to create. All translated words already have flashcards.'
        )
    
    return redirect('flashcard_list')

@login_required
def flashcard_dashboard(request):
    """Display detailed flashcard statistics and progress."""
    now = timezone.now()
    today = now.date()
    
    # Get all user's flashcards
    user_flashcards = Flashcard.objects.filter(user=request.user)
    
    # Today's statistics
    cards_due_today = user_flashcards.filter(next_review__date=today).count()
    cards_reviewed_today = user_flashcards.filter(last_reviewed__date=today).count()
    cards_remaining_today = max(0, cards_due_today - cards_reviewed_today)
    
    # Overall statistics
    total_cards = user_flashcards.count()
    cards_learned = user_flashcards.filter(review_count__gt=0).count()
    cards_mastered = user_flashcards.filter(review_count__gte=5).count()
    
    # Review streak
    current_streak = 0
    check_date = today
    while user_flashcards.filter(last_reviewed__date=check_date).exists():
        current_streak += 1
        check_date -= timedelta(days=1)
    
    # Next due dates
    upcoming_reviews = (
        user_flashcards
        .filter(next_review__gt=now)
        .values('next_review__date')
        .annotate(count=models.Count('id'))
        .order_by('next_review__date')[:7]
    )
    
    context = {
        'cards_due_today': cards_due_today,
        'cards_reviewed_today': cards_reviewed_today,
        'cards_remaining_today': cards_remaining_today,
        'total_cards': total_cards,
        'cards_learned': cards_learned,
        'cards_mastered': cards_mastered,
        'current_streak': current_streak,
        'upcoming_reviews': upcoming_reviews,
        'completion_rate': int((cards_reviewed_today / cards_due_today * 100) if cards_due_today > 0 else 100),
    }
    
    return render(request, 'pdftranslate/flashcard_dashboard.html', context)

@login_required
def reset_flashcard(request, pk):
    """Reset a flashcard's progress."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    flashcard = get_object_or_404(Flashcard, pk=pk, user=request.user)
    flashcard.reset()
    
    return JsonResponse({
        'status': 'success',
        'message': 'Flashcard has been reset'
    })

@login_required
def sse_progress(request, document_id):
    """Server-Sent Events endpoint for translation progress."""
    def event_stream():
        document = get_object_or_404(PDFDocument, id=document_id, user=request.user)
        last_progress = -1
        
        while True:
            try:
                # Get current progress
                document.refresh_from_db()
                current_progress = document.translation_progress
                current_words = document.translated_words
                total_words = document.total_words
                status = document.translation_status
                
                # Send initial state and heartbeat
                if last_progress == -1:
                    yield f"event: state\ndata: {json.dumps({'status': status, 'progress': current_progress, 'translated_words': current_words, 'total_words': total_words})}\n\n"
                    yield "event: heartbeat\ndata: ping\n\n"
                
                # Only send update if progress changed
                elif current_progress != last_progress:
                    data = {
                        'status': status,
                        'progress': current_progress,
                        'translated_words': current_words,
                        'total_words': total_words
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                else:
                    # Send heartbeat every 15 seconds to keep connection alive
                    yield "event: heartbeat\ndata: ping\n\n"
                
                last_progress = current_progress
                
                # Stop if translation is complete or failed
                if status in ['completed', 'failed']:
                    break
                
                # Wait before next check
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error in SSE stream: {str(e)}")
                break

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    # Add headers to prevent buffering
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Connection'] = 'keep-alive'
    return response

@login_required
def translated_words_list(request, document_id):
    document = get_object_or_404(PDFDocument, pk=document_id, user=request.user)
    words = WordEntry.objects.filter(document=document).order_by('original_text')
    return render(request, 'pdftranslate/translated_words_list.html', {
        'document': document,
        'words': words,
    })
