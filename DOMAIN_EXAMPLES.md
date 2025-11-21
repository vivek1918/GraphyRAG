# Domain Extraction Examples

## Example 1: Resume/CV

### Input Document

```
Sarah Chen
Data Scientist | Machine Learning Engineer
sarah.chen@email.com | (555) 123-4567 | Seattle, WA
linkedin.com/in/sarahchen | github.com/schen

SUMMARY
Data scientist with 5+ years experience in ML model development and deployment.
Specialized in NLP, computer vision, and recommendation systems.

TECHNICAL SKILLS
- ML/DL: PyTorch, TensorFlow, Scikit-learn, Hugging Face
- Languages: Python, R, SQL, Java
- Cloud: AWS (SageMaker, Lambda), GCP (Vertex AI)
- Tools: Docker, Kubernetes, MLflow, Airflow

EXPERIENCE

Senior Data Scientist | TechVision AI | Mar 2021 - Present
• Developed transformer-based NLP models achieving 94% accuracy
• Built recommendation system serving 5M+ daily users
• Led team of 3 ML engineers on computer vision project
• Reduced model inference latency by 60% through optimization

Data Scientist | DataCorp | Jun 2019 - Feb 2021
• Created fraud detection models saving $2M annually
• Implemented A/B testing framework for ML experiments
• Deployed 15+ models to production using MLOps best practices

EDUCATION

M.S. in Computer Science | Stanford University | 2019
Specialization: Artificial Intelligence and Machine Learning
Thesis: "Attention Mechanisms in Neural Machine Translation"
GPA: 3.9/4.0

B.S. in Mathematics | MIT | 2017
Minor: Computer Science
Summa Cum Laude

PUBLICATIONS
- "Efficient Transformers for Low-Resource Languages" - NeurIPS 2022
- "Multi-Task Learning for Recommendation Systems" - RecSys 2021

CERTIFICATIONS
- AWS Machine Learning Specialty (2022)
- Google Cloud Professional ML Engineer (2021)
- Deep Learning Specialization - Coursera (2019)
```

### Extracted Domain Entities

```json
{
  "domain": "resume",
  "entities": [
    {
      "type": "Person",
      "id": "person_sarah",
      "fields": {
        "name": "Sarah Chen",
        "email": "sarah.chen@email.com",
        "phone": "(555) 123-4567",
        "location": "Seattle, WA",
        "linkedin": "linkedin.com/in/sarahchen",
        "github": "github.com/schen"
      },
      "confidence": 0.96
    },
    {
      "type": "Skill",
      "id": "skill_pytorch",
      "fields": {
        "name": "PyTorch",
        "category": "technical",
        "proficiency": "expert"
      },
      "confidence": 0.94
    },
    {
      "type": "Skill",
      "id": "skill_nlp",
      "fields": {
        "name": "Natural Language Processing",
        "category": "technical",
        "proficiency": "expert"
      },
      "confidence": 0.92
    },
    {
      "type": "WorkExperience",
      "id": "work_techvision",
      "fields": {
        "company": "TechVision AI",
        "title": "Senior Data Scientist",
        "start_date": "2021-03",
        "end_date": "Present",
        "location": "Remote",
        "description": "Developed ML models and led engineering team",
        "achievements": [
          "NLP models with 94% accuracy",
          "Recommendation system for 5M+ users",
          "Led team of 3 ML engineers",
          "60% latency reduction"
        ]
      },
      "relations": [
        { "type": "USED_SKILL", "target": "skill_pytorch" },
        { "type": "USED_SKILL", "target": "skill_nlp" }
      ],
      "confidence": 0.93
    },
    {
      "type": "Education",
      "id": "edu_stanford",
      "fields": {
        "institution": "Stanford University",
        "degree": "Master of Science",
        "field": "Computer Science",
        "start_date": "2017",
        "end_date": "2019",
        "gpa": "3.9/4.0",
        "honors": ["Specialization: AI and ML", "Thesis on NMT"]
      },
      "confidence": 0.95
    },
    {
      "type": "Certification",
      "id": "cert_aws_ml",
      "fields": {
        "name": "AWS Machine Learning Specialty",
        "issuer": "Amazon Web Services",
        "issue_date": "2022",
        "credential_id": null
      },
      "confidence": 0.91
    }
  ]
}
```

### Generated SPARQL Queries

```sparql
# Query 1: Find all ML frameworks Sarah knows
SELECT ?skill_name ?proficiency
WHERE {
  ?person rdfs:label "Sarah Chen" ;
          kg:hasSkill ?skill .
  ?skill kg:hasName ?skill_name ;
         kg:hasCategory "technical" ;
         kg:hasProficiency ?proficiency .
  FILTER(CONTAINS(LCASE(?skill_name), "learn") ||
         CONTAINS(LCASE(?skill_name), "torch") ||
         CONTAINS(LCASE(?skill_name), "flow"))
}

# Query 2: Career progression with achievements
SELECT ?company ?title ?start ?achievements
WHERE {
  ?person rdfs:label "Sarah Chen" ;
          kg:workedAt ?exp .
  ?exp kg:hasCompany ?company ;
       kg:hasTitle ?title ;
       kg:hasStartDate ?start ;
       kg:hasAchievements ?achievements .
}
ORDER BY DESC(?start)
```

---

## Example 2: Research Paper

### Input Document (Abstract + Sections)

```
Title: Attention Is All You Need
Authors: Ashish Vaswani, Noam Shazeer, Niki Parmar, et al.
Published: NeurIPS 2017
DOI: 10.48550/arXiv.1706.03762

ABSTRACT
The dominant sequence transduction models are based on complex recurrent or
convolutional neural networks that include an encoder and a decoder. The best
performing models also connect the encoder and decoder through an attention
mechanism. We propose a new simple network architecture, the Transformer,
based solely on attention mechanisms, dispensing with recurrence and
convolutions entirely.

INTRODUCTION
Recurrent neural networks, long short-term memory and gated recurrent neural
networks have been firmly established as state of the art approaches in
sequence modeling and transduction problems...

METHODOLOGY
We propose the Transformer architecture which relies entirely on self-attention
to compute representations without using sequence-aligned RNNs or convolution.
The architecture consists of stacked encoder and decoder layers.

Model Architecture:
- Multi-Head Attention mechanism
- Position-wise Feed-Forward Networks
- Positional Encoding
- Layer Normalization and Residual Connections

RESULTS
On the WMT 2014 English-to-German translation task, our model achieves 28.4
BLEU score, improving over the existing best results by over 2 BLEU points.

CONCLUSION
We presented the Transformer, the first sequence transduction model based
entirely on attention. In future work, we plan to extend the Transformer to
other modalities and investigate local, restricted attention mechanisms.
```

### Extracted Domain Entities

```json
{
  "domain": "research_paper",
  "entities": [
    {
      "type": "Paper",
      "id": "paper_transformer",
      "fields": {
        "title": "Attention Is All You Need",
        "abstract": "The dominant sequence transduction models...",
        "doi": "10.48550/arXiv.1706.03762",
        "publication_date": "2017",
        "journal": "NeurIPS 2017",
        "keywords": ["transformer", "attention", "neural networks", "NLP"]
      },
      "confidence": 0.98
    },
    {
      "type": "Author",
      "id": "author_vaswani",
      "fields": {
        "name": "Ashish Vaswani",
        "affiliation": "Google Brain",
        "email": null,
        "orcid": null
      },
      "confidence": 0.95
    },
    {
      "type": "Methodology",
      "id": "method_transformer",
      "fields": {
        "name": "Transformer Architecture",
        "description": "Sequence transduction model based solely on attention mechanisms",
        "type": "quantitative"
      },
      "confidence": 0.94
    },
    {
      "type": "Methodology",
      "id": "method_attention",
      "fields": {
        "name": "Multi-Head Attention",
        "description": "Attention mechanism with multiple representation subspaces",
        "type": "quantitative"
      },
      "confidence": 0.92
    },
    {
      "type": "Finding",
      "id": "finding_bleu",
      "fields": {
        "description": "Achieved 28.4 BLEU on WMT 2014 English-German translation",
        "significance": "2+ BLEU improvement over previous best",
        "type": "primary"
      },
      "confidence": 0.93
    },
    {
      "type": "ResearchTopic",
      "id": "topic_seq2seq",
      "fields": {
        "name": "Sequence-to-Sequence Learning",
        "field": "Natural Language Processing"
      },
      "confidence": 0.91
    }
  ]
}
```

### Generated RDF Triples

```turtle
ent:paper_transformer a kg:ResearchPaper ;
    rdfs:label "Attention Is All You Need" ;
    kg:hasTitle "Attention Is All You Need" ;
    kg:hasDoi "10.48550/arXiv.1706.03762" ;
    kg:hasPublicationDate "2017" ;
    kg:authoredBy ent:author_vaswani ;
    kg:usesMethodology ent:method_transformer ;
    kg:hasFinding ent:finding_bleu ;
    kg:studiesTopi ent:topic_seq2seq .

ent:method_transformer a kg:Methodology ;
    rdfs:label "Transformer Architecture" ;
    kg:hasName "Transformer Architecture" ;
    kg:hasDescription "Sequence transduction model based solely on attention" ;
    kg:hasType "quantitative" .

ent:finding_bleu a kg:Finding ;
    rdfs:label "28.4 BLEU Score Achievement" ;
    kg:hasDescription "Achieved 28.4 BLEU on WMT 2014" ;
    kg:hasSignificance "2+ BLEU improvement" .
```

---

## Example 3: Business Report

### Input Document

```
QUARTERLY FINANCIAL REPORT - Q4 2023
TechGrowth Corporation

EXECUTIVE SUMMARY
TechGrowth Corp delivered strong Q4 results with revenue of $2.4B,
representing 18% YoY growth. Operating margin improved to 24%, up from 21%
in Q4 2022. Cloud segment showed exceptional performance with 45% growth.

FINANCIAL HIGHLIGHTS
- Total Revenue: $2.4B (up 18% YoY)
- Cloud Revenue: $1.1B (up 45% YoY)
- Software Revenue: $950M (up 8% YoY)
- Operating Income: $576M (24% margin)
- Net Income: $432M
- EPS: $3.12 (diluted)

SEGMENT ANALYSIS

Cloud Services
Our cloud infrastructure and SaaS offerings grew 45% driven by:
- 300+ new enterprise customers
- Average contract value up 22%
- 95% customer retention rate
Market opportunity remains significant with TAM estimated at $500B.

Enterprise Software
Traditional software segment grew 8%, below market average of 12%.
Plan to increase R&D investment by 30% to accelerate innovation.

MARKET POSITION
TechGrowth maintains #2 position in cloud infrastructure market with 18%
market share, behind CloudLeader (32%) but ahead of CompetitorX (14%).

Geographic breakdown:
- North America: 60% of revenue
- Europe: 25% of revenue
- Asia-Pacific: 15% of revenue

OUTLOOK & RECOMMENDATIONS
We project Q1 2024 revenue of $2.5-2.6B representing 15-20% YoY growth.

Key recommendations:
1. Increase cloud sales team by 50 headcount (HIGH PRIORITY)
2. Accelerate migration of legacy customers to cloud (MEDIUM)
3. Expand data center presence in APAC region (HIGH)
4. Invest $200M in AI/ML capabilities (HIGH)
```

### Extracted Domain Entities

```json
{
  "domain": "business_report",
  "entities": [
    {
      "type": "Company",
      "id": "company_techgrowth",
      "fields": {
        "name": "TechGrowth Corporation",
        "industry": "Technology/Cloud Services",
        "ticker": "TGRO"
      },
      "confidence": 0.97
    },
    {
      "type": "FinancialMetric",
      "id": "metric_revenue_q4",
      "fields": {
        "name": "Total Revenue",
        "value": 2400000000,
        "unit": "USD",
        "period": "Q4 2023",
        "change": "+18% YoY"
      },
      "confidence": 0.96
    },
    {
      "type": "FinancialMetric",
      "id": "metric_cloud_revenue",
      "fields": {
        "name": "Cloud Revenue",
        "value": 1100000000,
        "unit": "USD",
        "period": "Q4 2023",
        "change": "+45% YoY"
      },
      "confidence": 0.95
    },
    {
      "type": "FinancialMetric",
      "id": "metric_margin",
      "fields": {
        "name": "Operating Margin",
        "value": 24,
        "unit": "percent",
        "period": "Q4 2023",
        "change": "+3 points YoY"
      },
      "confidence": 0.94
    },
    {
      "type": "MarketSegment",
      "id": "segment_cloud",
      "fields": {
        "name": "Cloud Infrastructure",
        "size": "$500B TAM",
        "growth_rate": "45%"
      },
      "confidence": 0.92
    },
    {
      "type": "Company",
      "id": "company_cloudleader",
      "fields": {
        "name": "CloudLeader",
        "industry": "Cloud Services",
        "ticker": null
      },
      "confidence": 0.89
    },
    {
      "type": "Recommendation",
      "id": "rec_sales_team",
      "fields": {
        "description": "Increase cloud sales team by 50 headcount",
        "priority": "HIGH",
        "timeline": "Q1 2024"
      },
      "confidence": 0.93
    },
    {
      "type": "Recommendation",
      "id": "rec_ai_investment",
      "fields": {
        "description": "Invest $200M in AI/ML capabilities",
        "priority": "HIGH",
        "timeline": "2024"
      },
      "confidence": 0.91
    }
  ]
}
```

### Generated Neo4j Cypher Queries

```cypher
// Query 1: Visualize company financials
MATCH (c:Company {name: "TechGrowth Corporation"})-[:HAS_METRIC]->(m:FinancialMetric)
RETURN c, m

// Query 2: Compare revenue across segments
MATCH (c:Company)-[:OPERATES_IN_SECTOR]->(s:MarketSegment)
MATCH (c)-[:HAS_METRIC]->(m:FinancialMetric)
WHERE m.name CONTAINS "Revenue"
RETURN s.name, m.value, m.change

// Query 3: High priority recommendations
MATCH (r:Recommendation)
WHERE r.priority = "HIGH"
RETURN r.description, r.timeline
ORDER BY r.timeline

// Query 4: Competitive analysis
MATCH (c1:Company)-[:COMPETES_WITH]->(c2:Company)
MATCH (c1)-[:OPERATES_IN_SECTOR]->(s:MarketSegment)
RETURN c1.name, c2.name, s.name
```

---

## Benefits Demonstrated

### 1. Resume → Career Graph

- Skills mapped to proficiency levels
- Experience linked to skills used
- Education backing qualifications
- Certifications adding credentials

**Query**: "Find ML engineers with NLP experience and AWS certifications"
**Result**: Precise matches based on structured data

### 2. Research Paper → Citation Network

- Authors with affiliations
- Methodologies clearly defined
- Findings quantified
- Topics categorized

**Query**: "Papers using transformer architecture achieving >25 BLEU"
**Result**: Relevant papers with methodology and metrics

### 3. Business Report → Financial Analysis

- Metrics with temporal context
- Market segments quantified
- Competitive positioning
- Actionable recommendations

**Query**: "Companies with >40% cloud revenue growth and high-priority AI investments"
**Result**: Investment opportunities identified

## Comparison: Generic vs Domain-Aware

### Generic NER Extraction

```
Entities: ["Sarah Chen", "TechVision AI", "PyTorch", "Seattle"]
Relations: [("Sarah Chen", "WORKS_AT", "TechVision AI")]
```

### Domain-Aware Extraction

```
Person: {
  name: "Sarah Chen",
  skills: [PyTorch (expert), NLP (expert), AWS (advanced)],
  experience: [{
    company: "TechVision AI",
    title: "Senior Data Scientist",
    achievements: ["94% accuracy", "5M+ users", "60% latency reduction"]
  }],
  education: [{degree: "M.S. CS", school: "Stanford", gpa: 3.9}],
  certifications: ["AWS ML Specialty", "GCP Professional ML"]
}
```

**Richness**: 10x more structured information
**Queryability**: Enables precise filtering and aggregation
**Usability**: Direct mapping to business needs
