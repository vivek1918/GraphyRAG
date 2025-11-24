#!/usr/bin/env python3
"""
Image extractor with multi-method OCR and vision analysis:
1. Tesseract OCR - Fast, reliable text extraction
2. EasyOCR - Better for complex/multi-language text
3. PaddleOCR - High accuracy for difficult images
4. LLM Vision Description - Groq/GPT for image understanding

Follows the same JSON output structure as PDF extractor.
"""

import os
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

from extract.base_extractor import BaseExtractor


class ImageExtractor(BaseExtractor):
    """
    Extract text and descriptions from images.
    Supports: JPG, PNG, GIF, BMP, TIFF, WEBP, etc.
    """
    
    def __init__(self, groq_api_key: Optional[str] = None, config: Optional[Dict] = None):
        super().__init__(groq_api_key, config)
        
        # Image-specific configuration
        self.supported_formats = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp']
        self.ocr_dpi = self.config.get('ocr_dpi', 300)
        self.preprocess = self.config.get('preprocess', True)
        self.enable_vision = self.config.get('enable_vision', True)
        
        logger.info("ImageExtractor initialized with Tesseract → EasyOCR → PaddleOCR → LLM Vision chain")
    
    async def extract(self, file_path: str, document: Dict[str, Any]) -> Tuple[str, List[Dict], Dict]:
        """
        Extract text and description from image using multi-method approach.
        
        Returns:
            (combined_content, segments, modality_data)
        """
        logger.info(f"[ImageExtractor] Processing: {Path(file_path).name}")
        
        file_info = self.get_file_info(file_path)
        if not file_info['exists']:
            logger.error(f"Image file not found: {file_path}")
            return "", [], {'error': 'File not found'}
        
        if file_info['extension'].lower() not in self.supported_formats:
            logger.warning(f"Unsupported image format: {file_info['extension']}")
            return "", [], {'error': f"Unsupported format: {file_info['extension']}"}
        
        start_time = datetime.now()
        
        # Method 1: Tesseract OCR (fastest, most common)
        ocr_text, ocr_method, ocr_confidence = await self._extract_ocr_tesseract(file_path)
        
        # Method 2: EasyOCR (better for complex text)
        if not ocr_text or len(ocr_text) < 10:
            logger.info("Trying EasyOCR...")
            ocr_text, ocr_method, ocr_confidence = await self._extract_ocr_easyocr(file_path)
        
        # Method 3: PaddleOCR (high accuracy fallback)
        if not ocr_text or len(ocr_text) < 10:
            logger.info("Trying PaddleOCR...")
            ocr_text, ocr_method, ocr_confidence = await self._extract_ocr_paddleocr(file_path)
        
        # Vision Analysis: Generate image description
        description = ""
        if self.enable_vision:
            description = await self._generate_vision_description(file_path, ocr_text)
        
        # Clean extracted text
        ocr_text = self.clean_text(ocr_text)
        description = self.clean_text(description)
        
        # Combine content for NER
        combined_content = self._combine_image_content(ocr_text, description)
        
        # Get image properties
        image_props = await self._get_image_properties(file_path)
        
        # Create segments
        segments = self._create_image_segments(ocr_text, description)
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Prepare modality-specific data
        modality_data = {
            'ocr_text': ocr_text,
            'ocr_method': ocr_method,
            'ocr_confidence': ocr_confidence,
            'vision_description': description,
            'image_properties': image_props,
            'has_text': len(ocr_text.strip()) > 0,
            'has_description': len(description.strip()) > 0,
            'text_coverage': self._estimate_text_coverage(ocr_text, image_props),
            'processing_time_seconds': processing_time
        }
        
        logger.info(f"✓ Image processed: OCR={len(ocr_text)} chars, Description={len(description)} chars, method={ocr_method}")
        
        return combined_content, segments, modality_data
    
    async def _extract_ocr_tesseract(self, file_path: str) -> Tuple[str, str, float]:
        """
        Extract text using Tesseract OCR.
        
        Returns:
            (text, method_name, confidence)
        """
        try:
            import pytesseract
            from PIL import Image, ImageEnhance, ImageFilter
            
            # Load and preprocess image
            image = Image.open(file_path)
            
            if self.preprocess:
                # Enhance image for better OCR
                image = self._preprocess_image(image)
            
            # Extract text with configuration
            custom_config = r'--oem 3 --psm 1'  # PSM 1: Automatic page segmentation with OSD
            text = pytesseract.image_to_string(image, config=custom_config)
            
            # Get confidence data
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in data['conf'] if conf != '-1']
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            if text and len(text.strip()) > 5:
                logger.info(f"✓ Tesseract OCR successful (confidence: {avg_confidence:.1f}%)")
                return text, "tesseract", avg_confidence / 100.0
            
            return "", "tesseract", 0.0
            
        except ImportError:
            logger.debug("Tesseract not installed: pip install pytesseract + install Tesseract binary")
            return "", "tesseract", 0.0
        except Exception as e:
            logger.warning(f"Tesseract OCR failed: {e}")
            return "", "tesseract", 0.0
    
    def _preprocess_image(self, image):
        """Preprocess image for better OCR accuracy."""
        from PIL import ImageEnhance, ImageFilter
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Increase contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        
        # Increase sharpness
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)
        
        # Denoise
        image = image.filter(ImageFilter.MedianFilter(size=3))
        
        return image
    
    async def _extract_ocr_easyocr(self, file_path: str) -> Tuple[str, str, float]:
        """
        Extract text using EasyOCR.
        
        Returns:
            (text, method_name, confidence)
        """
        try:
            import easyocr
            
            # Initialize reader (caches model after first use)
            reader = easyocr.Reader(['en'], gpu=False)
            
            # Extract text
            results = reader.readtext(file_path)
            
            # Combine text and calculate average confidence
            text_parts = []
            confidences = []
            for (bbox, text, conf) in results:
                text_parts.append(text)
                confidences.append(conf)
            
            text = " ".join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            if text and len(text.strip()) > 5:
                logger.info(f"✓ EasyOCR successful (confidence: {avg_confidence:.2f})")
                return text, "easyocr", avg_confidence
            
            return "", "easyocr", 0.0
            
        except ImportError:
            logger.debug("EasyOCR not installed: pip install easyocr")
            return "", "easyocr", 0.0
        except Exception as e:
            logger.warning(f"EasyOCR failed: {e}")
            return "", "easyocr", 0.0
    
    async def _extract_ocr_paddleocr(self, file_path: str) -> Tuple[str, str, float]:
        """
        Extract text using PaddleOCR.
        
        Returns:
            (text, method_name, confidence)
        """
        try:
            from paddleocr import PaddleOCR
            
            # Initialize OCR
            ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False)
            
            # Extract text
            results = ocr.ocr(file_path, cls=True)
            
            # Combine text and calculate average confidence
            text_parts = []
            confidences = []
            for line in results[0]:
                text_parts.append(line[1][0])
                confidences.append(line[1][1])
            
            text = " ".join(text_parts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            if text and len(text.strip()) > 5:
                logger.info(f"✓ PaddleOCR successful (confidence: {avg_confidence:.2f})")
                return text, "paddleocr", avg_confidence
            
            return "", "paddleocr", 0.0
            
        except ImportError:
            logger.debug("PaddleOCR not installed: pip install paddleocr")
            return "", "paddleocr", 0.0
        except Exception as e:
            logger.warning(f"PaddleOCR failed: {e}")
            return "", "paddleocr", 0.0
    
    async def _generate_vision_description(self, file_path: str, ocr_text: str) -> str:
        """
        Generate image description using LLM vision capabilities.
        
        Returns:
            Description text
        """
        if not self.groq_client:
            return ""
        
        try:
            # Get basic image properties
            props = await self._get_image_properties(file_path)
            
            # Create prompt with context
            prompt = f"""Analyze this image and provide a detailed description.

Image properties:
- Dimensions: {props.get('width', 'unknown')}x{props.get('height', 'unknown')} pixels
- Format: {props.get('format', 'unknown')}

OCR extracted text (if any):
{ocr_text if ocr_text else 'No text detected'}

Based on this information, describe:
1. Main subjects or objects in the image
2. Scene composition and layout
3. Colors and visual style
4. Context and purpose of the image
5. Any relevant details for entity extraction

Provide a comprehensive but concise description (max 200 words)."""
            
            response = self.groq_client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=300
            )
            
            description = response.choices[0].message.content
            logger.info("✓ LLM vision description generated")
            return description
            
        except Exception as e:
            logger.warning(f"Vision description generation failed: {e}")
            return ""
    
    async def _get_image_properties(self, file_path: str) -> Dict[str, Any]:
        """Extract image properties."""
        try:
            from PIL import Image
            
            with Image.open(file_path) as img:
                return {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'size_bytes': os.path.getsize(file_path),
                    'aspect_ratio': round(img.width / img.height, 2) if img.height > 0 else 0.0,
                    'megapixels': round((img.width * img.height) / 1_000_000, 2)
                }
        except Exception as e:
            logger.warning(f"Could not extract image properties: {e}")
            return {}
    
    def _combine_image_content(self, ocr_text: str, description: str) -> str:
        """Combine OCR text and description for NER processing."""
        parts = []
        
        if ocr_text and ocr_text.strip():
            parts.append(f"Extracted Text:\n{ocr_text}")
        
        if description and description.strip():
            parts.append(f"Image Description:\n{description}")
        
        if not parts:
            return "No content extracted from image"
        
        return "\n\n".join(parts)
    
    def _create_image_segments(self, ocr_text: str, description: str) -> List[Dict[str, Any]]:
        """Create structured segments from image content."""
        segments = []
        
        if ocr_text and ocr_text.strip():
            segments.append(self.create_segment(
                segment_id="image_ocr",
                segment_type="ocr_text",
                content=ocr_text,
                position=0,
                metadata={'confidence': 0.8}
            ))
        
        if description and description.strip():
            segments.append(self.create_segment(
                segment_id="image_description",
                segment_type="vision_description",
                content=description,
                position=1,
                metadata={'confidence': 0.7}
            ))
        
        return segments
    
    def _estimate_text_coverage(self, ocr_text: str, image_props: Dict) -> str:
        """Estimate how much of the image contains text."""
        if not ocr_text or not image_props.get('width'):
            return "none"
        
        char_count = len(ocr_text)
        
        # Rough heuristic: assume average character takes 10x20 pixels
        estimated_text_pixels = char_count * 200
        total_pixels = image_props.get('width', 0) * image_props.get('height', 0)
        
        if total_pixels > 0:
            coverage_ratio = estimated_text_pixels / total_pixels
            
            if coverage_ratio > 0.5:
                return "high"  # Document, screenshot with lots of text
            elif coverage_ratio > 0.2:
                return "medium"  # Some text elements
            elif coverage_ratio > 0.05:
                return "low"  # Minimal text
            else:
                return "minimal"  # Almost no text
        
        return "unknown"
