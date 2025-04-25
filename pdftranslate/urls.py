from django.urls import path
from . import views

urlpatterns = [
    path('', views.pdf_list, name='pdf_list'),
    path('upload/', views.upload_pdf, name='upload_pdf'),
    path('delete/<int:pk>/', views.delete_pdf, name='delete_pdf'),
    path('translation-progress/<int:pk>/', views.get_translation_progress, name='translation_progress'),
    path('translation/<int:pk>/', views.view_translation, name='view_translation'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name='signup'),
    path('flashcards/', views.flashcard_list, name='flashcard_list'),
    path('flashcards/review/<int:pk>/', views.flashcard_review, name='flashcard_review'),
    path('flashcards/review/', views.flashcard_review, name='flashcard_review_base'),
    path('flashcards/create/<int:document_id>/', views.create_flashcards, name='create_flashcards'),
    path('flashcards/dashboard/', views.flashcard_dashboard, name='flashcard_dashboard'),
    path('sse/progress/<int:document_id>/', views.sse_progress, name='sse_progress'),
    path('videos/', views.video_list, name='video_list'),
    path('videos/upload/', views.upload_video, name='upload_video'),
    path('videos/<int:pk>/', views.video_detail, name='video_detail'),
    path('videos/<int:pk>/delete/', views.delete_video, name='delete_video'),
    path('videos/<int:pk>/progress/', views.get_transcription_progress, name='transcription_progress'),
] 