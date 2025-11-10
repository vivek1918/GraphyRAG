#!/usr/bin/env python3
"""
Synthetic PDF generator with embedded text and entities.
"""

import json
import random
from datetime import datetime
from pathlib import Path
from faker import Faker
from typing import Dict 
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

fake = Faker()
random.seed(42)

class PDFDataGenerator:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.organizations = [
            "TechCorp Inc", "Global Bank", "MediPharm", "EduFoundation",
            "GreenEnergy Co", "AutoManufacturers Ltd"
        ]
        
        self.people = [
            "John Smith", "Maria Garcia", "David Chen", "Sarah Johnson"
        ]
        
        self.places = ["New York", "San Francisco", "London", "Tokyo"]

    def generate_business_report(self, doc_id: str) -> Dict:
        """Generate a business report PDF with entities."""
        org = random.choice(self.organizations)
        ceo = random.choice(self.people)
        location = random.choice(self.places)
        
        content = f"""
        QUARTERLY BUSINESS REPORT
        {org}
        
        Executive Summary:
        This report covers the financial performance of {org} for the current quarter. 
        Under the leadership of {ceo}, the company has shown strong growth across all business segments.
        
        Financial Highlights:
        - Revenue increased by 15% compared to previous quarter
        - Operating margin improved to 25%
        - Market share grew in {location} region
        
        Operational Updates:
        The company continues to invest in research and development. New partnerships 
        have been established with key industry players in {location}.
        
        Outlook:
        {ceo} expressed confidence in the company's strategic direction and expects 
        continued growth in the coming quarters.
        """
        
        # Create PDF
        pdf_path = self.output_dir / f"{doc_id}.pdf"
        doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        title = Paragraph(f"Business Report: {org}", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 0.2*inch))
        
        for paragraph in content.split('\n\n'):
            if paragraph.strip():
                p = Paragraph(paragraph, styles['BodyText'])
                story.append(p)
                story.append(Spacer(1, 0.1*inch))
        
        doc.build(story)
        
        return {
            "doc_id": doc_id,
            "type": "business_report",
            "file_path": str(pdf_path),
            "content": content,
            "entities": [
                {"text": org, "type": "ORG", "canonical_name": org},
                {"text": ceo, "type": "PERSON", "canonical_name": ceo},
                {"text": location, "type": "PLACE", "canonical_name": location}
            ],
            "relations": [
                {
                    "subject": ceo,
                    "object": org,
                    "relation": "WORKS_FOR",
                    "evidence": f"leadership of {ceo}"
                }
            ]
        }

    def generate_resume(self, doc_id: str) -> Dict:
        """Generate a synthetic resume PDF."""
        person = random.choice(self.people)
        org = random.choice(self.organizations)
        location = random.choice(self.places)
        role = random.choice(["Senior Engineer", "Data Scientist", "Product Manager"])
        
        content = f"""
        RESUME
        {person}
        
        Professional Summary:
        Experienced {role} with 5+ years in the technology industry. 
        Currently employed at {org} in {location}.
        
        Work Experience:
        {role} at {org} ({location})
        - Led cross-functional teams
        - Delivered multiple successful projects
        - Improved operational efficiency by 30%
        
        Education:
        Bachelor of Science in Computer Science
        """
        
        pdf_path = self.output_dir / f"{doc_id}.pdf"
        doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        title = Paragraph(f"Resume: {person}", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 0.2*inch))
        
        for paragraph in content.split('\n\n'):
            if paragraph.strip():
                p = Paragraph(paragraph, styles['BodyText'])
                story.append(p)
                story.append(Spacer(1, 0.1*inch))
        
        doc.build(story)
        
        return {
            "doc_id": doc_id,
            "type": "resume", 
            "file_path": str(pdf_path),
            "content": content,
            "entities": [
                {"text": person, "type": "PERSON", "canonical_name": person},
                {"text": org, "type": "ORG", "canonical_name": org},
                {"text": location, "type": "PLACE", "canonical_name": location}
            ],
            "relations": [
                {
                    "subject": person,
                    "object": org, 
                    "relation": "WORKS_FOR",
                    "evidence": f"Currently employed at {org}"
                }
            ]
        }

    def generate_dataset(self, num_docs: int = 20):
        """Generate a dataset of synthetic PDFs."""
        documents = []
        
        for i in range(num_docs):
            doc_id = f"pdf_{i:04d}"
            if random.random() > 0.5:
                doc = self.generate_business_report(doc_id)
            else:
                doc = self.generate_resume(doc_id)
            documents.append(doc)
            
            # Save metadata
            meta_file = self.output_dir / f"{doc_id}.json"
            with open(meta_file, 'w') as f:
                json.dump(doc, f, indent=2)
                
        print(f"Generated {num_docs} PDF documents in {self.output_dir}")
        return documents

if __name__ == "__main__":
    output_dir = Path("data/raw/pdf")
    generator = PDFDataGenerator(output_dir)
    generator.generate_dataset(10)