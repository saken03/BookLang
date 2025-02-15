from django.urls import path
from .views import UploadBookView, UploadVideoView, FlashcardListView

urlpatterns = [
    path('upload/book/', UploadBookView.as_view(), name="upload-book"),
    path('upload/video/', UploadVideoView.as_view(), name="upload-video"),
    path('flashcards/', FlashcardListView.as_view(), name="flashcard-list"),
] 