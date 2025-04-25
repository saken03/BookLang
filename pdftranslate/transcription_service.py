import os
import logging
import openai
from moviepy.editor import VideoFileClip
import tempfile
from django.conf import settings

logger = logging.getLogger(__name__)

class TranscriptionService:
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY

    def extract_audio(self, video_path):
        """Extract audio from video file."""
        try:
            video = VideoFileClip(video_path)
            # Create a temporary file for the audio
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
                video.audio.write_audiofile(temp_audio.name, logger=None)
                video.close()
                return temp_audio.name
        except Exception as e:
            logger.error(f"Error extracting audio: {str(e)}")
            raise

    def transcribe_audio(self, audio_path, language=None):
        """Transcribe audio file using OpenAI Whisper API."""
        try:
            with open(audio_path, 'rb') as audio_file:
                response = openai.Audio.transcribe(
                    "whisper-1",
                    audio_file,
                    language=language
                )
                return response['text']
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            raise
        finally:
            # Clean up the temporary audio file
            if os.path.exists(audio_path):
                os.remove(audio_path)

    def process_video(self, video_path, language=None):
        """Process video file and return transcribed text."""
        try:
            # Extract audio from video
            audio_path = self.extract_audio(video_path)
            
            # Transcribe the audio
            transcribed_text = self.transcribe_audio(audio_path, language)
            
            return transcribed_text
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            raise 