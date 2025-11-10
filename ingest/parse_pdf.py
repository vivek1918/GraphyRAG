#!/usr/bin/env python3
"""
PDF document parser using multiple backends (PyMuPDF, pdfminer).
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from loguru import logger

class PDFParser:
    """PDF document parser with text extraction."""
    
    def __init__(self):
        self.backends = ['pymupdf', 'pdfminer']
    
    async def parse(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Parse PDF document and extract content."""
        try:
            file_path = Path(document['file_path'])
            
            if not file_path.exists():
                logger.error(f"PDF file not found: {file_path}")
                return await self._create_fallback_document(document)
            
            # For synthetic PDFs with known content
            if document.get('content'):
                return await self._create_document_from_content(document)
            
            # Try different PDF parsing backends
            pdf_content = await self._extract_pdf_content(file_path)
            
            parsed_doc = {
                'doc_id': document['doc_id'],
                'type': 'pdf',
                'content': pdf_content['text'],
                'metadata': {
                    'source_type': 'pdf',
                    'file_path': str(file_path),
                    'pages': pdf_content['pages'],
                    'backend': pdf_content['backend'],
                    'has_images': pdf_content.get('has_images', False),
                    'has_tables': pdf_content.get('has_tables', False)
                },
                'page_data': pdf_content.get('page_data', [])
            }
            
            # Add ground truth if available
            if 'entities' in document:
                parsed_doc['ground_truth_entities'] = document['entities']
            if 'relations' in document:
                parsed_doc['ground_truth_relations'] = document['relations']
            
            logger.debug(f"Parsed PDF document: {document['doc_id']}")
            return parsed_doc
            
        except Exception as e:
            logger.error(f"Error parsing PDF document {document.get('doc_id')}: {e}")
            return await self._create_fallback_document(document)
    
    async def _extract_pdf_content(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract content from PDF using available backends."""
        # Try PyMuPDF first (faster)
        try:
            return await self._extract_with_pymupdf(pdf_path)
        except Exception as e:
            logger.warning(f"PyMuPDF failed: {e}")
        
        # Fallback to pdfminer
        try:
            return await self._extract_with_pdfminer(pdf_path)
        except Exception as e:
            logger.warning(f"PDFMiner failed: {e}")
        
        # Final fallback
        return {
            'text': 'PDF parsing not available',
            'backend': 'none',
            'pages': 0,
            'page_data': []
        }
    
    async def _extract_with_pymupdf(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract PDF content using PyMuPDF."""
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(str(pdf_path))
            full_text = []
            page_data = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                full_text.append(text)
                page_data.append({
                    'page_number': page_num + 1,
                    'text': text,
                    'bbox': page.rect,
                    'has_images': len(page.get_images()) > 0
                })
            
            doc.close()
            
            return {
                'text': '\n'.join(full_text),
                'backend': 'pymupdf',
                'pages': len(doc),
                'page_data': page_data,
                'has_images': any(p['has_images'] for p in page_data)
            }
            
        except Exception as e:
            logger.error(f"PyMuPDF extraction error: {e}")
            raise
    
    async def _extract_with_pdfminer(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract PDF content using pdfminer."""
        try:
            from pdfminer.high_level import extract_text
            from pdfminer.layout import LAParams
            
            laparams = LAParams()
            text = extract_text(str(pdf_path), laparams=laparams)
            
            # Get page count
            from pdfminer.pdfpage import PDFPage
            with open(pdf_path, 'rb') as file:
                page_count = sum(1 for _ in PDFPage.get_pages(file))
            
            return {
                'text': text,
                'backend': 'pdfminer',
                'pages': page_count,
                'page_data': [{'page_number': 1, 'text': text}]  # pdfminer doesn't provide per-page data easily
            }
            
        except Exception as e:
            logger.error(f"PDFMiner extraction error: {e}")
            raise
    
    async def _create_document_from_content(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Create document from existing content (for synthetic data)."""
        return {
            'doc_id': document['doc_id'],
            'type': 'pdf',
            'content': document['content'],
            'metadata': {
                'source_type': 'pdf',
                'file_path': document.get('file_path', ''),
                'pages': 1,
                'backend': 'synthetic',
                'has_images': False,
                'has_tables': False
            },
            'ground_truth_entities': document.get('entities', []),
            'ground_truth_relations': document.get('relations', [])
        }
    
    async def _create_fallback_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Create fallback document when PDF parsing fails."""
        return {
            'doc_id': document['doc_id'],
            'type': 'pdf',
            'content': document.get('content', 'PDF parsing not available'),
            'metadata': {
                'source_type': 'pdf',
                'file_path': document.get('file_path', ''),
                'pages': 0,
                'backend': 'fallback',
                'has_images': False,
                'has_tables': False,
                'error': 'PDF processing failed'
            },
            'ground_truth_entities': document.get('entities', []),
            'ground_truth_relations': document.get('relations', [])
        }
    
    async def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from a single PDF file."""
        try:
            content = await self._extract_pdf_content(pdf_path)
            return content['text']
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
            return ""