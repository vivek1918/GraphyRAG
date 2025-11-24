#!/usr/bin/env python3
"""
Multi-format domain-specific extraction using structured prompts and LLMs.
Extracts entities from text, audio, images, PDFs, and video according to domain schemas.
"""

import os
import json
import yaml
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from loguru import logger

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use system env vars only

from extract.domain_schemas import DomainSchemas, DomainSchema, EntitySchema


class MultiModalExtractor:
    """Base class for multi-modal data extraction."""
    
    def __init__(self):
        self.supported_modalities = ['text', 'audio', 'image', 'pdf', 'video']
    
    def extract_from_text(self, content: str, domain: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract entities from text content."""
        raise NotImplementedError
        
    def extract_from_audio(self, audio_path: str, domain: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract entities from audio content."""
        raise NotImplementedError
        
    def extract_from_image(self, image_path: str, domain: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract entities from image content."""
        raise NotImplementedError
        
    def extract_from_pdf(self, pdf_path: str, domain: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract entities from PDF content."""
        raise NotImplementedError
        
    def extract_from_video(self, video_path: str, domain: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract entities from video content."""
        raise NotImplementedError


class DomainExtractor(MultiModalExtractor):
    """Extract domain-specific structured information from multi-format documents."""
    
    def __init__(self, mode: str = "groq", config_path: Optional[Path] = None):
        """
        Initialize domain extractor.
        
        Args:
            mode: Extraction mode ('groq', 'local', 'hybrid')
            config_path: Path to settings.yaml
        """
        super().__init__()
        self.mode = mode
        self.config = self._load_config(config_path)
        self._setup_llm()
        self._setup_modality_extractors()
        
    def _load_config(self, config_path: Optional[Path]) -> Dict[str, Any]:
        """Load configuration."""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "conf" / "settings.yaml"
            
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)
        return {}
        
    def _setup_llm(self):
        """Setup LLM client."""
        system_mode = self.config.get('system', {}).get('mode', 'local')
        
        if system_mode == 'groq' or self.mode == 'groq':
            try:
                from groq import Groq
                api_key = os.getenv('GROQ_API_KEY')
                if api_key:
                    self.llm_client = Groq(api_key=api_key)
                    self.llm_model = self.config.get('models', {}).get('llm', {}).get('groq', 'openai/gpt-oss-120b')
                    logger.info(f"Initialized Groq LLM ({self.llm_model}) for domain extraction")
                else:
                    logger.warning("GROQ_API_KEY not found, domain extraction will be limited")
                    self.llm_client = None
            except Exception as e:
                logger.error(f"Could not initialize Groq: {e}")
                self.llm_client = None
        else:
            logger.info("LLM not configured, using rule-based extraction")
            self.llm_client = None

    def _setup_modality_extractors(self):
        """Setup modality-specific extractors."""
        self.modality_extractors = {
            'text': self._extract_text_entities,
            'audio': self._extract_audio_entities,
            'image': self._extract_image_entities,
            'pdf': self._extract_pdf_entities,
            'video': self._extract_video_entities
        }
            
    async def extract(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract domain-specific entities from multi-format document.
        
        Args:
            document: Document dict with 'content', 'file_type', and 'domain_classification'
            
        Returns:
            Document with added 'domain_entities' field
        """
        domain_classification = document.get('domain_classification', {})
        domain = domain_classification.get('domain', 'general')
        file_type = document.get('file_type', 'text')
        
        schema = DomainSchemas.get_schema(domain)
        
        logger.info(f"Extracting {domain} entities from {file_type} document")
        
        # Extract entities based on modality
        if file_type in self.modality_extractors:
            entities = await self.modality_extractors[file_type](document, schema)
        else:
            logger.warning(f"Unsupported file type: {file_type}, falling back to text extraction")
            entities = await self._extract_text_entities(document, schema)
            
        document['domain_entities'] = {
            'domain': domain,
            'schema_version': '1.0',
            'file_type': file_type,
            'entities': entities,
            'extraction_method': 'llm' if self.llm_client else 'rule_based'
        }
        
        logger.info(f"Extracted {len(entities)} domain-specific entities from {file_type}")
        return document

    async def _extract_text_entities(self, document: Dict[str, Any], schema: DomainSchema) -> List[Dict[str, Any]]:
        """Extract entities from text content."""
        content = document.get('content', '')
        
        if self.llm_client and schema.domain != 'general':
            return await self._extract_with_llm(document, schema, 'text')
        else:
            return await self._extract_rule_based(document, schema, 'text')

    async def _extract_audio_entities(self, document: Dict[str, Any], schema: DomainSchema) -> List[Dict[str, Any]]:
        """Extract entities from audio content."""
        file_path = document.get('file_path', '')
        modality_data = document.get('modality_specific_data', {})
        transcript = modality_data.get('transcript', '')
        
        entities = []
        
        # If we have a transcript, use text extraction
        if transcript:
            temp_doc = document.copy()
            temp_doc['content'] = transcript
            entities.extend(await self._extract_text_entities(temp_doc, schema))
        
        # Add audio-specific entities
        if self.llm_client:
            audio_entities = await self._extract_audio_specific_entities(document, schema)
            entities.extend(audio_entities)
        else:
            # Rule-based audio entity extraction
            audio_entities = self._extract_audio_entities_rule_based(document, schema)
            entities.extend(audio_entities)
        
        return entities

    async def _extract_image_entities(self, document: Dict[str, Any], schema: DomainSchema) -> List[Dict[str, Any]]:
        """Extract entities from image content."""
        file_path = document.get('file_path', '')
        modality_data = document.get('modality_specific_data', {})
        
        entities = []
        
        # Use LLM for image analysis if available
        if self.llm_client:
            image_entities = await self._extract_image_specific_entities(document, schema)
            entities.extend(image_entities)
        else:
            # Rule-based image entity extraction
            image_entities = self._extract_image_entities_rule_based(document, schema)
            entities.extend(image_entities)
        
        return entities

    async def _extract_pdf_entities(self, document: Dict[str, Any], schema: DomainSchema) -> List[Dict[str, Any]]:
        """Extract entities from PDF content."""
        content = document.get('content', '')
        modality_data = document.get('modality_specific_data', {})
        text_by_page = modality_data.get('text_by_page', {})
        
        # Combine text from all pages
        full_text = content
        if text_by_page and not content:
            full_text = "\n".join(text_by_page.values())
        
        temp_doc = document.copy()
        temp_doc['content'] = full_text
        
        return await self._extract_text_entities(temp_doc, schema)

    async def _extract_video_entities(self, document: Dict[str, Any], schema: DomainSchema) -> List[Dict[str, Any]]:
        """Extract entities from video content."""
        file_path = document.get('file_path', '')
        modality_data = document.get('modality_specific_data', {})
        
        entities = []
        
        # Extract from audio transcript if available
        transcript = modality_data.get('transcript', '')
        if transcript:
            temp_doc = document.copy()
            temp_doc['content'] = transcript
            entities.extend(await self._extract_text_entities(temp_doc, schema))
        
        # Add video-specific entities
        if self.llm_client:
            video_entities = await self._extract_video_specific_entities(document, schema)
            entities.extend(video_entities)
        else:
            # Rule-based video entity extraction
            video_entities = self._extract_video_entities_rule_based(document, schema)
            entities.extend(video_entities)
        
        return entities
        
    async def _extract_with_llm(self, document: Dict[str, Any], schema: DomainSchema, modality: str) -> List[Dict[str, Any]]:
        """Extract entities using LLM with modality-aware structured prompts."""
        content = self._prepare_content_for_llm(document, modality)
        
        if not content:
            logger.warning(f"No content available for {modality} extraction")
            return []
            
        # Build modality-aware extraction prompt
        prompt = self._build_modality_extraction_prompt(schema, content, modality)
        
        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": self._get_modality_system_prompt(schema, modality)},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=3000
            )
            
            result_text = response.choices[0].message.content.strip()
            entities = self._parse_llm_response(result_text)
            
            # Add modality context to entities
            for entity in entities:
                entity['modality'] = modality
                entity['source_file_type'] = document.get('file_type', 'unknown')
            
            # Validate and enrich entities
            validated_entities = []
            for entity in entities:
                if self._validate_entity(entity, schema):
                    validated_entities.append(entity)
                else:
                    logger.warning(f"Invalid entity skipped: {entity.get('type', 'unknown')}")
            
            logger.info(f"LLM extracted {len(validated_entities)} valid entities from {modality}")
            return validated_entities
            
        except Exception as e:
            logger.error(f"LLM extraction failed for {modality}: {e}, falling back to rule-based")
            return await self._extract_rule_based(document, schema, modality)

    def _prepare_content_for_llm(self, document: Dict[str, Any], modality: str) -> str:
        """Prepare content for LLM based on modality."""
        if modality == 'text':
            content = document.get('content', '')
            # Truncate if too long
            max_chars = 6000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n...[truncated for API limits]..."
            return content
            
        elif modality == 'audio':
            modality_data = document.get('modality_specific_data', {})
            transcript = modality_data.get('transcript', '')
            audio_metadata = {
                'duration': modality_data.get('duration'),
                'sample_rate': modality_data.get('sample_rate'),
                'channels': modality_data.get('channels')
            }
            return f"Audio Transcript:\n{transcript}\n\nAudio Metadata: {audio_metadata}"
            
        elif modality == 'image':
            modality_data = document.get('modality_specific_data', {})
            image_metadata = {
                'dimensions': modality_data.get('dimensions'),
                'color_mode': modality_data.get('color_mode'),
                'dpi': modality_data.get('dpi'),
                'objects_detected': modality_data.get('objects_detected', [])
            }
            return f"Image Analysis Data:\nDetected Objects: {image_metadata['objects_detected']}\nMetadata: {image_metadata}"
            
        elif modality == 'video':
            modality_data = document.get('modality_specific_data', {})
            video_metadata = {
                'duration': modality_data.get('duration'),
                'resolution': modality_data.get('resolution'),
                'fps': modality_data.get('fps'),
                'frame_count': modality_data.get('frame_count')
            }
            transcript = modality_data.get('transcript', '')
            return f"Video Analysis:\nTranscript: {transcript}\nMetadata: {video_metadata}"
            
        return document.get('content', '')

    def _get_modality_system_prompt(self, schema: DomainSchema, modality: str) -> str:
        """Generate modality-aware system prompt for LLM."""
        modality_descriptions = {
            'text': 'text documents',
            'audio': 'audio recordings and transcripts',
            'image': 'images and visual content',
            'pdf': 'PDF documents',
            'video': 'video content with audio and visual elements'
        }
        
        return f"""You are an expert multi-modal information extraction system specializing in {schema.domain} {modality_descriptions.get(modality, 'documents')}.

Your task is to extract structured entities from {modality} content according to a provided schema.
- Extract ALL relevant entities mentioned in the content
- Be thorough and accurate
- Use exact information from the content when possible
- Include confidence scores (0.0-1.0)
- Return ONLY valid JSON in the specified format
- If a field is not present, omit it or set to null
- Consider the unique aspects of {modality} content when extracting entities
"""

    def _build_modality_extraction_prompt(self, schema: DomainSchema, content: str, modality: str) -> str:
        """Build modality-aware extraction prompt with schema definition."""
        # Get relevant entity schemas for this modality
        entity_schemas = self._get_relevant_entity_schemas(schema, modality)
        
        entity_defs = []
        for entity_schema in entity_schemas:
            fields_desc = []
            for field in entity_schema.fields:
                if field.required:
                    fields_desc.append(f"  - {field.name} ({field.type}, REQUIRED): {field.description}")
            
            # Add a few optional fields
            optional_count = 0
            for field in entity_schema.fields:
                if not field.required and optional_count < 3:
                    fields_desc.append(f"  - {field.name} ({field.type}, optional): {field.description}")
                    optional_count += 1
                
            entity_def = f"""
{entity_schema.entity_type}:
{chr(10).join(fields_desc) if fields_desc else '  (no fields defined)'}
"""
            entity_defs.append(entity_def)
            
        schema_text = "\n".join(entity_defs)
        
        prompt = f"""Extract key entities from this {schema.domain} {modality} content. Focus on the most important information.

ENTITY TYPES:
{schema_text}

CONTENT:
{content}

Return ONLY valid JSON (no markdown, no explanations):
{{
  "entities": [
    {{
      "type": "<entity_type>",
      "id": "<unique_id>",
      "fields": {{"field_name": "value"}},
      "confidence": 0.95,
      "modality": "{modality}"
    }}
  ]
}}

Extract 3-15 most important entities relevant to {modality} content."""
        
        return prompt

    def _get_relevant_entity_schemas(self, schema: DomainSchema, modality: str) -> List[EntitySchema]:
        """Get entity schemas relevant to the specific modality."""
        # Default: return all schemas, but can be customized per modality
        return schema.entities[:5]  # Top 5 most important
        
    async def _extract_audio_specific_entities(self, document: Dict[str, Any], schema: DomainSchema) -> List[Dict[str, Any]]:
        """Extract audio-specific entities using LLM."""
        # This would use audio-specific analysis
        # For now, return empty list - implement based on your audio processing capabilities
        return []

    async def _extract_image_specific_entities(self, document: Dict[str, Any], schema: DomainSchema) -> List[Dict[str, Any]]:
        """Extract image-specific entities using LLM."""
        # This would use image analysis and object detection
        # For now, return empty list - implement based on your image processing capabilities
        return []

    async def _extract_video_specific_entities(self, document: Dict[str, Any], schema: DomainSchema) -> List[Dict[str, Any]]:
        """Extract video-specific entities using LLM."""
        # This would use video analysis, scene detection, etc.
        # For now, return empty list - implement based on your video processing capabilities
        return []

    async def _extract_rule_based(self, document: Dict[str, Any], schema: DomainSchema, modality: str) -> List[Dict[str, Any]]:
        """Fallback rule-based extraction for when LLM unavailable."""
        logger.info(f"Using rule-based extraction for {modality} (LLM unavailable)")
        
        if modality == 'text':
            return self._extract_text_entities_rule_based(document, schema)
        elif modality == 'audio':
            return self._extract_audio_entities_rule_based(document, schema)
        elif modality == 'image':
            return self._extract_image_entities_rule_based(document, schema)
        elif modality == 'pdf':
            return self._extract_text_entities_rule_based(document, schema)  # PDFs are processed as text
        elif modality == 'video':
            return self._extract_video_entities_rule_based(document, schema)
        else:
            return []

    def _extract_text_entities_rule_based(self, document: Dict[str, Any], schema: DomainSchema) -> List[Dict[str, Any]]:
        """Rule-based text entity extraction."""
        content = document.get('content', '')
        domain = schema.domain
        
        # Generic rule-based extraction that works for any domain
        entities = self._extract_generic_entities(content, domain)
        
        # Domain-specific rule-based extraction
        if domain == 'resume':
            entities.extend(self._extract_resume_entities(content))
        elif domain == 'research_paper':
            entities.extend(self._extract_research_entities(content))
        # Add other domain-specific extractors as needed
        
        return entities

    def _extract_generic_entities(self, content: str, domain: str) -> List[Dict[str, Any]]:
        """Extract generic entities that apply to any domain."""
        import re
        entities = []
        
        # Extract emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, content)
        for idx, email in enumerate(emails[:3]):  # Limit to 3 emails
            entities.append({
                'type': 'Contact',
                'id': f'contact_{idx}',
                'fields': {'email': email, 'type': 'email'},
                'confidence': 0.9,
                'source_text': email
            })
        
        # Extract URLs
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, content)
        for idx, url in enumerate(urls[:3]):
            entities.append({
                'type': 'WebResource',
                'id': f'web_{idx}',
                'fields': {'url': url},
                'confidence': 0.9,
                'source_text': url
            })
        
        # Extract dates
        date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b'
        dates = re.findall(date_pattern, content)
        for idx, date in enumerate(dates[:5]):
            entities.append({
                'type': 'Date',
                'id': f'date_{idx}',
                'fields': {'value': date},
                'confidence': 0.8,
                'source_text': date
            })
        
        return entities

    def _extract_audio_entities_rule_based(self, document: Dict[str, Any], schema: DomainSchema) -> List[Dict[str, Any]]:
        """Rule-based audio entity extraction."""
        modality_data = document.get('modality_specific_data', {})
        entities = []
        
        # Extract audio-specific features
        duration = modality_data.get('duration')
        if duration:
            entities.append({
                'type': 'AudioFeature',
                'id': 'audio_duration',
                'fields': {'duration_seconds': duration, 'feature_type': 'duration'},
                'confidence': 0.9
            })
        
        sample_rate = modality_data.get('sample_rate')
        if sample_rate:
            entities.append({
                'type': 'AudioFeature',
                'id': 'audio_sample_rate',
                'fields': {'sample_rate_hz': sample_rate, 'feature_type': 'sample_rate'},
                'confidence': 0.9
            })
        
        return entities

    def _extract_image_entities_rule_based(self, document: Dict[str, Any], schema: DomainSchema) -> List[Dict[str, Any]]:
        """Rule-based image entity extraction."""
        modality_data = document.get('modality_specific_data', {})
        entities = []
        
        # Extract image-specific features
        dimensions = modality_data.get('dimensions')
        if dimensions:
            entities.append({
                'type': 'ImageFeature',
                'id': 'image_dimensions',
                'fields': {'width': dimensions[0], 'height': dimensions[1], 'feature_type': 'dimensions'},
                'confidence': 0.9
            })
        
        objects = modality_data.get('objects_detected', [])
        for idx, obj in enumerate(objects[:10]):  # Limit to 10 objects
            entities.append({
                'type': 'VisualObject',
                'id': f'object_{idx}',
                'fields': {'object_name': obj, 'detection_confidence': 0.7},
                'confidence': 0.7,
                'source_text': obj
            })
        
        return entities

    def _extract_video_entities_rule_based(self, document: Dict[str, Any], schema: DomainSchema) -> List[Dict[str, Any]]:
        """Rule-based video entity extraction."""
        modality_data = document.get('modality_specific_data', {})
        entities = []
        
        # Extract video-specific features
        duration = modality_data.get('duration')
        if duration:
            entities.append({
                'type': 'VideoFeature',
                'id': 'video_duration',
                'fields': {'duration_seconds': duration, 'feature_type': 'duration'},
                'confidence': 0.9
            })
        
        resolution = modality_data.get('resolution')
        if resolution:
            entities.append({
                'type': 'VideoFeature',
                'id': 'video_resolution',
                'fields': {'resolution': resolution, 'feature_type': 'resolution'},
                'confidence': 0.9
            })
        
        return entities

    # Keep the existing helper methods from your original code
    def _extract_resume_entities(self, content: str) -> List[Dict[str, Any]]:
        """Rule-based resume extraction."""
        import re
        entities = []
        
        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, content)
        if emails:
            entities.append({
                'type': 'Person',
                'id': 'person_1',
                'fields': {'email': emails[0]},
                'confidence': 0.9,
                'source_text': emails[0]
            })
            
        # Extract phone
        phone_pattern = r'[\+\(]?[1-9][0-9 .\-\(\)]{8,}[0-9]'
        phones = re.findall(phone_pattern, content)
        if phones and entities:
            entities[0]['fields']['phone'] = phones[0]
            
        # Extract skills (simple keyword matching)
        skill_keywords = [
            'Python', 'Java', 'JavaScript', 'C++', 'SQL', 'React', 'Node.js',
            'AWS', 'Docker', 'Kubernetes', 'Machine Learning', 'Data Science',
            'Git', 'Linux', 'REST API', 'MongoDB', 'PostgreSQL'
        ]
        
        for idx, skill in enumerate(skill_keywords):
            if skill.lower() in content.lower():
                entities.append({
                    'type': 'Skill',
                    'id': f'skill_{idx}',
                    'fields': {'name': skill, 'category': 'technical'},
                    'confidence': 0.8,
                    'source_text': skill
                })
                
        return entities
        
    def _extract_research_entities(self, content: str) -> List[Dict[str, Any]]:
        """Rule-based research paper extraction."""
        import re
        entities = []
        
        # Extract DOI
        doi_pattern = r'\b10\.\d{4,}/[^\s]+'
        dois = re.findall(doi_pattern, content)
        if dois:
            entities.append({
                'type': 'Paper',
                'id': 'paper_1',
                'fields': {'doi': dois[0]},
                'confidence': 0.95,
                'source_text': dois[0]
            })
            
        return entities

    def _parse_llm_response(self, result_text: str) -> List[Dict[str, Any]]:
        """Parse LLM response with multiple fallback strategies."""
        # Strategy 1: Remove markdown code blocks
        if '```json' in result_text:
            result_text = result_text.split('```json')[1].split('```')[0].strip()
        elif '```' in result_text:
            result_text = result_text.split('```')[1].split('```')[0].strip()
        
        # Strategy 2: Try to parse as-is
        try:
            result = json.loads(result_text)
            return result.get('entities', [])
        except json.JSONDecodeError:
            pass
        
        # Strategy 3: Find JSON object boundaries
        try:
            # Find first { and last }
            start = result_text.find('{')
            end = result_text.rfind('}')
            if start != -1 and end != -1:
                json_text = result_text[start:end+1]
                result = json.loads(json_text)
                return result.get('entities', [])
        except json.JSONDecodeError:
            pass
        
        # Strategy 4: Try to fix common issues
        try:
            # Remove trailing commas
            fixed_text = result_text.replace(',]', ']').replace(',}', '}')
            result = json.loads(fixed_text)
            return result.get('entities', [])
        except json.JSONDecodeError:
            pass
        
        logger.warning("Could not parse LLM response as JSON, returning empty list")
        return []
        
    def _validate_entity(self, entity: Dict[str, Any], schema: DomainSchema) -> bool:
        """Validate extracted entity against schema."""
        # Check required fields
        entity_type = entity.get('type')
        if not entity_type:
            return False
            
        # Find schema for this entity type
        entity_schema = None
        for es in schema.entities:
            if es.entity_type == entity_type:
                entity_schema = es
                break
                
        if not entity_schema:
            logger.warning(f"Unknown entity type: {entity_type}")
            return False
            
        # Check required fields
        fields = entity.get('fields', {})
        for field in entity_schema.fields:
            if field.required and field.name not in fields:
                logger.warning(f"Missing required field {field.name} in {entity_type}")
                return False
                
        return True


async def extract_domain_entities(document: Dict[str, Any], mode: str = "groq") -> Dict[str, Any]:
    """
    Convenience async function for domain extraction.
    
    Args:
        document: Document dict with classification
        mode: Extraction mode
        
    Returns:
        Document with domain entities
    """
    extractor = DomainExtractor(mode=mode)
    return await extractor.extract(document)