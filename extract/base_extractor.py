#!/usr/bin/env python3
"""
Base extractor class providing shared utilities for all format-specific extractors.
Defines the common interface and quality assessment methods.
"""

import os
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

try:
    from groq import Groq
except ImportError:
    Groq = None


class BaseExtractor(ABC):
    """
    Abstract base class for all format-specific extractors.
    Provides common utilities for text cleaning, quality assessment, and entity hint extraction.
    """
    
    def __init__(self, groq_api_key: Optional[str] = None, config: Optional[Dict] = None):
        """
        Initialize base extractor with optional Groq client.
        
        Args:
            groq_api_key: Optional Groq API key for LLM-enhanced extraction
            config: Optional configuration dict with extraction parameters
        """
        self.groq_client = None
        if groq_api_key and Groq:
            try:
                self.groq_client = Groq(api_key=groq_api_key)
                logger.debug(f"{self.__class__.__name__}: Groq client initialized")
            except Exception as e:
                logger.warning(f"{self.__class__.__name__}: Failed to initialize Groq: {e}")
        
        # Default configuration
        self.config = config or {}
        self.quality_thresholds = {
            'min_chars': self.config.get('min_chars', 50),
            'min_words': self.config.get('min_words', 10),
            'min_confidence': self.config.get('min_confidence', 0.5),
            'optimal_chars': self.config.get('optimal_chars', 500)
        }
    
    @abstractmethod
    async def extract(self, file_path: str, document: Dict[str, Any]) -> Tuple[str, List[Dict], Dict]:
        """
        Extract content from a file.
        
        Args:
            file_path: Path to the file to extract
            document: Document metadata dict
            
        Returns:
            Tuple of (content, segments, modality_data)
            - content: Main extracted text for NER
            - segments: List of structured content segments
            - modality_data: Format-specific metadata
        """
        pass
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize extracted text.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove control characters except newlines and tabs
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', text)
        
        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        # Remove excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    async def extract_entity_hints(self, content: str, modality: str) -> List[Dict[str, Any]]:
        """
        Extract potential entity hints from content for better NER downstream.
        Uses both pattern matching and optional LLM enhancement.
        
        Args:
            content: Extracted content text
            modality: Format type (audio, image, pdf, video, text)
            
        Returns:
            List of entity hint dicts with text, type, confidence
        """
        entity_hints = []
        
        # Pattern-based entity detection (always enabled, fast)
        pattern_hints = self._extract_pattern_entity_hints(content, modality)
        entity_hints.extend(pattern_hints)
        
        # LLM-enhanced entity detection (optional, can be slow)
        enable_llm = self.config.get('enable_llm_hints', False)
        if enable_llm and self.groq_client and len(content) > 100:
            llm_hints = await self._extract_llm_entity_hints(content, modality)
            entity_hints.extend(llm_hints)
        
        # Deduplicate by text
        seen = set()
        unique_hints = []
        for hint in entity_hints:
            text_lower = hint['text'].lower()
            if text_lower not in seen:
                seen.add(text_lower)
                unique_hints.append(hint)
        
        return unique_hints
    
    def _extract_pattern_entity_hints(self, content: str, modality: str) -> List[Dict[str, Any]]:
        """Extract entities using regex patterns."""
        hints = []
        
        # Common entity patterns
        patterns = {
            'PERSON': [
                r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b',  # First Last
                r'\b(?:Mr|Ms|Mrs|Dr)\.?\s+([A-Z][a-z]+ [A-Z][a-z]+)\b'  # Title Name
            ],
            'ORG': [
                r'\b([A-Z][a-zA-Z]+ (?:Inc|Corp|LLC|Ltd|Company|Corporation|University|Institute))\b',
                r'\b([A-Z][A-Z]+)\b'  # Acronyms
            ],
            'PLACE': [
                r'\b((?:New York|London|Tokyo|Paris|Berlin|San Francisco|Los Angeles|Chicago|Mumbai|Sydney))\b',
                r'\b([A-Z][a-z]+,\s*[A-Z]{2})\b'  # City, STATE
            ],
            'DATE': [
                r'\b(\d{1,2}/\d{1,2}/\d{4})\b',
                r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b'
            ],
            'EMAIL': [
                r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
            ],
            'PHONE': [
                r'\b(\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b'
            ],
            'URL': [
                r'\b((?:https?://)?(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)\b'
            ]
        }
        
        for entity_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                try:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        text = match.group(1) if match.groups() else match.group()
                        if len(text) > 2:  # Filter out very short matches
                            hints.append({
                                'text': text.strip(),
                                'type': entity_type,
                                'confidence': 0.7,
                                'source': 'pattern',
                                'modality': modality
                            })
                except Exception as e:
                    logger.warning(f"Pattern matching failed for {entity_type}: {e}")
        
        return hints
    
    async def _extract_llm_entity_hints(self, content: str, modality: str) -> List[Dict[str, Any]]:
        """Extract entities using LLM (Groq) for better accuracy."""
        if not self.groq_client:
            return []
        
        try:
            # Truncate content if too long
            content_sample = content[:2000] if len(content) > 2000 else content
            
            prompt = f"""Analyze this {modality} content and identify key entities.
Extract: PERSON names, ORGANIZATION names, PLACE/LOCATION names, DATE mentions, EMAIL addresses, PHONE numbers, URLs.

Content:
{content_sample}

Respond with JSON array ONLY (no markdown, no explanation):
[{{"text": "entity name", "type": "PERSON|ORG|PLACE|DATE|EMAIL|PHONE|URL"}}]"""
            
            response = self.groq_client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            import json
            entities = json.loads(result_text)
            
            # Convert to hint format
            hints = []
            for entity in entities:
                if isinstance(entity, dict) and 'text' in entity and 'type' in entity:
                    hints.append({
                        'text': entity['text'],
                        'type': entity['type'],
                        'confidence': 0.85,
                        'source': 'llm',
                        'modality': modality
                    })
            
            return hints
            
        except Exception as e:
            logger.warning(f"LLM entity hint extraction failed: {e}")
            return []
    
    def calculate_content_stats(self, content: str) -> Dict[str, Any]:
        """
        Calculate statistical metrics for extracted content.
        
        Args:
            content: Extracted text
            
        Returns:
            Dict with content statistics
        """
        if not content:
            return {
                'char_count': 0,
                'word_count': 0,
                'sentence_count': 0,
                'avg_word_length': 0.0,
                'avg_sentence_length': 0.0,
                'unique_words': 0
            }
        
        words = content.split()
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        word_lengths = [len(w) for w in words]
        sentence_lengths = [len(s.split()) for s in sentences]
        
        return {
            'char_count': len(content),
            'word_count': len(words),
            'sentence_count': len(sentences),
            'avg_word_length': sum(word_lengths) / len(word_lengths) if word_lengths else 0.0,
            'avg_sentence_length': sum(sentence_lengths) / len(sentence_lengths) if sentence_lengths else 0.0,
            'unique_words': len(set(w.lower() for w in words))
        }
    
    def assess_extraction_quality(
        self,
        content: str,
        extraction_method: str,
        method_confidence: float = 0.8
    ) -> Dict[str, Any]:
        """
        Assess the quality of extracted content.
        
        Args:
            content: Extracted text
            extraction_method: Name of the method used
            method_confidence: Base confidence of the method
            
        Returns:
            Quality assessment dict
        """
        stats = self.calculate_content_stats(content)
        
        # Calculate confidence based on content length and quality
        confidence = method_confidence
        if stats['char_count'] < self.quality_thresholds['min_chars']:
            confidence *= 0.5
        elif stats['char_count'] < self.quality_thresholds['optimal_chars']:
            confidence *= 0.7
        
        # Calculate completeness score
        completeness = min(1.0, stats['char_count'] / self.quality_thresholds['optimal_chars'])
        
        # Calculate text quality ratio (unique words / total words)
        text_quality = stats['unique_words'] / stats['word_count'] if stats['word_count'] > 0 else 0.0
        
        return {
            'confidence': round(confidence, 2),
            'completeness': round(completeness, 2),
            'text_quality': round(text_quality, 2),
            'extraction_method': extraction_method,
            'content_stats': stats,
            'meets_threshold': (
                stats['char_count'] >= self.quality_thresholds['min_chars'] and
                stats['word_count'] >= self.quality_thresholds['min_words']
            )
        }
    
    def create_segment(
        self,
        segment_id: str,
        segment_type: str,
        content: str,
        position: int,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create a standardized content segment.
        
        Args:
            segment_id: Unique segment identifier
            segment_type: Type of segment (page, paragraph, timestamp, etc.)
            content: Segment text content
            position: Position in document
            metadata: Optional additional metadata
            
        Returns:
            Structured segment dict
        """
        segment = {
            'segment_id': segment_id,
            'segment_type': segment_type,
            'content': self.clean_text(content),
            'position': position,
            'char_count': len(content),
            'word_count': len(content.split()) if content else 0
        }
        
        if metadata:
            segment.update(metadata)
        
        return segment
    
    def format_duration(self, seconds: float) -> str:
        """Format duration in HH:MM:SS or MM:SS format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get basic file information."""
        path = Path(file_path)
        
        if not path.exists():
            return {
                'exists': False,
                'size_bytes': 0,
                'size_mb': 0.0,
                'extension': '',
                'filename': ''
            }
        
        size_bytes = path.stat().st_size
        
        return {
            'exists': True,
            'size_bytes': size_bytes,
            'size_mb': round(size_bytes / (1024 * 1024), 2),
            'extension': path.suffix,
            'filename': path.name,
            'stem': path.stem
        }
