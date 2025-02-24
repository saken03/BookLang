from django.urls import path
from . import views

urlpatterns = [
    path('', views.pdf_list, name='pdf_list'),
    path('upload/', views.upload_pdf, name='upload_pdf'),
    path('delete/<int:pk>/', views.delete_pdf, name='delete_pdf'),
    path('progress/<int:pk>/', views.get_translation_progress, name='translation_progress'),
    path('flashcards/', views.flashcard_dashboard, name='flashcard_dashboard'),
    path('flashcards/list/', views.flashcard_list, name='flashcard_list'),
    path('flashcards/review/', views.flashcard_review, name='flashcard_review'),
    path('flashcards/review/<int:pk>/', views.flashcard_review, name='flashcard_review'),
    path('flashcards/create/<int:document_id>/', views.create_flashcards, name='create_flashcards'),
    path('flashcards/<int:pk>/reset/', views.reset_flashcard, name='reset_flashcard'),
] 