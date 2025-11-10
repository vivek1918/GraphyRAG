#!/usr/bin/env python3
"""
HTML document loader and parser for web content.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List
from loguru import logger

class HTMLParser:
    """HTML document parser with content extraction."""
    
    def __init__(self):
        self.clean_patterns = [
            (r'<script.*?</script>', ''),  # Remove scripts
            (r'<style.*?</style>', ''),    # Remove styles
            (r'<!--.*?-->', ''),           # Remove comments
            (r'<[^>]+>', ' '),             # Remove HTML tags
            (r'\s+', ' '),                 # Normalize whitespace
        ]
    
    async def parse(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Parse HTML document and extract content."""
        try:
            if 'content' in document:
                html_content = document['content']
            else:
                file_path = Path(document['file_path'])
                html_content = file_path.read_text(encoding='utf-8')
            
            # Extract clean text
            clean_text = await self._extract_text(html_content)
            
            # Extract metadata
            metadata = await self._extract_metadata(html_content, document)
            
            # Extract structured data
            structured_data = await self._extract_structured_data(html_content)
            
            parsed_doc = {
                'doc_id': document['doc_id'],
                'type': 'html',
                'content': clean_text,
                'metadata': metadata,
                'structured_data': structured_data,
                'source_url': document.get('url', document.get('file_path', ''))
            }
            
            # Add ground truth if available
            if 'entities' in document:
                parsed_doc['ground_truth_entities'] = document['entities']
            if 'relations' in document:
                parsed_doc['ground_truth_relations'] = document['relations']
            
            logger.debug(f"Parsed HTML document: {document['doc_id']}")
            return parsed_doc
            
        except Exception as e:
            logger.error(f"Error parsing HTML document {document.get('doc_id')}: {e}")
            raise
    
    async def _extract_text(self, html_content: str) -> str:
        """Extract clean text from HTML."""
        text = html_content
        
        # Apply cleaning patterns
        for pattern, replacement in self.clean_patterns:
            text = re.sub(pattern, replacement, text, flags=re.DOTALL | re.IGNORECASE)
        
        # Decode HTML entities
        text = await self._decode_html_entities(text)
        
        # Clean up
        text = text.strip()
        
        return text
    
    async def _decode_html_entities(self, text: str) -> str:
        """Decode HTML entities."""
        import html
        try:
            return html.unescape(text)
        except:
            return text
    
    async def _extract_metadata(self, html_content: str, document: Dict) -> Dict[str, Any]:
        """Extract metadata from HTML."""
        metadata = {
            'source_type': 'html',
            'file_path': document.get('file_path'),
            'title': await self._extract_title(html_content),
            'description': await self._extract_description(html_content),
            'keywords': await self._extract_keywords(html_content),
            'language': 'en'  # Default, could be extracted from HTML
        }
        
        return metadata
    
    async def _extract_title(self, html_content: str) -> str:
        """Extract title from HTML."""
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = re.sub(r'<[^>]+>', '', title_match.group(1))
            return title.strip()
        return ""
    
    async def _extract_description(self, html_content: str) -> str:
        """Extract meta description from HTML."""
        desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', 
                             html_content, re.IGNORECASE)
        if desc_match:
            return desc_match.group(1).strip()
        return ""
    
    async def _extract_keywords(self, html_content: str) -> List[str]:
        """Extract meta keywords from HTML."""
        keywords_match = re.search(r'<meta[^>]*name=["\']keywords["\'][^>]*content=["\'](.*?)["\']', 
                                 html_content, re.IGNORECASE)
        if keywords_match:
            keywords_text = keywords_match.group(1)
            return [k.strip() for k in keywords_text.split(',')]
        return []
    
    async def _extract_structured_data(self, html_content: str) -> Dict[str, Any]:
        """Extract structured data from HTML (microdata, JSON-LD, etc.)."""
        structured_data = {
            'json_ld': await self._extract_json_ld(html_content),
            'microdata': await self._extract_microdata(html_content),
            'headers': await self._extract_headers(html_content)
        }
        return structured_data
    
    async def _extract_json_ld(self, html_content: str) -> List[Dict]:
        """Extract JSON-LD structured data."""
        json_ld_data = []
        script_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        
        for match in re.finditer(script_pattern, html_content, re.IGNORECASE | re.DOTALL):
            try:
                json_text = match.group(1)
                data = json.loads(json_text)
                json_ld_data.append(data)
            except json.JSONDecodeError:
                continue
        
        return json_ld_data
    
    async def _extract_microdata(self, html_content: str) -> List[Dict]:
        """Extract microdata."""
        # Simplified microdata extraction
        microdata = []
        itemscope_pattern = r'<[^>]*itemscope[^>]*>.*?</[^>]*>'
        
        for match in re.finditer(itemscope_pattern, html_content, re.IGNORECASE | re.DOTALL):
            microdata.append({'html': match.group(0)})
        
        return microdata
    
    async def _extract_headers(self, html_content: str) -> Dict[str, List[str]]:
        """Extract header tags for document structure."""
        headers = {'h1': [], 'h2': [], 'h3': [], 'h4': [], 'h5': [], 'h6': []}
        
        for level in range(1, 7):
            tag = f'h{level}'
            pattern = f'<{tag}[^>]*>(.*?)</{tag}>'
            for match in re.finditer(pattern, html_content, re.IGNORECASE | re.DOTALL):
                header_text = re.sub(r'<[^>]+>', '', match.group(1))
                headers[tag].append(header_text.strip())
        
        return headers