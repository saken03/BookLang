from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class PDFDocument(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='pdf_documents',
        null=True,
        blank=True
    )
    title = models.CharField(max_length=255)
    pdf_file = models.FileField(upload_to='pdfs/')
    uploaded_at = models.DateTimeField(default=timezone.now)
    extracted_text = models.TextField(blank=True, null=True)
    translation_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('failed', 'Failed')
        ],
        default='pending'
    )
    translation_progress = models.IntegerField(default=0)
    total_words = models.IntegerField(default=0)
    translated_words = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username if self.user else 'No User'} - {self.title}"

    class Meta:
        ordering = ['-uploaded_at']


class WordEntry(models.Model):
    document = models.ForeignKey(PDFDocument, on_delete=models.CASCADE, related_name='words')
    original_text = models.CharField(max_length=255)
    translated_text = models.CharField(max_length=255, blank=True, null=True)
    page_number = models.IntegerField()
    position = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['page_number', 'position']
        verbose_name_plural = 'Word entries'

    def __str__(self):
        return f"{self.original_text} -> {self.translated_text}"
