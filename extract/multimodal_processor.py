#!/usr/bin/env python3
"""
Multi-modal data processor for handling different file formats before LLM processing.
Converts audio, images, PDFs, and video to structured text format optimized for:
- Named Entity Recognition (NER)
- Document Classification
- Knowledge Graph Construction
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from loguru import logger

try:
    from groq import Groq
except ImportError:
    logger.warning("Groq SDK not installed")


class MultiModalProcessor:
    """
    Processes different file formats and converts them to structured text for NER and classification.
    
    Returns standardized document structure:
    {
        'doc_id': str,
        'file_path': str,
        'file_type': str,
        'content': str,              # Main extracted text for NER
        'content_segments': List[Dict],  # Structured content sections
        'metadata': Dict,            # File metadata
        'modality_specific_data': Dict,  # Modality-specific extracted data
        'extraction_quality': Dict,  # Quality metrics
        'processed_at': str
    }
    """
    
    def __init__(self, groq_api_key: Optional[str] = None):
        self.groq_client = None
        if groq_api_key:
            try:
                self.groq_client = Groq(api_key=groq_api_key)
                logger.info("Groq client initialized for multi-modal processing")
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")
        
        # Model configurations for different tasks
        self.model_config = {
            'text': 'llama-3.1-70b-versatile',  # General text processing
            'audio': 'llama-3.1-70b-versatile',  # Transcript analysis
            'image': 'llama-3.1-70b-versatile',  # Image description analysis
            'pdf': 'llama-3.1-70b-versatile',   # PDF content analysis
            'video': 'llama-3.1-70b-versatile', # Video content analysis
            'transcription': 'whisper-large-v3', # Audio transcription (if using different service)
        }
    
    async def process_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process document based on its modality and convert to structured format for NER/classification.
        
        Args:
            document: Document dictionary with file_path, file_type, doc_id, etc.
            
        Returns:
            Structured document with:
            - content: clean text for NER extraction
            - content_segments: structured sections with metadata
            - modality_specific_data: modality-specific features
            - metadata: extraction metadata
            - extraction_quality: quality metrics
        """
        file_path = document.get('file_path')
        file_type = document.get('file_type', 'text')
        doc_id = document.get('doc_id', Path(file_path).stem if file_path else 'unknown')
        
        if not file_path or not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return self._create_error_document(document, "File not found")
        
        logger.info(f"Processing {file_type} document: {doc_id}")
        
        try:
            if file_type == 'audio':
                return await self._process_audio(document)
            elif file_type == 'image':
                return await self._process_image(document)
            elif file_type == 'pdf':
                return await self._process_pdf(document)
            elif file_type == 'video':
                return await self._process_video(document)
            elif file_type == 'text':
                return await self._process_text(document)
            else:
                logger.warning(f"Unsupported file type: {file_type}")
                return self._create_error_document(document, f"Unsupported file type: {file_type}")
                
        except Exception as e:
            logger.error(f"Error processing {file_type} document {file_path}: {e}")
            return self._create_error_document(document, str(e))
    
    def _create_error_document(self, document: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """Create a structured error document."""
        return {
            **document,
            'content': '',
            'content_segments': [],
            'metadata': {
                'extraction_status': 'failed',
                'error_message': error_message,
                'file_size': 0,
                'processing_time': 0.0
            },
            'modality_specific_data': {},
            'extraction_quality': {
                'success': False,
                'confidence': 0.0,
                'completeness': 0.0
            },
            'processed_at': datetime.now().isoformat()
        }
    
    def _create_structured_document(
        self,
        document: Dict[str, Any],
        content: str,
        content_segments: List[Dict[str, Any]],
        modality_data: Dict[str, Any],
        extraction_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a standardized structured document for downstream processing."""
        file_path = document.get('file_path', '')
        file_size = os.path.getsize(file_path) if file_path and os.path.exists(file_path) else 0
        
        return {
            **document,  # Preserve original document fields
            'content': content,  # Main text for NER
            'content_segments': content_segments,  # Structured sections
            'metadata': {
                'extraction_status': 'success',
                'file_size': file_size,
                'content_length': len(content),
                'num_segments': len(content_segments),
                'processing_time': extraction_metadata.get('processing_time', 0.0),
                **extraction_metadata
            },
            'modality_specific_data': modality_data,
            'extraction_quality': self._assess_extraction_quality(content, content_segments, modality_data),
            'processed_at': datetime.now().isoformat()
        }
    
    def _assess_extraction_quality(
        self,
        content: str,
        segments: List[Dict],
        modality_data: Dict
    ) -> Dict[str, Any]:
        """Assess the quality of extracted content."""
        # Basic quality metrics
        has_content = len(content.strip()) > 0
        content_length = len(content)
        num_segments = len(segments)
        
        # Calculate confidence based on extraction method and content
        confidence = 0.0
        if has_content:
            if content_length > 100:
                confidence = 0.9
            elif content_length > 50:
                confidence = 0.7
            else:
                confidence = 0.5
        
        # Check completeness
        completeness = min(1.0, content_length / 1000) if content_length > 0 else 0.0
        
        return {
            'success': has_content,
            'confidence': confidence,
            'completeness': completeness,
            'content_length': content_length,
            'num_segments': num_segments,
            'has_structured_data': num_segments > 0
        }
    
    async def _process_audio(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Process audio files to extract transcript and metadata in structured format."""
        file_path = document['file_path']
        start_time = datetime.now()
        
        # Method 1: Use Groq Whisper model if available
        transcript = await self._transcribe_audio_groq(file_path)
        
        # Method 2: Fallback to local Whisper or other ASR
        if not transcript:
            transcript = await self._transcribe_audio_local(file_path)
        
        # Method 3: Use external service (Google Speech-to-Text, Azure, etc.)
        if not transcript:
            transcript = await self._transcribe_audio_external(file_path)
        
        # Get audio metadata
        duration = await self._get_audio_duration(file_path)
        
        # Create structured segments (e.g., by speaker or time)
        content_segments = self._segment_transcript(transcript, duration)
        
        # Prepare modality-specific data
        modality_data = {
            'transcript': transcript,
            'duration': duration,
            'duration_formatted': self._format_duration(duration),
            'processing_method': 'audio_transcription',
            'audio_quality': self._assess_audio_quality(transcript, duration),
            'has_speech': len(transcript.strip()) > 0,
            'estimated_words': len(transcript.split()) if transcript else 0
        }
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return self._create_structured_document(
            document=document,
            content=transcript or "Audio content not transcribed",
            content_segments=content_segments,
            modality_data=modality_data,
            extraction_metadata={
                'processing_time': processing_time,
                'extraction_method': 'audio_transcription'
            }
        )
    
    def _segment_transcript(self, transcript: str, duration: float) -> List[Dict[str, Any]]:
        """Segment transcript into structured parts for better entity extraction."""
        if not transcript:
            return []
        
        segments = []
        # Split by sentences or paragraphs
        sentences = transcript.split('. ')
        
        for idx, sentence in enumerate(sentences):
            if sentence.strip():
                segments.append({
                    'segment_id': f"audio_seg_{idx}",
                    'segment_type': 'sentence',
                    'content': sentence.strip(),
                    'position': idx,
                    'estimated_time': (duration / len(sentences)) * idx if duration > 0 else 0
                })
        
        return segments
    
    def _format_duration(self, duration: float) -> str:
        """Format duration in human-readable format."""
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        return f"{minutes}m {seconds}s"
    
    def _assess_audio_quality(self, transcript: str, duration: float) -> str:
        """Assess the quality of audio transcription."""
        if not transcript or len(transcript.strip()) < 10:
            return "poor"
        
        words_per_minute = (len(transcript.split()) / duration * 60) if duration > 0 else 0
        
        if 100 <= words_per_minute <= 200:
            return "high"
        elif 50 <= words_per_minute <= 250:
            return "medium"
        else:
            return "low"
    
    async def _process_image(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Process image files to generate descriptions and extract text in structured format."""
        file_path = document['file_path']
        start_time = datetime.now()
        
        # Method 1: Use Groq with image description prompt
        description = await self._describe_image_groq(file_path)
        
        # Method 2: Use local OCR for text extraction
        extracted_text = await self._extract_image_text(file_path)
        
        # Method 3: Use local vision models (if available)
        if not description:
            description = await self._describe_image_local(file_path)
        
        # Get image dimensions and properties
        image_properties = await self._get_image_properties(file_path)
        
        # Combine content for NER
        combined_content = self._combine_image_content(description, extracted_text)
        
        # Create structured segments
        content_segments = []
        if description:
            content_segments.append({
                'segment_id': 'image_description',
                'segment_type': 'description',
                'content': description,
                'confidence': 0.8
            })
        if extracted_text:
            content_segments.append({
                'segment_id': 'image_ocr_text',
                'segment_type': 'ocr_text',
                'content': extracted_text,
                'confidence': 0.9
            })
        
        # Prepare modality-specific data
        modality_data = {
            'description': description,
            'extracted_text': extracted_text,
            'objects_detected': await self._detect_objects(file_path),
            'image_properties': image_properties,
            'processing_method': 'image_analysis',
            'has_text': len(extracted_text.strip()) > 0 if extracted_text else False,
            'has_description': len(description.strip()) > 0 if description else False
        }
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return self._create_structured_document(
            document=document,
            content=combined_content,
            content_segments=content_segments,
            modality_data=modality_data,
            extraction_metadata={
                'processing_time': processing_time,
                'extraction_method': 'image_ocr_and_description'
            }
        )
    
    def _combine_image_content(self, description: str, extracted_text: str) -> str:
        """Combine image description and OCR text for NER processing."""
        parts = []
        if description and description.strip():
            parts.append(f"Image Description: {description}")
        if extracted_text and extracted_text.strip():
            parts.append(f"Extracted Text: {extracted_text}")
        
        return "\n\n".join(parts) if parts else "No content extracted from image"
    
    async def _get_image_properties(self, image_path: str) -> Dict[str, Any]:
        """Extract image properties like dimensions, format, etc."""
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                return {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'size_bytes': os.path.getsize(image_path)
                }
        except Exception as e:
            logger.warning(f"Could not extract image properties: {e}")
            return {}
    
    async def _process_pdf(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Process PDF files to extract text and structure in standardized format."""
        file_path = document['file_path']
        start_time = datetime.now()
        
        # Method 1: Use PyPDF2 or pdfplumber
        text_content = await self._extract_pdf_text(file_path)
        
        # Method 2: Use OCR for scanned PDFs
        if not text_content or len(text_content.strip()) < 50:
            text_content = await self._ocr_pdf(file_path)
        
        # Method 3: Use Groq to analyze PDF structure
        analysis = await self._analyze_pdf_structure(file_path, text_content)
        
        # Get page count and metadata
        page_count = await self._get_pdf_page_count(file_path)
        
        # Create structured segments by page or section
        content_segments = self._segment_pdf_content(text_content, page_count)
        
        # Prepare modality-specific data
        modality_data = {
            'text_content': text_content,
            'page_count': page_count,
            'structure_analysis': analysis,
            'processing_method': 'pdf_extraction',
            'is_scanned': len(text_content.strip()) < 50,
            'estimated_pages_with_text': len([s for s in content_segments if len(s.get('content', '')) > 20]),
            'document_type': self._infer_pdf_type(text_content, analysis)
        }
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return self._create_structured_document(
            document=document,
            content=text_content or "PDF content not extracted",
            content_segments=content_segments,
            modality_data=modality_data,
            extraction_metadata={
                'processing_time': processing_time,
                'extraction_method': 'pdf_text_extraction'
            }
        )
    
    def _segment_pdf_content(self, text_content: str, page_count: int) -> List[Dict[str, Any]]:
        """Segment PDF content by pages or sections."""
        if not text_content:
            return []
        
        segments = []
        # Try to split by page indicators or paragraphs
        paragraphs = text_content.split('\n\n')
        
        for idx, para in enumerate(paragraphs):
            if para.strip():
                segments.append({
                    'segment_id': f"pdf_seg_{idx}",
                    'segment_type': 'paragraph',
                    'content': para.strip(),
                    'position': idx,
                    'estimated_page': min(page_count, (idx // 3) + 1) if page_count > 0 else 1
                })
        
        return segments
    
    def _infer_pdf_type(self, content: str, analysis: Dict) -> str:
        """Infer the type of PDF document."""
        if not content:
            return "unknown"
        
        content_lower = content.lower()
        
        # Check for common document types
        if any(word in content_lower for word in ['abstract', 'methodology', 'references']):
            return "research_paper"
        elif any(word in content_lower for word in ['invoice', 'amount', 'payment']):
            return "invoice"
        elif any(word in content_lower for word in ['resume', 'experience', 'education']):
            return "resume"
        elif any(word in content_lower for word in ['contract', 'agreement', 'terms']):
            return "legal_document"
        else:
            return "general_document"
    
    async def _process_video(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Process video files to extract audio, frames, and generate descriptions."""
        file_path = document['file_path']
        
        # Extract audio from video
        audio_path = await self._extract_audio_from_video(file_path)
        
        # Transcribe audio
        transcript = ""
        if audio_path:
            transcript = await self._transcribe_audio_groq(audio_path)
            # Clean up temporary audio file
            if audio_path != file_path:
                os.unlink(audio_path)
        
        # Extract key frames and generate descriptions
        frame_descriptions = await self._analyze_video_frames(file_path)
        
        combined_content = f"Video Transcript: {transcript}\nFrame Analysis: {frame_descriptions}"
        
        document['content'] = combined_content
        document['modality_specific_data'] = {
            'transcript': transcript,
            'frame_descriptions': frame_descriptions,
            'duration': await self._get_video_duration(file_path),
            'processing_method': 'video_analysis'
        }
        
        return document
    
    async def _process_text(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Process text files (minimal processing needed)."""
        file_path = document['file_path']
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
        
        document['content'] = content
        document['modality_specific_data'] = {
            'processing_method': 'direct_read'
        }
        
        return document
    
    # Audio Processing Methods
    async def _transcribe_audio_groq(self, audio_path: str) -> str:
        """Transcribe audio using Groq's Whisper model."""
        if not self.groq_client:
            return ""
            
        try:
            # Note: Groq currently doesn't have direct Whisper API
            # You would need to use their supported models or external services
            # This is a placeholder for future implementation
            logger.info("Groq Whisper transcription would be implemented here")
            return ""
        except Exception as e:
            logger.error(f"Groq audio transcription failed: {e}")
            return ""
    
    async def _transcribe_audio_local(self, audio_path: str) -> str:
        """Transcribe audio using local Whisper model."""
        try:
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(audio_path)
            return result["text"]
        except ImportError:
            logger.warning("Whisper not installed for local audio transcription")
            return ""
        except Exception as e:
            logger.error(f"Local audio transcription failed: {e}")
            return ""
    
    async def _transcribe_audio_external(self, audio_path: str) -> str:
        """Transcribe audio using external services."""
        # Implement Google Speech-to-Text, Azure Cognitive Services, etc.
        # Placeholder for external service integration
        return ""
    
    async def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio file duration."""
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0  # Convert to seconds
        except ImportError:
            logger.warning("pydub not installed for audio duration detection")
            return 0.0
    
    # Image Processing Methods
    async def _describe_image_groq(self, image_path: str) -> str:
        """Generate image description using Groq LLM with image analysis."""
        if not self.groq_client:
            return ""
            
        try:
            # Since Groq doesn't support direct image input, we need to use OCR first
            # then ask the LLM to describe based on extracted text and metadata
            extracted_text = await self._extract_image_text(image_path)
            
            prompt = f"""
            Analyze this image based on the extracted text and provide a detailed description.
            Extracted text: {extracted_text}
            
            Describe what you think the image contains, the main subjects, colors, composition,
            and any other relevant details. Be comprehensive but concise.
            """
            
            response = self.groq_client.chat.completions.create(
                model=self.model_config['image'],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Groq image description failed: {e}")
            return ""
    
    async def _extract_image_text(self, image_path: str) -> str:
        """Extract text from image using OCR."""
        try:
            import pytesseract
            from PIL import Image
            
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            return text.strip()
            
        except ImportError:
            logger.warning("pytesseract or PIL not installed for OCR")
            return ""
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return ""
    
    async def _describe_image_local(self, image_path: str) -> str:
        """Generate image description using local vision models."""
        # Placeholder for local vision models (CLIP, etc.)
        return ""
    
    async def _detect_objects(self, image_path: str) -> List[str]:
        """Detect objects in image."""
        # Placeholder for object detection
        return []
    
    # PDF Processing Methods
    async def _extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text from PDF using PyPDF2 or pdfplumber."""
        try:
            import pdfplumber
            
            text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text.strip()
            
        except ImportError:
            # Fallback to PyPDF2
            try:
                import PyPDF2
                text = ""
                with open(pdf_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                return text.strip()
            except ImportError:
                logger.warning("PDF processing libraries not installed")
                return ""
        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            return ""
    
    async def _ocr_pdf(self, pdf_path: str) -> str:
        """OCR scanned PDFs."""
        # Placeholder for PDF OCR implementation
        return ""
    
    async def _analyze_pdf_structure(self, pdf_path: str, content: str) -> Dict[str, Any]:
        """Analyze PDF structure using Groq."""
        if not self.groq_client or not content:
            return {}
            
        try:
            prompt = f"""
            Analyze this PDF content and identify its structure:
            
            {content[:3000]}  # Limit content length
            
            Identify:
            1. Document type (report, paper, manual, etc.)
            2. Main sections/headings
            3. Key topics covered
            4. Writing style and tone
            
            Provide a structured analysis.
            """
            
            response = self.groq_client.chat.completions.create(
                model=self.model_config['pdf'],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            return {"structure_analysis": response.choices[0].message.content}
            
        except Exception as e:
            logger.error(f"PDF structure analysis failed: {e}")
            return {}
    
    async def _get_pdf_page_count(self, pdf_path: str) -> int:
        """Get number of pages in PDF."""
        try:
            import PyPDF2
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                return len(reader.pages)
        except:
            return 0
    
    # Video Processing Methods
    async def _extract_audio_from_video(self, video_path: str) -> str:
        """Extract audio from video file."""
        try:
            from moviepy.editor import VideoFileClip
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                video = VideoFileClip(video_path)
                video.audio.write_audiofile(temp_audio.name)
                return temp_audio.name
                
        except ImportError:
            logger.warning("moviepy not installed for audio extraction")
            return video_path  # Return original path as fallback
        except Exception as e:
            logger.error(f"Audio extraction failed: {e}")
            return video_path
    
    async def _analyze_video_frames(self, video_path: str) -> str:
        """Analyze video frames and generate descriptions."""
        # Placeholder for frame extraction and analysis
        return "Video frame analysis not implemented"
    
    async def _get_video_duration(self, video_path: str) -> float:
        """Get video duration."""
        try:
            from moviepy.editor import VideoFileClip
            video = VideoFileClip(video_path)
            return video.duration
        except ImportError:
            return 0.0


# Utility function for the pipeline
async def preprocess_document(document: Dict[str, Any], groq_api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Preprocess document to convert multi-modal data to text for LLM processing.
    
    Args:
        document: Document dictionary
        groq_api_key: Groq API key for processing
        
    Returns:
        Processed document with text content
    """
    processor = MultiModalProcessor(groq_api_key=groq_api_key)
    return await processor.process_document(document)