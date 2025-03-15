from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
import math
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """Extended user profile information."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    default_language = models.CharField(max_length=10, default='en', choices=[
        ('en', 'English'),
        ('ru', 'Russian'),
    ])
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    social_media = models.CharField(max_length=255, blank=True, null=True, 
                                   help_text="Social media handles or activity description")
    profile_photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s profile"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile when a User is created."""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the UserProfile when the User is saved."""
    instance.profile.save()

class PDFDocument(models.Model):
    """Represents a PDF document uploaded by a user."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255)
    pdf_file = models.FileField(upload_to='pdfs/')
    uploaded_at = models.DateTimeField(default=timezone.now)
    
    # Translation status
    TRANSLATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    translation_status = models.CharField(
        max_length=20,
        choices=TRANSLATION_STATUS_CHOICES,
        default='pending'
    )
    translation_progress = models.IntegerField(default=0)  # 0-100%
    total_words = models.IntegerField(default=0)
    translated_words = models.IntegerField(default=0)
    
    def __str__(self):
        return self.title
    
    @property
    def flashcard_count(self):
        """Count flashcards associated with this document."""
        return Flashcard.objects.filter(
            word_entry__document=self
        ).count()
    
    def create_all_flashcards(self, user):
        """Create flashcards for all translated words in this document."""
        # Get all words that don't have flashcards yet
        words_without_flashcards = WordEntry.objects.filter(
            document=self,
            translated_text__isnull=False
        ).exclude(
            id__in=Flashcard.objects.filter(
                word_entry__document=self
            ).values_list('word_entry_id', flat=True)
        )
        
        # Create flashcards for each word
        created_count = 0
        for word in words_without_flashcards:
            Flashcard.objects.create(
                user=user,
                word_entry=word,
                next_review=timezone.now()
            )
            created_count += 1
        
        return created_count

class WordEntry(models.Model):
    """Represents a word or phrase extracted from a PDF document."""
    document = models.ForeignKey(
        PDFDocument, 
        on_delete=models.CASCADE,
        related_name='words'
    )
    original_text = models.CharField(max_length=255)
    translated_text = models.CharField(max_length=255, null=True, blank=True)
    page_number = models.IntegerField()
    position = models.IntegerField(default=0)  # Position in the document
    
    def __str__(self):
        return f"{self.original_text} -> {self.translated_text}"

class Flashcard(models.Model):
    """Represents a flashcard for learning a word."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    word_entry = models.ForeignKey(WordEntry, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)
    last_reviewed = models.DateTimeField(null=True, blank=True)
    next_review = models.DateTimeField()
    
    # Spaced repetition data
    ease_factor = models.FloatField(default=2.5)  # Ease factor (2.5 is default)
    interval = models.IntegerField(default=0)  # Interval in days
    review_count = models.IntegerField(default=0)  # Number of reviews
    
    def __str__(self):
        return f"Flashcard: {self.word_entry.original_text}"
    
    def update_schedule(self, remembered):
        """Update the flashcard schedule based on whether it was remembered."""
        now = timezone.now()
        self.last_reviewed = now
        self.review_count += 1
        
        if remembered:
            # If remembered, increase interval using SM-2 algorithm
            if self.interval == 0:
                self.interval = 1
            elif self.interval == 1:
                self.interval = 6
            else:
                self.interval = math.ceil(self.interval * self.ease_factor)
                
            # Cap interval at 365 days
            self.interval = min(self.interval, 365)
            
            # Adjust ease factor (min 1.3, max 2.5)
            self.ease_factor = max(1.3, min(2.5, self.ease_factor + 0.1))
        else:
            # If forgotten, reset interval and decrease ease factor
            self.interval = 0
            self.ease_factor = max(1.3, self.ease_factor - 0.2)
        
        # Set next review time
        if self.interval == 0:
            # Review again in 10 minutes if forgotten
            self.next_review = now + timedelta(minutes=10)
        else:
            # Review after the calculated interval
            self.next_review = now + timedelta(days=self.interval)
        
        self.save()
    
    def reset(self):
        """Reset the flashcard to its initial state."""
        self.ease_factor = 2.5
        self.interval = 0
        self.review_count = 0
        self.next_review = timezone.now()
        self.save()
    
    def get_next_review_description(self):
        """Get a human-readable description of when the next review is due."""
        now = timezone.now()
        diff = self.next_review - now
        
        if diff.days > 0:
            if diff.days == 1:
                return "tomorrow"
            elif diff.days < 7:
                return f"{diff.days} days"
            elif diff.days < 30:
                weeks = diff.days // 7
                return f"{weeks} week{'s' if weeks > 1 else ''}"
            elif diff.days < 365:
                months = diff.days // 30
                return f"{months} month{'s' if months > 1 else ''}"
            else:
                years = diff.days // 365
                return f"{years} year{'s' if years > 1 else ''}"
        else:
            hours = diff.seconds // 3600
            if hours > 0:
                return f"{hours} hour{'s' if hours > 1 else ''}"
            else:
                minutes = (diff.seconds % 3600) // 60
                return f"{minutes} minute{'s' if minutes > 1 else ''}"
