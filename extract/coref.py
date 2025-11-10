#!/usr/bin/env python3
"""
Coreference Resolution module for resolving entity mentions to canonical entities.
"""

import json
import re
from typing import List, Dict, Any, Tuple
from loguru import logger

class CoreferenceResolver:
    """Resolves coreferences in extracted entities."""
    
    def __init__(self):
        self.pronouns = {
            'he', 'him', 'his', 'she', 'her', 'hers', 
            'it', 'its', 'they', 'them', 'their', 'theirs'
        }
        self.honorifics = {'mr', 'mrs', 'ms', 'dr', 'prof'}
        
    async def resolve(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve coreferences in document entities."""
        try:
            content = document.get('content', '')
            entities = document.get('extracted_entities', [])
            
            if not entities:
                return {
                    'coreferences': [],
                    'resolved_entities': [],
                    'same_as': []
                }
            
            # Group entities by type and similarity
            clusters = await self._cluster_entities(entities, content)
            
            # Resolve coreferences
            coreferences = await self._build_coreference_chains(clusters, content)
            
            # Create resolved entities
            resolved_entities = await self._create_resolved_entities(entities, coreferences)
            
            # Find sameAs relations
            same_as = await self._find_same_as_relations(coreferences)
            
            return {
                'coreferences': coreferences,
                'resolved_entities': resolved_entities,
                'same_as': same_as
            }
            
        except Exception as e:
            logger.error(f"Error in coreference resolution: {e}")
            return {
                'coreferences': [],
                'resolved_entities': [],
                'same_as': []
            }
    
    async def _cluster_entities(self, entities: List[Dict], content: str) -> List[List[Dict]]:
        """Cluster entities that likely refer to the same real-world entity."""
        clusters = []
        
        # Group by type first
        by_type = {}
        for entity in entities:
            entity_type = entity.get('type', 'UNKNOWN')
            if entity_type not in by_type:
                by_type[entity_type] = []
            by_type[entity_type].append(entity)
        
        # For each type, cluster by similarity
        for entity_type, type_entities in by_type.items():
            if entity_type == 'PERSON':
                clusters.extend(await self._cluster_persons(type_entities, content))
            elif entity_type == 'ORG':
                clusters.extend(await self._cluster_organizations(type_entities, content))
            else:
                # For other types, use simple text similarity
                clusters.extend(await self._cluster_by_similarity(type_entities))
        
        return clusters
    
    async def _cluster_persons(self, persons: List[Dict], content: str) -> List[List[Dict]]:
        """Cluster person entities."""
        clusters = []
        used_indices = set()
        
        for i, person1 in enumerate(persons):
            if i in used_indices:
                continue
                
            cluster = [person1]
            used_indices.add(i)
            name1 = person1.get('canonical_name', person1['text']).lower()
            
            for j, person2 in enumerate(persons[i+1:], i+1):
                if j in used_indices:
                    continue
                    
                name2 = person2.get('canonical_name', person2['text']).lower()
                
                # Check for exact match
                if name1 == name2:
                    cluster.append(person2)
                    used_indices.add(j)
                    continue
                
                # Check for partial match (first name or last name)
                name1_parts = set(name1.split())
                name2_parts = set(name2.split())
                common_parts = name1_parts.intersection(name2_parts)
                
                if len(common_parts) >= 1 and len(common_parts) >= min(len(name1_parts), len(name2_parts)) - 1:
                    # Check context for additional evidence
                    if await self._check_same_person_context(person1, person2, content):
                        cluster.append(person2)
                        used_indices.add(j)
            
            clusters.append(cluster)
        
        return clusters
    
    async def _cluster_organizations(self, orgs: List[Dict], content: str) -> List[List[Dict]]:
        """Cluster organization entities."""
        clusters = []
        used_indices = set()
        
        for i, org1 in enumerate(orgs):
            if i in used_indices:
                continue
                
            cluster = [org1]
            used_indices.add(i)
            name1 = org1.get('canonical_name', org1['text']).lower()
            
            for j, org2 in enumerate(orgs[i+1:], i+1):
                if j in used_indices:
                    continue
                    
                name2 = org2.get('canonical_name', org2['text']).lower()
                
                # Check for exact or partial match
                if (name1 == name2 or 
                    name1 in name2 or 
                    name2 in name1 or
                    await self._are_orgs_similar(name1, name2)):
                    cluster.append(org2)
                    used_indices.add(j)
            
            clusters.append(cluster)
        
        return clusters
    
    async def _cluster_by_similarity(self, entities: List[Dict]) -> List[List[Dict]]:
        """Cluster entities by text similarity."""
        clusters = []
        used_indices = set()
        
        for i, entity1 in enumerate(entities):
            if i in used_indices:
                continue
                
            cluster = [entity1]
            used_indices.add(i)
            text1 = entity1.get('canonical_name', entity1['text']).lower()
            
            for j, entity2 in enumerate(entities[i+1:], i+1):
                if j in used_indices:
                    continue
                    
                text2 = entity2.get('canonical_name', entity2['text']).lower()
                
                # Simple similarity: exact match or one contains the other
                if text1 == text2 or text1 in text2 or text2 in text1:
                    cluster.append(entity2)
                    used_indices.add(j)
            
            clusters.append(cluster)
        
        return clusters
    
    async def _check_same_person_context(self, person1: Dict, person2: Dict, content: str) -> bool:
        """Check if two person mentions likely refer to the same person based on context."""
        text1 = person1['text']
        text2 = person2['text']
        
        # Check if they appear in the same sentence or nearby context
        sentences = re.split(r'[.!?]+', content)
        for sentence in sentences:
            if text1 in sentence and text2 in sentence:
                # If both appear in same sentence, they're likely different people
                return False
        
        # Check for honorific patterns
        patterns = [
            rf"{text1}.*{text2}",  # Full name followed by partial
            rf"{text2}.*{text1}",  # Partial followed by full name
        ]
        
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
    
    async def _are_orgs_similar(self, org1: str, org2: str) -> bool:
        """Check if two organization names are similar."""
        # Remove common suffixes and compare
        suffixes = ['inc', 'corp', 'ltd', 'co', 'llc', 'company']
        
        name1 = org1.lower()
        name2 = org2.lower()
        
        for suffix in suffixes:
            name1 = name1.replace(f' {suffix}', '').replace(f'.{suffix}', '')
            name2 = name2.replace(f' {suffix}', '').replace(f'.{suffix}', '')
        
        return name1 == name2 or name1 in name2 or name2 in name1
    
    async def _build_coreference_chains(self, clusters: List[List[Dict]], content: str) -> List[Dict]:
        """Build coreference chains from entity clusters."""
        coreferences = []
        
        for i, cluster in enumerate(clusters):
            if not cluster:
                continue
                
            # Find the most representative mention (longest canonical name)
            canonical_entity = max(cluster, key=lambda x: len(x.get('canonical_name', x['text'])))
            mentions = [entity['text'] for entity in cluster]
            
            coreferences.append({
                'cluster_id': f"cluster_{i}",
                'mentions': mentions,
                'canonical_entity': canonical_entity.get('canonical_name', canonical_entity['text']),
                'type': cluster[0].get('type', 'ENTITY'),
                'confidence': await self._calculate_cluster_confidence(cluster, content)
            })
        
        return coreferences
    
    async def _create_resolved_entities(self, entities: List[Dict], coreferences: List[Dict]) -> List[Dict]:
        """Create resolved entities with canonical IDs."""
        resolved_entities = []
        
        # Map from original text to canonical entity
        text_to_canonical = {}
        for coref in coreferences:
            canonical_name = coref['canonical_entity']
            for mention in coref['mentions']:
                text_to_canonical[mention] = {
                    'canonical_name': canonical_name,
                    'entity_id': coref['cluster_id'],
                    'type': coref['type']
                }
        
        # Create resolved entities
        for entity in entities:
            original_text = entity['text']
            if original_text in text_to_canonical:
                canonical_info = text_to_canonical[original_text]
                resolved_entities.append({
                    'original_text': original_text,
                    'canonical_name': canonical_info['canonical_name'],
                    'entity_id': canonical_info['entity_id'],
                    'type': canonical_info['type'],
                    'start_char': entity.get('start_char'),
                    'end_char': entity.get('end_char'),
                    'confidence': entity.get('confidence', 0.5)
                })
            else:
                # Entity not in any coreference chain
                resolved_entities.append({
                    'original_text': original_text,
                    'canonical_name': entity.get('canonical_name', original_text),
                    'entity_id': f"entity_{hash(original_text)}",
                    'type': entity.get('type', 'ENTITY'),
                    'start_char': entity.get('start_char'),
                    'end_char': entity.get('end_char'),
                    'confidence': entity.get('confidence', 0.5)
                })
        
        return resolved_entities
    
    async def _find_same_as_relations(self, coreferences: List[Dict]) -> List[Dict]:
        """Find sameAs relations between entities."""
        same_as = []
        
        for coref in coreferences:
            mentions = coref['mentions']
            if len(mentions) > 1:
                # Create sameAs relations between all mentions
                for i in range(len(mentions)):
                    for j in range(i + 1, len(mentions)):
                        same_as.append({
                            'entity1': mentions[i],
                            'entity2': mentions[j],
                            'confidence': coref.get('confidence', 0.8),
                            'evidence': f"Coreference cluster {coref['cluster_id']}",
                            'type': 'SAME_AS'
                        })
        
        return same_as
    
    async def _calculate_cluster_confidence(self, cluster: List[Dict], content: str) -> float:
        """Calculate confidence score for a coreference cluster."""
        if len(cluster) <= 1:
            return 0.3  # Low confidence for single entities
        
        base_confidence = min(0.9, 0.5 + (len(cluster) * 0.1))
        
        # Check if entities have similar attributes
        first_entity = cluster[0]
        consistent_attributes = True
        
        for entity in cluster[1:]:
            if entity.get('type') != first_entity.get('type'):
                consistent_attributes = False
                break
        
        if consistent_attributes:
            base_confidence += 0.1
        
        return min(0.95, base_confidence)