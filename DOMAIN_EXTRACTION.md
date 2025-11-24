# Domain-Aware Knowledge Graph Extraction

## Overview

The system now includes intelligent document classification and domain-specific extraction capabilities. Instead of applying generic NER/RE to all documents, the pipeline:

1. **Classifies** each document into a domain (resume, research paper, business report, etc.)
2. **Extracts** structured information using domain-specific schemas
3. **Builds** knowledge graphs with properly typed domain entities

## Architecture

### Document Classification (`extract/document_classifier.py`)

Classifies documents into domains using multiple strategies:

**Supported Domains:**

- `resume` - Curriculum vitae, job applications
- `research_paper` - Academic papers, journal articles
- `business_report` - Financial reports, business analyses
- `technical_documentation` - API docs, manuals
- `legal_document` - Contracts, agreements
- `medical_document` - Medical records, clinical notes
- `general` - Fallback for unclassified documents

**Classification Modes:**

- `rule` - Pattern matching (fast, no API needed)
- `keyword` - Keyword frequency analysis
- `llm` - LLM-based classification (most accurate, requires Groq API)
- `hybrid` (default) - Combines multiple strategies

**Example:**

```python
from extract.document_classifier import classify_document

doc = {
    'content': 'John Doe\nSoftware Engineer\nSkills: Python, AWS...',
    'metadata': {'filename': 'resume.pdf'}
}

doc = await classify_document(doc, mode="hybrid")
# doc['domain_classification'] = {
#     'domain': 'resume',
#     'confidence': 0.87,
#     'reasoning': 'Filename hint confirmed by content analysis'
# }
```

### Domain Schemas (`extract/domain_schemas.py`)

Defines structured extraction templates for each domain.

**Resume Schema Example:**

```python
from extract.domain_schemas import DomainSchemas

schema = DomainSchemas.get_resume_schema()
# Returns schema with entity types:
# - Person (name, email, phone, location, linkedin, github)
# - Skill (name, category, proficiency)
# - WorkExperience (company, title, dates, description, achievements)
# - Education (institution, degree, field, dates, gpa, honors)
# - Certification (name, issuer, dates, credential_id)
# - Project (name, description, technologies, url, dates)
```

**Research Paper Schema:**

- Paper (title, abstract, DOI, keywords)
- Author (name, affiliation, ORCID)
- Methodology (name, description, type)
- Finding (description, significance)
- Citation (title, authors, year, DOI)
- ResearchTopic (name, field)

**Business Report Schema:**

- Company (name, industry, ticker)
- FinancialMetric (name, value, unit, period, change)
- MarketSegment (name, size, growth_rate)
- Recommendation (description, priority, timeline)

### Domain Extraction (`extract/domain_extractors.py`)

Uses LLM-based structured prompts to extract domain-specific entities.

**Features:**

- Schema-guided extraction with field validation
- Structured JSON output matching domain schemas
- Confidence scores for each entity
- Relations between entities
- Fallback to rule-based extraction when LLM unavailable

**Example:**

```python
from extract.domain_extractors import extract_domain_entities

# Assumes doc has 'domain_classification' field
doc = await extract_domain_entities(doc, mode="groq")

# doc['domain_entities'] = {
#     'domain': 'resume',
#     'schema_version': '1.0',
#     'entities': [
#         {
#             'type': 'Person',
#             'id': 'person_1',
#             'fields': {
#                 'name': 'John Doe',
#                 'email': 'john@example.com',
#                 'phone': '+1-555-0100',
#                 'location': 'San Francisco, CA'
#             },
#             'confidence': 0.95
#         },
#         {
#             'type': 'Skill',
#             'id': 'skill_1',
#             'fields': {
#                 'name': 'Python',
#                 'category': 'technical',
#                 'proficiency': 'expert'
#             },
#             'confidence': 0.92
#         },
#         ...
#     ]
# }
```

### Enhanced Ontology (`ontology/core.ttl`)

Extended with domain-specific classes and properties:

**Domain Classes Added:**

- Resume domain: `Skill`, `WorkExperience`, `Education`, `Certification`, `Project`
- Research domain: `ResearchPaper`, `Author`, `Methodology`, `Finding`, `Citation`, `ResearchTopic`
- Business domain: `Company`, `FinancialMetric`, `MarketSegment`, `Recommendation`
- Technical domain: `API`, `Endpoint`, `Parameter`
- Legal domain: `Party`, `Clause`, `Obligation`
- Medical domain: `Patient`, `Diagnosis`, `Treatment`

**Domain Properties Added:**

- Resume: `hasSkill`, `workedAt`, `studiedAt`, `hasCertification`, `usedSkill`, `atCompany`
- Research: `authoredBy`, `cites`, `usesMethodology`, `hasFinding`, `studiesTopi`, `affiliatedWith`
- Business: `hasMetric`, `operatesInSector`, `competesWith`
- Technical: `hasEndpoint`, `acceptsParameter`
- Legal: `partyTo`, `hasClause`, `hasObligation`
- Medical: `hasCondition`, `treatedWith`, `prescribedTo`

### Enhanced Pipeline (`scripts/demo_pipeline.py`)

Pipeline now includes domain-aware stages:

**Extraction Flow:**

1. **Document Classification** - Identify domain type
2. **Domain Extraction** - Apply domain-specific schemas (LLM-based)
3. **Generic NER** - Standard entity extraction (fallback/supplement)
4. **Relation Extraction** - Extract relationships
5. **Entity Linking** - Resolve and canonicalize entities
6. **Ontology Generation** - Create dataset-specific ontologies
7. **Triple Building** - Generate RDF with domain entities

**Logging Output:**

```
[1/5] Classification start: doc_001
[1/5] Classification done: doc_001 in 0.34s, domain=resume (conf=0.87)
[1/5] Domain extraction start: doc_001
[1/5] Domain extraction done: doc_001 in 2.15s, domain_entities=12
[1/5] NER start: doc_001 (chars=3456)
[1/5] NER done: doc_001 in 0.52s, entities=8
...
Progress: 5/5 docs, elapsed=18.43s, domain_entities=45, entities=32, relations=21
```

### Enhanced Triple Builder (`kg/build_triples.py`)

Now handles domain-specific entities with proper typing:

**Features:**

- Separate processing for domain entities vs generic entities
- Structured field mapping to RDF properties
- Domain-specific Neo4j labels
- All fields from schema preserved as datatype properties

**Example Output:**

```turtle
@prefix kg: <http://kg.example.org/ontology/> .
@prefix ent: <http://kg.example.org/entity/> .

ent:person_1 a kg:Person ;
    rdfs:label "John Doe" ;
    kg:hasName "John Doe" ;
    kg:hasEmail "john@example.com" ;
    kg:hasPhone "+1-555-0100" ;
    kg:hasLocation "San Francisco, CA" ;
    kg:extractedFrom doc:resume_001 .

ent:skill_1 a kg:Skill ;
    rdfs:label "Python" ;
    kg:hasName "Python" ;
    kg:hasCategory "technical" ;
    kg:hasProficiency "expert" ;
    kg:hasConfidence "0.92"^^xsd:float ;
    kg:extractedFrom doc:resume_001 .

ent:work_exp_1 a kg:WorkExperience ;
    rdfs:label "Software Engineer at TechCorp" ;
    kg:hasCompany "TechCorp" ;
    kg:hasTitle "Software Engineer" ;
    kg:hasStartDate "2020-01" ;
    kg:hasEndDate "2023-12" ;
    kg:hasDescription "Led development of microservices..." ;
    kg:extractedFrom doc:resume_001 .

# Relations
ent:person_1 kg:hasSkill ent:skill_1 .
ent:person_1 kg:workedAt ent:work_exp_1 .
ent:work_exp_1 kg:usedSkill ent:skill_1 .
```

## Configuration

### Enable/Disable Domain Extraction

In `conf/settings.yaml`:

```yaml
extraction:
  domain_aware: true # Enable domain-specific extraction
  classification_mode: "hybrid" # rule, keyword, llm, hybrid
  domain_extraction_mode: "groq" # groq, local, hybrid
```

### LLM Configuration

For best results, use Groq API (fast, free tier available):

```bash
export GROQ_API_KEY="your-api-key-here"
```

Models used:

- Classification: `openai/gpt-oss-120b` (fast)
- Extraction: `llama-3.1-70b-versatile` (accurate)

## Usage Examples

### Example 1: Resume Processing

```python
from pathlib import Path
from scripts.demo_pipeline import DemoPipeline

# Place resume PDFs in data/raw/pdf/
pipeline = DemoPipeline()
await pipeline.run()

# Results include:
# - Domain classification: resume
# - Structured extraction: Person, Skills, WorkExperience, Education
# - RDF triples with kg:Skill, kg:WorkExperience classes
# - Neo4j graph with proper labels
```

### Example 2: Research Paper Analysis

```python
# Place research papers in data/raw/pdf/
pipeline = DemoPipeline()
results = await pipeline.run()

# Extracted entities:
# - Paper metadata (title, DOI, abstract)
# - Authors with affiliations
# - Methodologies used
# - Research findings
# - Citations
# - Research topics
```

### Example 3: Business Report Processing

```python
# Place reports in data/raw/pdf/
pipeline = DemoPipeline()
results = await pipeline.run()

# Extracted entities:
# - Company information
# - Financial metrics (revenue, profit, growth rates)
# - Market segments
# - Recommendations
```

## Benefits

1. **Precision**: Domain-specific schemas eliminate ambiguity
2. **Completeness**: Structured extraction captures all relevant fields
3. **Semantics**: Proper ontology classes enable rich querying
4. **Flexibility**: Easy to add new domains or extend schemas
5. **Hybrid Approach**: Combines LLM intelligence with rule-based fallbacks

## Performance

**Classification:**

- Rule/keyword mode: ~10ms per document
- Hybrid mode: ~300ms per document
- LLM mode: ~500ms per document

**Domain Extraction:**

- Rule-based: ~50ms per document
- LLM-based: 1-3s per document (depends on content length)
- Parallelization: Can process batches concurrently

**Recommendations:**

- Small datasets (<100 docs): Use LLM mode for best accuracy
- Large datasets (>1000 docs): Use hybrid classification + LLM extraction for critical domains
- Real-time systems: Use rule/keyword classification + rule-based extraction

## Extending the System

### Adding a New Domain

1. **Define Schema** in `extract/domain_schemas.py`:

```python
@staticmethod
def get_invoice_schema() -> DomainSchema:
    return DomainSchema(
        domain='invoice',
        description='Invoice or billing document',
        entities=[
            EntitySchema(
                entity_type='Invoice',
                fields=[
                    ExtractionField('invoice_number', 'string', 'Invoice number', required=True),
                    ExtractionField('total_amount', 'number', 'Total amount'),
                    ...
                ]
            ),
            ...
        ]
    )
```

2. **Update Classifier** in `extract/document_classifier.py`:

```python
DOMAINS = {
    'invoice': {
        'keywords': ['invoice', 'bill', 'payment', 'due date', ...],
        'patterns': [r'\binvoice\s+#?\d+', ...]
    },
    ...
}
```

3. **Extend Ontology** in `ontology/core.ttl`:

```turtle
:Invoice a owl:Class ;
    rdfs:subClassOf :Document .

:hasInvoiceNumber a owl:DatatypeProperty ;
    rdfs:domain :Invoice ;
    rdfs:range xsd:string .
```

4. **Update Dynamic Ontology Generator** to recognize new classes.

## Troubleshooting

**Issue**: Domain entities not extracted

- Check `GROQ_API_KEY` is set
- Verify document content is not empty
- Check classification confidence (low confidence → generic extraction)

**Issue**: Wrong domain classification

- Add domain-specific keywords to classifier
- Use LLM mode for better accuracy
- Check filename hints are correct

**Issue**: Missing structured fields

- Review schema definition
- Check LLM prompt includes all fields
- Validate entity against schema

## Future Enhancements

- [ ] Multi-domain documents (e.g., resume + portfolio)
- [ ] Cross-domain relation extraction
- [ ] Active learning for schema refinement
- [ ] Domain-specific RAG query templates
- [ ] Hierarchical domain classification
- [ ] Transfer learning for custom domains
