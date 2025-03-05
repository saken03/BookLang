from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
import math


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

    def create_all_flashcards(self, user):
        created_count = 0
        for word in self.words.all():
            if word.translated_text and not word.has_flashcard:
                word.create_flashcard(user)
                created_count += 1
        return created_count

    @property
    def flashcard_count(self):
        return self.words.filter(flashcard__isnull=False).count()

    @property
    def available_words(self):
        return self.words.filter(
            translated_text__isnull=False,
            flashcard__isnull=True
        )


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

    def create_flashcard(self, user):
        if not hasattr(self, 'flashcard'):
            from .models import Flashcard
            flashcard = Flashcard.objects.create(
                word_entry=self,
                user=user
            )
            return flashcard
        return self.flashcard

    @property
    def has_flashcard(self):
        return hasattr(self, 'flashcard')


class Flashcard(models.Model):
    INTERVAL_CHOICES = [
        ('again', '<10m'),
        ('hard', '<15m'),
        ('good', '1d'),
        ('easy', '2d'),
    ]

    word_entry = models.OneToOneField(
        WordEntry,
        on_delete=models.CASCADE,
        related_name='flashcard'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='flashcards'
    )
    last_reviewed = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When this card was last reviewed'
    )
    next_review = models.DateTimeField(
        default=timezone.now,
        help_text='When this card should be reviewed next'
    )
    review_count = models.IntegerField(
        default=0,
        help_text='Number of successful reviews'
    )
    interval = models.CharField(
        max_length=10,
        choices=INTERVAL_CHOICES,
        default='good',
        help_text='Current review interval'
    )

    class Meta:
        ordering = ['next_review']
        indexes = [
            models.Index(fields=['user', 'next_review']),
            models.Index(fields=['word_entry']),
        ]

    def __str__(self):
        return f"Flashcard for {self.word_entry}"

    def calculate_next_interval(self, remembered: bool) -> int:
        """Calculate the next review interval in days."""
        if remembered:
            # Exponential increase: 1 → 2 → 4 → 8 → 16 → 32 days
            return int(math.pow(2, self.review_count))
        else:
            # Review tomorrow if forgotten
            return 1

    def update_schedule(self, remembered: bool):
        """
        Update the flashcard schedule based on review result.
        
        Args:
            remembered (bool): Whether the user remembered the card
        """
        now = timezone.now()
        self.last_reviewed = now

        if remembered:
            self.review_count += 1
            self.interval = 'good'  
        else:
            self.review_count = max(0, self.review_count - 1)
            self.interval = 'again'  

        # Calculate next review date
        interval_days = self.calculate_next_interval(remembered)
        self.next_review = now + timedelta(days=interval_days)
        self.save()

    def get_next_review_description(self) -> str:
        """Get a human-readable description of the next review interval."""
        if not self.last_reviewed:
            return "Not reviewed yet"
        
        interval = self.next_review - self.last_reviewed
        days = interval.days
        
        if days == 0:
            return "Review today"
        elif days == 1:
            return "Review tomorrow"
        else:
            return f"Review in {days} days"

    def reset(self):
        """Reset the card to its initial state."""
        self.last_reviewed = None
        self.next_review = timezone.now()
        self.review_count = 0
        self.interval = 'good'  # Reset to standard interval
        self.save()
