#!/usr/bin/env python3
"""
Named Entity Recognition module with multiple backends.
Supports local models (spaCy), Hugging Face, and Groq API.
"""

import json
import asyncio
from typing import List, Dict, Any
from loguru import logger

class NERExtractor:
    """NER extractor with configurable backends."""
    
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
            
    def setup_local_models(self):
        """Setup local spaCy models."""
        try:
            import spacy
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("Loaded local spaCy model for NER")
        except Exception as e:
            logger.warning(f"Could not load spaCy model: {e}. Using rule-based fallback.")
            self.nlp = None
            
    async def extract(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract entities from document."""
        content = document.get('content', '')
        
        if self.mode == "local" and self.nlp:
            return await self.extract_local(content)
        elif self.mode == "hf":
            return await self.extract_huggingface(content)
        elif self.mode == "groq":
            return await self.extract_groq(content, document)
        else:
            return await self.extract_fallback(content)
            
    async def extract_local(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities using local spaCy model."""
        if not self.nlp:
            return await self.extract_fallback(text)
            
        doc = self.nlp(text)
        entities = []
        
        for ent in doc.ents:
            # Map spaCy labels to our schema
            entity_type = self.map_entity_type(ent.label_)
            
            entities.append({
                'text': ent.text,
                'type': entity_type,
                'start_char': ent.start_char,
                'end_char': ent.end_char,
                'confidence': 0.9,  # spaCy doesn't provide confidence
                'canonical_name': ent.text,
                'attributes': {}
            })
            
        return entities
        
    def map_entity_type(self, spacy_label: str) -> str:
        """Map spaCy entity types to our schema."""
        mapping = {
            'PERSON': 'PERSON',
            'ORG': 'ORG', 
            'GPE': 'PLACE',
            'LOC': 'PLACE',
            'EVENT': 'EVENT',
            'WORK_OF_ART': 'CONCEPT'
        }
        return mapping.get(spacy_label, 'CONCEPT')
        
    async def extract_fallback(self, text: str) -> List[Dict[str, Any]]:
        """Fallback entity extraction using simple rules."""
        # This is a very basic fallback - in practice you'd want more sophisticated rules
        entities = []
        
        # Simple keyword-based extraction for demo
        people_keywords = ['John', 'Maria', 'David', 'Sarah', 'Robert', 'Lisa', 'Michael', 'Emily']
        org_keywords = ['TechCorp', 'Global Bank', 'MediPharm', 'EduFoundation']
        
        words = text.split()
        for i, word in enumerate(words):
            if word in people_keywords:
                # Simple context-based full name extraction
                full_name = word
                if i + 1 < len(words) and words[i+1] in ['Smith', 'Garcia', 'Chen', 'Johnson', 'Williams', 'Brown', 'Davis', 'Wilson']:
                    full_name = f"{word} {words[i+1]}"
                    
                entities.append({
                    'text': full_name,
                    'type': 'PERSON',
                    'start_char': text.find(full_name),
                    'end_char': text.find(full_name) + len(full_name),
                    'confidence': 0.7,
                    'canonical_name': full_name,
                    'attributes': {}
                })
                
            elif word in org_keywords:
                entities.append({
                    'text': word,
                    'type': 'ORG',
                    'start_char': text.find(word),
                    'end_char': text.find(word) + len(word),
                    'confidence': 0.8,
                    'canonical_name': word,
                    'attributes': {}
                })
                
        return entities
        
    async def extract_huggingface(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities using Hugging Face inference API."""
        # Implementation for HF API
        logger.info("HF NER extraction would be implemented here")
        return await self.extract_local(text)  # Fallback for now
        
    async def extract_groq(self, text: str, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract entities using Groq API with structured output."""
        # Implementation for Groq API with prompt engineering
        logger.info("Groq NER extraction would be implemented here")
        return await self.extract_local(text)  # Fallback for now