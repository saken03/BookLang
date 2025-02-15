from django.db import models


class Book(models.Model):
    file = models.FileField(upload_to='books/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Book {self.id}"


class Video(models.Model):
    file = models.FileField(upload_to='videos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Video {self.id}"


class Flashcard(models.Model):
    word = models.CharField(max_length=100)
    translation = models.CharField(max_length=100)
    # Optionally link to a source Book or Video
    source_book = models.ForeignKey(
        Book,
        related_name='flashcards',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    source_video = models.ForeignKey(
        Video,
        related_name='flashcards',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.word} - {self.translation}"
