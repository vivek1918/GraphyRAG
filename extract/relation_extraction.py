#!/usr/bin/env python3
"""
Relation Extraction module for extracting semantic relations between entities.
"""

import json
import re
from typing import List, Dict, Any, Tuple
from loguru import logger

class RelationExtractor:
    """Extracts semantic relations between entities."""
    
    def __init__(self, mode: str = "local"):
        self.mode = mode
        self.relation_patterns = self._initialize_relation_patterns()
        
    def _initialize_relation_patterns(self) -> Dict[str, List[Tuple[str, re.Pattern]]]:
        """Initialize regex patterns for relation extraction."""
        patterns = {
            'WORKS_FOR': [
                (r'(\w+\s\w+)\s+(?:is|was|are|were)\s+(?:the\s+)?(\w+)\s+of\s+([^,.]+)', 'PERSON', 'ORG'),
                (r'(\w+\s\w+)\s+(?:works?|worked)\s+for\s+([^,.]+)', 'PERSON', 'ORG'),
                (r'(\w+\s\w+)\s+from\s+([^,.]+)', 'PERSON', 'ORG'),
                (r'([^,.]+)\s+(?:employee|staff|worker|executive)\s+(\w+\s\w+)', 'ORG', 'PERSON'),
            ],
            'LOCATED_IN': [
                (r'([^,.]+)\s+in\s+([^,.]+)', 'ENTITY', 'PLACE'),
                (r'([^,.]+)\s+at\s+([^,.]+)', 'ENTITY', 'PLACE'),
                (r'([^,.]+)\s+located\s+in\s+([^,.]+)', 'ENTITY', 'PLACE'),
                (r'([^,.]+)\s+based\s+in\s+([^,.]+)', 'ENTITY', 'PLACE'),
            ],
            'HAS_ROLE': [
                (r'(\w+\s\w+)\s+(?:is|was|are|were)\s+(?:the\s+)?(\w+)', 'PERSON', 'ROLE'),
                (r'(\w+\s\w+)\s*,\s*(\w+(?:\s+\w+)*)', 'PERSON', 'ROLE'),
                (r'the\s+(\w+)\s+(\w+\s\w+)', 'ROLE', 'PERSON'),
            ],
            'PARTICIPATED_IN': [
                (r'(\w+\s\w+)\s+(?:attended|participated|joined)\s+([^,.]+)', 'PERSON', 'EVENT'),
                (r'([^,.]+)\s+(?:with|by)\s+(\w+\s\w+)', 'EVENT', 'PERSON'),
            ]
        }
        
        # Compile patterns
        compiled_patterns = {}
        for rel_type, pattern_list in patterns.items():
            compiled_patterns[rel_type] = []
            for pattern, subj_type, obj_type in pattern_list:
                try:
                    compiled = re.compile(pattern, re.IGNORECASE)
                    compiled_patterns[rel_type].append((compiled, subj_type, obj_type))
                except re.error as e:
                    logger.warning(f"Invalid regex pattern {pattern}: {e}")
        
        return compiled_patterns
    
    async def extract(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract relations from document."""
        try:
            content = document.get('content', '')
            entities = document.get('extracted_entities', [])
            coref_data = document.get('coref_data', {})
            resolved_entities = coref_data.get('resolved_entities', [])
            
            # Use resolved entities if available
            entities_to_use = resolved_entities if resolved_entities else entities
            
            if not entities_to_use or not content:
                return []
            
            # Extract relations using multiple methods
            pattern_relations = await self._extract_with_patterns(content, entities_to_use)
            proximity_relations = await self._extract_with_proximity(content, entities_to_use)
            syntactic_relations = await self._extract_with_syntax(content, entities_to_use)
            
            # Combine and deduplicate relations
            all_relations = pattern_relations + proximity_relations + syntactic_relations
            unique_relations = await self._deduplicate_relations(all_relations)
            
            # Filter by confidence
            filtered_relations = [rel for rel in unique_relations if rel.get('confidence', 0) > 0.3]
            
            logger.debug(f"Extracted {len(filtered_relations)} relations from {document['doc_id']}")
            return filtered_relations
            
        except Exception as e:
            logger.error(f"Error extracting relations from {document.get('doc_id')}: {e}")
            return []
    
    async def _extract_with_patterns(self, content: str, entities: List[Dict]) -> List[Dict]:
        """Extract relations using regex patterns."""
        relations = []
        entity_texts = [e['text'] for e in entities]
        entity_map = {e['text']: e for e in entities}
        
        for rel_type, patterns in self.relation_patterns.items():
            for pattern, subj_type, obj_type in patterns:
                matches = pattern.findall(content)
                for match in matches:
                    if len(match) >= 2:
                        subject_candidate, object_candidate = match[0], match[1]
                        
                        # Find matching entities
                        subject_entity = await self._find_matching_entity(subject_candidate, entity_texts, entity_map, subj_type)
                        object_entity = await self._find_matching_entity(object_candidate, entity_texts, entity_map, obj_type)
                        
                        if subject_entity and object_entity:
                            relation = await self._create_relation(
                                subject_entity, object_entity, rel_type, content,
                                confidence=0.8, evidence=f"Pattern: {pattern.pattern}"
                            )
                            relations.append(relation)
        
        return relations
    
    async def _extract_with_proximity(self, content: str, entities: List[Dict]) -> List[Dict]:
        """Extract relations based on entity proximity in text."""
        relations = []
        
        # Sort entities by position
        positioned_entities = [e for e in entities if 'start_char' in e]
        positioned_entities.sort(key=lambda x: x['start_char'])
        
        # Check entities that are close to each other
        for i, entity1 in enumerate(positioned_entities):
            for j, entity2 in enumerate(positioned_entities[i+1:], i+1):
                distance = entity2['start_char'] - entity1['end_char']
                
                # Entities within 50 characters might be related
                if 0 < distance < 50:
                    rel_type = await self._infer_relation_type(entity1, entity2, content)
                    if rel_type:
                        relation = await self._create_relation(
                            entity1, entity2, rel_type, content,
                            confidence=0.6 - (distance / 100),
                            evidence=f"Proximity: {distance} chars"
                        )
                        relations.append(relation)
        
        return relations
    
    async def _extract_with_syntax(self, content: str, entities: List[Dict]) -> List[Dict]:
        """Extract relations using simple syntactic analysis."""
        relations = []
        
        # Simple sentence-based analysis
        sentences = re.split(r'[.!?]+', content)
        entity_texts = [e['text'] for e in entities]
        entity_map = {e['text']: e for e in entities}
        
        for sentence in sentences:
            sentence_entities = []
            for entity_text in entity_texts:
                if entity_text in sentence:
                    sentence_entities.append(entity_map[entity_text])
            
            # If multiple entities in same sentence, they might be related
            if len(sentence_entities) >= 2:
                for i, entity1 in enumerate(sentence_entities):
                    for entity2 in sentence_entities[i+1:]:
                        rel_type = await self._infer_relation_type(entity1, entity2, sentence)
                        if rel_type:
                            relation = await self._create_relation(
                                entity1, entity2, rel_type, sentence,
                                confidence=0.5,
                                evidence=f"Same sentence: '{sentence.strip()}'"
                            )
                            relations.append(relation)
        
        return relations
    
    async def _find_matching_entity(self, candidate: str, entity_texts: List[str], 
                                  entity_map: Dict, expected_type: str) -> Dict:
        """Find entity that matches the candidate text."""
        candidate_clean = candidate.strip()
        
        # Exact match
        if candidate_clean in entity_texts:
            entity = entity_map[candidate_clean]
            if expected_type == 'ENTITY' or entity.get('type') == expected_type:
                return entity
        
        # Partial match
        for entity_text in entity_texts:
            if (candidate_clean in entity_text or entity_text in candidate_clean):
                entity = entity_map[entity_text]
                if expected_type == 'ENTITY' or entity.get('type') == expected_type:
                    return entity
        
        return None
    
    async def _infer_relation_type(self, entity1: Dict, entity2: Dict, context: str) -> str:
        """Infer relation type based on entity types and context."""
        type1, type2 = entity1.get('type'), entity2.get('type')
        
        # Person-Organization → WORKS_FOR
        if (type1 == 'PERSON' and type2 == 'ORG') or (type1 == 'ORG' and type2 == 'PERSON'):
            return 'WORKS_FOR'
        
        # Entity-Place → LOCATED_IN
        if (type2 == 'PLACE') and (type1 in ['PERSON', 'ORG', 'EVENT']):
            return 'LOCATED_IN'
        if (type1 == 'PLACE') and (type2 in ['PERSON', 'ORG', 'EVENT']):
            return 'LOCATED_IN'
        
        # Person-Event → PARTICIPATED_IN
        if (type1 == 'PERSON' and type2 == 'EVENT') or (type1 == 'EVENT' and type2 == 'PERSON'):
            return 'PARTICIPATED_IN'
        
        # Person-Role → HAS_ROLE
        if type1 == 'PERSON' and 'role' in entity2.get('attributes', {}):
            return 'HAS_ROLE'
        if type2 == 'PERSON' and 'role' in entity1.get('attributes', {}):
            return 'HAS_ROLE'
        
        return 'RELATED_TO'
    
    async def _create_relation(self, subject: Dict, object: Dict, rel_type: str, 
                             context: str, confidence: float, evidence: str) -> Dict:
        """Create a relation object."""
        # Ensure subject and object are in correct order for certain relations
        if rel_type == 'WORKS_FOR' and subject.get('type') == 'ORG' and object.get('type') == 'PERSON':
            subject, object = object, subject
        
        return {
            'subject': subject.get('canonical_name', subject['text']),
            'object': object.get('canonical_name', object['text']),
            'relation': rel_type,
            'confidence': confidence,
            'evidence': evidence,
            'subject_type': subject.get('type'),
            'object_type': object.get('type'),
            'context_snippet': context[:100] + '...' if len(context) > 100 else context
        }
    
    async def _deduplicate_relations(self, relations: List[Dict]) -> List[Dict]:
        """Remove duplicate relations."""
        unique_relations = []
        seen = set()
        
        for relation in relations:
            key = (relation['subject'], relation['object'], relation['relation'])
            if key not in seen:
                seen.add(key)
                unique_relations.append(relation)
            else:
                # Keep the higher confidence version
                for existing in unique_relations:
                    if (existing['subject'], existing['object'], existing['relation']) == key:
                        if relation['confidence'] > existing['confidence']:
                            unique_relations.remove(existing)
                            unique_relations.append(relation)
                        break
        
        return unique_relations