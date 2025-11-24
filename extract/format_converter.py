#!/usr/bin/env python3
"""
Data format converter to ensure compatibility between
generalized extractors and existing KG building code.
Supports multiple data formats: text, audio, images, PDFs, video.
"""

from typing import List, Dict, Any, Optional
import os
import mimetypes
from pathlib import Path
from loguru import logger

# Supported file extensions by type
SUPPORTED_FORMATS = {
    'text': ['.txt', '.md', '.json', '.xml', '.csv'],
    'audio': ['.wav', '.mp3', '.m4a', '.flac', '.aac', '.ogg'],
    'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'],
    'pdf': ['.pdf'],
    'video': ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
}

def detect_file_type(file_path: str) -> str:
    """
    Detect the type of file based on extension and MIME type.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File type: 'text', 'audio', 'image', 'pdf', 'video', or 'unknown'
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    # Check by extension first
    for file_type, extensions in SUPPORTED_FORMATS.items():
        if suffix in extensions:
            return file_type
    
    # Fallback to MIME type detection
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        if mime_type.startswith('text/'):
            return 'text'
        elif mime_type.startswith('audio/'):
            return 'audio'
        elif mime_type.startswith('image/'):
            return 'image'
        elif mime_type.startswith('video/'):
            return 'video'
        elif mime_type == 'application/pdf':
            return 'pdf'
    
    return 'unknown'

def create_document_from_file(file_path: str, file_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a standardized document structure from any file type.
    
    Args:
        file_path: Path to the file
        file_type: Pre-detected file type (optional)
        
    Returns:
        Standardized document dictionary
    """
    if file_type is None:
        file_type = detect_file_type(file_path)
    
    path = Path(file_path)
    
    # Base document structure
    doc = {
        'doc_id': str(path.absolute()),
        'file_path': str(path.absolute()),
        'file_name': path.name,
        'file_type': file_type,
        'file_size': path.stat().st_size if path.exists() else 0,
        'content': '',  # Will be populated by specific extractors
        'metadata': {
            'file_extension': path.suffix.lower(),
            'file_type': file_type,
            'processing_status': 'pending'
        },
        'extracted_entities': [],
        'extracted_relations': [],
        'modality_specific_data': {}  # For format-specific data
    }
    
    # Add modality-specific initial data
    if file_type == 'audio':
        doc['modality_specific_data'] = {
            'duration': None,
            'sample_rate': None,
            'channels': None,
            'transcript': ''
        }
    elif file_type == 'image':
        doc['modality_specific_data'] = {
            'dimensions': None,  # (width, height)
            'color_mode': None,
            'dpi': None,
            'objects_detected': []
        }
    elif file_type == 'pdf':
        doc['modality_specific_data'] = {
            'page_count': None,
            'author': None,
            'title': None,
            'text_by_page': {}
        }
    elif file_type == 'video':
        doc['modality_specific_data'] = {
            'duration': None,
            'resolution': None,
            'fps': None,
            'frame_count': None,
            'audio_tracks': []
        }
    
    return doc

def convert_to_legacy_format(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert documents with generalized extraction format to legacy format
    expected by build_triples and other downstream components.
    
    Enhanced to handle multi-modal data.
    
    Args:
        documents: Documents with 'extracted_entities' and 'extracted_relations' as lists
        
    Returns:
        Documents with converted format compatible with legacy code
    """
    converted_docs = []
    
    for doc in documents:
        converted_doc = doc.copy()
        file_type = doc.get('file_type', 'text')
        
        # Convert entities from list format to expected format
        entities = doc.get('extracted_entities', [])
        linked_entities = doc.get('linked_entities', [])
        
        # Use linked entities if available (they're deduplicated)
        entities_to_use = linked_entities if linked_entities else entities
        
        # Ensure entities is a list of dicts
        if entities_to_use and isinstance(entities_to_use, list):
            legacy_entities = []
            for entity in entities_to_use:
                if isinstance(entity, dict):
                    # Enhanced entity format with modality support
                    legacy_entity = {
                        'text': entity.get('name', entity.get('text', '')),
                        'type': entity.get('category', entity.get('type', 'ENTITY')).upper(),
                        'canonical_name': entity.get('name', entity.get('canonical_name', entity.get('text', ''))),
                        'confidence': entity.get('confidence', 0.7),
                        'attributes': entity.get('properties', entity.get('attributes', {})),
                        'aliases': entity.get('aliases', []),
                        'source_modality': file_type,
                        'position': entity.get('position', {}),  # For spatial/temporal positioning
                        'modality_specific': entity.get('modality_specific', {})
                    }
                    legacy_entities.append(legacy_entity)
            
            converted_doc['extracted_entities'] = legacy_entities
        else:
            converted_doc['extracted_entities'] = []
        
        # Convert relations from list format to expected format
        relations = doc.get('extracted_relations', [])
        
        if relations and isinstance(relations, list):
            legacy_relations = []
            for relation in relations:
                if isinstance(relation, dict):
                    # Enhanced relation format with cross-modal support
                    legacy_relation = {
                        'subject': relation.get('source', relation.get('subject', '')),
                        'object': relation.get('target', relation.get('object', '')),
                        'relation': relation.get('type', relation.get('relation', 'RELATED_TO')),
                        'confidence': relation.get('confidence', 0.6),
                        'evidence': relation.get('evidence', [''])[0] if relation.get('evidence') else '',
                        'subject_type': _infer_type_from_name(relation.get('source', ''), legacy_entities),
                        'object_type': _infer_type_from_name(relation.get('target', ''), legacy_entities),
                        'cross_modal': relation.get('cross_modal', False),
                        'modality_context': file_type
                    }
                    legacy_relations.append(legacy_relation)
            
            converted_doc['extracted_relations'] = legacy_relations
        else:
            converted_doc['extracted_relations'] = []
        
        # Ensure linked_entities is also in expected format
        if 'linked_entities' in converted_doc:
            if isinstance(converted_doc['linked_entities'], list):
                # Already in list format, just ensure proper structure
                pass
            elif isinstance(converted_doc['linked_entities'], dict):
                # Extract the actual list if wrapped in dict
                if 'linked_entities' in converted_doc['linked_entities']:
                    converted_doc['linked_entities'] = converted_doc['linked_entities']['linked_entities']
        
        converted_docs.append(converted_doc)
    
    logger.info(f"Converted {len(converted_docs)} documents to legacy format")
    return converted_docs

def _infer_type_from_name(entity_name: str, entities: List[Dict]) -> str:
    """
    Infer entity type from name by looking it up in entities list.
    
    Args:
        entity_name: Entity name to look up
        entities: List of entities
        
    Returns:
        Entity type or 'ENTITY' if not found
    """
    if not entity_name:
        return 'ENTITY'
    
    name_lower = entity_name.lower()
    
    for entity in entities:
        if entity.get('canonical_name', '').lower() == name_lower:
            return entity.get('type', 'ENTITY')
        if entity.get('text', '').lower() == name_lower:
            return entity.get('type', 'ENTITY')
        # Check aliases
        aliases = entity.get('aliases', [])
        if any(alias.lower() == name_lower for alias in aliases):
            return entity.get('type', 'ENTITY')
    
    return 'ENTITY'

def normalize_entity_types(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize entity types to standard categories expected by ontology.
    
    Enhanced with multi-modal entity types.
    
    Maps generalized categories to ontology classes:
    - person -> Person
    - organization -> Organization  
    - location -> Place
    - event -> Event
    - concept -> Concept
    - object -> Object
    - metric -> Metric
    - date -> Date
    - audio_entity -> AudioEntity
    - visual_entity -> VisualEntity
    - unknown -> Entity
    
    Args:
        documents: Documents with entities
        
    Returns:
        Documents with normalized entity types
    """
    type_mapping = {
        'person': 'PERSON',
        'organization': 'ORG',
        'location': 'PLACE',
        'event': 'EVENT',
        'concept': 'CONCEPT',
        'object': 'OBJECT',
        'metric': 'METRIC',
        'date': 'DATE',
        'audio_entity': 'AUDIO_ENTITY',
        'visual_entity': 'VISUAL_ENTITY',
        'unknown': 'ENTITY'
    }
    
    for doc in documents:
        file_type = doc.get('file_type', 'text')
        
        entities = doc.get('extracted_entities', [])
        for entity in entities:
            if isinstance(entity, dict):
                entity_type = entity.get('type', 'ENTITY').lower()
                normalized_type = type_mapping.get(entity_type, 'ENTITY')
                
                # Enhance type based on modality for unknown types
                if normalized_type == 'ENTITY':
                    if file_type == 'audio' and 'audio' in entity_type:
                        normalized_type = 'AUDIO_ENTITY'
                    elif file_type in ['image', 'video'] and any(x in entity_type for x in ['visual', 'image', 'video']):
                        normalized_type = 'VISUAL_ENTITY'
                
                entity['type'] = normalized_type
        
        # Also normalize in linked_entities
        linked = doc.get('linked_entities', [])
        if isinstance(linked, list):
            for entity in linked:
                if isinstance(entity, dict):
                    entity_type = entity.get('type', 'ENTITY').lower()
                    normalized_type = type_mapping.get(entity_type, 'ENTITY')
                    
                    # Enhance type based on modality
                    if normalized_type == 'ENTITY':
                        if file_type == 'audio' and 'audio' in entity_type:
                            normalized_type = 'AUDIO_ENTITY'
                        elif file_type in ['image', 'video'] and any(x in entity_type for x in ['visual', 'image', 'video']):
                            normalized_type = 'VISUAL_ENTITY'
                    
                    entity['type'] = normalized_type
    
    return documents

def validate_document_structure(doc: Dict[str, Any]) -> bool:
    """
    Validate that document has expected structure for KG building.
    Enhanced for multi-modal data validation.
    
    Args:
        doc: Document to validate
        
    Returns:
        True if valid, False otherwise
    """
    required_fields = ['doc_id', 'content', 'file_type']
    
    # Check required fields
    for field in required_fields:
        if field not in doc:
            logger.warning(f"Document missing required field: {field}")
            return False
    
    # Validate file type
    file_type = doc.get('file_type')
    if file_type not in ['text', 'audio', 'image', 'pdf', 'video']:
        logger.warning(f"Document {doc.get('doc_id')} has invalid file type: {file_type}")
        return False
    
    # Check entities format
    entities = doc.get('extracted_entities', [])
    if not isinstance(entities, list):
        logger.warning(f"Document {doc.get('doc_id')} has invalid entities format")
        return False
    
    # Check relations format
    relations = doc.get('extracted_relations', [])
    if not isinstance(relations, list):
        logger.warning(f"Document {doc.get('doc_id')} has invalid relations format")
        return False
    
    # Validate modality-specific structure
    modality_data = doc.get('modality_specific_data', {})
    if not isinstance(modality_data, dict):
        logger.warning(f"Document {doc.get('doc_id')} has invalid modality_specific_data format")
        return False
    
    return True

# Add this function to your existing format_converter.py
async def preprocess_multimodal_data(documents: List[Dict[str, Any]], groq_api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Preprocess multi-modal documents to convert them to text for LLM processing.
    
    Args:
        documents: List of document dictionaries
        groq_api_key: Groq API key for processing
        
    Returns:
        Preprocessed documents with text content
    """
    from extract.multimodal_processor import preprocess_document
    
    processed_docs = []
    
    for doc in documents:
        try:
            # Only preprocess if content is empty or needs processing
            if not doc.get('content') or doc.get('file_type') != 'text':
                processed_doc = await preprocess_document(doc, groq_api_key)
                processed_docs.append(processed_doc)
            else:
                processed_docs.append(doc)
                
        except Exception as e:
            logger.error(f"Error preprocessing document {doc.get('doc_id')}: {e}")
            processed_docs.append(doc)  # Keep original doc on error
    
    return processed_docs

# Update prepare_documents_for_kg to include preprocessing
async def prepare_documents_for_kg(documents: List[Dict[str, Any]], groq_api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Complete preparation of documents for KG building with multi-modal support.
    
    Args:
        documents: Raw documents from extraction
        groq_api_key: Groq API key for multi-modal processing
        
    Returns:
        Prepared documents ready for KG building
    """
    logger.info(f"Preparing {len(documents)} documents for KG building...")
    
    # Step 0: Preprocess multi-modal data
    if groq_api_key:
        documents = await preprocess_multimodal_data(documents, groq_api_key)
    
    # Rest of your existing code...
    # Step 1: Convert format
    converted = convert_to_legacy_format(documents)
    
    # Step 2: Normalize types
    normalized = normalize_entity_types(converted)
    
    # Step 3: Validate and filter
    valid_docs = []
    for doc in normalized:
        if validate_document_structure(doc):
            valid_docs.append(doc)
        else:
            logger.warning(f"Skipping invalid document: {doc.get('doc_id', 'unknown')}")
    
    logger.info(f"Prepared {len(valid_docs)} valid documents for KG building")
    
    # Log statistics
    total_entities = sum(len(doc.get('extracted_entities', [])) for doc in valid_docs)
    total_relations = sum(len(doc.get('extracted_relations', [])) for doc in valid_docs)
    
    logger.info(f"Total entities: {total_entities}, Total relations: {total_relations}")
    
    return valid_docs

def get_extraction_summary(documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Get summary statistics of extraction results.
    Enhanced for multi-modal data analysis.
    
    Args:
        documents: Extracted documents
        
    Returns:
        Summary statistics
    """
    total_docs = len(documents)
    total_entities = 0
    total_relations = 0
    entity_types = {}
    relation_types = {}
    modality_stats = {
        'text': {'count': 0, 'entities': 0, 'relations': 0},
        'audio': {'count': 0, 'entities': 0, 'relations': 0},
        'image': {'count': 0, 'entities': 0, 'relations': 0},
        'pdf': {'count': 0, 'entities': 0, 'relations': 0},
        'video': {'count': 0, 'entities': 0, 'relations': 0}
    }
    
    for doc in documents:
        file_type = doc.get('file_type', 'unknown')
        entities = doc.get('extracted_entities', [])
        relations = doc.get('extracted_relations', [])
        
        total_entities += len(entities)
        total_relations += len(relations)
        
        # Update modality statistics
        if file_type in modality_stats:
            modality_stats[file_type]['count'] += 1
            modality_stats[file_type]['entities'] += len(entities)
            modality_stats[file_type]['relations'] += len(relations)
        
        # Count entity types
        for entity in entities:
            if isinstance(entity, dict):
                etype = entity.get('type', 'UNKNOWN')
                entity_types[etype] = entity_types.get(etype, 0) + 1
        
        # Count relation types
        for relation in relations:
            if isinstance(relation, dict):
                rtype = relation.get('relation', relation.get('type', 'UNKNOWN'))
                relation_types[rtype] = relation_types.get(rtype, 0) + 1
    
    return {
        'total_documents': total_docs,
        'total_entities': total_entities,
        'total_relations': total_relations,
        'entities_per_doc': total_entities / max(total_docs, 1),
        'relations_per_doc': total_relations / max(total_docs, 1),
        'entity_type_distribution': entity_types,
        'relation_type_distribution': relation_types,
        'modality_statistics': modality_stats,
        'supported_formats': SUPPORTED_FORMATS
    }

def batch_process_files(file_paths: List[str]) -> List[Dict[str, Any]]:
    """
    Batch process multiple files and create standardized document structures.
    
    Args:
        file_paths: List of file paths to process
        
    Returns:
        List of standardized document structures
    """
    documents = []
    
    for file_path in file_paths:
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            continue
            
        file_type = detect_file_type(file_path)
        if file_type == 'unknown':
            logger.warning(f"Unsupported file type: {file_path}")
            continue
            
        doc = create_document_from_file(file_path, file_type)
        documents.append(doc)
        logger.debug(f"Created document structure for: {file_path} ({file_type})")
    
    logger.info(f"Created {len(documents)} document structures from {len(file_paths)} files")
    return documents