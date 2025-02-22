# BookLand PDF Translator

A Django application for uploading and translating PDF files to Russian using Google Cloud Translation API.

## Features
- PDF file upload with drag-and-drop support
- Text extraction from PDF files
- Word-by-word translation to Russian
- Clean, responsive UI
- Translation progress tracking
- Word frequency analysis

## Prerequisites
- Python 3.8 or higher
- Google Cloud account with Translation API enabled
- Google Cloud service account credentials

## Setup Instructions

1. Clone the repository:
```bash
git clone <repository-url>
cd BookLand_B
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
```
Edit `.env` file with your configuration settings.

5. Set up Google Cloud credentials:
- Create a service account in Google Cloud Console
- Download the credentials JSON file
- Save it as `google_cred.json` in the project root
- Make sure the Translation API is enabled in your Google Cloud project

6. Apply database migrations:
```bash
python manage.py migrate
```

7. Create a superuser (optional):
```bash
python manage.py createsuperuser
```

8. Collect static files:
```bash
python manage.py collectstatic
```

9. Run the development server:
```bash
python manage.py runserver
```

The application will be available at http://127.0.0.1:8000/

## Usage

1. Upload a PDF:
   - Click "Upload PDF" in the navigation
   - Drag and drop a PDF file or click to choose
   - Wait for processing and translation

2. View translations:
   - Go to "PDF List"
   - Click "View Translations" for any document
   - See word-by-word translations with page numbers

## Word Frequency Analysis

The application handles duplicate words in the following ways:
- Words are stored with their page numbers and positions
- The UI shows frequency counts for repeated words
- Translations are cached to avoid redundant API calls
- Words are case-insensitive for better grouping

## Production Deployment

For production deployment:
1. Set `DEBUG=False` in `.env`
2. Configure a proper database (e.g., PostgreSQL)
3. Use a production-grade server (e.g., Gunicorn)
4. Set up proper static files serving
5. Configure proper security settings

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 