#!/usr/bin/env python3
"""
PDF parser with robust fallbacks:
1) PyMuPDF text extraction
2) pdfminer.six text extraction
3) OCR (render pages via PyMuPDF and run Tesseract)
"""
import asyncio
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, Optional, List

from loguru import logger

# Optional deps are imported inside functions to avoid import cost if not used


@dataclass
class PDFParserConfig:
    max_pages: Optional[int] = None  # limit pages for very large PDFs
    ocr_dpi: int = 200               # render DPI for OCR
    ocr_enabled: bool = True


class PDFParser:
    def __init__(self, config: Optional[PDFParserConfig] = None):
        self.config = config or PDFParserConfig()

    async def parse(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        doc must include:
          - doc_id: str
          - file_path: str
        """
        file_path = doc.get("file_path")
        if not file_path:
            raise ValueError("PDFParser.parse: 'file_path' missing in doc")

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")

        # Do all heavy work in a background thread to keep event loop responsive
        content = await asyncio.to_thread(self._extract_pdf_content, path)

        metadata = {
            "pages": None,  # filled where possible below
            "source_path": str(path),
            "extraction": "automatic",
        }

        return {
            "doc_id": doc.get("doc_id", path.stem),
            "type": "pdf",
            "title": doc.get("title", path.stem),
            "content": content,
            "metadata": metadata,
        }

    def _extract_pdf_content(self, path: Path) -> str:
        # 1) Try PyMuPDF
        try:
            text, pages = self._extract_with_pymupdf(path)
            if text.strip():
                return text
            logger.warning(f"PyMuPDF returned empty text for {path}, falling back to pdfminer")
        except Exception as e:
            logger.error(f"PyMuPDF extraction error for {path}: {e}")

        # 2) Fallback to pdfminer.six
        try:
            text = self._extract_with_pdfminer(path)
            if text.strip():
                return text
            logger.warning(f"pdfminer returned empty text for {path}")
        except Exception as e:
            logger.warning(f"pdfminer extraction error for {path}: {e}")

        # 3) Final fallback: OCR (if enabled)
        if self.config.ocr_enabled:
            try:
                text = self._extract_with_ocr(path)
                if text.strip():
                    logger.info(f"OCR succeeded for {path}")
                    return text
            except Exception as e:
                logger.warning(f"OCR extraction error for {path}: {e}")

        # Nothing worked
        logger.warning(f"No text could be extracted from {path}")
        return ""

    def _extract_with_pymupdf(self, path: Path) -> tuple[str, int]:
        import fitz  # PyMuPDF

        texts: List[str] = []
        pages = 0
        # IMPORTANT: keep doc open for the whole loop, no async here.
        with fitz.open(str(path)) as doc:
            total = len(doc)
            limit = min(total, self.config.max_pages) if self.config.max_pages else total
            for i in range(limit):
                page = doc.load_page(i)
                # "text" layout is generally best for plain text
                t = page.get_text("text") or ""
                if not t.strip():
                    # Try a different extractor as a backup
                    t = page.get_text("blocks") or ""
                texts.append(t)
                pages += 1
        return ("\n\n".join(texts), pages)

    def _extract_with_pdfminer(self, path: Path) -> str:
        from pdfminer.high_level import extract_text
        # Suppress pdfminer noisy warnings is optional; keep default
        return extract_text(str(path)) or ""

    def _extract_with_ocr(self, path: Path) -> str:
        """
        Render pages with PyMuPDF to PNG bytes, then OCR via Tesseract.
        """
        import fitz  # PyMuPDF
        from PIL import Image
        import pytesseract

        texts: List[str] = []
        zoom = self.config.ocr_dpi / 72.0  # 72dpi base
        mat = fitz.Matrix(zoom, zoom)

        with fitz.open(str(path)) as doc:
            total = len(doc)
            limit = min(total, self.config.max_pages) if self.config.max_pages else total
            for i in range(limit):
                page = doc.load_page(i)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                png_bytes = pix.tobytes("png")
                img = Image.open(BytesIO(png_bytes))
                text = pytesseract.image_to_string(img)
                texts.append(text)

        return "\n\n".join(texts)