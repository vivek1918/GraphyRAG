#!/usr/bin/env python3
"""
PDF parser with robust fallbacks and extraction accuracy proxy.

Fallback order:
1) PyMuPDF
2) pdfminer.six
3) OCR (Tesseract)

Computes Extraction Accuracy Proxy (0–100) using PDF as weak ground truth.
"""

import asyncio
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from loguru import logger


@dataclass
class PDFParserConfig:
    max_pages: Optional[int] = None
    ocr_dpi: int = 300  # Higher DPI for better OCR
    ocr_enabled: bool = True
    ocr_lang: str = "eng"  # Tesseract language
    enhance_images: bool = True  # Pre-process images
    post_process_text: bool = True  # Clean common OCR errors
    compare_methods: bool = True  # Compare multiple methods and pick best


class PDFParser:
    def __init__(self, config: Optional[PDFParserConfig] = None):
        self.config = config or PDFParserConfig()

    async def parse(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        path = Path(doc["file_path"])

        content, method, pdf_stats = await asyncio.to_thread(
            self._extract_pdf_content, path
        )

        accuracy, breakdown = self._extraction_accuracy(content, pdf_stats)

        logger.info(
            f"[PDF] {path.name} | "
            f"method={method:<8} | "
            f"accuracy={accuracy:>3}/100"
        )

        return {
            "doc_id": doc.get("doc_id", path.stem),
            "type": "pdf",
            "title": doc.get("title", path.stem),
            "content": content,
            "metadata": {
                "source_path": str(path),
                "extraction_method": method,
                "extraction_accuracy": accuracy,
                "accuracy_breakdown": breakdown,
                "pdf_stats": pdf_stats,
            },
        }

    # ------------------------------------------------------------------
    # EXTRACTION
    # ------------------------------------------------------------------

    def _extract_pdf_content(self, path: Path) -> Tuple[str, str, Dict]:
        import fitz

        pdf_stats = {}
        texts: List[str] = []
        candidates = []  # Store (text, method, accuracy) tuples

        with fitz.open(str(path)) as doc:
            total_pages = len(doc)
            pdf_stats["page_count"] = total_pages

            limit = min(total_pages, self.config.max_pages) if self.config.max_pages else total_pages

            # --- Try PyMuPDF ---
            try:
                for i in range(limit):
                    page = doc.load_page(i)
                    texts.append(page.get_text("text") or "")
                text = "\n\n".join(texts)
                if text.strip():
                    pdf_stats["expected_density"] = self._expected_density(doc, limit)
                    if self.config.post_process_text:
                        text = self._post_process_text(text)
                    if self.config.compare_methods:
                        acc, _ = self._extraction_accuracy(text, pdf_stats)
                        candidates.append((text, "pymupdf", acc))
                    else:
                        return text, "pymupdf", pdf_stats
            except Exception as e:
                logger.warning(f"[PDF] PyMuPDF failed ({path.name}): {e}")

        # --- pdfminer ---
        try:
            from pdfminer.high_level import extract_text
            text = extract_text(str(path)) or ""
            if text.strip():
                if self.config.post_process_text:
                    text = self._post_process_text(text)
                if self.config.compare_methods:
                    acc, _ = self._extraction_accuracy(text, pdf_stats)
                    candidates.append((text, "pdfminer", acc))
                else:
                    return text, "pdfminer", pdf_stats
        except Exception as e:
            logger.warning(f"[PDF] pdfminer failed ({path.name}): {e}")

        # --- OCR ---
        if self.config.ocr_enabled:
            try:
                text = self._extract_with_ocr(path)
                if text.strip():
                    if self.config.post_process_text:
                        text = self._post_process_text(text)
                    if self.config.compare_methods:
                        acc, _ = self._extraction_accuracy(text, pdf_stats)
                        candidates.append((text, "ocr", acc))
                    else:
                        return text, "ocr", pdf_stats
            except Exception as e:
                logger.warning(f"[PDF] OCR failed ({path.name}): {e}")

        # Pick best method based on accuracy
        if candidates:
            best = max(candidates, key=lambda x: x[2])
            logger.debug(f"[PDF] Selected {best[1]} (accuracy: {best[2]})")
            return best[0], best[1], pdf_stats

        return "", "failed", pdf_stats

    def _extract_with_ocr(self, path: Path) -> str:
        import fitz
        from PIL import Image, ImageEnhance, ImageFilter
        import pytesseract

        texts = []
        zoom = self.config.ocr_dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        with fitz.open(str(path)) as doc:
            for page in doc:
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = Image.open(BytesIO(pix.tobytes("png")))
                
                # Pre-process image for better OCR
                if self.config.enhance_images:
                    img = self._enhance_image(img)
                
                # Better OCR config with language support
                ocr_config = (
                    f"--psm 6 -l {self.config.ocr_lang} "
                    "-c preserve_interword_spaces=1 "
                    "--oem 3"  # Use LSTM OCR engine
                )
                texts.append(pytesseract.image_to_string(img, config=ocr_config))

        return "\n\n".join(texts)
    
    def _enhance_image(self, img: 'Image.Image') -> 'Image.Image':
        """Pre-process image for better OCR accuracy."""
        from PIL import ImageEnhance, ImageFilter
        
        # Convert to grayscale
        img = img.convert('L')
        
        # Increase contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        
        # Sharpen
        img = img.filter(ImageFilter.SHARPEN)
        
        # Denoise
        img = img.filter(ImageFilter.MedianFilter(size=3))
        
        return img
    
    def _post_process_text(self, text: str) -> str:
        """Clean common OCR errors and formatting issues."""
        # Fix common OCR substitutions
        replacements = {
            r'\b0(?=[a-z])': 'o',  # 0 -> o
            r'\b1(?=[a-z])': 'l',  # 1 -> l
            r'(?<=[a-z])1\b': 'l',
            r'(?<=[a-z])0\b': 'o',
            r'\|\|': 'll',  # || -> ll
            r'\s+': ' ',  # Multiple spaces -> single space
        }
        
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        # Remove excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Fix broken hyphenation at line ends
        text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
        
        return text.strip()

    # ------------------------------------------------------------------
    # PDF-AWARE ACCURACY METRICS
    # ------------------------------------------------------------------

    def _expected_density(self, doc, pages: int) -> float:
        """Expected chars/page based on page area."""
        areas = []
        for i in range(pages):
            rect = doc.load_page(i).rect
            areas.append(rect.width * rect.height)
        return sum(areas) / max(pages, 1)

    def _extraction_accuracy(self, text: str, pdf_stats: Dict) -> Tuple[int, Dict]:
        if not text.strip():
            return 0, {}

        char_count = len(text)
        word_count = len(text.split())

        noise_ratio = self._ocr_noise_ratio(text)
        broken_ratio = self._broken_word_ratio(text)
        spacing_ratio = self._weird_spacing_ratio(text)
        corruption_ratio = self._char_corruption_ratio(text)

        # Text density vs expected (PDF-aware)
        expected = pdf_stats.get("expected_density", 1)
        density_ratio = min(char_count / (expected * pdf_stats.get("page_count", 1)), 1.5)

        score = 100
        score -= noise_ratio * 250
        score -= broken_ratio * 200
        score -= spacing_ratio * 120
        score -= corruption_ratio * 300

        # Density penalty (too sparse = missing text)
        if density_ratio < 0.4:
            score -= 30
        elif density_ratio < 0.6:
            score -= 15

        score = max(int(score), 0)

        breakdown = {
            "noise_ratio": round(noise_ratio, 4),
            "broken_word_ratio": round(broken_ratio, 4),
            "spacing_ratio": round(spacing_ratio, 4),
            "corruption_ratio": round(corruption_ratio, 4),
            "density_ratio": round(density_ratio, 4),
        }

        return score, breakdown

    # ------------------------------------------------------------------
    # LOW-LEVEL SIGNALS
    # ------------------------------------------------------------------

    def _ocr_noise_ratio(self, text: str) -> float:
        bad = re.findall(r"[^\w\s@.+\-()/,:]", text)
        return len(bad) / max(len(text), 1)

    def _broken_word_ratio(self, text: str) -> float:
        words = text.split()
        broken = [w for w in words if len(w) > 3 and any(c.isdigit() for c in w)]
        return len(broken) / max(len(words), 1)

    def _weird_spacing_ratio(self, text: str) -> float:
        return text.count("  ") / max(len(text.split()), 1)

    def _char_corruption_ratio(self, text: str) -> float:
        corrupt = sum(1 for c in text if ord(c) > 0xFFFD or c == "\uFFFD")
        return corrupt / max(len(text), 1)
