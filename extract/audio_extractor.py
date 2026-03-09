#!/usr/bin/env python3
"""
Audio extractor with multi-method fallback chain:
1. Whisper (local) - Fast, accurate for various audio types
2. Groq Whisper API - Cloud-based transcription
3. AssemblyAI - High-quality commercial transcription
4. Google Speech-to-Text - Enterprise-grade fallback

Follows the same JSON output structure as PDF extractor.
"""

import os
import json
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

from extract.base_extractor import BaseExtractor


class AudioExtractor(BaseExtractor):
    """
    Extract transcript and metadata from audio files.
    Supports: MP3, WAV, M4A, FLAC, OGG, etc.
    """
    
    def __init__(self, groq_api_key: Optional[str] = None, config: Optional[Dict] = None):
        super().__init__(groq_api_key, config)
        
        # Audio-specific configuration
        self.supported_formats = ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.wma', '.aac']
        self.sample_rate = self.config.get('sample_rate', 16000)
        self.language = self.config.get('language', 'en')
        
        logger.info("AudioExtractor initialized with Whisper → Groq → AssemblyAI → Google fallback chain")
    
    async def extract(self, file_path: str, document: Dict[str, Any]) -> Tuple[str, List[Dict], Dict]:
        """
        Extract transcript from audio file using multi-method approach.
        
        Returns:
            (transcript_text, segments, modality_data)
        """
        logger.info(f"[AudioExtractor] Processing: {Path(file_path).name}")
        
        file_info = self.get_file_info(file_path)
        if not file_info['exists']:
            logger.error(f"Audio file not found: {file_path}")
            return "", [], {'error': 'File not found'}
        
        # Validate audio format
        if file_info['extension'].lower() not in self.supported_formats:
            logger.warning(f"Unsupported audio format: {file_info['extension']}")
            return "", [], {'error': f"Unsupported format: {file_info['extension']}"}
        
        start_time = datetime.now()
        
        # Method 1: Try local Whisper first (fastest, most reliable)
        transcript, method, confidence = await self._transcribe_whisper_local(file_path)
        
        # Method 2: Try Groq Whisper API if local failed
        if not transcript or len(transcript) < 10:
            logger.info("Trying Groq Whisper API...")
            transcript, method, confidence = await self._transcribe_groq(file_path)
        
        # Method 3: Try AssemblyAI (commercial service)
        if not transcript or len(transcript) < 10:
            logger.info("Trying AssemblyAI...")
            transcript, method, confidence = await self._transcribe_assemblyai(file_path)
        
        # Method 4: Try Google Speech-to-Text (enterprise fallback)
        if not transcript or len(transcript) < 10:
            logger.info("Trying Google Speech-to-Text...")
            transcript, method, confidence = await self._transcribe_google(file_path)
        
        # Clean and validate transcript
        transcript = self.clean_text(transcript)
        
        if not transcript:
            logger.warning(f"All transcription methods failed for {file_path}")
            return "", [], {
                'error': 'All transcription methods failed',
                'methods_tried': ['whisper_local', 'groq', 'assemblyai', 'google']
            }
        
        # Get audio metadata
        duration = await self._get_audio_duration(file_path)
        audio_props = await self._get_audio_properties(file_path)
        
        # Create time-aligned segments
        segments = self._create_audio_segments(transcript, duration)
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Prepare modality-specific data
        modality_data = {
            'transcript': transcript,
            'duration_seconds': duration,
            'duration_formatted': self.format_duration(duration),
            'extraction_method': method,
            'transcription_confidence': confidence,
            'audi¡o_properties': audio_props,
            'word_count': len(transcript.split()) if transcript else 0,
            'estimated_wpm': self._calculate_words_per_minute(transcript, duration),
            'has_speech': len(transcript.strip()) > 10,
            'audio_quality': self._assess_audio_quality(transcript, duration),
            'processing_time_seconds': processing_time
        }
        
        logger.info(f"✓ Audio transcribed: {len(transcript)} chars, {duration:.1f}s duration, method: {method}")
        
        return transcript, segments, modality_data
    
    async def _transcribe_whisper_local(self, file_path: str) -> Tuple[str, str, float]:
        """
        Transcribe using local Whisper model (runs in thread pool to avoid blocking).
        
        Returns:
            (transcript, method_name, confidence)
        """
        try:
            import whisper
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            
            def _transcribe_sync():
                """Synchronous transcription to run in thread pool."""
                model_size = self.config.get('whisper_model', 'base')
                logger.debug(f"Loading Whisper {model_size} model...")
                model = whisper.load_model(model_size)
                
                logger.debug(f"Transcribing {Path(file_path).name}...")
                result = whisper.transcribe(model, file_path, language=self.language, fp16=False)
                
                return result.get("text", ""), f"whisper_local_{model_size}", 0.9
            
            # Run in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as pool:
                transcript, method, confidence = await loop.run_in_executor(pool, _transcribe_sync)
            
            if transcript and len(transcript) > 10:
                logger.info(f"✓ Whisper (local) transcription successful: {len(transcript)} chars")
                return transcript, method, confidence
            
            return "", "whisper_local", 0.0
            
        except ImportError:
            logger.debug("Whisper not installed: pip install openai-whisper")
            return "", "whisper_local", 0.0
        except Exception as e:
            logger.warning(f"Local Whisper transcription failed: {e}")
            return "", "whisper_local", 0.0
    
    async def _transcribe_groq(self, file_path: str) -> Tuple[str, str, float]:
        """
        Transcribe using Groq Whisper API.
        
        Returns:
            (transcript, method_name, confidence)
        """
        if not self.groq_client:
            return "", "groq", 0.0
        
        try:
            # Groq has Whisper endpoint
            with open(file_path, 'rb') as audio_file:
                # Note: Groq's actual API might differ, this is a placeholder
                # Check Groq's documentation for actual implementation
                logger.info("Groq Whisper API would be called here (check Groq docs for actual implementation)")
                return "", "groq", 0.0
                
        except Exception as e:
            logger.warning(f"Groq transcription failed: {e}")
            return "", "groq", 0.0
    
    async def _transcribe_assemblyai(self, file_path: str) -> Tuple[str, str, float]:
        """
        Transcribe using AssemblyAI.
        
        Returns:
            (transcript, method_name, confidence)
        """
        try:
            # AssemblyAI requires API key from environment
            api_key = os.getenv('ASSEMBLYAI_API_KEY')
            if not api_key:
                return "", "assemblyai", 0.0
            
            import assemblyai as aai
            
            aai.settings.api_key = api_key
            transcriber = aai.Transcriber()
            
            transcript_obj = transcriber.transcribe(file_path)
            
            if transcript_obj.status == aai.TranscriptStatus.completed:
                transcript = transcript_obj.text
                confidence = transcript_obj.confidence if hasattr(transcript_obj, 'confidence') else 0.85
                logger.info(f"✓ AssemblyAI transcription successful (confidence: {confidence})")
                return transcript, "assemblyai", confidence
            
            return "", "assemblyai", 0.0
            
        except ImportError:
            logger.debug("AssemblyAI not installed: pip install assemblyai")
            return "", "assemblyai", 0.0
        except Exception as e:
            logger.warning(f"AssemblyAI transcription failed: {e}")
            return "", "assemblyai", 0.0
    
    async def _transcribe_google(self, file_path: str) -> Tuple[str, str, float]:
        """
        Transcribe using Google Speech-to-Text.
        
        Returns:
            (transcript, method_name, confidence)
        """
        try:
            from google.cloud import speech
            
            client = speech.SpeechClient()
            
            # Load audio file
            with open(file_path, 'rb') as audio_file:
                content = audio_file.read()
            
            audio = speech.RecognitionAudio(content=content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.sample_rate,
                language_code=self.language
            )
            
            response = client.recognize(config=config, audio=audio)
            
            transcript_parts = []
            total_confidence = 0.0
            
            for result in response.results:
                transcript_parts.append(result.alternatives[0].transcript)
                total_confidence += result.alternatives[0].confidence
            
            if transcript_parts:
                transcript = " ".join(transcript_parts)
                avg_confidence = total_confidence / len(response.results)
                logger.info(f"✓ Google Speech-to-Text successful (confidence: {avg_confidence})")
                return transcript, "google_speech", avg_confidence
            
            return "", "google_speech", 0.0
            
        except ImportError:
            logger.debug("Google Cloud Speech not installed: pip install google-cloud-speech")
            return "", "google_speech", 0.0
        except Exception as e:
            logger.warning(f"Google Speech-to-Text failed: {e}")
            return "", "google_speech", 0.0
    
    async def _get_audio_duration(self, file_path: str) -> float:
        """Get audio file duration in seconds."""
        try:
            # Try pydub first
            from pydub import AudioSegment
            audio = AudioSegment.from_file(file_path)
            return len(audio) / 1000.0  # Convert ms to seconds
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"pydub duration detection failed: {e}")
        
        try:
            # Try mutagen as fallback
            from mutagen import File
            audio_file = File(file_path)
            if audio_file and hasattr(audio_file.info, 'length'):
                return float(audio_file.info.length)
        except ImportError:
            logger.debug("mutagen not installed for audio metadata")
        except Exception as e:
            logger.warning(f"mutagen duration detection failed: {e}")
        
        return 0.0
    
    async def _get_audio_properties(self, file_path: str) -> Dict[str, Any]:
        """Extract audio file properties."""
        props = {
            'format': Path(file_path).suffix[1:].upper(),
            'channels': None,
            'sample_rate': None,
            'bit_rate': None
        }
        
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(file_path)
            props.update({
                'channels': audio.channels,
                'sample_rate': audio.frame_rate,
                'bit_rate': None  # pydub doesn't provide bit rate
            })
        except:
            pass
        
        try:
            from mutagen import File
            audio_file = File(file_path)
            if audio_file and hasattr(audio_file.info, 'sample_rate'):
                props['sample_rate'] = audio_file.info.sample_rate
            if audio_file and hasattr(audio_file.info, 'bitrate'):
                props['bit_rate'] = audio_file.info.bitrate
        except:
            pass
        
        return props
    
    def _create_audio_segments(self, transcript: str, duration: float) -> List[Dict[str, Any]]:
        """
        Create time-aligned segments from transcript.
        Splits by sentences and estimates timestamps.
        """
        if not transcript:
            return []
        
        segments = []
        
        # Split by sentence-ending punctuation
        import re
        sentences = re.split(r'[.!?]+', transcript)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            # Fallback: single segment
            return [self.create_segment(
                segment_id="audio_seg_0",
                segment_type="full_transcript",
                content=transcript,
                position=0,
                metadata={
                    'start_time': 0.0,
                    'end_time': duration,
                    'duration': duration
                }
            )]
        
        # Estimate time per segment based on word count
        total_words = len(transcript.split())
        time_per_word = duration / total_words if total_words > 0 else 0
        
        current_time = 0.0
        for idx, sentence in enumerate(sentences):
            word_count = len(sentence.split())
            segment_duration = word_count * time_per_word
            
            segments.append(self.create_segment(
                segment_id=f"audio_seg_{idx}",
                segment_type="sentence",
                content=sentence,
                position=idx,
                metadata={
                    'start_time': current_time,
                    'end_time': current_time + segment_duration,
                    'duration': segment_duration,
                    'timestamp': self.format_duration(current_time)
                }
            ))
            
            current_time += segment_duration
        
        return segments
    
    def _calculate_words_per_minute(self, transcript: str, duration: float) -> float:
        """Calculate speaking rate in words per minute."""
        if not transcript or duration <= 0:
            return 0.0
        
        word_count = len(transcript.split())
        wpm = (word_count / duration) * 60
        return round(wpm, 1)
    
    def _assess_audio_quality(self, transcript: str, duration: float) -> str:
        """
        Assess audio quality based on transcript and duration.
        
        Returns:
            'high', 'medium', 'low', or 'poor'
        """
        if not transcript or len(transcript) < 10:
            return "poor"
        
        wpm = self._calculate_words_per_minute(transcript, duration)
        
        # Typical speaking rates:
        # Slow: 100-125 WPM
        # Normal: 125-160 WPM
        # Fast: 160-200 WPM
        # Very fast: 200+ WPM
        
        if 100 <= wpm <= 200:
            return "high"  # Natural speaking rate
        elif 80 <= wpm <= 220:
            return "medium"  # Acceptable range
        elif 50 <= wpm <= 250:
            return "low"  # Questionable but usable
        else:
            return "poor"  # Likely transcription error
