#!/usr/bin/env python3
"""
Audio ASR (Automatic Speech Recognition) parser using Whisper.
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List
from loguru import logger

class AudioParser:
    """Audio parser using Whisper for speech recognition."""
    
    def __init__(self):
        self.model = None
        self.model_loaded = False
    
    async def load_model(self):
        """Load Whisper model (runs in thread pool to avoid blocking)."""
        try:
            import whisper
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            
            def _load_sync():
                return whisper.load_model("base")
            
            # Load model in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.model = await loop.run_in_executor(pool, _load_sync)
            
            self.model_loaded = True
            logger.info("Loaded Whisper model for ASR")
        except ImportError:
            logger.warning("Whisper not available, using fallback")
        except Exception as e:
            logger.error(f"Error loading Whisper model: {e}")
    
    async def parse(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Parse audio file and transcribe speech."""
        try:
            if not self.model_loaded:
                await self.load_model()
            
            file_path = Path(document['file_path'])
            
            if not file_path.exists():
                logger.error(f"Audio file not found: {file_path}")
                return await self._create_fallback_document(document)
            
            # For synthetic audio files with placeholder content
            if file_path.stat().st_size < 100:  # Very small file, likely placeholder
                return await self._create_fallback_document(document)
            
            if self.model:
                # Transcribe with Whisper (in thread pool to avoid blocking)
                import asyncio
                from concurrent.futures import ThreadPoolExecutor
                
                def _transcribe_sync():
                    return self.model.transcribe(str(file_path), fp16=False)
                
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    result = await loop.run_in_executor(pool, _transcribe_sync)
                
                transcript = result["text"]
                segments = result.get("segments", [])
            else:
                # Fallback: use existing content or generate basic transcript
                transcript = document.get('content', 'Audio content placeholder')
                segments = []
            
            parsed_doc = {
                'doc_id': document['doc_id'],
                'type': 'audio',
                'content': transcript,
                'metadata': {
                    'source_type': 'audio',
                    'file_path': str(file_path),
                    'duration': document.get('duration', 0),
                    'segments': segments,
                    'transcription_model': 'whisper' if self.model else 'fallback'
                },
                'segments': segments
            }
            
            # Add ground truth if available
            if 'entities' in document:
                parsed_doc['ground_truth_entities'] = document['entities']
            if 'relations' in document:
                parsed_doc['ground_truth_relations'] = document['relations']
            
            logger.debug(f"Transcribed audio document: {document['doc_id']}")
            return parsed_doc
            
        except Exception as e:
            logger.error(f"Error parsing audio document {document.get('doc_id')}: {e}")
            return await self._create_fallback_document(document)
    
    async def _create_fallback_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Create fallback document when ASR fails."""
        fallback_content = document.get('content', 'Audio transcription not available')
        
        return {
            'doc_id': document['doc_id'],
            'type': 'audio',
            'content': fallback_content,
            'metadata': {
                'source_type': 'audio',
                'file_path': document.get('file_path', ''),
                'duration': document.get('duration', 0),
                'transcription_model': 'fallback',
                'error': 'ASR not available, using provided content'
            },
            'segments': [],
            'ground_truth_entities': document.get('entities', []),
            'ground_truth_relations': document.get('relations', [])
        }
    
    async def transcribe_file(self, audio_path: Path) -> Dict[str, Any]:
        """Transcribe a single audio file."""
        try:
            if not self.model_loaded:
                await self.load_model()
            
            if self.model and audio_path.exists():
                result = self.model.transcribe(str(audio_path))
                return {
                    'text': result['text'],
                    'segments': result.get('segments', []),
                    'language': result.get('language', 'en'),
                    'success': True
                }
            else:
                return {
                    'text': 'Transcription not available',
                    'segments': [],
                    'language': 'en',
                    'success': False
                }
                
        except Exception as e:
            logger.error(f"Error transcribing {audio_path}: {e}")
            return {
                'text': f'Transcription error: {e}',
                'segments': [],
                'language': 'en',
                'success': False
            }