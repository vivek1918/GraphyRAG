#!/usr/bin/env python3
"""
Synthetic video generator using image sequences and audio.
Generates presentation videos and interview clips.
"""

import json
import random
from datetime import datetime
from typing import Dict 
from pathlib import Path
from faker import Faker

fake = Faker()
random.seed(42)

class VideoDataGenerator:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.organizations = [
            "TechCorp", "Global Bank", "MediPharm", "EduFoundation"
        ]
        
        self.people = [
            "John Smith", "Maria Garcia", "David Chen", "Sarah Johnson"
        ]
        
        self.places = ["New York", "San Francisco", "London", "Tokyo"]

    def generate_presentation_video(self, doc_id: str) -> Dict:
        """Generate synthetic presentation video metadata."""
        presenter = random.choice(self.people)
        org = random.choice(self.organizations)
        topic = random.choice(["AI Strategy", "Market Analysis", "Product Roadmap"])
        location = random.choice(self.places)
        
        # Create slide content
        slides = [
            f"Welcome to {org} {topic} Presentation",
            f"Presented by {presenter}",
            f"Key Initiatives for Q3",
            f"Market Opportunity in {location}",
            f"Thank You"
        ]
        
        transcript = f"Hello, I'm {presenter} from {org}. Today I'll be discussing our {topic}. We see significant opportunities in the {location} market."
        
        # For synthetic data, we'll create metadata but not actual video files
        # In a real implementation, you'd use moviepy or similar to generate videos
        
        video_path = self.output_dir / f"{doc_id}.mp4"
        
        # Create a placeholder file
        with open(video_path, 'w') as f:
            f.write("Synthetic video placeholder")
        
        return {
            "doc_id": doc_id,
            "type": "presentation",
            "file_path": str(video_path),
            "content": transcript,
            "slides": slides,
            "duration": 300,  # 5 minutes
            "entities": [
                {"text": presenter, "type": "PERSON", "canonical_name": presenter},
                {"text": org, "type": "ORG", "canonical_name": org},
                {"text": location, "type": "PLACE", "canonical_name": location},
                {"text": topic, "type": "CONCEPT", "canonical_name": topic}
            ],
            "relations": [
                {
                    "subject": presenter,
                    "object": org,
                    "relation": "WORKS_FOR",
                    "evidence": f"{presenter} from {org}"
                },
                {
                    "subject": org,
                    "object": topic,
                    "relation": "HAS_TOPIC",
                    "evidence": f"{org} presentation about {topic}"
                }
            ]
        }

    def generate_interview_video(self, doc_id: str) -> Dict:
        """Generate synthetic interview video metadata."""
        interviewer = random.choice(self.people)
        interviewee = random.choice([p for p in self.people if p != interviewer])
        org = random.choice(self.organizations)
        topic = random.choice(["career journey", "industry trends", "leadership insights"])
        
        transcript_parts = [
            f"{interviewer}: Welcome to our interview series. Today we're speaking with {interviewee} from {org}.",
            f"{interviewee}: Thank you for having me. I'm excited to discuss my {topic}.",
            f"{interviewer}: Could you tell us about your experience at {org}?",
            f"{interviewee}: Certainly. Working at {org} has been incredibly rewarding.",
            f"{interviewer}: What advice would you give to aspiring professionals?",
            f"{interviewee}: Focus on continuous learning and building strong relationships."
        ]
        
        transcript = " ".join(transcript_parts)
        
        video_path = self.output_dir / f"{doc_id}.mp4"
        
        # Create placeholder
        with open(video_path, 'w') as f:
            f.write("Synthetic video placeholder")
        
        return {
            "doc_id": doc_id,
            "type": "interview",
            "file_path": str(video_path),
            "content": transcript,
            "duration": 600,  # 10 minutes
            "participants": [interviewer, interviewee],
            "entities": [
                {"text": interviewer, "type": "PERSON", "canonical_name": interviewer},
                {"text": interviewee, "type": "PERSON", "canonical_name": interviewee},
                {"text": org, "type": "ORG", "canonical_name": org}
            ],
            "relations": [
                {
                    "subject": interviewee,
                    "object": org,
                    "relation": "WORKS_FOR",
                    "evidence": f"{interviewee} from {org}"
                }
            ]
        }

    def generate_dataset(self, num_docs: int = 8):
        """Generate a dataset of synthetic video metadata."""
        documents = []
        
        for i in range(num_docs):
            doc_id = f"video_{i:04d}"
            if random.random() > 0.5:
                doc = self.generate_presentation_video(doc_id)
            else:
                doc = self.generate_interview_video(doc_id)
            documents.append(doc)
            
            # Save metadata
            meta_file = self.output_dir / f"{doc_id}.json"
            with open(meta_file, 'w') as f:
                json.dump(doc, f, indent=2)
                
        print(f"Generated {num_docs} video documents in {self.output_dir}")
        return documents

if __name__ == "__main__":
    output_dir = Path("data/raw/video")
    generator = VideoDataGenerator(output_dir)
    generator.generate_dataset(5)