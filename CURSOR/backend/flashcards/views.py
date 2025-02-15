from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

# from .models import Video, Flashcard
from PyPDF2 import PdfReader


class UploadBookView(APIView):
    def post(self, request, format=None):
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        book_file = request.FILES['file']
        # Process the uploaded PDF file directly (do not save in the DB)
        try:
            reader = PdfReader(book_file)
            extracted_text = ""
            for page in reader.pages:
                extracted_text += page.extract_text() or ""
        except Exception as e:
            error_message = "Failed to extract PDF text: " + str(e)
            return Response(
                {'error': error_message},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Print the extracted text to the terminal
        print("Extracted text:", extracted_text)

        # Return a simple message (do not return the extracted text)
        return Response(
            {
                'message':
                'Book processed. Check your terminal for extracted text.'},
            status=status.HTTP_201_CREATED
        )


class UploadVideoView(APIView):
    def post(self, request, format=None):
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        video_file = request.FILES['file']
        # Do not save to the database.
        print("Video file uploaded with name:", video_file.name)
        return Response(
            {'message': 'Video processed. Check your terminal for details.'},
            status=status.HTTP_201_CREATED
        )


class FlashcardListView(APIView):
    def get(self, request, format=None):
        # Since no flashcards are saved in the database, return an empty list.
        return Response([], status=status.HTTP_200_OK)
