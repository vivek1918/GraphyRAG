#!/usr/bin/env python3
"""
Domain-specific extraction schemas.
Defines structured extraction templates for each document domain.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class ExtractionField:
    """Definition of a field to extract."""
    name: str
    type: str  # 'string', 'list', 'object', 'date', 'number'
    description: str
    required: bool = False
    patterns: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)


@dataclass
class EntitySchema:
    """Schema for a domain-specific entity type."""
    entity_type: str
    description: str
    fields: List[ExtractionField]
    relations: List[str] = field(default_factory=list)


@dataclass
class DomainSchema:
    """Complete extraction schema for a document domain."""
    domain: str
    description: str
    entities: List[EntitySchema]
    key_sections: List[str] = field(default_factory=list)


class DomainSchemas:
    """Registry of extraction schemas for different document domains."""
    
    @staticmethod
    def get_resume_schema() -> DomainSchema:
        """Schema for resume/CV documents."""
        return DomainSchema(
            domain='resume',
            description='Resume or Curriculum Vitae document',
            key_sections=['personal_info', 'summary', 'experience', 'education', 'skills', 'certifications'],
            entities=[
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
                    relations=['HAS_SKILL', 'WORKED_AT', 'STUDIED_AT', 'HAS_CERTIFICATION']
                ),
                EntitySchema(
                    entity_type='Skill',
                    description='Technical or soft skill',
                    fields=[
                        ExtractionField('name', 'string', 'Skill name', required=True),
                        ExtractionField('category', 'string', 'Skill category (technical, soft, language, etc.)'),
                        ExtractionField('proficiency', 'string', 'Proficiency level (beginner, intermediate, expert)'),
                    ],
                    relations=['USED_IN_PROJECT', 'USED_AT_JOB']
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
                    relations=['USED_SKILL', 'LED_PROJECT', 'AT_COMPANY']
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
                    relations=['AT_INSTITUTION', 'STUDIED_FIELD']
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
                    relations=['ISSUED_BY']
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
                    relations=['USED_SKILL', 'PART_OF_EXPERIENCE']
                ),
            ]
        )
        
    @staticmethod
    def get_research_paper_schema() -> DomainSchema:
        """Schema for research papers and academic articles."""
        return DomainSchema(
            domain='research_paper',
            description='Academic research paper or journal article',
            key_sections=['abstract', 'introduction', 'methodology', 'results', 'discussion', 'conclusion', 'references'],
            entities=[
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
                    relations=['AUTHORED_BY', 'CITES', 'PUBLISHED_IN', 'STUDIES_TOPIC']
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
                    relations=['AFFILIATED_WITH', 'CO_AUTHOR_OF']
                ),
                EntitySchema(
                    entity_type='Methodology',
                    description='Research methodology or approach',
                    fields=[
                        ExtractionField('name', 'string', 'Method name', required=True),
                        ExtractionField('description', 'string', 'Method description'),
                        ExtractionField('type', 'string', 'Method type (quantitative, qualitative, mixed)'),
                    ],
                    relations=['USED_IN_STUDY', 'ANALYZES_DATA']
                ),
                EntitySchema(
                    entity_type='Finding',
                    description='Research finding or result',
                    fields=[
                        ExtractionField('description', 'string', 'Finding description', required=True),
                        ExtractionField('significance', 'string', 'Statistical significance'),
                        ExtractionField('type', 'string', 'Type of finding (primary, secondary)'),
                    ],
                    relations=['SUPPORTS_HYPOTHESIS', 'CONTRADICTS', 'IMPLIES']
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
                    relations=['CITED_BY', 'AUTHORED_BY']
                ),
                EntitySchema(
                    entity_type='ResearchTopic',
                    description='Research topic or domain',
                    fields=[
                        ExtractionField('name', 'string', 'Topic name', required=True),
                        ExtractionField('field', 'string', 'Academic field'),
                    ],
                    relations=['RELATES_TO', 'SUBSET_OF']
                ),
            ]
        )
        
    @staticmethod
    def get_business_report_schema() -> DomainSchema:
        """Schema for business reports."""
        return DomainSchema(
            domain='business_report',
            description='Business or financial report',
            key_sections=['executive_summary', 'financial_overview', 'market_analysis', 'recommendations'],
            entities=[
                EntitySchema(
                    entity_type='Company',
                    description='Company or organization',
                    fields=[
                        ExtractionField('name', 'string', 'Company name', required=True),
                        ExtractionField('industry', 'string', 'Industry/sector'),
                        ExtractionField('ticker', 'string', 'Stock ticker symbol'),
                    ],
                    relations=['OPERATES_IN_SECTOR', 'COMPETES_WITH', 'HAS_METRIC']
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
                    relations=['MEASURES', 'COMPARED_TO']
                ),
                EntitySchema(
                    entity_type='MarketSegment',
                    description='Market or industry segment',
                    fields=[
                        ExtractionField('name', 'string', 'Segment name', required=True),
                        ExtractionField('size', 'string', 'Market size'),
                        ExtractionField('growth_rate', 'string', 'Growth rate'),
                    ],
                    relations=['PART_OF_MARKET', 'TARGETED_BY']
                ),
                EntitySchema(
                    entity_type='Recommendation',
                    description='Business recommendation or action item',
                    fields=[
                        ExtractionField('description', 'string', 'Recommendation text', required=True),
                        ExtractionField('priority', 'string', 'Priority (high, medium, low)'),
                        ExtractionField('timeline', 'string', 'Suggested timeline'),
                    ],
                    relations=['ADDRESSES_ISSUE', 'TARGETS_METRIC']
                ),
            ]
        )
        
    @staticmethod
    def get_technical_documentation_schema() -> DomainSchema:
        """Schema for technical documentation."""
        return DomainSchema(
            domain='technical_documentation',
            description='API documentation, technical manual, or developer guide',
            key_sections=['overview', 'installation', 'usage', 'api_reference', 'examples'],
            entities=[
                EntitySchema(
                    entity_type='API',
                    description='API or software interface',
                    fields=[
                        ExtractionField('name', 'string', 'API name', required=True),
                        ExtractionField('version', 'string', 'Version'),
                        ExtractionField('base_url', 'string', 'Base URL'),
                    ],
                    relations=['HAS_ENDPOINT', 'REQUIRES_AUTH', 'RETURNS_TYPE']
                ),
                EntitySchema(
                    entity_type='Endpoint',
                    description='API endpoint or route',
                    fields=[
                        ExtractionField('path', 'string', 'Endpoint path', required=True),
                        ExtractionField('method', 'string', 'HTTP method', required=True),
                        ExtractionField('description', 'string', 'Endpoint description'),
                    ],
                    relations=['ACCEPTS_PARAM', 'RETURNS_RESPONSE', 'PART_OF_API']
                ),
                EntitySchema(
                    entity_type='Parameter',
                    description='Function parameter or API parameter',
                    fields=[
                        ExtractionField('name', 'string', 'Parameter name', required=True),
                        ExtractionField('type', 'string', 'Data type', required=True),
                        ExtractionField('required', 'string', 'Whether required'),
                        ExtractionField('description', 'string', 'Parameter description'),
                    ],
                    relations=['PARAM_OF', 'HAS_TYPE']
                ),
            ]
        )
        
    @staticmethod
    def get_legal_document_schema() -> DomainSchema:
        """Schema for legal documents."""
        return DomainSchema(
            domain='legal_document',
            description='Legal contract, agreement, or terms document',
            key_sections=['parties', 'terms', 'obligations', 'liability', 'termination'],
            entities=[
                EntitySchema(
                    entity_type='Party',
                    description='Legal party in agreement',
                    fields=[
                        ExtractionField('name', 'string', 'Party name', required=True),
                        ExtractionField('role', 'string', 'Role in agreement'),
                        ExtractionField('address', 'string', 'Legal address'),
                    ],
                    relations=['PARTY_TO', 'HAS_OBLIGATION', 'HAS_RIGHT']
                ),
                EntitySchema(
                    entity_type='Clause',
                    description='Contract clause or term',
                    fields=[
                        ExtractionField('number', 'string', 'Clause number', required=True),
                        ExtractionField('title', 'string', 'Clause title'),
                        ExtractionField('description', 'string', 'Clause text', required=True),
                    ],
                    relations=['APPLIES_TO_PARTY', 'MODIFIES_CLAUSE', 'DEPENDS_ON']
                ),
                EntitySchema(
                    entity_type='Obligation',
                    description='Legal obligation or duty',
                    fields=[
                        ExtractionField('description', 'string', 'Obligation description', required=True),
                        ExtractionField('deadline', 'date', 'Deadline or timeline'),
                    ],
                    relations=['OBLIGATES_PARTY', 'SPECIFIED_IN_CLAUSE']
                ),
            ]
        )
        
    @staticmethod
    def get_medical_document_schema() -> DomainSchema:
        """Schema for medical documents."""
        return DomainSchema(
            domain='medical_document',
            description='Medical record, clinical note, or health document',
            key_sections=['patient_info', 'chief_complaint', 'diagnosis', 'treatment', 'plan'],
            entities=[
                EntitySchema(
                    entity_type='Patient',
                    description='Patient information',
                    fields=[
                        ExtractionField('name', 'string', 'Patient name', required=True),
                        ExtractionField('age', 'number', 'Age'),
                        ExtractionField('gender', 'string', 'Gender'),
                        ExtractionField('mrn', 'string', 'Medical record number'),
                    ],
                    relations=['HAS_CONDITION', 'PRESCRIBED', 'TREATED_BY']
                ),
                EntitySchema(
                    entity_type='Diagnosis',
                    description='Medical diagnosis',
                    fields=[
                        ExtractionField('condition', 'string', 'Condition name', required=True),
                        ExtractionField('icd_code', 'string', 'ICD diagnostic code'),
                        ExtractionField('severity', 'string', 'Severity level'),
                    ],
                    relations=['DIAGNOSED_IN_PATIENT', 'TREATED_WITH']
                ),
                EntitySchema(
                    entity_type='Treatment',
                    description='Treatment or intervention',
                    fields=[
                        ExtractionField('name', 'string', 'Treatment name', required=True),
                        ExtractionField('type', 'string', 'Treatment type (medication, procedure, etc.)'),
                        ExtractionField('dosage', 'string', 'Dosage or frequency'),
                    ],
                    relations=['TREATS_CONDITION', 'PRESCRIBED_TO']
                ),
            ]
        )
        
    @staticmethod
    def get_general_schema() -> DomainSchema:
        """Fallback schema for general documents."""
        return DomainSchema(
            domain='general',
            description='General document with no specific domain',
            key_sections=['main_content'],
            entities=[
                EntitySchema(
                    entity_type='Entity',
                    description='Generic entity',
                    fields=[
                        ExtractionField('name', 'string', 'Entity name', required=True),
                        ExtractionField('type', 'string', 'Entity type'),
                        ExtractionField('description', 'string', 'Description'),
                    ],
                    relations=['RELATES_TO', 'MENTIONED_IN']
                ),
            ]
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
            'general': cls.get_general_schema,
        }
        
        schema_fn = schema_map.get(domain, cls.get_general_schema)
        return schema_fn()
        
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
            'general'
        ]
