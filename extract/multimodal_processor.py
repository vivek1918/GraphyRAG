#!/usr/bin/env python3
"""
Multi-modal data processor for handling different file formats before LLM processing.
Coordinator that routes documents to format-specific extractors.

Architecture:
- AudioExtractor: Whisper → Groq → AssemblyAI → Google Speech-to-Text
- ImageExtractor: Tesseract → EasyOCR → PaddleOCR + LLM Vision
- VideoExtractor: Audio transcription + Frame analysis
- TextExtractor: Encoding detection + Paragraph segmentation
- PDF: Using existing robust multi-method extraction

All extractors return standardized JSON structure for consistent NER/RE downstream processing.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import tempfile
from loguru import logger

# Import format-specific extractors
from extract.audio_extractor import AudioExtractor
from extract.image_extractor import ImageExtractor
from extract.video_extractor import VideoExtractor
from extract.text_extractor import TextExtractor

# PDF imports (keep existing robust implementation)
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


class MultiModalProcessor:
    """
    Coordinator for multi-modal document processing.
    Routes documents to format-specific extractors and returns standardized output.
    """
    
    def __init__(self, groq_api_key: Optional[str] = None, enable_llm_hints: bool = False):
        """
        Initialize MultiModalProcessor with format-specific extractors.
        
        Args:
            groq_api_key: Groq API key for LLM-based enhancements
            enable_llm_hints: Enable LLM-based entity hint extraction (default: False to avoid blocking)
        """
        if not groq_api_key:
            groq_api_key = os.getenv('GROQ_API_KEY')
        
        # Configuration for extractors
        extractor_config = {
            'enable_llm_hints': enable_llm_hints
        }
        
        # Initialize format-specific extractors
        self.audio_extractor = AudioExtractor(groq_api_key=groq_api_key, config=extractor_config)
        self.image_extractor = ImageExtractor(groq_api_key=groq_api_key, config=extractor_config)
        self.video_extractor = VideoExtractor(groq_api_key=groq_api_key, config=extractor_config)
        self.text_extractor = TextExtractor(groq_api_key=groq_api_key, config=extractor_config)
        self.enable_llm_hints = enable_llm_hints
        
        logger.info(f"✓ MultiModalProcessor initialized (LLM hints: {'enabled' if enable_llm_hints else 'disabled'})")
    
    async def process_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process document using appropriate format-specific extractor.
        
        Args:
            document: Document dictionary with file_path, file_type, doc_id, etc.
            
        Returns:
            Structured document with standardized format for NER/RE
        """
        file_path = document.get('file_path')
        file_type = document.get('file_type', 'text')
        doc_id = document.get('doc_id', Path(file_path).stem if file_path else 'unknown')
        
        if not file_path or not os.path.exists(file_path):
            logger.warning(f"[{doc_id}] File not found: {file_path}")
            return self._create_error_document(document, "File not found")
        
        logger.info(f"[{doc_id}] Processing {file_type} document...")
        start_time = datetime.now()
        
        try:
            # Route to appropriate extractor
            if file_type == 'audio':
                content, segments, modality_data = await self.audio_extractor.extract(file_path, document)
            elif file_type == 'image':
                content, segments, modality_data = await self.image_extractor.extract(file_path, document)
            elif file_type == 'video':
                content, segments, modality_data = await self.video_extractor.extract(file_path, document)
            elif file_type == 'text':
                content, segments, modality_data = await self.text_extractor.extract(file_path, document)
            elif file_type == 'pdf':
                # PDF uses existing implementation (already has robust extraction)
                return await self._process_pdf(document)
            else:
                logger.warning(f"[{doc_id}] Unsupported file type: {file_type}")
                return self._create_error_document(document, f"Unsupported file type: {file_type}")
            
            # Check if extraction failed
            if 'error' in modality_data:
                return self._create_error_document(document, modality_data['error'])
            
            # Extract entity hints for downstream NER
            entity_hints = await self._extract_entity_hints(content, file_type)
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Create standardized structured document
            structured_doc = {
                **document,  # Preserve original fields
                'content': content,
                'content_segments': segments,
                'modality_specific_data': modality_data,
                'extracted_entities_hints': entity_hints,
                'metadata': {
                    'extraction_status': 'success',
                    'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                    'content_length': len(content),
                    'num_segments': len(segments),
                    'processing_time': processing_time,
                    'extractor_used': f"{file_type}_extractor"
                },
                'extraction_quality': self._assess_extraction_quality(content, segments),
                'processed_at': datetime.now().isoformat()
            }
            
            logger.info(f"[{doc_id}] ✓ Processed successfully in {processing_time:.2f}s")
            return structured_doc
            
        except Exception as e:
            logger.error(f"[{doc_id}] Error processing {file_type} document: {e}")
            return self._create_error_document(document, str(e))
    
    async def _extract_entity_hints(self, content: str, modality: str) -> list:
        """Extract entity hints from content using base extractor utility."""
        try:
            # Use any extractor's entity hint method (they all inherit from BaseExtractor)
            return await self.text_extractor.extract_entity_hints(content, modality)
        except Exception as e:
            logger.warning(f"Entity hint extraction failed: {e}")
            return []
    
    def _assess_extraction_quality(self, content: str, segments: list) -> Dict[str, Any]:
        """Assess extraction quality."""
        has_content = len(content.strip()) > 0
        content_length = len(content)
        
        # Calculate confidence
        if content_length > 500:
            confidence = 0.9
        elif content_length > 100:
            confidence = 0.7
        else:
            confidence = 0.5 if has_content else 0.0
        
        return {
            'success': has_content,
            'confidence': confidence,
            'completeness': min(1.0, content_length / 1000) if content_length > 0 else 0.0,
            'content_length': content_length,
            'num_segments': len(segments)
        }
    
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
    
    # ========== PDF Processing (Keep existing robust implementation) ==========
    
    async def _process_pdf(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Process PDF files to extract text and structure in standardized format."""
        file_path = document['file_path']
        doc_id = document.get('doc_id', Path(file_path).stem)
        start_time = datetime.now()
        
        # Method 1: Use pdfplumber or PyPDF2
        text_content = await self._extract_pdf_text(file_path)
        
        # Get page count
        page_count = await self._get_pdf_page_count(file_path)
        
        # Create structured segments by page or section
        content_segments = self._segment_pdf_content(text_content, page_count)
        
        # Prepare modality-specific data
        modality_data = {
            'text_content': text_content,
            'page_count': page_count,
            'processing_method': 'pdf_extraction',
            'is_scanned': len(text_content.strip()) < 50,
            'estimated_pages_with_text': len([s for s in content_segments if len(s.get('content', '')) > 20]),
            'document_type': self._infer_pdf_type(text_content)
        }
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Create standardized document
        return {
            **document,
            'content': text_content or "PDF content not extracted",
            'content_segments': content_segments,
            'modality_specific_data': modality_data,
            'metadata': {
                'extraction_status': 'success',
                'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                'content_length': len(text_content),
                'num_segments': len(content_segments),
                'processing_time': processing_time,
                'extractor_used': 'pdf_legacy'
            },
            'extraction_quality': self._assess_extraction_quality(text_content, content_segments),
            'processed_at': datetime.now().isoformat()
        }
    
    async def _extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text from PDF using pdfplumber or PyPDF2."""
        try:
            if pdfplumber:
                text = ""
                with pdfplumber.open(pdf_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                return text.strip()
            elif PyPDF2:
                text = ""
                with open(pdf_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                return text.strip()
            else:
                logger.warning("PDF processing libraries not installed")
                return ""
        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            return ""
    
    async def _get_pdf_page_count(self, pdf_path: str) -> int:
        """Get number of pages in PDF."""
        try:
            if PyPDF2:
                with open(pdf_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    return len(reader.pages)
            elif pdfplumber:
                with pdfplumber.open(pdf_path) as pdf:
                    return len(pdf.pages)
            return 0
        except:
            return 0
    
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
    
    def _infer_pdf_type(self, content: str) -> str:
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
