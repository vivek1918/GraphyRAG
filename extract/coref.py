#!/usr/bin/env python3
"""
Multi-modal Coreference Resolution module for resolving entity mentions to canonical entities.
Supports text, audio transcripts, image descriptions, and video content.
"""

import json
import re
from typing import List, Dict, Any, Tuple, Set
from loguru import logger

class CoreferenceResolver:
    """Resolves coreferences in extracted entities across multiple modalities."""
    
    def __init__(self):
        self.pronouns = {
            'he', 'him', 'his', 'she', 'her', 'hers', 
            'it', 'its', 'they', 'them', 'their', 'theirs',
            'this', 'that', 'these', 'those', 'here', 'there'
        }
        self.honorifics = {'mr', 'mrs', 'ms', 'dr', 'prof', 'sir', 'madam'}
        
        # Modality-specific coreference patterns
        self.modality_patterns = {
            'audio': {
                'speaker_indicators': ['speaker', 'voice', 'narrator', 'interviewer', 'interviewee'],
                'temporal_indicators': ['previously', 'earlier', 'later', 'before', 'after']
            },
            'image': {
                'spatial_indicators': ['left', 'right', 'top', 'bottom', 'center', 'foreground', 'background'],
                'visual_indicators': ['visible', 'shown', 'depicted', 'illustrated']
            },
            'video': {
                'temporal_indicators': ['scene', 'frame', 'shot', 'clip', 'previously', 'next'],
                'visual_indicators': ['on screen', 'visible', 'appears', 'disappears']
            }
        }
        
    async def resolve(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve coreferences in document entities across modalities."""
        try:
            content = document.get('content', '')
            entities = document.get('extracted_entities', [])
            modality = document.get('file_type', 'text')
            modality_data = document.get('modality_specific_data', {})
            
            if not entities:
                return {
                    'coreferences': [],
                    'resolved_entities': [],
                    'same_as': [],
                    'cross_modal_references': []
                }
            
            # Group entities by type and similarity across modalities
            clusters = await self._cluster_entities(entities, content, modality, modality_data)
            
            # Resolve coreferences
            coreferences = await self._build_coreference_chains(clusters, content, modality)
            
            # Create resolved entities
            resolved_entities = await self._create_resolved_entities(entities, coreferences, modality)
            
            # Find sameAs relations
            same_as = await self._find_same_as_relations(coreferences)
            
            # Find cross-modal references
            cross_modal_refs = await self._find_cross_modal_references(document, resolved_entities)
            
            return {
                'coreferences': coreferences,
                'resolved_entities': resolved_entities,
                'same_as': same_as,
                'cross_modal_references': cross_modal_refs,
                'modality': modality,
                'resolution_confidence': await self._calculate_overall_confidence(coreferences, modality)
            }
            
        except Exception as e:
            logger.error(f"Error in coreference resolution: {e}")
            return {
                'coreferences': [],
                'resolved_entities': [],
                'same_as': [],
                'cross_modal_references': [],
                'modality': document.get('file_type', 'text'),
                'resolution_confidence': 0.0
            }
    
    async def _cluster_entities(self, entities: List[Dict], content: str, modality: str, modality_data: Dict) -> List[List[Dict]]:
        """Cluster entities that likely refer to the same real-world entity across modalities."""
        clusters = []
        
        # Group by type first
        by_type = {}
        for entity in entities:
            entity_type = entity.get('type', 'UNKNOWN')
            if entity_type not in by_type:
                by_type[entity_type] = []
            by_type[entity_type].append(entity)
        
        # For each type, cluster by similarity with modality awareness
        for entity_type, type_entities in by_type.items():
            if entity_type == 'PERSON':
                clusters.extend(await self._cluster_persons(type_entities, content, modality, modality_data))
            elif entity_type == 'ORG':
                clusters.extend(await self._cluster_organizations(type_entities, content, modality))
            elif entity_type in ['VISUAL_OBJECT', 'AUDIO_ENTITY']:
                clusters.extend(await self._cluster_modality_specific(type_entities, content, modality, modality_data))
            else:
                # For other types, use enhanced similarity with modality context
                clusters.extend(await self._cluster_by_enhanced_similarity(type_entities, content, modality))
        
        # Merge clusters that refer to the same entity
        merged_clusters = await self._merge_cross_type_clusters(clusters, content, modality)
        
        return merged_clusters
    
    async def _cluster_persons(self, persons: List[Dict], content: str, modality: str, modality_data: Dict) -> List[List[Dict]]:
        """Cluster person entities with modality awareness."""
        clusters = []
        used_indices = set()
        
        for i, person1 in enumerate(persons):
            if i in used_indices:
                continue
                
            cluster = [person1]
            used_indices.add(i)
            name1 = person1.get('canonical_name', person1['text']).lower()
            modality1 = person1.get('modality', modality)
            
            for j, person2 in enumerate(persons[i+1:], i+1):
                if j in used_indices:
                    continue
                    
                name2 = person2.get('canonical_name', person2['text']).lower()
                modality2 = person2.get('modality', modality)
                
                # Check for exact match
                if name1 == name2:
                    cluster.append(person2)
                    used_indices.add(j)
                    continue
                
                # Check for partial match (first name or last name)
                name1_parts = set(name1.split())
                name2_parts = set(name2.split())
                common_parts = name1_parts.intersection(name2_parts)
                
                similarity_threshold = 1 if modality in ['audio', 'video'] else 2
                if (len(common_parts) >= min(len(name1_parts), len(name2_parts)) - 1 or
                    len(common_parts) >= similarity_threshold):
                    
                    # Check context for additional evidence with modality awareness
                    if await self._check_same_person_context(person1, person2, content, modality, modality_data):
                        cluster.append(person2)
                        used_indices.add(j)
            
            clusters.append(cluster)
        
        return clusters
    
    async def _cluster_organizations(self, orgs: List[Dict], content: str, modality: str) -> List[List[Dict]]:
        """Cluster organization entities with modality awareness."""
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
                
                # Enhanced organization matching with modality context
                if (await self._are_orgs_similar(name1, name2) or
                    await self._check_org_context_similarity(org1, org2, content, modality)):
                    cluster.append(org2)
                    used_indices.add(j)
            
            clusters.append(cluster)
        
        return clusters
    
    async def _cluster_modality_specific(self, entities: List[Dict], content: str, modality: str, modality_data: Dict) -> List[List[Dict]]:
        """Cluster modality-specific entities (visual objects, audio entities, etc.)."""
        clusters = []
        used_indices = set()
        
        for i, entity1 in enumerate(entities):
            if i in used_indices:
                continue
                
            cluster = [entity1]
            used_indices.add(i)
            text1 = entity1.get('canonical_name', entity1['text']).lower()
            position1 = entity1.get('position', {})
            
            for j, entity2 in enumerate(entities[i+1:], i+1):
                if j in used_indices:
                    continue
                    
                text2 = entity2.get('canonical_name', entity2['text']).lower()
                position2 = entity2.get('position', {})
                
                # Modality-specific clustering logic
                if modality == 'image':
                    if await self._are_visual_entities_similar(entity1, entity2, modality_data):
                        cluster.append(entity2)
                        used_indices.add(j)
                elif modality == 'audio':
                    if await self._are_audio_entities_similar(entity1, entity2, modality_data):
                        cluster.append(entity2)
                        used_indices.add(j)
                elif modality == 'video':
                    if await self._are_video_entities_similar(entity1, entity2, modality_data):
                        cluster.append(entity2)
                        used_indices.add(j)
                else:
                    # Fallback to text similarity
                    if text1 == text2 or text1 in text2 or text2 in text1:
                        cluster.append(entity2)
                        used_indices.add(j)
            
            clusters.append(cluster)
        
        return clusters
    
    async def _cluster_by_enhanced_similarity(self, entities: List[Dict], content: str, modality: str) -> List[List[Dict]]:
        """Cluster entities by enhanced text similarity with modality context."""
        clusters = []
        used_indices = set()
        
        for i, entity1 in enumerate(entities):
            if i in used_indices:
                continue
                
            cluster = [entity1]
            used_indices.add(i)
            text1 = entity1.get('canonical_name', entity1['text']).lower()
            attributes1 = entity1.get('attributes', {})
            
            for j, entity2 in enumerate(entities[i+1:], i+1):
                if j in used_indices:
                    continue
                    
                text2 = entity2.get('canonical_name', entity2['text']).lower()
                attributes2 = entity2.get('attributes', {})
                
                # Enhanced similarity checking
                similarity_score = await self._calculate_entity_similarity(
                    entity1, entity2, content, modality
                )
                
                if similarity_score > 0.7:  # Adjust threshold as needed
                    cluster.append(entity2)
                    used_indices.add(j)
            
            clusters.append(cluster)
        
        return clusters
    
    async def _merge_cross_type_clusters(self, clusters: List[List[Dict]], content: str, modality: str) -> List[List[Dict]]:
        """Merge clusters that might refer to the same entity across different types."""
        # This is a simplified implementation - in practice, you might want more sophisticated merging
        merged_clusters = []
        used_clusters = set()
        
        for i, cluster1 in enumerate(clusters):
            if i in used_clusters:
                continue
                
            merged_cluster = cluster1.copy()
            used_clusters.add(i)
            
            for j, cluster2 in enumerate(clusters[i+1:], i+1):
                if j in used_clusters:
                    continue
                    
                # Check if clusters might refer to same entity (e.g., person and organization)
                if await self._are_clusters_related(cluster1, cluster2, content, modality):
                    merged_cluster.extend(cluster2)
                    used_clusters.add(j)
            
            merged_clusters.append(merged_cluster)
        
        return merged_clusters
    
    async def _check_same_person_context(self, person1: Dict, person2: Dict, content: str, modality: str, modality_data: Dict) -> bool:
        """Check if two person mentions likely refer to the same person based on context and modality."""
        text1 = person1['text']
        text2 = person2['text']
        
        # Modality-specific context checking
        if modality == 'audio':
            return await self._check_audio_person_context(person1, person2, modality_data)
        elif modality == 'video':
            return await self._check_video_person_context(person1, person2, modality_data)
        elif modality == 'image':
            return await self._check_image_person_context(person1, person2, modality_data)
        
        # Text-based context checking (original logic)
        sentences = re.split(r'[.!?]+', content)
        for sentence in sentences:
            if text1 in sentence and text2 in sentence:
                # If both appear in same sentence, check if they're likely the same
                if await self._are_names_coreferential(text1, text2, sentence):
                    return True
                else:
                    return False
        
        # Check for honorific patterns and other indicators
        patterns = [
            rf"{re.escape(text1)}.*{re.escape(text2)}",
            rf"{re.escape(text2)}.*{re.escape(text1)}",
            rf"\b{re.escape(text1)}\b.*\b(?:also|formerly|known as)\b.*\b{re.escape(text2)}\b"
        ]
        
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
    
    async def _are_names_coreferential(self, name1: str, name2: str, context: str) -> bool:
        """Check if two names in the same context are likely coreferential."""
        # If one name is clearly a subset of the other
        if name1 in name2 or name2 in name1:
            return True
            
        # Check for pronoun references
        name1_words = set(name1.lower().split())
        name2_words = set(name2.lower().split())
        common_words = name1_words.intersection(name2_words)
        
        # If they share significant words and context suggests coreference
        if len(common_words) >= min(len(name1_words), len(name2_words)):
            return True
            
        return False
    
    async def _check_audio_person_context(self, person1: Dict, person2: Dict, modality_data: Dict) -> bool:
        """Check audio-specific person context."""
        # Use speaker identification, timestamps, etc.
        speaker1 = person1.get('attributes', {}).get('speaker')
        speaker2 = person2.get('attributes', {}).get('speaker')
        
        if speaker1 and speaker2 and speaker1 == speaker2:
            return True
            
        # Check temporal proximity in audio
        time1 = person1.get('position', {}).get('timestamp')
        time2 = person2.get('position', {}).get('timestamp')
        
        if time1 and time2 and abs(time1 - time2) < 30:  # Within 30 seconds
            return True
            
        return False
    
    async def _check_video_person_context(self, person1: Dict, person2: Dict, modality_data: Dict) -> bool:
        """Check video-specific person context."""
        # Use visual features, face recognition, scene context
        scene1 = person1.get('position', {}).get('scene')
        scene2 = person2.get('position', {}).get('scene')
        
        if scene1 and scene2 and scene1 == scene2:
            return True
            
        # Check temporal proximity
        time1 = person1.get('position', {}).get('timestamp')
        time2 = person2.get('position', {}).get('timestamp')
        
        if time1 and time2 and abs(time1 - time2) < 10:  # Within 10 seconds
            return True
            
        return False
    
    async def _check_image_person_context(self, person1: Dict, person2: Dict, modality_data: Dict) -> bool:
        """Check image-specific person context."""
        # Use spatial proximity, visual similarity
        bbox1 = person1.get('position', {}).get('bounding_box')
        bbox2 = person2.get('position', {}).get('bounding_box')
        
        if bbox1 and bbox2:
            # Simple bounding box proximity check
            return await self._are_boxes_proximate(bbox1, bbox2)
            
        return False
    
    async def _are_orgs_similar(self, org1: str, org2: str) -> bool:
        """Check if two organization names are similar."""
        # Remove common suffixes and compare
        suffixes = ['inc', 'corp', 'ltd', 'co', 'llc', 'company', 'corporation', 'limited']
        
        name1 = org1.lower()
        name2 = org2.lower()
        
        for suffix in suffixes:
            pattern = rf'\b{re.escape(suffix)}\b\.?'
            name1 = re.sub(pattern, '', name1).strip()
            name2 = re.sub(pattern, '', name2).strip()
        
        # Compare cleaned names
        if name1 == name2:
            return True
            
        # Check for acronym matches
        acronym1 = ''.join(word[0] for word in name1.split() if word)
        acronym2 = ''.join(word[0] for word in name2.split() if word)
        
        if acronym1 and acronym2 and acronym1 == acronym2:
            return True
            
        # Check for significant word overlap
        words1 = set(name1.split())
        words2 = set(name2.split())
        overlap = words1.intersection(words2)
        
        return len(overlap) >= min(len(words1), len(words2)) * 0.5
    
    async def _check_org_context_similarity(self, org1: Dict, org2: Dict, content: str, modality: str) -> bool:
        """Check if organizations appear in similar contexts."""
        # This could be enhanced with more sophisticated context analysis
        text1 = org1['text']
        text2 = org2['text']
        
        # Simple context window comparison
        window_size = 100
        positions1 = [m.start() for m in re.finditer(re.escape(text1), content)]
        positions2 = [m.start() for m in re.finditer(re.escape(text2), content)]
        
        for pos1 in positions1:
            for pos2 in positions2:
                if abs(pos1 - pos2) < window_size:
                    return True
                    
        return False
    
    async def _are_visual_entities_similar(self, entity1: Dict, entity2: Dict, modality_data: Dict) -> bool:
        """Check if two visual entities are similar."""
        # Use visual features, spatial relationships, etc.
        bbox1 = entity1.get('position', {}).get('bounding_box')
        bbox2 = entity2.get('position', {}).get('bounding_box')
        
        if bbox1 and bbox2:
            return await self._are_boxes_proximate(bbox1, bbox2)
            
        # Fallback to text similarity
        text1 = entity1.get('canonical_name', entity1['text']).lower()
        text2 = entity2.get('canonical_name', entity2['text']).lower()
        return text1 == text2 or text1 in text2 or text2 in text1
    
    async def _are_audio_entities_similar(self, entity1: Dict, entity2: Dict, modality_data: Dict) -> bool:
        """Check if two audio entities are similar."""
        # Use acoustic features, temporal proximity, etc.
        time1 = entity1.get('position', {}).get('timestamp')
        time2 = entity2.get('position', {}).get('timestamp')
        
        if time1 and time2 and abs(time1 - time2) < 5:  # Within 5 seconds
            return True
            
        # Fallback to text similarity
        text1 = entity1.get('canonical_name', entity1['text']).lower()
        text2 = entity2.get('canonical_name', entity2['text']).lower()
        return text1 == text2 or text1 in text2 or text2 in text1
    
    async def _are_video_entities_similar(self, entity1: Dict, entity2: Dict, modality_data: Dict) -> bool:
        """Check if two video entities are similar."""
        # Use both spatial and temporal proximity
        time1 = entity1.get('position', {}).get('timestamp')
        time2 = entity2.get('position', {}).get('timestamp')
        bbox1 = entity1.get('position', {}).get('bounding_box')
        bbox2 = entity2.get('position', {}).get('bounding_box')
        
        temporal_similar = time1 and time2 and abs(time1 - time2) < 3  # Within 3 seconds
        spatial_similar = bbox1 and bbox2 and await self._are_boxes_proximate(bbox1, bbox2)
        
        return temporal_similar or spatial_similar
    
    async def _are_boxes_proximate(self, bbox1: List[float], bbox2: List[float], threshold: float = 0.3) -> bool:
        """Check if two bounding boxes are proximate."""
        # Simple IoU (Intersection over Union) calculation
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        # Calculate intersection area
        xi = max(x1, x2)
        yi = max(y1, y2)
        wi = min(x1 + w1, x2 + w2) - xi
        hi = min(y1 + h1, y2 + h2) - yi
        
        if wi <= 0 or hi <= 0:
            return False
            
        intersection = wi * hi
        area1 = w1 * h1
        area2 = w2 * h2
        union = area1 + area2 - intersection
        
        iou = intersection / union if union > 0 else 0
        return iou > threshold
    
    async def _calculate_entity_similarity(self, entity1: Dict, entity2: Dict, content: str, modality: str) -> float:
        """Calculate similarity score between two entities."""
        score = 0.0
        
        # Text similarity
        text1 = entity1.get('canonical_name', entity1['text']).lower()
        text2 = entity2.get('canonical_name', entity2['text']).lower()
        
        if text1 == text2:
            score += 0.6
        elif text1 in text2 or text2 in text1:
            score += 0.4
        else:
            # Word overlap
            words1 = set(text1.split())
            words2 = set(text2.split())
            overlap = len(words1.intersection(words2))
            total = len(words1.union(words2))
            if total > 0:
                score += (overlap / total) * 0.3
        
        # Type similarity
        if entity1.get('type') == entity2.get('type'):
            score += 0.2
        
        # Attribute similarity
        attrs1 = entity1.get('attributes', {})
        attrs2 = entity2.get('attributes', {})
        common_attrs = set(attrs1.keys()).intersection(set(attrs2.keys()))
        for attr in common_attrs:
            if attrs1[attr] == attrs2[attr]:
                score += 0.1
        
        return min(score, 1.0)
    
    async def _are_clusters_related(self, cluster1: List[Dict], cluster2: List[Dict], content: str, modality: str) -> bool:
        """Check if two clusters might refer to the same entity across types."""
        # Simple implementation - check if any entities in cluster1 are similar to any in cluster2
        for entity1 in cluster1:
            for entity2 in cluster2:
                similarity = await self._calculate_entity_similarity(entity1, entity2, content, modality)
                if similarity > 0.8:
                    return True
        return False
    
    async def _build_coreference_chains(self, clusters: List[List[Dict]], content: str, modality: str) -> List[Dict]:
        """Build coreference chains from entity clusters with modality awareness."""
        coreferences = []
        
        for i, cluster in enumerate(clusters):
            if not cluster:
                continue
                
            # Find the most representative mention
            canonical_entity = await self._select_canonical_entity(cluster, modality)
            mentions = [{
                'text': entity['text'],
                'modality': entity.get('modality', modality),
                'position': entity.get('position'),
                'confidence': entity.get('confidence', 0.5)
            } for entity in cluster]
            
            coreferences.append({
                'cluster_id': f"cluster_{i}",
                'mentions': mentions,
                'canonical_entity': canonical_entity.get('canonical_name', canonical_entity['text']),
                'canonical_type': canonical_entity.get('type', 'ENTITY'),
                'modality': modality,
                'cluster_size': len(cluster),
                'confidence': await self._calculate_cluster_confidence(cluster, content, modality)
            })
        
        return coreferences
    
    async def _select_canonical_entity(self, cluster: List[Dict], modality: str) -> Dict:
        """Select the most representative entity from a cluster."""
        # Prefer entities with canonical names
        entities_with_canonical = [e for e in cluster if e.get('canonical_name')]
        if entities_with_canonical:
            cluster = entities_with_canonical
        
        # Modality-specific selection criteria
        if modality in ['image', 'video']:
            # Prefer entities with position information
            entities_with_position = [e for e in cluster if e.get('position')]
            if entities_with_position:
                return max(entities_with_position, key=lambda x: len(x.get('canonical_name', x['text'])))
        
        # Default: longest canonical name
        return max(cluster, key=lambda x: len(x.get('canonical_name', x['text'])))
    
    async def _create_resolved_entities(self, entities: List[Dict], coreferences: List[Dict], modality: str) -> List[Dict]:
        """Create resolved entities with canonical IDs and modality information."""
        resolved_entities = []
        
        # Map from original text to canonical entity
        text_to_canonical = {}
        for coref in coreferences:
            canonical_name = coref['canonical_entity']
            for mention in coref['mentions']:
                text_to_canonical[mention['text']] = {
                    'canonical_name': canonical_name,
                    'entity_id': coref['cluster_id'],
                    'type': coref['canonical_type'],
                    'modality': mention.get('modality', modality)
                }
        
        # Create resolved entities
        for entity in entities:
            original_text = entity['text']
            if original_text in text_to_canonical:
                canonical_info = text_to_canonical[original_text]
                resolved_entity = {
                    'original_text': original_text,
                    'canonical_name': canonical_info['canonical_name'],
                    'entity_id': canonical_info['entity_id'],
                    'type': canonical_info['type'],
                    'modality': canonical_info['modality'],
                    'start_char': entity.get('start_char'),
                    'end_char': entity.get('end_char'),
                    'position': entity.get('position'),
                    'confidence': entity.get('confidence', 0.5),
                    'attributes': entity.get('attributes', {})
                }
                resolved_entities.append(resolved_entity)
            else:
                # Entity not in any coreference chain
                resolved_entity = {
                    'original_text': original_text,
                    'canonical_name': entity.get('canonical_name', original_text),
                    'entity_id': f"entity_{hash(original_text)}",
                    'type': entity.get('type', 'ENTITY'),
                    'modality': entity.get('modality', modality),
                    'start_char': entity.get('start_char'),
                    'end_char': entity.get('end_char'),
                    'position': entity.get('position'),
                    'confidence': entity.get('confidence', 0.5),
                    'attributes': entity.get('attributes', {})
                }
                resolved_entities.append(resolved_entity)
        
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
                            'entity1': mentions[i]['text'],
                            'entity2': mentions[j]['text'],
                            'confidence': coref.get('confidence', 0.8),
                            'evidence': f"Coreference cluster {coref['cluster_id']}",
                            'type': 'SAME_AS',
                            'modality': coref.get('modality', 'text')
                        })
        
        return same_as
    
    async def _find_cross_modal_references(self, document: Dict[str, Any], resolved_entities: List[Dict]) -> List[Dict]:
        """Find references between entities across different modalities."""
        # This is a placeholder for cross-modal reference resolution
        # In practice, this would require more sophisticated multi-modal analysis
        cross_modal_refs = []
        
        # Simple implementation: look for entities with same canonical names across different positions
        entities_by_name = {}
        for entity in resolved_entities:
            canonical_name = entity['canonical_name']
            if canonical_name not in entities_by_name:
                entities_by_name[canonical_name] = []
            entities_by_name[canonical_name].append(entity)
        
        for canonical_name, entities in entities_by_name.items():
            if len(entities) > 1:
                # Check if entities have different modalities or positions
                modalities = set(e['modality'] for e in entities)
                if len(modalities) > 1:
                    for i in range(len(entities)):
                        for j in range(i + 1, len(entities)):
                            if entities[i]['modality'] != entities[j]['modality']:
                                cross_modal_refs.append({
                                    'entity1': entities[i]['original_text'],
                                    'entity2': entities[j]['original_text'],
                                    'canonical_name': canonical_name,
                                    'modality1': entities[i]['modality'],
                                    'modality2': entities[j]['modality'],
                                    'confidence': 0.7,
                                    'type': 'CROSS_MODAL_REFERENCE'
                                })
        
        return cross_modal_refs
    
    async def _calculate_cluster_confidence(self, cluster: List[Dict], content: str, modality: str) -> float:
        """Calculate confidence score for a coreference cluster with modality awareness."""
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
        
        # Modality-specific confidence adjustments
        if modality in ['audio', 'video']:
            # Temporal consistency check
            if await self._check_temporal_consistency(cluster, modality):
                base_confidence += 0.1
        elif modality == 'image':
            # Spatial consistency check
            if await self._check_spatial_consistency(cluster):
                base_confidence += 0.1
        
        return min(0.95, base_confidence)
    
    async def _check_temporal_consistency(self, cluster: List[Dict], modality: str) -> bool:
        """Check if entities in cluster have temporally consistent appearances."""
        timestamps = []
        for entity in cluster:
            position = entity.get('position', {})
            if 'timestamp' in position:
                timestamps.append(position['timestamp'])
        
        if len(timestamps) < 2:
            return True  # Not enough data to determine inconsistency
        
        # Check if timestamps are reasonably close
        timestamps.sort()
        max_gap = max(timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1))
        
        threshold = 60 if modality == 'audio' else 30  # seconds
        return max_gap <= threshold
    
    async def _check_spatial_consistency(self, cluster: List[Dict]) -> bool:
        """Check if entities in cluster have spatially consistent positions."""
        bboxes = []
        for entity in cluster:
            position = entity.get('position', {})
            if 'bounding_box' in position:
                bboxes.append(position['bounding_box'])
        
        if len(bboxes) < 2:
            return True  # Not enough data to determine inconsistency
        
        # Check if bounding boxes are reasonably proximate
        for i in range(len(bboxes)):
            for j in range(i + 1, len(bboxes)):
                if not await self._are_boxes_proximate(bboxes[i], bboxes[j], threshold=0.1):
                    return False
        return True
    
    async def _calculate_overall_confidence(self, coreferences: List[Dict], modality: str) -> float:
        """Calculate overall confidence for the coreference resolution."""
        if not coreferences:
            return 0.0
        
        total_confidence = sum(coref.get('confidence', 0.0) for coref in coreferences)
        avg_confidence = total_confidence / len(coreferences)
        
        # Adjust based on modality
        modality_factors = {
            'text': 1.0,
            'pdf': 1.0,
            'audio': 0.8,
            'image': 0.7,
            'video': 0.75
        }
        
        modality_factor = modality_factors.get(modality, 0.8)
        return avg_confidence * modality_factor