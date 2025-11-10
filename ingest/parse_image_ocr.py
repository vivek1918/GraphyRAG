#!/usr/bin/env python3
"""
Image OCR parser using PaddleOCR and Tesseract fallback.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from loguru import logger

class ImageParser:
    """Image parser with OCR capabilities."""
    
    def __init__(self):
        self.paddle_ocr = None
        self.tesseract_available = False
        self._initialize_ocr()
    
    def _initialize_ocr(self):
        """Initialize OCR engines."""
        # Try PaddleOCR first
        try:
            from paddleocr import PaddleOCR
            self.paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en')
            logger.info("Initialized PaddleOCR")
        except ImportError:
            logger.warning("PaddleOCR not available")
        
        # Check Tesseract availability
        try:
            import pytesseract
            self.tesseract_available = True
            logger.info("Tesseract is available")
        except ImportError:
            logger.warning("Tesseract not available")
    
    async def parse(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Parse image file and extract text with OCR."""
        try:
            file_path = Path(document['file_path'])
            
            if not file_path.exists():
                logger.error(f"Image file not found: {file_path}")
                return await self._create_fallback_document(document)
            
            # For synthetic image files with known content
            if document.get('content'):
                return await self._create_document_from_content(document)
            
            # Perform OCR
            ocr_result = await self._perform_ocr(file_path)
            
            parsed_doc = {
                'doc_id': document['doc_id'],
                'type': 'image',
                'content': ocr_result['text'],
                'metadata': {
                    'source_type': 'image',
                    'file_path': str(file_path),
                    'ocr_engine': ocr_result['engine'],
                    'confidence': ocr_result['confidence'],
                    'text_regions': ocr_result['regions']
                },
                'ocr_data': {
                    'regions': ocr_result['regions'],
                    'full_result': ocr_result.get('full_result', {})
                }
            }
            
            # Add ground truth if available
            if 'entities' in document:
                parsed_doc['ground_truth_entities'] = document['entities']
            if 'relations' in document:
                parsed_doc['ground_truth_relations'] = document['relations']
            
            logger.debug(f"Processed image document: {document['doc_id']}")
            return parsed_doc
            
        except Exception as e:
            logger.error(f"Error parsing image document {document.get('doc_id')}: {e}")
            return await self._create_fallback_document(document)
    
    async def _perform_ocr(self, image_path: Path) -> Dict[str, Any]:
        """Perform OCR on image using available engines."""
        # Try PaddleOCR first
        if self.paddle_ocr:
            try:
                result = self.paddle_ocr.ocr(str(image_path), cls=True)
                return await self._parse_paddle_result(result, image_path)
            except Exception as e:
                logger.warning(f"PaddleOCR failed: {e}")
        
        # Fallback to Tesseract
        if self.tesseract_available:
            try:
                return await self._perform_tesseract_ocr(image_path)
            except Exception as e:
                logger.warning(f"Tesseract failed: {e}")
        
        # Final fallback
        return {
            'text': 'OCR not available for this image',
            'engine': 'none',
            'confidence': 0.0,
            'regions': []
        }
    
    async def _parse_paddle_result(self, result: List, image_path: Path) -> Dict[str, Any]:
        """Parse PaddleOCR result."""
        if not result or not result[0]:
            return {
                'text': '',
                'engine': 'paddle',
                'confidence': 0.0,
                'regions': []
            }
        
        full_text = []
        regions = []
        total_confidence = 0.0
        count = 0
        
        for line in result[0]:
            if line and len(line) >= 2:
                text = line[1][0]
                confidence = line[1][1]
                coordinates = line[0]
                
                full_text.append(text)
                regions.append({
                    'text': text,
                    'confidence': confidence,
                    'bbox': coordinates,
                    'type': 'text'
                })
                
                total_confidence += confidence
                count += 1
        
        avg_confidence = total_confidence / count if count > 0 else 0.0
        
        return {
            'text': ' '.join(full_text),
            'engine': 'paddle',
            'confidence': avg_confidence,
            'regions': regions,
            'full_result': result
        }
    
    async def _perform_tesseract_ocr(self, image_path: Path) -> Dict[str, Any]:
        """Perform OCR using Tesseract."""
        try:
            import pytesseract
            from PIL import Image
            
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            
            # Get detailed data
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            
            regions = []
            confidences = []
            
            for i in range(len(data['text'])):
                text_item = data['text'][i].strip()
                if text_item:  # Only non-empty text
                    confidence = float(data['conf'][i]) / 100.0  # Normalize to 0-1
                    regions.append({
                        'text': text_item,
                        'confidence': confidence,
                        'bbox': [
                            data['left'][i],
                            data['top'][i],
                            data['width'][i],
                            data['height'][i]
                        ],
                        'type': 'text'
                    })
                    confidences.append(confidence)
            
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return {
                'text': text,
                'engine': 'tesseract',
                'confidence': avg_confidence,
                'regions': regions,
                'full_result': data
            }
            
        except Exception as e:
            logger.error(f"Tesseract OCR error: {e}")
            raise
    
    async def _create_document_from_content(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Create document from existing content (for synthetic data)."""
        return {
            'doc_id': document['doc_id'],
            'type': 'image',
            'content': document['content'],
            'metadata': {
                'source_type': 'image',
                'file_path': document.get('file_path', ''),
                'ocr_engine': 'synthetic',
                'confidence': 1.0,
                'text_regions': []
            },
            'ground_truth_entities': document.get('entities', []),
            'ground_truth_relations': document.get('relations', [])
        }
    
    async def _create_fallback_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Create fallback document when OCR fails."""
        return {
            'doc_id': document['doc_id'],
            'type': 'image',
            'content': document.get('content', 'OCR not available'),
            'metadata': {
                'source_type': 'image',
                'file_path': document.get('file_path', ''),
                'ocr_engine': 'fallback',
                'confidence': 0.0,
                'text_regions': [],
                'error': 'OCR processing failed'
            },
            'ground_truth_entities': document.get('entities', []),
            'ground_truth_relations': document.get('relations', [])
        }
    
    async def extract_text_from_image(self, image_path: Path) -> str:
        """Extract text from a single image file."""
        try:
            ocr_result = await self._perform_ocr(image_path)
            return ocr_result['text']
        except Exception as e:
            logger.error(f"Error extracting text from {image_path}: {e}")
            return ""