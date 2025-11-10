#!/usr/bin/env python3
"""
Synthetic text data generator for knowledge graph testing.
Generates news articles, emails, and documents with entities and relations.
"""

import json
import random
from datetime import datetime
from pathlib import Path
from faker import Faker
from typing import List, Dict, Any

fake = Faker()
random.seed(42)

class TextDataGenerator:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Predefined entities for consistency
        self.organizations = [
            "TechCorp Inc", "Global Bank", "MediPharm", "EduFoundation",
            "GreenEnergy Co", "AutoManufacturers Ltd", "FoodDistributors Inc"
        ]
        
        self.people = [
            "John Smith", "Maria Garcia", "David Chen", "Sarah Johnson",
            "Robert Williams", "Lisa Brown", "Michael Davis", "Emily Wilson"
        ]
        
        self.places = [
            "New York", "San Francisco", "London", "Tokyo", "Berlin",
            "Sydney", "Toronto", "Singapore", "Paris", "Dubai"
        ]
        
        self.events = [
            "annual conference", "merger announcement", "product launch",
            "charity gala", "board meeting", "earnings call", "tech summit"
        ]
        
        self.roles = ["CEO", "CTO", "CFO", "Director", "Manager", "Analyst"]

    def generate_news_article(self, doc_id: str) -> Dict[str, Any]:
        """Generate a synthetic news article with entities and relations."""
        org1, org2 = random.sample(self.organizations, 2)
        person = random.choice(self.people)
        place = random.choice(self.places)
        event = random.choice(self.events)
        role = random.choice(self.roles)
        
        templates = [
            f"{person}, the {role} of {org1}, announced today that the company will host its {event} in {place}. The event will focus on new partnerships with {org2}.",
            f"In a major development, {org1} and {org2} have agreed to merge operations. {person}, currently serving as {role}, will lead the combined entity from {place}.",
            f"{org1} reported strong quarterly results during yesterday's {event} in {place}. {person}, the company's {role}, highlighted growth in all business segments.",
            f"The {event} hosted by {org1} in {place} featured keynote speaker {person}, who discussed future collaborations with {org2}.",
            f"{person} has been appointed as the new {role} of {org1}, effective immediately. The announcement was made at a press conference in {place}."
        ]
        
        content = random.choice(templates)
        timestamp = fake.date_time_this_year()
        
        return {
            "doc_id": doc_id,
            "type": "news_article",
            "content": content,
            "title": f"News: {org1} {event.title()}",
            "source": "Synthetic News Network",
            "created_at": timestamp.isoformat(),
            "entities": self._extract_ground_truth_entities(content),
            "relations": self._extract_ground_truth_relations(content)
        }

    def generate_email(self, doc_id: str) -> Dict[str, Any]:
        """Generate a synthetic email with business context."""
        sender = random.choice(self.people)
        receiver = random.choice([p for p in self.people if p != sender])
        org = random.choice(self.organizations)
        place = random.choice(self.places)
        event = random.choice(self.events)
        
        templates = [
            f"Subject: Update on {event}\n\nHi {receiver},\n\nJust wanted to follow up on our discussion about the {event} in {place}. Please review the attached documents from {org}.\n\nBest,\n{sender}",
            f"Subject: Meeting Request\n\nHello {receiver},\n\nI'd like to schedule a call to discuss the partnership with {org}. They're interested in our proposal for the {event}.\n\nRegards,\n{sender}",
            f"Subject: Action Required: {event}\n\nDear {receiver},\n\nAs discussed, we need your approval for the budget allocation for the upcoming {event} in {place}. {org} is waiting for our confirmation.\n\nThanks,\n{sender}"
        ]
        
        content = random.choice(templates)
        timestamp = fake.date_time_this_year()
        
        return {
            "doc_id": doc_id,
            "type": "email",
            "content": content,
            "subject": content.split('\n')[0].replace('Subject: ', ''),
            "sender": sender,
            "receiver": receiver,
            "created_at": timestamp.isoformat(),
            "entities": self._extract_ground_truth_entities(content),
            "relations": self._extract_ground_truth_relations(content)
        }

    def _extract_ground_truth_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract ground truth entities from generated text."""
        entities = []
        
        # Simple pattern matching for ground truth
        for person in self.people:
            if person in text:
                entities.append({
                    "text": person,
                    "type": "PERSON",
                    "start_char": text.find(person),
                    "end_char": text.find(person) + len(person),
                    "canonical_name": person
                })
                
        for org in self.organizations:
            if org in text:
                entities.append({
                    "text": org,
                    "type": "ORG", 
                    "start_char": text.find(org),
                    "end_char": text.find(org) + len(org),
                    "canonical_name": org
                })
                
        for place in self.places:
            if place in text:
                entities.append({
                    "text": place,
                    "type": "PLACE",
                    "start_char": text.find(place),
                    "end_char": text.find(place) + len(place),
                    "canonical_name": place
                })
                
        for event in self.events:
            if event in text:
                entities.append({
                    "text": event,
                    "type": "EVENT",
                    "start_char": text.find(event),
                    "end_char": text.find(event) + len(event),
                    "canonical_name": event.title()
                })
                
        return entities

    def _extract_ground_truth_relations(self, text: str) -> List[Dict[str, Any]]:
        """Extract ground truth relations from generated text."""
        relations = []
        entities = self._extract_ground_truth_entities(text)
        
        # Simple relation extraction based on text patterns
        for entity in entities:
            if entity["type"] == "PERSON":
                # Look for role patterns
                role_start = text.find("the ", entity["end_char"])
                if role_start != -1 and role_start - entity["end_char"] < 20:
                    role_end = text.find(" of", role_start)
                    if role_end != -1:
                        role = text[role_start+4:role_end]
                        if role in self.roles:
                            # Find organization after "of"
                            org_start = text.find(" of ", role_end)
                            if org_start != -1:
                                org_end = text.find(".", org_start)
                                org_text = text[org_start+4:org_end].strip()
                                for org_entity in entities:
                                    if org_entity["type"] == "ORG" and org_entity["text"] in org_text:
                                        relations.append({
                                            "subject": entity["text"],
                                            "object": org_entity["text"],
                                            "relation": "WORKS_FOR",
                                            "evidence": text[entity["start_char"]:org_end]
                                        })
                                        relations.append({
                                            "subject": entity["text"], 
                                            "object": org_entity["text"],
                                            "relation": "HAS_ROLE",
                                            "evidence": text[entity["start_char"]:org_end]
                                        })
        
        return relations

    def generate_dataset(self, num_docs: int = 20):
        """Generate a mixed dataset of news articles and emails."""
        documents = []
        
        for i in range(num_docs):
            doc_id = f"doc_{i:04d}"
            if random.random() > 0.5:
                doc = self.generate_news_article(doc_id)
            else:
                doc = self.generate_email(doc_id)
            documents.append(doc)
            
            # Save individual files
            output_file = self.output_dir / f"{doc_id}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(doc, f, indent=2)
                
        # Save combined dataset
        combined_file = self.output_dir / "synthetic_text_dataset.jsonl"
        with open(combined_file, 'w', encoding='utf-8') as f:
            for doc in documents:
                f.write(json.dumps(doc) + '\n')
                
        # Save ground truth for evaluation
        ground_truth = {
            "entities": [e for doc in documents for e in doc["entities"]],
            "relations": [r for doc in documents for r in doc["relations"]]
        }
        
        gt_file = self.output_dir / "ground_truth.json"
        with open(gt_file, 'w', encoding='utf-8') as f:
            json.dump(ground_truth, f, indent=2)
            
        print(f"Generated {num_docs} text documents in {self.output_dir}")
        return documents

if __name__ == "__main__":
    output_dir = Path("data/raw/text")
    generator = TextDataGenerator(output_dir)
    generator.generate_dataset(5)  # Smaller dataset for testing