#!/usr/bin/env python3
"""
Entity Linker module for linking entities to knowledge base and resolving aliases.
"""

import json
import re
from typing import List, Dict, Any, Set
from loguru import logger

class EntityLinker:
    """Links entities to canonical representations and resolves aliases."""
    
    def __init__(self):
        self.entity_kb = {}  # Simple in-memory KB for demo
        self.alias_map = {}  # Map from aliases to canonical names
        self._initialize_demo_kb()
    
    def _initialize_demo_kb(self):
        """Initialize demo knowledge base with common entities."""
        # Person entities
        self.entity_kb.update({
            "John Smith": {"type": "PERSON", "id": "person_1", "aliases": ["John", "Mr. Smith"]},
            "Maria Garcia": {"type": "PERSON", "id": "person_2", "aliases": ["Maria", "Ms. Garcia"]},
            "David Chen": {"type": "PERSON", "id": "person_3", "aliases": ["David", "Mr. Chen"]},
            "Sarah Johnson": {"type": "PERSON", "id": "person_4", "aliases": ["Sarah", "Dr. Johnson"]},
        })
        
        # Organization entities
        self.entity_kb.update({
            "TechCorp Inc": {"type": "ORG", "id": "org_1", "aliases": ["TechCorp", "TechCorp Incorporated"]},
            "Global Bank": {"type": "ORG", "id": "org_2", "aliases": ["Global Bank Corp"]},
            "MediPharm": {"type": "ORG", "id": "org_3", "aliases": ["MediPharm Ltd"]},
            "EduFoundation": {"type": "ORG", "id": "org_4", "aliases": ["Education Foundation"]},
        })
        
        # Place entities
        self.entity_kb.update({
            "New York": {"type": "PLACE", "id": "place_1", "aliases": ["NY", "New York City"]},
            "San Francisco": {"type": "PLACE", "id": "place_2", "aliases": ["SF", "San Fran"]},
            "London": {"type": "PLACE", "id": "place_3", "aliases": ["London UK"]},
            "Tokyo": {"type": "PLACE", "id": "place_4", "aliases": ["Tokyo Japan"]},
        })
        
        # Build alias map
        for canonical, info in self.entity_kb.items():
            for alias in info.get('aliases', []):
                self.alias_map[alias.lower()] = canonical
            self.alias_map[canonical.lower()] = canonical
    
    async def link(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Link entities to knowledge base and resolve aliases."""
        try:
            entities = document.get('extracted_entities', [])
            coref_data = document.get('coref_data', {})
            resolved_entities = coref_data.get('resolved_entities', [])
            
            if not entities and not resolved_entities:
                return {
                    'linked_entities': [],
                    'kb_matches': [],
                    'alias_resolutions': []
                }
            
            # Use resolved entities if available, otherwise use raw entities
            entities_to_link = resolved_entities if resolved_entities else entities
            
            # Link entities to KB
            linked_entities = await self._link_to_kb(entities_to_link)
            
            # Resolve aliases
            alias_resolutions = await self._resolve_aliases(entities_to_link)
            
            # Create enhanced entity representations
            enhanced_entities = await self._create_enhanced_entities(linked_entities, alias_resolutions)
            
            return {
                'linked_entities': enhanced_entities,
                'kb_matches': linked_entities,
                'alias_resolutions': alias_resolutions
            }
            
        except Exception as e:
            logger.error(f"Error in entity linking: {e}")
            return {
                'linked_entities': [],
                'kb_matches': [],
                'alias_resolutions': []
            }
    
    async def _link_to_kb(self, entities: List[Dict]) -> List[Dict]:
        """Link entities to knowledge base."""
        linked_entities = []
        
        for entity in entities:
            entity_text = entity.get('canonical_name', entity['text'])
            entity_type = entity.get('type', 'ENTITY')
            
            # Try exact match first
            kb_match = await self._find_kb_match(entity_text, entity_type)
            
            if kb_match:
                linked_entities.append({
                    'original_text': entity['text'],
                    'canonical_name': kb_match['canonical'],
                    'entity_id': kb_match['id'],
                    'type': entity_type,
                    'kb_confidence': kb_match['confidence'],
                    'match_type': kb_match['type'],
                    'attributes': kb_match.get('attributes', {})
                })
            else:
                # No KB match, use original entity
                linked_entities.append({
                    'original_text': entity['text'],
                    'canonical_name': entity_text,
                    'entity_id': entity.get('entity_id', f"entity_{hash(entity_text)}"),
                    'type': entity_type,
                    'kb_confidence': 0.0,
                    'match_type': 'NO_MATCH',
                    'attributes': entity.get('attributes', {})
                })
        
        return linked_entities
    
    async def _find_kb_match(self, entity_text: str, entity_type: str) -> Dict[str, Any]:
        """Find matching entity in knowledge base."""
        text_lower = entity_text.lower()
        
        # Exact match
        if text_lower in self.alias_map:
            canonical = self.alias_map[text_lower]
            kb_info = self.entity_kb.get(canonical, {})
            if kb_info.get('type') == entity_type:
                return {
                    'canonical': canonical,
                    'id': kb_info['id'],
                    'confidence': 0.95,
                    'type': 'EXACT_MATCH',
                    'attributes': {k: v for k, v in kb_info.items() if k not in ['type', 'id', 'aliases']}
                }
        
        # Partial match
        for canonical, kb_info in self.entity_kb.items():
            if kb_info.get('type') != entity_type:
                continue
                
            # Check if entity text contains canonical name or vice versa
            canonical_lower = canonical.lower()
            if (text_lower in canonical_lower or 
                canonical_lower in text_lower or
                await self._fuzzy_match(text_lower, canonical_lower)):
                
                return {
                    'canonical': canonical,
                    'id': kb_info['id'],
                    'confidence': 0.7,
                    'type': 'PARTIAL_MATCH',
                    'attributes': {k: v for k, v in kb_info.items() if k not in ['type', 'id', 'aliases']}
                }
        
        return None
    
    async def _fuzzy_match(self, text1: str, text2: str) -> bool:
        """Check fuzzy match between two strings."""
        # Simple fuzzy matching for demo
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        common_words = words1.intersection(words2)
        if len(common_words) >= min(len(words1), len(words2)):
            return True
        
        # Check Levenshtein-like similarity (simplified)
        if len(text1) > 3 and len(text2) > 3:
            if text1[:4] == text2[:4]:  # Same prefix
                return True
        
        return False
    
    async def _resolve_aliases(self, entities: List[Dict]) -> List[Dict]:
        """Resolve entity aliases to canonical names."""
        alias_resolutions = []
        
        for entity in entities:
            entity_text = entity.get('canonical_name', entity['text'])
            
            if entity_text.lower() in self.alias_map:
                canonical = self.alias_map[entity_text.lower()]
                if canonical != entity_text:
                    alias_resolutions.append({
                        'alias': entity_text,
                        'canonical': canonical,
                        'confidence': 0.9,
                        'type': 'ALIAS_RESOLUTION'
                    })
        
        return alias_resolutions
    
    async def _create_enhanced_entities(self, linked_entities: List[Dict], alias_resolutions: List[Dict]) -> List[Dict]:
        """Create enhanced entity representations with linking information."""
        enhanced_entities = []
        alias_map = {res['alias']: res['canonical'] for res in alias_resolutions}
        
        for entity in linked_entities:
            enhanced_entity = entity.copy()
            
            # Apply alias resolution if applicable
            canonical_name = enhanced_entity['canonical_name']
            if canonical_name in alias_map:
                enhanced_entity['canonical_name'] = alias_map[canonical_name]
                enhanced_entity['alias_resolved'] = True
            
            # Add linking metadata
            enhanced_entity['linking_metadata'] = {
                'kb_linked': enhanced_entity['kb_confidence'] > 0.5,
                'confidence': enhanced_entity['kb_confidence'],
                'match_type': enhanced_entity['match_type']
            }
            
            enhanced_entities.append(enhanced_entity)
        
        return enhanced_entities
    
    async def add_entity_to_kb(self, entity: Dict[str, Any]):
        """Add entity to knowledge base (for demo purposes)."""
        try:
            canonical_name = entity.get('canonical_name', entity['text'])
            entity_type = entity.get('type', 'ENTITY')
            entity_id = entity.get('entity_id', f"{entity_type.lower()}_{len(self.entity_kb) + 1}")
            
            self.entity_kb[canonical_name] = {
                'type': entity_type,
                'id': entity_id,
                'aliases': entity.get('aliases', [])
            }
            
            # Update alias map
            self.alias_map[canonical_name.lower()] = canonical_name
            for alias in entity.get('aliases', []):
                self.alias_map[alias.lower()] = canonical_name
            
            logger.info(f"Added entity to KB: {canonical_name} ({entity_type})")
            
        except Exception as e:
            logger.error(f"Error adding entity to KB: {e}")