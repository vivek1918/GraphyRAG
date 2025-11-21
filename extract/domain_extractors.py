#!/usr/bin/env python3
"""
Domain-specific extraction using structured prompts and LLMs.
Extracts entities according to domain schemas.
"""

import os
import json
import yaml
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use system env vars only

from extract.domain_schemas import DomainSchemas, DomainSchema, EntitySchema


class DomainExtractor:
    """Extract domain-specific structured information from documents."""
    
    def __init__(self, mode: str = "groq", config_path: Optional[Path] = None):
        """
        Initialize domain extractor.
        
        Args:
            mode: Extraction mode ('groq', 'local', 'hybrid')
            config_path: Path to settings.yaml
        """
        self.mode = mode
        self.config = self._load_config(config_path)
        self._setup_llm()
        
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
                    logger.info("Initialized Groq LLM client for domain extraction")
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
            
    async def extract(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract domain-specific entities from document.
        
        Args:
            document: Document dict with 'content' and 'domain_classification'
            
        Returns:
            Document with added 'domain_entities' field
        """
        domain_classification = document.get('domain_classification', {})
        domain = domain_classification.get('domain', 'general')
        
        schema = DomainSchemas.get_schema(domain)
        
        logger.info(f"Extracting {domain} entities from document")
        
        if self.llm_client and domain != 'general':
            entities = await self._extract_with_llm(document, schema)
        else:
            entities = await self._extract_rule_based(document, schema)
            
        document['domain_entities'] = {
            'domain': domain,
            'schema_version': '1.0',
            'entities': entities
        }
        
        logger.info(f"Extracted {len(entities)} domain-specific entities")
        return document
        
    async def _extract_with_llm(self, document: Dict[str, Any], schema: DomainSchema) -> List[Dict[str, Any]]:
        """Extract entities using LLM with structured prompts."""
        content = document.get('content', '')
        
        # Truncate if too long (leave room for response)
        max_chars = 6000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n...[truncated for API limits]..."
            logger.info(f"Truncated content to {max_chars} chars for LLM extraction")
            
        # Build extraction prompt
        prompt = self._build_extraction_prompt(schema, content)
        
        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt(schema)},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=3000  # Reduced to avoid truncation
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON response with multiple strategies
            entities = self._parse_llm_response(result_text)
            
            # Validate and enrich entities
            validated_entities = []
            for entity in entities:
                if self._validate_entity(entity, schema):
                    validated_entities.append(entity)
                else:
                    logger.warning(f"Invalid entity skipped: {entity.get('type', 'unknown')}")
            
            logger.info(f"LLM extracted {len(validated_entities)} valid entities out of {len(entities)} total")
            return validated_entities
            
        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON: {e}")
            logger.debug(f"Response preview: {result_text[:500] if 'result_text' in locals() else 'N/A'}...")
            return await self._extract_rule_based(document, schema)
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}, falling back to rule-based")
            return await self._extract_rule_based(document, schema)
            
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
            
    def _get_system_prompt(self, schema: DomainSchema) -> str:
        """Generate system prompt for LLM."""
        return f"""You are an expert information extraction system specializing in {schema.domain} documents.

Your task is to extract structured entities from documents according to a provided schema.
- Extract ALL relevant entities mentioned in the document
- Be thorough and accurate
- Use exact text from document when possible
- Include confidence scores (0.0-1.0)
- Return ONLY valid JSON in the specified format
- If a field is not present, omit it or set to null
"""

    def _build_extraction_prompt(self, schema: DomainSchema, content: str) -> str:
        """Build extraction prompt with schema definition."""
        # Limit number of entity types to avoid overwhelming the model
        entity_schemas = schema.entities[:5]  # Top 5 most important
        
        entity_defs = []
        for entity_schema in entity_schemas:
            # Only include required fields to keep prompt concise
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
        
        prompt = f"""Extract key entities from this {schema.domain} document. Focus on the most important information.

ENTITY TYPES:
{schema_text}

DOCUMENT:
{content}

Return ONLY valid JSON (no markdown, no explanations):
{{
  "entities": [
    {{
      "type": "<entity_type>",
      "id": "<unique_id>",
      "fields": {{"field_name": "value"}},
      "confidence": 0.95
    }}
  ]
}}

Extract 3-10 most important entities."""
        
        return prompt
        
    async def _extract_rule_based(self, document: Dict[str, Any], schema: DomainSchema) -> List[Dict[str, Any]]:
        """Fallback rule-based extraction for when LLM unavailable."""
        logger.info("Using rule-based extraction (LLM unavailable)")
        
        content = document.get('content', '')
        entities = []
        
        # Simple pattern-based extraction
        # This is a basic fallback - in production you'd want more sophisticated rules
        
        if schema.domain == 'resume':
            entities.extend(self._extract_resume_entities(content))
        elif schema.domain == 'research_paper':
            entities.extend(self._extract_research_entities(content))
        # Add other domains as needed
        
        return entities
        
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
            
        # Extract author names from common patterns
        # "Author A, Author B, and Author C"
        # This is very simplified
        
        return entities
        
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
