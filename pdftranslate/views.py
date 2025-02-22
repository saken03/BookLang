from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.files.storage import default_storage
from django.http import JsonResponse
from .models import PDFDocument, WordEntry
from .tasks import start_translation
from PyPDF2 import PdfReader
import io
import re
import logging
import os

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
