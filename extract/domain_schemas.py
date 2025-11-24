#!/usr/bin/env python3
"""
Multi-format domain-specific extraction schemas.
Defines structured extraction templates for each document domain and modality.
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum


class ModalityType(Enum):
    """Supported data modalities."""
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    PDF = "pdf"
    VIDEO = "video"
    MULTIMODAL = "multimodal"


@dataclass
class ExtractionField:
    """Definition of a field to extract."""
    name: str
    type: str  # 'string', 'list', 'object', 'date', 'number', 'boolean', 'timestamp'
    description: str
    required: bool = False
    patterns: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    modality_specific: bool = False
    supported_modalities: List[ModalityType] = field(default_factory=lambda: [ModalityType.TEXT])


@dataclass
class EntitySchema:
    """Schema for a domain-specific entity type."""
    entity_type: str
    description: str
    fields: List[ExtractionField]
    relations: List[str] = field(default_factory=list)
    modality_specific: bool = False
    supported_modalities: List[ModalityType] = field(default_factory=lambda: [ModalityType.TEXT])
    cross_modal: bool = False  # Whether this entity can appear across multiple modalities


@dataclass
class DomainSchema:
    """Complete extraction schema for a document domain."""
    domain: str
    description: str
    entities: List[EntitySchema]
    key_sections: List[str] = field(default_factory=list)
    supported_modalities: List[ModalityType] = field(default_factory=lambda: [ModalityType.TEXT])
    domain_keywords: List[str] = field(default_factory=list)


class DomainSchemas:
    """Registry of extraction schemas for different document domains and modalities."""
    
    @staticmethod
    def get_general_schema() -> DomainSchema:
        """General schema for any document type with multi-modal support."""
        return DomainSchema(
            domain='general',
            description='General document with no specific domain - supports all modalities',
            key_sections=['main_content'],
            supported_modalities=[modality for modality in ModalityType],
            domain_keywords=[],
            entities=[
                # Core entity types that work across all modalities
                EntitySchema(
                    entity_type='Entity',
                    description='Generic named entity',
                    fields=[
                        ExtractionField('name', 'string', 'Entity name', required=True),
                        ExtractionField('type', 'string', 'Entity type'),
                        ExtractionField('description', 'string', 'Description'),
                        ExtractionField('confidence', 'number', 'Extraction confidence score'),
                    ],
                    relations=['RELATES_TO', 'MENTIONED_IN'],
                    cross_modal=True,
                    supported_modalities=[modality for modality in ModalityType]
                ),
                EntitySchema(
                    entity_type='Person',
                    description='Person or individual',
                    fields=[
                        ExtractionField('name', 'string', 'Full name', required=True),
                        ExtractionField('role', 'string', 'Role or title'),
                        ExtractionField('organization', 'string', 'Associated organization'),
                        ExtractionField('contact_info', 'object', 'Contact information'),
                    ],
                    relations=['WORKS_FOR', 'CONTACTED_VIA', 'APPEARS_IN'],
                    cross_modal=True,
                    supported_modalities=[modality for modality in ModalityType]
                ),
                EntitySchema(
                    entity_type='Organization',
                    description='Company, institution, or group',
                    fields=[
                        ExtractionField('name', 'string', 'Organization name', required=True),
                        ExtractionField('type', 'string', 'Organization type'),
                        ExtractionField('industry', 'string', 'Industry or sector'),
                        ExtractionField('location', 'string', 'Location'),
                    ],
                    relations=['LOCATED_IN', 'OPERATES_IN', 'EMPLOYS'],
                    cross_modal=True,
                    supported_modalities=[modality for modality in ModalityType]
                ),
                EntitySchema(
                    entity_type='Location',
                    description='Geographical location',
                    fields=[
                        ExtractionField('name', 'string', 'Location name', required=True),
                        ExtractionField('type', 'string', 'Location type (city, country, etc.)'),
                        ExtractionField('coordinates', 'string', 'Geographic coordinates'),
                    ],
                    relations=['LOCATED_IN', 'NEAR'],
                    cross_modal=True,
                    supported_modalities=[modality for modality in ModalityType]
                ),
                
                # Modality-specific entity types
                EntitySchema(
                    entity_type='AudioEntity',
                    description='Audio-specific entities and features',
                    fields=[
                        ExtractionField('name', 'string', 'Entity name', required=True),
                        ExtractionField('type', 'string', 'Audio entity type (speaker, sound, music, etc.)'),
                        ExtractionField('timestamp', 'timestamp', 'When it occurs in audio'),
                        ExtractionField('duration', 'number', 'Duration in seconds'),
                        ExtractionField('confidence', 'number', 'Detection confidence'),
                    ],
                    relations=['OCCURS_AT', 'FOLLOWS', 'PRECEDES'],
                    modality_specific=True,
                    supported_modalities=[ModalityType.AUDIO, ModalityType.VIDEO]
                ),
                EntitySchema(
                    entity_type='VisualObject',
                    description='Objects detected in visual content',
                    fields=[
                        ExtractionField('name', 'string', 'Object name', required=True),
                        ExtractionField('type', 'string', 'Object category'),
                        ExtractionField('position', 'object', 'Position in image/video'),
                        ExtractionField('confidence', 'number', 'Detection confidence'),
                        ExtractionField('attributes', 'object', 'Visual attributes'),
                    ],
                    relations=['APPEARS_IN', 'LOCATED_AT', 'RELATED_TO'],
                    modality_specific=True,
                    supported_modalities=[ModalityType.IMAGE, ModalityType.VIDEO]
                ),
                EntitySchema(
                    entity_type='TextSegment',
                    description='Text segments from any modality',
                    fields=[
                        ExtractionField('content', 'string', 'Text content', required=True),
                        ExtractionField('source', 'string', 'Source modality'),
                        ExtractionField('position', 'object', 'Position information'),
                        ExtractionField('language', 'string', 'Language of text'),
                    ],
                    relations=['CONTAINS_ENTITY', 'PART_OF'],
                    cross_modal=True,
                    supported_modalities=[modality for modality in ModalityType]
                ),
                
                # Temporal entities
                EntitySchema(
                    entity_type='Event',
                    description='Temporal event or occurrence',
                    fields=[
                        ExtractionField('name', 'string', 'Event name', required=True),
                        ExtractionField('type', 'string', 'Event type'),
                        ExtractionField('start_time', 'timestamp', 'Start time'),
                        ExtractionField('end_time', 'timestamp', 'End time'),
                        ExtractionField('participants', 'list', 'Event participants'),
                    ],
                    relations=['HAS_PARTICIPANT', 'OCCURS_AT', 'PRECEDES'],
                    cross_modal=True,
                    supported_modalities=[modality for modality in ModalityType]
                ),
                
                # Document structure entities
                EntitySchema(
                    entity_type='DocumentSection',
                    description='Document section or segment',
                    fields=[
                        ExtractionField('title', 'string', 'Section title'),
                        ExtractionField('content', 'string', 'Section content'),
                        ExtractionField('type', 'string', 'Section type'),
                        ExtractionField('page_number', 'number', 'Page number if applicable'),
                    ],
                    relations=['CONTAINS', 'FOLLOWS', 'PRECEDES'],
                    cross_modal=True,
                    supported_modalities=[ModalityType.TEXT, ModalityType.PDF]
                ),
            ]
        )
    
    @staticmethod
    def get_resume_schema() -> DomainSchema:
        """Schema for resume/CV documents with multi-modal support."""
        base_schema = DomainSchemas.get_general_schema()
        
        resume_entities = [
            EntitySchema(
                entity_type='Person',
                description='The candidate/resume owner',
                fields=[
                    ExtractionField('name', 'string', 'Full name', required=True),
                    ExtractionField('email', 'string', 'Email address'),
                    ExtractionField('phone', 'string', 'Phone number'),
                    ExtractionField('location', 'string', 'City/State/Country'),
                    ExtractionField('linkedin', 'string', 'LinkedIn profile URL'),
                    ExtractionField('github', 'string', 'GitHub profile URL'),
                    ExtractionField('website', 'string', 'Personal website'),
                ],
                relations=['HAS_SKILL', 'WORKED_AT', 'STUDIED_AT', 'HAS_CERTIFICATION'],
                cross_modal=True,
                supported_modalities=[modality for modality in ModalityType]
            ),
            EntitySchema(
                entity_type='Skill',
                description='Technical or soft skill',
                fields=[
                    ExtractionField('name', 'string', 'Skill name', required=True),
                    ExtractionField('category', 'string', 'Skill category (technical, soft, language, etc.)'),
                    ExtractionField('proficiency', 'string', 'Proficiency level (beginner, intermediate, expert)'),
                    ExtractionField('years_experience', 'number', 'Years of experience'),
                ],
                relations=['USED_IN_PROJECT', 'USED_AT_JOB'],
                cross_modal=True,
                supported_modalities=[modality for modality in ModalityType]
            ),
            EntitySchema(
                entity_type='WorkExperience',
                description='Job/work experience entry',
                fields=[
                    ExtractionField('company', 'string', 'Company/organization name', required=True),
                    ExtractionField('title', 'string', 'Job title/role', required=True),
                    ExtractionField('start_date', 'date', 'Start date'),
                    ExtractionField('end_date', 'date', 'End date (or "Present")'),
                    ExtractionField('location', 'string', 'Job location'),
                    ExtractionField('description', 'string', 'Job description/responsibilities'),
                    ExtractionField('achievements', 'list', 'Key achievements/accomplishments'),
                ],
                relations=['USED_SKILL', 'LED_PROJECT', 'AT_COMPANY'],
                cross_modal=True,
                supported_modalities=[ModalityType.TEXT, ModalityType.PDF]
            ),
            EntitySchema(
                entity_type='Education',
                description='Educational qualification',
                fields=[
                    ExtractionField('institution', 'string', 'School/University name', required=True),
                    ExtractionField('degree', 'string', 'Degree/diploma', required=True),
                    ExtractionField('field', 'string', 'Field of study/major'),
                    ExtractionField('start_date', 'date', 'Start date'),
                    ExtractionField('end_date', 'date', 'End date/graduation date'),
                    ExtractionField('gpa', 'string', 'GPA or grade'),
                    ExtractionField('honors', 'list', 'Honors, awards, distinctions'),
                ],
                relations=['AT_INSTITUTION', 'STUDIED_FIELD'],
                cross_modal=True,
                supported_modalities=[ModalityType.TEXT, ModalityType.PDF]
            ),
            EntitySchema(
                entity_type='Certification',
                description='Professional certification or license',
                fields=[
                    ExtractionField('name', 'string', 'Certification name', required=True),
                    ExtractionField('issuer', 'string', 'Issuing organization'),
                    ExtractionField('issue_date', 'date', 'Issue date'),
                    ExtractionField('expiry_date', 'date', 'Expiry date'),
                    ExtractionField('credential_id', 'string', 'Credential ID'),
                ],
                relations=['ISSUED_BY'],
                cross_modal=True,
                supported_modalities=[ModalityType.TEXT, ModalityType.PDF, ModalityType.IMAGE]
            ),
            EntitySchema(
                entity_type='Project',
                description='Personal or professional project',
                fields=[
                    ExtractionField('name', 'string', 'Project name', required=True),
                    ExtractionField('description', 'string', 'Project description'),
                    ExtractionField('technologies', 'list', 'Technologies used'),
                    ExtractionField('url', 'string', 'Project URL/repository'),
                    ExtractionField('start_date', 'date', 'Start date'),
                    ExtractionField('end_date', 'date', 'End date'),
                ],
                relations=['USED_SKILL', 'PART_OF_EXPERIENCE'],
                cross_modal=True,
                supported_modalities=[ModalityType.TEXT, ModalityType.PDF, ModalityType.VIDEO]
            ),
        ]
        
        return DomainSchema(
            domain='resume',
            description='Resume or Curriculum Vitae document with multi-modal support',
            key_sections=['personal_info', 'summary', 'experience', 'education', 'skills', 'certifications'],
            supported_modalities=[modality for modality in ModalityType],
            domain_keywords=['resume', 'cv', 'curriculum vitae', 'work experience', 'skills', 'education'],
            entities=resume_entities + [entity for entity in base_schema.entities if entity.entity_type not in ['Person']]
        )
    
    @staticmethod
    def get_research_paper_schema() -> DomainSchema:
        """Schema for research papers and academic articles with multi-modal support."""
        base_schema = DomainSchemas.get_general_schema()
        
        research_entities = [
            EntitySchema(
                entity_type='Paper',
                description='The research paper itself',
                fields=[
                    ExtractionField('title', 'string', 'Paper title', required=True),
                    ExtractionField('abstract', 'string', 'Abstract/summary'),
                    ExtractionField('doi', 'string', 'DOI identifier'),
                    ExtractionField('publication_date', 'date', 'Publication date'),
                    ExtractionField('journal', 'string', 'Journal/conference name'),
                    ExtractionField('keywords', 'list', 'Keywords'),
                ],
                relations=['AUTHORED_BY', 'CITES', 'PUBLISHED_IN', 'STUDIES_TOPIC'],
                cross_modal=True,
                supported_modalities=[ModalityType.TEXT, ModalityType.PDF]
            ),
            EntitySchema(
                entity_type='Author',
                description='Paper author',
                fields=[
                    ExtractionField('name', 'string', 'Author name', required=True),
                    ExtractionField('affiliation', 'string', 'Institution/affiliation'),
                    ExtractionField('email', 'string', 'Email address'),
                    ExtractionField('orcid', 'string', 'ORCID identifier'),
                ],
                relations=['AFFILIATED_WITH', 'CO_AUTHOR_OF'],
                cross_modal=True,
                supported_modalities=[modality for modality in ModalityType]
            ),
            EntitySchema(
                entity_type='Methodology',
                description='Research methodology or approach',
                fields=[
                    ExtractionField('name', 'string', 'Method name', required=True),
                    ExtractionField('description', 'string', 'Method description'),
                    ExtractionField('type', 'string', 'Method type (quantitative, qualitative, mixed)'),
                ],
                relations=['USED_IN_STUDY', 'ANALYZES_DATA'],
                cross_modal=True,
                supported_modalities=[ModalityType.TEXT, ModalityType.PDF]
            ),
            EntitySchema(
                entity_type='Finding',
                description='Research finding or result',
                fields=[
                    ExtractionField('description', 'string', 'Finding description', required=True),
                    ExtractionField('significance', 'string', 'Statistical significance'),
                    ExtractionField('type', 'string', 'Type of finding (primary, secondary)'),
                ],
                relations=['SUPPORTS_HYPOTHESIS', 'CONTRADICTS', 'IMPLIES'],
                cross_modal=True,
                supported_modalities=[ModalityType.TEXT, ModalityType.PDF, ModalityType.IMAGE]
            ),
            EntitySchema(
                entity_type='Citation',
                description='Referenced work',
                fields=[
                    ExtractionField('title', 'string', 'Cited work title', required=True),
                    ExtractionField('authors', 'list', 'Authors'),
                    ExtractionField('year', 'string', 'Publication year'),
                    ExtractionField('doi', 'string', 'DOI'),
                ],
                relations=['CITED_BY', 'AUTHORED_BY'],
                cross_modal=True,
                supported_modalities=[ModalityType.TEXT, ModalityType.PDF]
            ),
            EntitySchema(
                entity_type='ResearchTopic',
                description='Research topic or domain',
                fields=[
                    ExtractionField('name', 'string', 'Topic name', required=True),
                    ExtractionField('field', 'string', 'Academic field'),
                ],
                relations=['RELATES_TO', 'SUBSET_OF'],
                cross_modal=True,
                supported_modalities=[modality for modality in ModalityType]
            ),
            EntitySchema(
                entity_type='Figure',
                description='Research figure or diagram',
                fields=[
                    ExtractionField('caption', 'string', 'Figure caption', required=True),
                    ExtractionField('type', 'string', 'Figure type (chart, diagram, photo, etc.)'),
                    ExtractionField('position', 'string', 'Position in document'),
                ],
                relations=['ILLUSTRATES', 'SUPPORTS_FINDING'],
                modality_specific=True,
                supported_modalities=[ModalityType.IMAGE, ModalityType.PDF]
            ),
        ]
        
        return DomainSchema(
            domain='research_paper',
            description='Academic research paper or journal article with multi-modal support',
            key_sections=['abstract', 'introduction', 'methodology', 'results', 'discussion', 'conclusion', 'references'],
            supported_modalities=[modality for modality in ModalityType],
            domain_keywords=['research', 'paper', 'academic', 'journal', 'study', 'publication'],
            entities=research_entities + base_schema.entities
        )
    
    @staticmethod
    def get_media_content_schema() -> DomainSchema:
        """Schema for audio, image, and video content analysis."""
        base_schema = DomainSchemas.get_general_schema()
        
        media_entities = [
            EntitySchema(
                entity_type='AudioSegment',
                description='Segment of audio content',
                fields=[
                    ExtractionField('content', 'string', 'Transcribed content'),
                    ExtractionField('start_time', 'timestamp', 'Start timestamp', required=True),
                    ExtractionField('end_time', 'timestamp', 'End timestamp', required=True),
                    ExtractionField('speaker', 'string', 'Speaker identification'),
                    ExtractionField('confidence', 'number', 'Transcription confidence'),
                ],
                relations=['CONTAINS_ENTITY', 'FOLLOWS', 'PRECEDES'],
                modality_specific=True,
                supported_modalities=[ModalityType.AUDIO, ModalityType.VIDEO]
            ),
            EntitySchema(
                entity_type='VisualScene',
                description='Scene in visual content',
                fields=[
                    ExtractionField('description', 'string', 'Scene description', required=True),
                    ExtractionField('timestamp', 'timestamp', 'Scene timestamp'),
                    ExtractionField('objects', 'list', 'Detected objects'),
                    ExtractionField('activities', 'list', 'Detected activities'),
                ],
                relations=['CONTAINS_OBJECT', 'FOLLOWS_SCENE', 'PRECEDES_SCENE'],
                modality_specific=True,
                supported_modalities=[ModalityType.IMAGE, ModalityType.VIDEO]
            ),
            EntitySchema(
                entity_type='Speaker',
                description='Speaker in audio/video content',
                fields=[
                    ExtractionField('name', 'string', 'Speaker name'),
                    ExtractionField('gender', 'string', 'Speaker gender'),
                    ExtractionField('role', 'string', 'Speaker role'),
                ],
                relations=['SPEAKS_IN', 'INTERACTS_WITH'],
                modality_specific=True,
                supported_modalities=[ModalityType.AUDIO, ModalityType.VIDEO]
            ),
        ]
        
        return DomainSchema(
            domain='media_content',
            description='Audio, image, and video content analysis',
            key_sections=['transcript', 'visual_elements', 'audio_features', 'metadata'],
            supported_modalities=[ModalityType.AUDIO, ModalityType.IMAGE, ModalityType.VIDEO],
            domain_keywords=['audio', 'video', 'image', 'media', 'multimedia'],
            entities=media_entities + base_schema.entities
        )
    
    @staticmethod
    def create_dynamic_schema(domain: str, description: str, keywords: List[str] = None) -> DomainSchema:
        """
        Create a dynamic schema for any domain.
        
        Args:
            domain: Domain name
            description: Domain description
            keywords: Domain-specific keywords for classification
            
        Returns:
            Dynamic DomainSchema
        """
        base_schema = DomainSchemas.get_general_schema()
        
        return DomainSchema(
            domain=domain,
            description=description,
            key_sections=['main_content', 'key_points', 'summary'],
            supported_modalities=[modality for modality in ModalityType],
            domain_keywords=keywords or [domain],
            entities=base_schema.entities
        )
    
    @staticmethod
    def get_business_report_schema() -> DomainSchema:
        """Schema for business reports with multi-modal support."""
        base_schema = DomainSchemas.get_general_schema()
        
        business_entities = [
            EntitySchema(
                entity_type='Company',
                description='Company or organization',
                fields=[
                    ExtractionField('name', 'string', 'Company name', required=True),
                    ExtractionField('industry', 'string', 'Industry/sector'),
                    ExtractionField('ticker', 'string', 'Stock ticker symbol'),
                ],
                relations=['OPERATES_IN_SECTOR', 'COMPETES_WITH', 'HAS_METRIC'],
                cross_modal=True,
                supported_modalities=[modality for modality in ModalityType]
            ),
            EntitySchema(
                entity_type='FinancialMetric',
                description='Financial metric or KPI',
                fields=[
                    ExtractionField('name', 'string', 'Metric name', required=True),
                    ExtractionField('value', 'number', 'Metric value', required=True),
                    ExtractionField('unit', 'string', 'Unit (dollars, percentage, etc.)'),
                    ExtractionField('period', 'string', 'Time period (Q1 2024, FY2023, etc.)'),
                    ExtractionField('change', 'string', 'Change from previous period'),
                ],
                relations=['MEASURES', 'COMPARED_TO'],
                cross_modal=True,
                supported_modalities=[ModalityType.TEXT, ModalityType.PDF, ModalityType.IMAGE]
            ),
        ]
        
        return DomainSchema(
            domain='business_report',
            description='Business or financial report with multi-modal support',
            key_sections=['executive_summary', 'financial_overview', 'market_analysis', 'recommendations'],
            supported_modalities=[modality for modality in ModalityType],
            domain_keywords=['business', 'report', 'financial', 'analysis', 'market'],
            entities=business_entities + base_schema.entities
        )
    
    # Keep existing schemas but enhance them with multi-modal support
    @staticmethod
    def get_technical_documentation_schema() -> DomainSchema:
        """Schema for technical documentation with multi-modal support."""
        schema = DomainSchemas.get_general_schema()
        return DomainSchema(
            domain='technical_documentation',
            description='API documentation, technical manual, or developer guide with multi-modal support',
            key_sections=['overview', 'installation', 'usage', 'api_reference', 'examples'],
            supported_modalities=[modality for modality in ModalityType],
            domain_keywords=['technical', 'documentation', 'api', 'manual', 'guide'],
            entities=schema.entities
        )
    
    @staticmethod
    def get_legal_document_schema() -> DomainSchema:
        """Schema for legal documents with multi-modal support."""
        schema = DomainSchemas.get_general_schema()
        return DomainSchema(
            domain='legal_document',
            description='Legal contract, agreement, or terms document with multi-modal support',
            key_sections=['parties', 'terms', 'obligations', 'liability', 'termination'],
            supported_modalities=[modality for modality in ModalityType],
            domain_keywords=['legal', 'contract', 'agreement', 'terms', 'law'],
            entities=schema.entities
        )
    
    @staticmethod
    def get_medical_document_schema() -> DomainSchema:
        """Schema for medical documents with multi-modal support."""
        schema = DomainSchemas.get_general_schema()
        return DomainSchema(
            domain='medical_document',
            description='Medical record, clinical note, or health document with multi-modal support',
            key_sections=['patient_info', 'chief_complaint', 'diagnosis', 'treatment', 'plan'],
            supported_modalities=[modality for modality in ModalityType],
            domain_keywords=['medical', 'health', 'clinical', 'patient', 'diagnosis'],
            entities=schema.entities
        )
    
    @classmethod
    def get_schema(cls, domain: str) -> DomainSchema:
        """
        Get extraction schema for a domain.
        
        Args:
            domain: Domain name
            
        Returns:
            DomainSchema for the domain
        """
        schema_map = {
            'resume': cls.get_resume_schema,
            'research_paper': cls.get_research_paper_schema,
            'business_report': cls.get_business_report_schema,
            'technical_documentation': cls.get_technical_documentation_schema,
            'legal_document': cls.get_legal_document_schema,
            'medical_document': cls.get_medical_document_schema,
            'media_content': cls.get_media_content_schema,
            'general': cls.get_general_schema,
        }
        
        schema_fn = schema_map.get(domain, cls.get_general_schema)
        return schema_fn()
    
    @classmethod
    def get_schema_for_modality(cls, domain: str, modality: ModalityType) -> DomainSchema:
        """
        Get schema filtered for specific modality.
        
        Args:
            domain: Domain name
            modality: Target modality
            
        Returns:
            DomainSchema with entities filtered for the modality
        """
        schema = cls.get_schema(domain)
        
        # Filter entities to only those supported by the modality
        filtered_entities = [
            entity for entity in schema.entities
            if modality in entity.supported_modalities
        ]
        
        return DomainSchema(
            domain=schema.domain,
            description=schema.description,
            entities=filtered_entities,
            key_sections=schema.key_sections,
            supported_modalities=[modality],
            domain_keywords=schema.domain_keywords
        )
    
    @classmethod
    def list_domains(cls) -> List[str]:
        """List all available domains."""
        return [
            'resume',
            'research_paper',
            'business_report',
            'technical_documentation',
            'legal_document',
            'medical_document',
            'media_content',
            'general'
        ]
    
    @classmethod
    def get_available_modalities(cls, domain: str) -> List[ModalityType]:
        """Get supported modalities for a domain."""
        schema = cls.get_schema(domain)
        return schema.supported_modalities
    
    @classmethod
    def is_modality_supported(cls, domain: str, modality: ModalityType) -> bool:
        """Check if a modality is supported for a domain."""
        schema = cls.get_schema(domain)
        return modality in schema.supported_modalities