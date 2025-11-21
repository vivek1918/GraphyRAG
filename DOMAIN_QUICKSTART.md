# Domain-Aware Extraction - Quick Start

## Test with a Resume Example

### 1. Create a Sample Resume

Create `data/raw/pdf/sample_resume.txt`:

```
John Doe
Senior Software Engineer
john.doe@example.com | +1-555-0123 | San Francisco, CA
linkedin.com/in/johndoe | github.com/johndoe

PROFESSIONAL SUMMARY
Experienced software engineer with 8+ years building scalable cloud applications.
Expert in Python, AWS, and microservices architecture.

SKILLS
- Languages: Python, Java, JavaScript, Go
- Cloud: AWS (EC2, S3, Lambda), Azure, GCP
- Databases: PostgreSQL, MongoDB, Redis
- Tools: Docker, Kubernetes, Terraform, Git

WORK EXPERIENCE

Senior Software Engineer | TechCorp Inc. | Jan 2020 - Present
• Led development of microservices platform serving 10M+ users
• Reduced infrastructure costs by 40% through optimization
• Mentored team of 5 junior engineers
• Technologies: Python, AWS, Kubernetes, PostgreSQL

Software Engineer | StartupXYZ | Jun 2016 - Dec 2019
• Built RESTful APIs for mobile applications
• Implemented CI/CD pipelines using Jenkins and Docker
• Achieved 99.9% uptime for critical services
• Technologies: Java, Spring Boot, MongoDB

EDUCATION

Master of Science in Computer Science | Stanford University | 2016
- Specialization: Distributed Systems
- GPA: 3.8/4.0

Bachelor of Science in Computer Engineering | UC Berkeley | 2014
- Dean's List all semesters

CERTIFICATIONS
- AWS Certified Solutions Architect - Professional (2022)
- Certified Kubernetes Administrator (2021)
```

### 2. Run the Pipeline

```bash
# Set Groq API key (optional but recommended)
export GROQ_API_KEY="your-key-here"

# Run pipeline
cd "Knowledge Graph"
python -m scripts.demo_pipeline
```

### 3. Expected Output

**Console Log:**

```
[INFO] Starting demo pipeline...
[INFO] Using existing data from data/raw
[INFO] Parsing documents...
[INFO] Parsed 1 documents total

[INFO] Extracting entities and relations...
[1/1] Classification start: sample_resume
[1/1] Classification done: sample_resume in 0.28s, domain=resume (conf=0.92)
[1/1] Domain extraction start: sample_resume
[1/1] Domain extraction done: sample_resume in 2.34s, domain_entities=18
  - Extracted: 1 Person, 4 Skills, 2 WorkExperience, 2 Education, 2 Certification
[1/1] NER start: sample_resume (chars=1456)
[1/1] NER done: sample_resume in 0.41s, entities=6
[1/1] RE start: sample_resume
[1/1] RE done: sample_resume in 0.52s, relations=8
[1/1] Link done: sample_resume in 0.18s, linked=12

Progress: 1/1 docs, elapsed=4.12s, domain_entities=18, entities=6, relations=8

[INFO] Dataset ontologies generated: {'pdf': 'ontology/dataset_pdf_ontology.ttl'}
[INFO] Building knowledge graph...
[INFO] Built 247 triples from 1 documents
```

**Extracted Domain Entities:**

```json
{
  "domain": "resume",
  "entities": [
    {
      "type": "Person",
      "id": "person_1",
      "fields": {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "+1-555-0123",
        "location": "San Francisco, CA",
        "linkedin": "linkedin.com/in/johndoe",
        "github": "github.com/johndoe"
      },
      "confidence": 0.95
    },
    {
      "type": "Skill",
      "id": "skill_1",
      "fields": {
        "name": "Python",
        "category": "technical",
        "proficiency": "expert"
      },
      "confidence": 0.93
    },
    {
      "type": "WorkExperience",
      "id": "work_1",
      "fields": {
        "company": "TechCorp Inc.",
        "title": "Senior Software Engineer",
        "start_date": "2020-01",
        "end_date": "Present",
        "description": "Led development of microservices platform...",
        "achievements": [
          "Served 10M+ users",
          "Reduced costs by 40%",
          "Mentored 5 engineers"
        ]
      },
      "relations": [
        {"type": "USED_SKILL", "target": "skill_1"}
      ],
      "confidence": 0.91
    },
    ...
  ]
}
```

### 4. Query the Knowledge Graph

**SPARQL Query (Fuseki):**

```sparql
PREFIX kg: <http://kg.example.org/ontology/>
PREFIX ent: <http://kg.example.org/entity/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

# Find all skills for a person
SELECT ?person_name ?skill_name ?proficiency
WHERE {
  ?person a kg:Person ;
          rdfs:label ?person_name ;
          kg:hasSkill ?skill .
  ?skill a kg:Skill ;
         kg:hasName ?skill_name ;
         kg:hasProficiency ?proficiency .
}
```

**Cypher Query (Neo4j):**

```cypher
// Find career path
MATCH (p:Person)-[:WORKED_AT]->(exp:WorkExperience)
RETURN p.name, exp.company, exp.title, exp.start_date, exp.end_date
ORDER BY exp.start_date

// Find skills used in each job
MATCH (p:Person)-[:WORKED_AT]->(exp:WorkExperience)-[:USED_SKILL]->(s:Skill)
RETURN exp.company, collect(s.name) as skills
```

**GraphRAG Query:**

```python
from rag.graph_rag import GraphRAG

rag = GraphRAG()
results = await rag.query(
    "What are John Doe's technical skills and where did he use them?",
    top_k=5
)

# Returns structured answer with:
# - Skills: Python, Java, AWS, Kubernetes...
# - Usage context: At TechCorp (microservices), At StartupXYZ (APIs)
# - Proficiency levels
# - Related certifications
```

## Test with Different Domains

### Research Paper Example

Place a research paper PDF in `data/raw/pdf/research_paper.pdf` and run:

```bash
python -m scripts.demo_pipeline
```

**Expected Extractions:**

- Paper (title, abstract, DOI)
- Authors (names, affiliations)
- Methodology (approach used)
- Findings (key results)
- Citations (referenced works)

### Business Report Example

Place a quarterly report in `data/raw/pdf/q4_report.pdf`:

**Expected Extractions:**

- Company (name, industry)
- Financial metrics (revenue, profit, growth)
- Market segments
- Recommendations

## Validation

Check generated files:

```bash
# Domain classification results
cat data/interim/enriched_documents.jsonl | jq '.domain_classification'

# Domain entities
cat data/interim/enriched_documents.jsonl | jq '.domain_entities'

# RDF triples
cat data/processed/knowledge_graph.ttl | grep "a kg:Skill"
cat data/processed/knowledge_graph.ttl | grep "a kg:WorkExperience"

# Dataset-specific ontology
cat ontology/dataset_pdf_ontology.ttl | grep "rdfs:label"
```

## Performance Tips

1. **Batch Processing**: Process multiple documents at once for better efficiency
2. **Cache Classifications**: Store domain classifications to skip re-classification
3. **Parallel Extraction**: Pipeline already parallelizes where possible
4. **LLM Selection**: Use smaller models for classification, larger for extraction

## Troubleshooting

**No domain entities extracted:**

```bash
# Check if Groq API key is set
echo $GROQ_API_KEY

# Verify document was parsed correctly
cat data/interim/parsed_documents.jsonl | jq '.content' | head -20

# Check classification result
cat data/interim/enriched_documents.jsonl | jq '.domain_classification'
```

**Low extraction quality:**

- Use `mode="llm"` for classification (more accurate)
- Increase content context (avoid truncation)
- Fine-tune prompts in `domain_extractors.py`

**Performance too slow:**

- Use `mode="hybrid"` or `mode="keyword"` for classification
- Process smaller batches
- Consider caching results

## Next Steps

1. Add more documents to test robustness
2. Customize schemas for your specific use case
3. Add validation rules for extracted fields
4. Build domain-specific RAG templates
5. Create visualization dashboards

See `DOMAIN_EXTRACTION.md` for full documentation.
