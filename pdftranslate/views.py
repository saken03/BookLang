from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
from .models import PDFDocument, WordEntry, Flashcard, UserProfile
from .tasks import start_translation
from PyPDF2 import PdfReader
import io
import re
import logging
import os
from datetime import datetime, timedelta
from django.db import models
import json

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
def user_profile(request):
    """
    View and edit user profile information.
    
    This view handles:
    - Updating basic user information (name, email)
    - Updating profile information (language, phone, social media)
    - Profile photo upload and management
    - Password changes with validation
    """
    user = request.user
    
    if request.method == 'POST':
        # Initialize validation errors dictionary
        validation_errors = {}
        
        # Validate email
        email = request.POST.get('email', '').strip()
        if not email:
            validation_errors['email'] = 'Email is required'
        elif '@' not in email or '.' not in email:
            validation_errors['email'] = 'Please enter a valid email address'
        
        # If no validation errors, proceed with updates
        if not validation_errors:
            # Update user information
            user.email = email
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            
            # Update profile information
            user.profile.default_language = request.POST.get('default_language', user.profile.default_language)
            user.profile.phone_number = request.POST.get('phone_number', '').strip()
            user.profile.social_media = request.POST.get('social_media', '').strip()
            
            # Handle profile photo upload
            if 'profile_photo' in request.FILES:
                profile_photo = request.FILES['profile_photo']
                
                # Validate file type
                allowed_types = ['image/jpeg', 'image/png', 'image/gif']
                if profile_photo.content_type not in allowed_types:
                    messages.error(request, 'Please upload a valid image file (JPEG, PNG, or GIF)')
                    return render(request, 'pdftranslate/user_profile.html')
                
                # Validate file size (max 5MB)
                if profile_photo.size > 5 * 1024 * 1024:
                    messages.error(request, 'Image file is too large. Maximum size is 5MB.')
                    return render(request, 'pdftranslate/user_profile.html')
                
                # Delete old photo if it exists
                if user.profile.profile_photo:
                    try:
                        old_photo_path = user.profile.profile_photo.path
                        if os.path.exists(old_photo_path):
                            os.remove(old_photo_path)
                    except Exception as e:
                        logger.warning(f"Error deleting old profile photo: {str(e)}")
                
                # Save new photo
                user.profile.profile_photo = profile_photo
            
            # Handle password change if provided
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')
            
            if current_password and new_password and confirm_password:
                # Validate password strength
                if len(new_password) < 8:
                    messages.error(request, 'Password must be at least 8 characters long.')
                    return render(request, 'pdftranslate/user_profile.html')
                
                if new_password == confirm_password:
                    # Check if current password is correct
                    if user.check_password(current_password):
                        user.set_password(new_password)
                        messages.success(request, 'Your password has been updated successfully.')
                        # Update session to prevent logout
                        update_session_auth_hash(request, user)
                    else:
                        messages.error(request, 'Your current password is incorrect.')
                        return render(request, 'pdftranslate/user_profile.html')
                else:
                    messages.error(request, 'New passwords do not match.')
                    return render(request, 'pdftranslate/user_profile.html')
            
            # Save changes
            user.save()
            user.profile.save()
            
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('user_profile')
        else:
            # Display validation errors
            for field, error in validation_errors.items():
                messages.error(request, error)
    
    return render(request, 'pdftranslate/user_profile.html')

@login_required
def delete_pdf(request, pk):
    """Delete a PDF document and its associated files."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    document = get_object_or_404(PDFDocument, pk=pk, user=request.user)
    
    try:
        # Get the document directory path
        doc_dir = os.path.dirname(document.pdf_file.path)
        
        # Delete the actual file from storage
        if document.pdf_file:
            try:
                # Delete the file
                if os.path.exists(document.pdf_file.path):
                    os.remove(document.pdf_file.path)
                # Delete the parent directory if empty
                if os.path.exists(doc_dir) and not os.listdir(doc_dir):
                    os.rmdir(doc_dir)
            except Exception as e:
                logger.warning(f"Error deleting file {document.pdf_file.path}: {str(e)}")
        
        # Delete all associated flashcards
        Flashcard.objects.filter(word_entry__document=document).delete()
        
        # Delete all word entries
        WordEntry.objects.filter(document=document).delete()
        
        # Delete the document record
        document.delete()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        else:
            messages.success(request, f'"{document.title}" has been deleted.')
            return redirect('pdf_list')
            
    except Exception as e:
        logger.error(f"Error deleting PDF {document.title}: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Failed to delete document'}, status=500)
        else:
            messages.error(request, 'Error deleting the PDF file.')
            return redirect('pdf_list')

@login_required
def upload_pdf(request):
    if request.method == 'POST':
        if 'pdf_file' not in request.FILES:
            messages.error(request, 'No file was uploaded.')
            return redirect('upload_pdf')
        
        pdf_file = request.FILES['pdf_file']
        
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
    
    return render(request, 'pdftranslate/upload.html')

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
    """Display flashcards that are due for review."""
    now = timezone.now()
    
    # Check if a specific deck is selected
    selected_deck_id = request.GET.get('deck')
    selected_document = None
    
    # Base query for flashcards
    flashcard_query = Flashcard.objects.filter(user=request.user)
    
    if selected_deck_id:
        try:
            selected_document = PDFDocument.objects.get(
                id=selected_deck_id,
                user=request.user
            )
            # Filter flashcards for selected deck
            flashcard_query = flashcard_query.filter(
                word_entry__document=selected_document
            )
        except PDFDocument.DoesNotExist:
            messages.error(request, 'Selected deck not found.')
    
    # Get flashcards that are either due for review or new
    flashcards = (
        flashcard_query
        .filter(next_review__lte=now)
        .select_related('word_entry__document')
        .order_by('next_review')
    )
    
    # Get statistics
    if selected_document:
        # Stats for selected deck
        total_cards = flashcard_query.count()
        cards_due = flashcards.count()
        cards_learned = flashcard_query.filter(
            review_count__gt=0
        ).count()
    else:
        # Stats for all decks
        total_cards = flashcard_query.count()
        cards_due = flashcards.count()
        cards_learned = flashcard_query.filter(
            review_count__gt=0
        ).count()
    
    context = {
        'flashcards': flashcards,
        'total_cards': total_cards,
        'cards_due': cards_due,
        'cards_learned': cards_learned,
        'selected_document': selected_document,
    }
    return render(request, 'pdftranslate/flashcard_list.html', context)

@login_required
def flashcard_review(request, pk=None):
    """Review a specific flashcard or get the next due card."""
    now = timezone.now()
    selected_deck_id = request.GET.get('deck')
    
    # Base query for flashcards
    flashcard_query = Flashcard.objects.filter(user=request.user)
    
    # Filter by deck if specified
    if selected_deck_id:
        try:
            selected_document = PDFDocument.objects.get(
                id=selected_deck_id,
                user=request.user
            )
            flashcard_query = flashcard_query.filter(
                word_entry__document=selected_document
            )
        except PDFDocument.DoesNotExist:
            messages.error(request, 'Selected deck not found.')
    
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
        
        # Update flashcard schedule
        flashcard.update_schedule(remembered)
        
        # Show appropriate message
        if remembered:
            msg = (
                f'Great job! Next review in '
                f'{flashcard.get_next_review_description()}.'
            )
            messages.success(request, msg)
        else:
            messages.info(
                request,
                'Keep practicing! This card will be reviewed again soon.'
            )
        
        # Find the next card to review
        next_card = (
            flashcard_query
            .filter(next_review__lte=now)
            .exclude(pk=flashcard.pk)
            .first()
        )
        
        if next_card:
            redirect_kwargs = {'pk': next_card.pk}
            if selected_deck_id:
                redirect_kwargs['deck'] = selected_deck_id
            return redirect('flashcard_review', **redirect_kwargs)
        else:
            messages.success(
                request,
                "Congratulations! You've completed all reviews for now."
            )
            if selected_deck_id:
                return redirect('flashcard_list', deck=selected_deck_id)
            return redirect('flashcard_list')
    
    # GET request - show the next card
    if pk is None:
        # Get the next due card
        flashcard = flashcard_query.filter(next_review__lte=now).first()
        if not flashcard:
            messages.info(request, 'No cards due for review at this time.')
            return redirect('flashcard_list')
    else:
        # Get the specific card
        flashcard = get_object_or_404(
            flashcard_query,
            pk=pk
        )
    
    # Get progress information
    total_due = flashcard_query.filter(next_review__lte=now).count()
    reviewed_today = flashcard_query.filter(
        last_reviewed__date=now.date()
    ).count()
    cards_remaining_today = max(0, total_due - reviewed_today)
    
    # Get total learned cards (cards that have been reviewed at least once)
    total_learned = flashcard_query.filter(review_count__gt=0).count()
    
    context = {
        'flashcard': flashcard,
        'total_due': total_due,
        'reviewed_today': reviewed_today,
        'cards_remaining_today': cards_remaining_today,
        'selected_deck_id': selected_deck_id,
        'total_learned': total_learned,
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
def rename_document(request, pk):
    """AJAX endpoint to rename a document."""
    try:
        document = PDFDocument.objects.get(pk=pk, user=request.user)
        
        if request.method == 'POST':
            data = json.loads(request.body)
            new_title = data.get('title', '').strip()
            
            if new_title:
                document.title = new_title
                document.save()
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse(
                    {'error': 'Title cannot be empty'}, 
                    status=400
                )
                
    except PDFDocument.DoesNotExist:
        return JsonResponse(
            {'error': 'Document not found'}, 
            status=404
        )
    except Exception as e:
        logger.error(f"Error renaming document: {str(e)}")
        return JsonResponse(
            {'error': 'Failed to rename document'}, 
            status=500
        )
