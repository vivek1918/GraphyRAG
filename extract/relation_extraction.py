#!/usr/bin/env python3
"""
Multi-modal Relation Extraction module for extracting semantic relations between entities.
Supports text, audio transcripts, image descriptions, PDFs, and video content.
"""

import json
import re
from typing import List, Dict, Any, Tuple, Optional
from loguru import logger

class MultiModalRelationExtractor:
    """Extracts semantic relations between entities across multiple modalities."""
    
    def __init__(self, mode: str = "local"):
        self.mode = mode
        self.relation_patterns = self._initialize_relation_patterns()
        self.modality_specific_patterns = self._initialize_modality_patterns()
        
    def _initialize_relation_patterns(self) -> Dict[str, List[Tuple[str, re.Pattern]]]:
        """Initialize regex patterns for relation extraction across all modalities."""
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
            ],
            'RELATED_TO': [
                (r'([^,.]+)\s+(?:and|with)\s+([^,.]+)', 'ENTITY', 'ENTITY'),
                (r'([^,.]+)\s+related\s+to\s+([^,.]+)', 'ENTITY', 'ENTITY'),
                (r'([^,.]+)\s+associated\s+with\s+([^,.]+)', 'ENTITY', 'ENTITY'),
            ],
            'PART_OF': [
                (r'([^,.]+)\s+part\s+of\s+([^,.]+)', 'ENTITY', 'ENTITY'),
                (r'([^,.]+)\s+component\s+of\s+([^,.]+)', 'ENTITY', 'ENTITY'),
                (r'([^,.]+)\s+section\s+of\s+([^,.]+)', 'ENTITY', 'ENTITY'),
            ],
            'USES': [
                (r'([^,.]+)\s+uses?\s+([^,.]+)', 'ENTITY', 'ENTITY'),
                (r'([^,.]+)\s+utilizes?\s+([^,.]+)', 'ENTITY', 'ENTITY'),
                (r'([^,.]+)\s+employs?\s+([^,.]+)', 'ENTITY', 'ENTITY'),
            ],
            'CREATED_BY': [
                (r'([^,.]+)\s+created\s+by\s+([^,.]+)', 'ENTITY', 'PERSON'),
                (r'([^,.]+)\s+developed\s+by\s+([^,.]+)', 'ENTITY', 'PERSON'),
                (r'([^,.]+)\s+authored\s+by\s+([^,.]+)', 'ENTITY', 'PERSON'),
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
    
    def _initialize_modality_patterns(self) -> Dict[str, Dict[str, List[Tuple[str, re.Pattern]]]]:
        """Initialize modality-specific relation patterns."""
        modality_patterns = {
            'audio': {
                'SPEAKS_IN': [
                    (r'(\w+\s\w+)\s+(?:speaks|talks)\s+in\s+([^,.]+)', 'PERSON', 'AUDIO_ENTITY'),
                    (r'([^,.]+)\s+spoken\s+by\s+(\w+\s\w+)', 'AUDIO_ENTITY', 'PERSON'),
                ],
                'OCCURS_AT': [
                    (r'([^,.]+)\s+at\s+time\s+([\d:]+)', 'AUDIO_ENTITY', 'TIME'),
                    (r'([^,.]+)\s+during\s+([^,.]+)', 'AUDIO_ENTITY', 'TIME'),
                ]
            },
            'image': {
                'APPEARS_IN': [
                    (r'([^,.]+)\s+in\s+the\s+image', 'VISUAL_OBJECT', 'IMAGE'),
                    (r'([^,.]+)\s+shown\s+in\s+([^,.]+)', 'VISUAL_OBJECT', 'IMAGE'),
                ],
                'LOCATED_AT': [
                    (r'([^,.]+)\s+on\s+the\s+(left|right|top|bottom)', 'VISUAL_OBJECT', 'POSITION'),
                    (r'([^,.]+)\s+in\s+(background|foreground)', 'VISUAL_OBJECT', 'POSITION'),
                ],
                'NEAR': [
                    (r'([^,.]+)\s+near\s+([^,.]+)', 'VISUAL_OBJECT', 'VISUAL_OBJECT'),
                    (r'([^,.]+)\s+next\s+to\s+([^,.]+)', 'VISUAL_OBJECT', 'VISUAL_OBJECT'),
                ]
            },
            'video': {
                'APPEARS_IN_SCENE': [
                    (r'([^,.]+)\s+in\s+scene\s+([^,.]+)', 'VISUAL_OBJECT', 'SCENE'),
                    (r'([^,.]+)\s+during\s+([^,.]+)', 'VISUAL_OBJECT', 'SCENE'),
                ],
                'PERFORMS_ACTION': [
                    (r'([^,.]+)\s+(walking|running|talking|driving)', 'PERSON', 'ACTION'),
                    (r'([^,.]+)\s+performs?\s+([^,.]+)', 'PERSON', 'ACTION'),
                ],
                'TEMPORAL_SEQUENCE': [
                    (r'([^,.]+)\s+before\s+([^,.]+)', 'EVENT', 'EVENT'),
                    (r'([^,.]+)\s+after\s+([^,.]+)', 'EVENT', 'EVENT'),
                ]
            },
            'pdf': {
                'CONTAINS_SECTION': [
                    (r'([^,.]+)\s+contains\s+([^,.]+)', 'DOCUMENT', 'SECTION'),
                    (r'([^,.]+)\s+includes\s+([^,.]+)', 'DOCUMENT', 'SECTION'),
                ],
                'REFERENCES': [
                    (r'([^,.]+)\s+references?\s+([^,.]+)', 'SECTION', 'DOCUMENT'),
                    (r'([^,.]+)\s+cites?\s+([^,.]+)', 'SECTION', 'DOCUMENT'),
                ]
            }
        }
        
        # Compile modality patterns
        compiled_modality_patterns = {}
        for modality, patterns in modality_patterns.items():
            compiled_modality_patterns[modality] = {}
            for rel_type, pattern_list in patterns.items():
                compiled_modality_patterns[modality][rel_type] = []
                for pattern, subj_type, obj_type in pattern_list:
                    try:
                        compiled = re.compile(pattern, re.IGNORECASE)
                        compiled_modality_patterns[modality][rel_type].append((compiled, subj_type, obj_type))
                    except re.error as e:
                        logger.warning(f"Invalid modality regex pattern {pattern}: {e}")
        
        return compiled_modality_patterns
    
    async def extract(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract relations from multi-modal document."""
        try:
            content = document.get('content', '')
            entities = document.get('extracted_entities', [])
            modality = document.get('file_type', 'text')
            modality_data = document.get('modality_specific_data', {})
            coref_data = document.get('coref_data', {})
            resolved_entities = coref_data.get('resolved_entities', [])
            
            # Use resolved entities if available
            entities_to_use = resolved_entities if resolved_entities else entities
            
            if not entities_to_use or not content:
                return []
            
            logger.info(f"Extracting relations from {modality} document with {len(entities_to_use)} entities")
            
            # Extract relations using multiple methods
            pattern_relations = await self._extract_with_patterns(content, entities_to_use, modality)
            proximity_relations = await self._extract_with_proximity(content, entities_to_use, modality, modality_data)
            syntactic_relations = await self._extract_with_syntax(content, entities_to_use, modality)
            modality_relations = await self._extract_modality_specific(content, entities_to_use, modality, modality_data)
            
            # Combine all relations
            all_relations = (pattern_relations + proximity_relations + 
                           syntactic_relations + modality_relations)
            
            # Deduplicate and filter
            unique_relations = await self._deduplicate_relations(all_relations)
            filtered_relations = await self._filter_relations(unique_relations, modality)
            
            # Enhance with cross-modal context
            enhanced_relations = await self._enhance_relations_with_modality(
                filtered_relations, document
            )
            
            logger.debug(f"Extracted {len(enhanced_relations)} relations from {document.get('doc_id', 'unknown')}")
            return enhanced_relations
            
        except Exception as e:
            logger.error(f"Error extracting relations from {document.get('doc_id', 'unknown')}: {e}")
            return []
    
    async def _extract_with_patterns(self, content: str, entities: List[Dict], modality: str) -> List[Dict]:
        """Extract relations using regex patterns with modality awareness."""
        relations = []
        entity_texts = [e['text'] for e in entities]
        entity_map = {e['text']: e for e in entities}
        
        # Use general patterns for all modalities
        for rel_type, patterns in self.relation_patterns.items():
            for pattern, subj_type, obj_type in patterns:
                matches = pattern.findall(content)
                for match in matches:
                    if len(match) >= 2:
                        subject_candidate, object_candidate = match[0], match[1]
                        
                        # Find matching entities
                        subject_entity = await self._find_matching_entity(
                            subject_candidate, entity_texts, entity_map, subj_type, modality
                        )
                        object_entity = await self._find_matching_entity(
                            object_candidate, entity_texts, entity_map, obj_type, modality
                        )
                        
                        if subject_entity and object_entity:
                            relation = await self._create_relation(
                                subject_entity, object_entity, rel_type, content,
                                confidence=0.8, 
                                evidence=f"Pattern: {pattern.pattern}",
                                modality=modality
                            )
                            relations.append(relation)
        
        return relations
    
    async def _extract_modality_specific(self, content: str, entities: List[Dict], 
                                       modality: str, modality_data: Dict) -> List[Dict]:
        """Extract modality-specific relations."""
        relations = []
        
        if modality not in self.modality_specific_patterns:
            return relations
            
        entity_texts = [e['text'] for e in entities]
        entity_map = {e['text']: e for e in entities}
        patterns = self.modality_specific_patterns[modality]
        
        for rel_type, pattern_list in patterns.items():
            for pattern, subj_type, obj_type in pattern_list:
                matches = pattern.findall(content)
                for match in matches:
                    if len(match) >= 2:
                        subject_candidate, object_candidate = match[0], match[1]
                        
                        subject_entity = await self._find_matching_entity(
                            subject_candidate, entity_texts, entity_map, subj_type, modality
                        )
                        object_entity = await self._find_matching_entity(
                            object_candidate, entity_texts, entity_map, obj_type, modality
                        )
                        
                        if subject_entity and object_entity:
                            # Enhance confidence for modality-specific patterns
                            confidence = 0.85
                            relation = await self._create_relation(
                                subject_entity, object_entity, rel_type, content,
                                confidence=confidence,
                                evidence=f"Modality pattern ({modality}): {pattern.pattern}",
                                modality=modality
                            )
                            relations.append(relation)
        
        return relations
    
    async def _extract_with_proximity(self, content: str, entities: List[Dict], 
                                    modality: str, modality_data: Dict) -> List[Dict]:
        """Extract relations based on entity proximity with modality awareness."""
        relations = []
        
        # Sort entities by position
        positioned_entities = [e for e in entities if 'start_char' in e]
        if not positioned_entities:
            return relations
            
        positioned_entities.sort(key=lambda x: x['start_char'])
        
        # Modality-specific proximity thresholds
        proximity_thresholds = {
            'text': 50,
            'pdf': 100,
            'audio': 30,
            'image': 25,
            'video': 40
        }
        threshold = proximity_thresholds.get(modality, 50)
        
        # Check entities that are close to each other
        for i, entity1 in enumerate(positioned_entities):
            for j, entity2 in enumerate(positioned_entities[i+1:], i+1):
                distance = entity2['start_char'] - entity1['end_char']
                
                # Entities within threshold might be related
                if 0 < distance < threshold:
                    rel_type = await self._infer_relation_type(entity1, entity2, content, modality)
                    if rel_type:
                        # Adjust confidence based on distance and modality
                        base_confidence = 0.6 - (distance / (threshold * 2))
                        modality_confidence = await self._get_modality_confidence_factor(modality)
                        confidence = base_confidence * modality_confidence
                        
                        relation = await self._create_relation(
                            entity1, entity2, rel_type, content,
                            confidence=max(confidence, 0.3),
                            evidence=f"Proximity: {distance} chars in {modality}",
                            modality=modality
                        )
                        relations.append(relation)
        
        return relations
    
    async def _extract_with_syntax(self, content: str, entities: List[Dict], modality: str) -> List[Dict]:
        """Extract relations using simple syntactic analysis with modality awareness."""
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
                        rel_type = await self._infer_relation_type(entity1, entity2, sentence, modality)
                        if rel_type:
                            relation = await self._create_relation(
                                entity1, entity2, rel_type, sentence,
                                confidence=0.5,
                                evidence=f"Same sentence in {modality}: '{sentence.strip()}'",
                                modality=modality
                            )
                            relations.append(relation)
        
        return relations
    
    async def _find_matching_entity(self, candidate: str, entity_texts: List[str], 
                                  entity_map: Dict, expected_type: str, modality: str) -> Optional[Dict]:
        """Find entity that matches the candidate text with modality awareness."""
        candidate_clean = candidate.strip()
        
        # Exact match
        if candidate_clean in entity_texts:
            entity = entity_map[candidate_clean]
            if await self._is_type_compatible(entity.get('type'), expected_type, modality):
                return entity
        
        # Partial match with modality consideration
        for entity_text in entity_texts:
            if (candidate_clean in entity_text or entity_text in candidate_clean):
                entity = entity_map[entity_text]
                if await self._is_type_compatible(entity.get('type'), expected_type, modality):
                    return entity
        
        return None
    
    async def _is_type_compatible(self, actual_type: str, expected_type: str, modality: str) -> bool:
        """Check if entity types are compatible considering modality."""
        if expected_type == 'ENTITY':
            return True
            
        # Modality-specific type compatibility
        modality_compatibility = {
            'audio': {
                'PERSON': ['PERSON', 'AUDIO_ENTITY'],
                'AUDIO_ENTITY': ['AUDIO_ENTITY', 'PERSON', 'SOUND']
            },
            'image': {
                'VISUAL_OBJECT': ['VISUAL_OBJECT', 'OBJECT', 'PERSON', 'ORG'],
                'POSITION': ['POSITION', 'LOCATION', 'PLACE']
            },
            'video': {
                'VISUAL_OBJECT': ['VISUAL_OBJECT', 'OBJECT', 'PERSON', 'ORG'],
                'SCENE': ['SCENE', 'EVENT', 'LOCATION']
            }
        }
        
        if modality in modality_compatibility:
            compatible_types = modality_compatibility[modality].get(expected_type, [expected_type])
            return actual_type in compatible_types
        
        return actual_type == expected_type
    
    async def _infer_relation_type(self, entity1: Dict, entity2: Dict, context: str, modality: str) -> str:
        """Infer relation type based on entity types, context, and modality."""
        type1, type2 = entity1.get('type'), entity2.get('type')
        
        # Modality-specific relation inference
        modality_relations = await self._infer_modality_relations(type1, type2, modality)
        if modality_relations:
            return modality_relations
        
        # General relation inference
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
        
        # Part-whole relations
        if await self._suggests_part_whole(context):
            return 'PART_OF'
        
        # Usage relations
        if await self._suggests_usage(context):
            return 'USES'
        
        return 'RELATED_TO'
    
    async def _infer_modality_relations(self, type1: str, type2: str, modality: str) -> Optional[str]:
        """Infer modality-specific relations."""
        if modality == 'audio':
            if (type1 == 'PERSON' and type2 == 'AUDIO_ENTITY') or (type1 == 'AUDIO_ENTITY' and type2 == 'PERSON'):
                return 'SPEAKS_IN'
            if type1 == 'AUDIO_ENTITY' and type2 == 'TIME':
                return 'OCCURS_AT'
                
        elif modality == 'image':
            if type1 == 'VISUAL_OBJECT' and type2 in ['POSITION', 'LOCATION']:
                return 'LOCATED_AT'
            if type1 == 'VISUAL_OBJECT' and type2 == 'VISUAL_OBJECT':
                return 'NEAR'
                
        elif modality == 'video':
            if type1 == 'VISUAL_OBJECT' and type2 == 'SCENE':
                return 'APPEARS_IN_SCENE'
            if type1 == 'PERSON' and type2 == 'ACTION':
                return 'PERFORMS_ACTION'
            if type1 == 'EVENT' and type2 == 'EVENT':
                return 'TEMPORAL_SEQUENCE'
                
        elif modality == 'pdf':
            if (type1 == 'DOCUMENT' and type2 == 'SECTION') or (type1 == 'SECTION' and type2 == 'DOCUMENT'):
                return 'CONTAINS_SECTION'
            if type1 == 'SECTION' and type2 == 'DOCUMENT':
                return 'REFERENCES'
                
        return None
    
    async def _suggests_part_whole(self, context: str) -> bool:
        """Check if context suggests part-whole relationship."""
        part_whole_indicators = ['part of', 'component of', 'section of', 'element of', 'piece of']
        return any(indicator in context.lower() for indicator in part_whole_indicators)
    
    async def _suggests_usage(self, context: str) -> bool:
        """Check if context suggests usage relationship."""
        usage_indicators = ['uses', 'utilizes', 'employs', 'with', 'using']
        return any(indicator in context.lower() for indicator in usage_indicators)
    
    async def _create_relation(self, subject: Dict, object: Dict, rel_type: str, 
                             context: str, confidence: float, evidence: str, modality: str) -> Dict:
        """Create a relation object with modality context."""
        # Ensure subject and object are in correct order for certain relations
        if rel_type in ['WORKS_FOR', 'CREATED_BY']:
            if subject.get('type') in ['ORG', 'ENTITY'] and object.get('type') == 'PERSON':
                subject, object = object, subject
        
        return {
            'subject': subject.get('canonical_name', subject['text']),
            'object': object.get('canonical_name', object['text']),
            'relation': rel_type,
            'confidence': confidence,
            'evidence': evidence,
            'subject_type': subject.get('type'),
            'object_type': object.get('type'),
            'modality': modality,
            'subject_modality': subject.get('modality', modality),
            'object_modality': object.get('modality', modality),
            'context_snippet': context[:100] + '...' if len(context) > 100 else context,
            'cross_modal': subject.get('modality') != object.get('modality'),
            'extraction_method': self.mode
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
    
    async def _filter_relations(self, relations: List[Dict], modality: str) -> List[Dict]:
        """Filter relations based on confidence and modality-specific rules."""
        filtered_relations = []
        
        for relation in relations:
            confidence = relation.get('confidence', 0)
            
            # Modality-specific confidence thresholds
            modality_thresholds = {
                'text': 0.3,
                'pdf': 0.3,
                'audio': 0.4,
                'image': 0.45,
                'video': 0.4
            }
            threshold = modality_thresholds.get(modality, 0.3)
            
            if confidence >= threshold:
                filtered_relations.append(relation)
        
        return filtered_relations
    
    async def _enhance_relations_with_modality(self, relations: List[Dict], document: Dict[str, Any]) -> List[Dict]:
        """Enhance relations with cross-modal context and additional metadata."""
        enhanced_relations = []
        modality = document.get('file_type', 'text')
        
        for relation in relations:
            enhanced_relation = relation.copy()
            
            # Add cross-modal context
            enhanced_relation['cross_modal_context'] = await self._get_cross_modal_context(relation, document)
            
            # Enhance confidence based on cross-modal evidence
            if enhanced_relation['cross_modal']:
                enhanced_relation['confidence'] = min(enhanced_relation['confidence'] * 1.1, 1.0)
            
            # Add document context
            enhanced_relation['document_id'] = document.get('doc_id')
            enhanced_relation['source_modality'] = modality
            
            enhanced_relations.append(enhanced_relation)
            
        return enhanced_relations
    
    async def _get_cross_modal_context(self, relation: Dict, document: Dict[str, Any]) -> Dict[str, Any]:
        """Get cross-modal context for a relation."""
        context = {
            'has_cross_modal_evidence': relation['cross_modal'],
            'modality_pairs': [],
            'context_confidence': 0.5
        }
        
        if relation['cross_modal']:
            context['modality_pairs'] = [
                f"{relation['subject_modality']}-{relation['object_modality']}"
            ]
            context['context_confidence'] = 0.7
            
        return context
    
    async def _get_modality_confidence_factor(self, modality: str) -> float:
        """Get confidence factor based on modality."""
        modality_factors = {
            'text': 1.0,
            'pdf': 1.0,
            'audio': 0.9,
            'image': 0.8,
            'video': 0.85
        }
        return modality_factors.get(modality, 0.8)


async def extract_relations(document: Dict[str, Any], mode: str = "local") -> List[Dict[str, Any]]:
    """
    Convenience function for relation extraction.
    
    Args:
        document: Document dict with content, entities, and modality information
        mode: Extraction mode ('local', 'hf', 'groq')
        
    Returns:
        List of extracted relations
    """
    extractor = MultiModalRelationExtractor(mode=mode)
    return await extractor.extract(document)