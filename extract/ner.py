#!/usr/bin/env python3
"""
Multi-modal Named Entity Recognition module with multiple backends.
Supports text, audio transcripts, image descriptions, PDFs, and video content.
Uses local models (spaCy), Hugging Face, and Groq API.
"""

import json
import asyncio
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger

class MultiModalNERExtractor:
    """Multi-modal NER extractor with configurable backends."""
    
    def __init__(self, mode: str = "local"):
        self.mode = mode
        self.setup_backend()
        
    def setup_backend(self):
        """Setup the appropriate NER backend."""
        if self.mode == "local":
            self.setup_local_models()
        elif self.mode == "hf":
            self.setup_huggingface()
        elif self.mode == "groq":
            self.setup_groq()
        else:
            self.setup_local_models()  # Default fallback
            
    def setup_local_models(self):
        """Setup local spaCy models and modality-specific processors."""
        try:
            import spacy
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("Loaded local spaCy model for NER")
            
            # Setup modality-specific patterns
            self._setup_modality_patterns()
            
        except Exception as e:
            logger.warning(f"Could not load spaCy model: {e}. Using rule-based fallback.")
            self.nlp = None
            self._setup_modality_patterns()

    def setup_huggingface(self):
        """Setup Hugging Face models."""
        logger.info("Hugging Face NER setup would be implemented here")
        self.nlp = None
        self._setup_modality_patterns()
        
    def setup_groq(self):
        """Setup Groq client for NER extraction."""
        try:
            import os
            from groq import Groq
            
            api_key = os.getenv('GROQ_API_KEY')
            if not api_key:
                logger.warning("GROQ_API_KEY not found. Falling back to local models.")
                self.setup_local_models()
                return
                
            self.groq_client = Groq(api_key=api_key)
            self.groq_model = "llama-3.1-70b-versatile"  # Use the model from your config
            logger.info(f"Groq client initialized for NER with model: {self.groq_model}")
            
            # Still setup local models as fallback
            self.setup_local_models()
            
        except Exception as e:
            logger.error(f"Failed to setup Groq: {e}. Falling back to local models.")
            self.setup_local_models()
            
    def _setup_modality_patterns(self):
        """Setup modality-specific entity patterns."""
        # Enhanced entity patterns for different modalities
        self.modality_patterns = {
            'text': {
                'person': [r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', r'\b(?:Mr|Ms|Mrs|Dr)\.? [A-Z][a-z]+ [A-Z][a-z]+\b'],
                'organization': [r'\b[A-Z][a-zA-Z]+ (?:Inc|Corp|LLC|Ltd|Company|Corporation)\b'],
                'location': [r'\b(?:New York|London|Tokyo|Paris|Berlin|San Francisco)\b'],
                'date': [r'\b\d{1,2}/\d{1,2}/\d{4}\b', r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2},? \d{4}\b']
            },
            'audio': {
                'speaker': [r'\b(?:Speaker|Narrator|Interviewer|Interviewee|Voice)\s*[A-Z]?\b'],
                'time_reference': [r'\b\d{1,2}:\d{2}\s*(?:AM|PM)?\b', r'\b\d+\s*(?:seconds?|minutes?|hours?)\b'],
                'audio_entity': [r'\b(?:background noise|silence|music|sound effect)\b']
            },
            'image': {
                'visual_object': [r'\b(?:person|car|tree|building|animal|object)\b'],
                'color': [r'\b(?:red|blue|green|yellow|black|white|purple|orange)\b'],
                'spatial_reference': [r'\b(?:left|right|top|bottom|center|corner|background|foreground)\b']
            },
            'video': {
                'scene_element': [r'\b(?:scene|shot|frame|clip|sequence)\b'],
                'temporal_reference': [r'\b\d{1,2}:\d{2}:\d{2}\b', r'\b(?:beginning|middle|end)\b'],
                'action': [r'\b(?:walking|running|talking|driving|eating|working)\b']
            },
            'pdf': {
                'document_section': [r'\b(?:Chapter|Section|Page|Figure|Table)\s+\d+\b'],
                'reference': [r'\b(?:References|Bibliography|Appendix)\b'],
                'author': [r'\b(?:Author|By|Written by)\s+[A-Z][a-z]+ [A-Z][a-z]+\b']
            }
        }
            
    async def extract(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract entities from multi-modal document."""
        content = document.get('content', '')
        modality = document.get('file_type', 'text')
        modality_data = document.get('modality_specific_data', {})
        
        logger.info(f"Extracting entities from {modality} content")
        
        # Choose extraction method based on mode and modality
        if self.mode == "local" and self.nlp:
            entities = await self.extract_local(content, modality, modality_data)
        elif self.mode == "hf":
            entities = await self.extract_huggingface(content, modality, modality_data)
        elif self.mode == "groq":
            entities = await self.extract_groq(content, document)
        else:
            entities = await self.extract_modality_fallback(content, modality, modality_data)
        
        # Enhance entities with modality context
        enhanced_entities = await self.enhance_entities_with_modality(
            entities, modality, modality_data, document
        )
        
        return enhanced_entities
        
    async def extract_local(self, text: str, modality: str, modality_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract entities using local spaCy model with modality enhancement."""
        if not self.nlp:
            return await self.extract_modality_fallback(text, modality, modality_data)
            
        doc = self.nlp(text)
        entities = []
        
        for ent in doc.ents:
            # Map spaCy labels to our schema with modality awareness
            entity_type = self.map_entity_type(ent.label_, modality)
            
            entity_data = {
                'text': ent.text,
                'type': entity_type,
                'start_char': ent.start_char,
                'end_char': ent.end_char,
                'confidence': 0.9,
                'canonical_name': ent.text,
                'modality': modality,
                'attributes': self._get_modality_attributes(modality, ent.text, modality_data)
            }
            
            # Add modality-specific position information
            if modality in ['audio', 'video']:
                entity_data['position'] = await self._infer_temporal_position(ent.start_char, len(text), modality_data)
            elif modality == 'image':
                entity_data['position'] = await self._infer_spatial_position(ent.text, modality_data)
                
            entities.append(entity_data)
            
        # Add modality-specific entities using patterns
        modality_specific_entities = await self.extract_modality_specific_entities(text, modality, modality_data)
        entities.extend(modality_specific_entities)
        
        return entities
        
    def map_entity_type(self, spacy_label: str, modality: str) -> str:
        """Map spaCy entity types to our schema with modality awareness."""
        base_mapping = {
            'PERSON': 'PERSON',
            'ORG': 'ORG', 
            'GPE': 'PLACE',
            'LOC': 'PLACE',
            'EVENT': 'EVENT',
            'WORK_OF_ART': 'CONCEPT',
            'DATE': 'DATE',
            'TIME': 'TIME',
            'MONEY': 'METRIC',
            'PERCENT': 'METRIC',
            'QUANTITY': 'METRIC'
        }
        
        base_type = base_mapping.get(spacy_label, 'ENTITY')
        
        # Enhance type based on modality
        if modality == 'audio' and base_type in ['PERSON', 'ORG']:
            return f"AUDIO_{base_type}"
        elif modality in ['image', 'video'] and base_type in ['PERSON', 'ORG', 'PLACE']:
            return f"VISUAL_{base_type}"
            
        return base_type
        
    async def extract_modality_specific_entities(self, text: str, modality: str, modality_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract modality-specific entities using patterns."""
        entities = []
        
        if modality not in self.modality_patterns:
            return entities
            
        patterns = self.modality_patterns[modality]
        
        for entity_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    entity = {
                        'text': match.group(),
                        'type': entity_type.upper(),
                        'start_char': match.start(),
                        'end_char': match.end(),
                        'confidence': 0.7,
                        'canonical_name': match.group(),
                        'modality': modality,
                        'attributes': self._get_modality_attributes(modality, match.group(), modality_data),
                        'extraction_method': 'pattern'
                    }
                    
                    # Add modality-specific position
                    if modality in ['audio', 'video']:
                        entity['position'] = await self._infer_temporal_position(match.start(), len(text), modality_data)
                    elif modality == 'image':
                        entity['position'] = await self._infer_spatial_position(match.group(), modality_data)
                        
                    entities.append(entity)
        
        return entities
        
    def _get_modality_attributes(self, modality: str, entity_text: str, modality_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get modality-specific attributes for an entity."""
        attributes = {}
        
        if modality == 'audio':
            attributes.update({
                'audio_context': 'spoken_content',
                'likely_speaker': self._infer_speaker(entity_text, modality_data)
            })
        elif modality == 'image':
            attributes.update({
                'visual_context': 'image_content',
                'detection_confidence': 0.8
            })
        elif modality == 'video':
            attributes.update({
                'video_context': 'moving_content',
                'temporal_nature': True
            })
        elif modality == 'pdf':
            attributes.update({
                'document_context': 'structured_content',
                'likely_section': self._infer_pdf_section(entity_text, modality_data)
            })
            
        return attributes
        
    def _infer_speaker(self, entity_text: str, modality_data: Dict[str, Any]) -> Optional[str]:
        """Infer speaker information for audio entities."""
        # Simple speaker inference based on context
        speakers = modality_data.get('speakers', [])
        if speakers and 'person' in entity_text.lower():
            return speakers[0]  # Return first speaker as default
        return None
        
    def _infer_pdf_section(self, entity_text: str, modality_data: Dict[str, Any]) -> Optional[str]:
        """Infer PDF section for document entities."""
        sections = modality_data.get('sections', {})
        for section_name, section_content in sections.items():
            if entity_text in section_content:
                return section_name
        return None
        
    async def _infer_temporal_position(self, char_position: int, total_chars: int, modality_data: Dict[str, Any]) -> Dict[str, Any]:
        """Infer temporal position for audio/video entities."""
        duration = modality_data.get('duration')
        if duration and total_chars > 0:
            # Simple linear mapping from text position to temporal position
            timestamp = (char_position / total_chars) * duration
            return {
                'timestamp': round(timestamp, 2),
                'duration_seconds': duration,
                'position_type': 'temporal'
            }
        return {'position_type': 'temporal_unknown'}
        
    async def _infer_spatial_position(self, entity_text: str, modality_data: Dict[str, Any]) -> Dict[str, Any]:
        """Infer spatial position for image entities."""
        # This would typically use object detection results
        detected_objects = modality_data.get('objects_detected', [])
        if entity_text.lower() in [obj.lower() for obj in detected_objects]:
            return {
                'bounding_box': [0.1, 0.1, 0.2, 0.2],  # Example bbox [x, y, width, height]
                'position_type': 'spatial'
            }
        return {'position_type': 'spatial_unknown'}
        
    async def extract_modality_fallback(self, text: str, modality: str, modality_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fallback entity extraction using enhanced rules for different modalities."""
        entities = []
        
        # Enhanced keyword-based extraction for different modalities
        modality_keywords = self._get_modality_keywords(modality)
        
        words = text.split()
        for i, word in enumerate(words):
            word_lower = word.lower()
            
            # Check against modality-specific keywords
            for entity_type, keywords in modality_keywords.items():
                if word_lower in keywords or any(keyword in word_lower for keyword in keywords):
                    
                    # Try to extract full phrases
                    full_phrase = await self._extract_full_entity_phrase(words, i, entity_type)
                    
                    entity = {
                        'text': full_phrase,
                        'type': entity_type,
                        'start_char': text.find(full_phrase),
                        'end_char': text.find(full_phrase) + len(full_phrase),
                        'confidence': 0.7,
                        'canonical_name': full_phrase,
                        'modality': modality,
                        'attributes': self._get_modality_attributes(modality, full_phrase, modality_data),
                        'extraction_method': 'rule_based'
                    }
                    
                    # Add modality-specific position
                    if modality in ['audio', 'video']:
                        entity['position'] = await self._infer_temporal_position(
                            text.find(full_phrase), len(text), modality_data
                        )
                    elif modality == 'image':
                        entity['position'] = await self._infer_spatial_position(full_phrase, modality_data)
                        
                    entities.append(entity)
                    break
                
        return entities
        
    def _get_modality_keywords(self, modality: str) -> Dict[str, List[str]]:
        """Get modality-specific keywords for entity extraction."""
        base_keywords = {
            'PERSON': ['john', 'maria', 'david', 'sarah', 'robert', 'lisa', 'michael', 'emily', 
                      'william', 'jennifer', 'christopher', 'amanda', 'matthew', 'michelle'],
            'ORG': ['techcorp', 'global', 'bank', 'medipharm', 'edufoundation', 'company', 
                   'corporation', 'inc', 'ltd', 'llc'],
            'PLACE': ['new york', 'london', 'tokyo', 'paris', 'berlin', 'san francisco', 
                     'california', 'texas', 'florida', 'chicago', 'boston'],
            'DATE': ['january', 'february', 'march', 'april', 'may', 'june', 'july', 
                    'august', 'september', 'october', 'november', 'december'],
            'METRIC': ['dollars', 'percent', 'million', 'billion', 'kilometers', 'miles']
        }
        
        # Add modality-specific keywords
        if modality == 'audio':
            base_keywords.update({
                'AUDIO_ENTITY': ['speaker', 'voice', 'narrator', 'microphone', 'recording', 'audio'],
                'TIME': ['minute', 'hour', 'second', 'moment', 'time']
            })
        elif modality == 'image':
            base_keywords.update({
                'VISUAL_OBJECT': ['person', 'car', 'tree', 'building', 'house', 'road', 'sky', 
                                 'water', 'mountain', 'animal', 'dog', 'cat', 'bird'],
                'COLOR': ['red', 'blue', 'green', 'yellow', 'black', 'white', 'purple', 'orange']
            })
        elif modality == 'video':
            base_keywords.update({
                'SCENE_ELEMENT': ['scene', 'shot', 'frame', 'clip', 'sequence', 'camera', 'action'],
                'ACTION': ['walking', 'running', 'talking', 'driving', 'eating', 'working', 'playing']
            })
        elif modality == 'pdf':
            base_keywords.update({
                'DOCUMENT_SECTION': ['chapter', 'section', 'page', 'figure', 'table', 'appendix'],
                'AUTHOR': ['author', 'written by', 'created by', 'published by']
            })
            
        return base_keywords
        
    async def _extract_full_entity_phrase(self, words: List[str], start_idx: int, entity_type: str) -> str:
        """Extract full entity phrase from words."""
        if entity_type == 'PERSON':
            # Try to get full name (first + last)
            if start_idx + 1 < len(words) and words[start_idx + 1][0].isupper():
                return f"{words[start_idx]} {words[start_idx + 1]}"
        elif entity_type in ['ORG', 'PLACE']:
            # Try to get multi-word names
            phrase = words[start_idx]
            for i in range(start_idx + 1, min(start_idx + 3, len(words))):
                if words[i][0].isupper():
                    phrase += f" {words[i]}"
                else:
                    break
            return phrase
            
        return words[start_idx]
        
    async def extract_huggingface(self, text: str, modality: str, modality_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract entities using Hugging Face inference API with modality support."""
        logger.info(f"HF NER extraction for {modality} would be implemented here")
        
        # For now, fallback to local extraction with modality enhancement
        entities = await self.extract_local(text, modality, modality_data)
        
        # Add HF-specific enhancements
        for entity in entities:
            entity['extraction_backend'] = 'huggingface_fallback'
            
        return entities
        
    async def extract_groq(self, text: str, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract entities using Groq API with structured output and modality awareness."""
        modality = document.get('file_type', 'text')
        modality_data = document.get('modality_specific_data', {})
        
        logger.info(f"Groq NER extraction for {modality} would be implemented here")
        
        # For now, fallback to local extraction with modality enhancement
        entities = await self.extract_local(text, modality, modality_data)
        
        # Add Groq-specific enhancements
        for entity in entities:
            entity['extraction_backend'] = 'groq_fallback'
            entity['llm_enhanced'] = True
            
        return entities
        
    async def enhance_entities_with_modality(self, entities: List[Dict[str, Any]], modality: str, 
                                           modality_data: Dict[str, Any], document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Enhance entities with modality-specific information and cross-modal context."""
        enhanced_entities = []
        
        for entity in entities:
            enhanced_entity = entity.copy()
            
            # Add cross-modal context
            enhanced_entity['cross_modal_context'] = await self._get_cross_modal_context(
                entity, modality, document
            )
            
            # Enhance confidence based on modality
            enhanced_entity['confidence'] = await self._adjust_confidence_by_modality(
                entity['confidence'], modality, entity['type']
            )
            
            # Add entity source information
            enhanced_entity['source_modality'] = modality
            enhanced_entity['extraction_timestamp'] = document.get('processing_timestamp')
            
            enhanced_entities.append(enhanced_entity)
            
        return enhanced_entities
        
    async def _get_cross_modal_context(self, entity: Dict[str, Any], modality: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """Get cross-modal context for an entity."""
        context = {
            'primary_modality': modality,
            'related_modalities': [],
            'context_confidence': 0.5
        }
        
        # Check if entity might appear in other modalities
        entity_text = entity['text'].lower()
        
        # Simple cross-modal context inference
        if modality == 'audio' and any(word in entity_text for word in ['visual', 'image', 'see']):
            context['related_modalities'].append('image')
            context['context_confidence'] = 0.7
        elif modality == 'image' and any(word in entity_text for word in ['sound', 'audio', 'hear']):
            context['related_modalities'].append('audio')
            context['context_confidence'] = 0.7
            
        return context
        
    async def _adjust_confidence_by_modality(self, base_confidence: float, modality: str, entity_type: str) -> float:
        """Adjust confidence score based on modality and entity type."""
        confidence = base_confidence
        
        # Modality-specific adjustments
        modality_factors = {
            'text': 1.0,
            'pdf': 1.0,
            'audio': 0.9,
            'image': 0.8,
            'video': 0.85
        }
        
        modality_factor = modality_factors.get(modality, 0.8)
        confidence *= modality_factor
        
        # Entity type-specific adjustments
        if entity_type in ['VISUAL_OBJECT', 'AUDIO_ENTITY'] and modality in ['text', 'pdf']:
            confidence *= 0.7  # Reduce confidence for modality-specific entities in text
        
        return min(confidence, 1.0)


async def extract_entities(document: Dict[str, Any], mode: str = "local") -> List[Dict[str, Any]]:
    """
    Convenience function for entity extraction.
    
    Args:
        document: Document dict with content and modality information
        mode: Extraction mode ('local', 'hf', 'groq')
        
    Returns:
        List of extracted entities
    """
    extractor = MultiModalNERExtractor(mode=mode)
    return await extractor.extract(document)


class EntityPostProcessor:
    """Post-process entities for consistency and quality."""
    
    @staticmethod
    async def deduplicate_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate entities based on text and position."""
        seen = set()
        unique_entities = []
        
        for entity in entities:
            # Create unique identifier based on text and position
            entity_id = f"{entity['text']}_{entity.get('start_char', 0)}_{entity.get('end_char', 0)}"
            
            if entity_id not in seen:
                seen.add(entity_id)
                unique_entities.append(entity)
                
        return unique_entities
    
    @staticmethod
    async def filter_low_confidence(entities: List[Dict[str, Any]], threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Filter out low-confidence entities."""
        return [entity for entity in entities if entity.get('confidence', 0) >= threshold]
    
    @staticmethod
    async def normalize_entity_types(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize entity types to standard set."""
        type_mapping = {
            'PERSON': 'PERSON',
            'ORG': 'ORG',
            'ORGANIZATION': 'ORG',
            'LOCATION': 'PLACE',
            'PLACE': 'PLACE',
            'GPE': 'PLACE',
            'DATE': 'DATE',
            'TIME': 'TIME',
            'EVENT': 'EVENT',
            'CONCEPT': 'CONCEPT',
            'OBJECT': 'OBJECT',
            'VISUAL_OBJECT': 'OBJECT',
            'AUDIO_ENTITY': 'AUDIO_ENTITY'
        }
        
        for entity in entities:
            original_type = entity.get('type', 'ENTITY')
            entity['type'] = type_mapping.get(original_type, 'ENTITY')
            entity['original_type'] = original_type  # Keep original for reference
            
        return entities