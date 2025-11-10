#!/usr/bin/env python3
"""
Synthetic image generator with text overlays for OCR testing.
Generates business cards, receipts, and document scans.
"""

import json
import random
from datetime import datetime
from pathlib import Path
from faker import Faker
from typing import Dict 
from PIL import Image, ImageDraw, ImageFont
import numpy as np

fake = Faker()
random.seed(42)

class ImageDataGenerator:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.organizations = [
            "TechCorp Inc", "Global Bank", "MediPharm", "EduFoundation"
        ]
        
        self.people = [
            "John Smith", "Maria Garcia", "David Chen", "Sarah Johnson"
        ]
        
        self.places = ["New York", "San Francisco", "London", "Tokyo"]
        
        # Try to load a font, fallback to default
        try:
            self.font = ImageFont.truetype("arial.ttf", 20)
            self.small_font = ImageFont.truetype("arial.ttf", 14)
        except:
            self.font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()

    def generate_business_card(self, doc_id: str) -> Dict:
        """Generate a synthetic business card image."""
        person = random.choice(self.people)
        org = random.choice(self.organizations)
        role = random.choice(["CEO", "CTO", "CFO", "Director"])
        phone = fake.phone_number()
        email = fake.email()
        address = fake.address().replace('\n', ', ')
        
        # Create image
        img = Image.new('RGB', (400, 250), color='white')
        draw = ImageDraw.Draw(img)
        
        # Add some background noise
        self._add_noise(img, intensity=5)
        
        # Draw content
        draw.text((20, 20), person, fill='black', font=self.font)
        draw.text((20, 50), role, fill='gray', font=self.small_font)
        draw.text((20, 70), org, fill='darkblue', font=self.small_font)
        draw.text((20, 100), f"Phone: {phone}", fill='black', font=self.small_font)
        draw.text((20, 120), f"Email: {email}", fill='black', font=self.small_font)
        draw.text((20, 140), f"Address: {address}", fill='black', font=self.small_font)
        
        # Add some decorative elements
        draw.rectangle([15, 15, 385, 235], outline='black', width=2)
        
        img_path = self.output_dir / f"{doc_id}.png"
        img.save(img_path)
        
        content = f"{person}\n{role}\n{org}\nPhone: {phone}\nEmail: {email}\nAddress: {address}"
        
        return {
            "doc_id": doc_id,
            "type": "business_card",
            "file_path": str(img_path),
            "content": content,
            "entities": [
                {"text": person, "type": "PERSON", "canonical_name": person},
                {"text": org, "type": "ORG", "canonical_name": org},
                {"text": role, "type": "CONCEPT", "canonical_name": role}
            ],
            "relations": [
                {
                    "subject": person,
                    "object": org,
                    "relation": "WORKS_FOR", 
                    "evidence": f"{person} works at {org}"
                },
                {
                    "subject": person,
                    "object": role,
                    "relation": "HAS_ROLE",
                    "evidence": f"{person} is {role}"
                }
            ]
        }

    def generate_receipt(self, doc_id: str) -> Dict:
        """Generate a synthetic receipt image."""
        store = random.choice(["TechStore", "OfficeSupplies", "BookShop", "Cafe"])
        location = random.choice(self.places)
        items = [
            ("Laptop", "1299.99"),
            ("Mouse", "29.99"), 
            ("Keyboard", "79.99"),
            ("Monitor", "399.99")
        ]
        
        total = sum(float(price) for _, price in items)
        
        # Create image
        img = Image.new('RGB', (300, 400), color='white')
        draw = ImageDraw.Draw(img)
        
        # Add background pattern
        self._add_receipt_texture(img)
        
        # Draw content
        draw.text((20, 20), f"RECEIPT - {store}", fill='black', font=self.font)
        draw.text((20, 50), f"Location: {location}", fill='gray', font=self.small_font)
        draw.text((20, 70), f"Date: {datetime.now().strftime('%Y-%m-%d')}", fill='gray', font=self.small_font)
        
        y_pos = 100
        for item, price in items:
            draw.text((20, y_pos), f"{item}: ${price}", fill='black', font=self.small_font)
            y_pos += 20
            
        draw.text((20, y_pos + 10), f"TOTAL: ${total:.2f}", fill='black', font=self.font)
        
        img_path = self.output_dir / f"{doc_id}.png"
        img.save(img_path)
        
        content = f"RECEIPT - {store}\nLocation: {location}\n"
        for item, price in items:
            content += f"{item}: ${price}\n"
        content += f"TOTAL: ${total:.2f}"
        
        return {
            "doc_id": doc_id,
            "type": "receipt",
            "file_path": str(img_path), 
            "content": content,
            "entities": [
                {"text": store, "type": "ORG", "canonical_name": store},
                {"text": location, "type": "PLACE", "canonical_name": location}
            ],
            "relations": [
                {
                    "subject": store,
                    "object": location, 
                    "relation": "LOCATED_IN",
                    "evidence": f"Store located in {location}"
                }
            ]
        }

    def _add_noise(self, img: Image.Image, intensity: int = 5):
        """Add random noise to image to simulate real-world conditions."""
        arr = np.array(img)
        noise = np.random.randint(-intensity, intensity, arr.shape, dtype='int16')
        arr = np.clip(arr + noise, 0, 255).astype('uint8')
        img.putdata([tuple(pixel) for pixel in arr.reshape(-1, 3)])

    def _add_receipt_texture(self, img: Image.Image):
        """Add receipt-like texture to image."""
        arr = np.array(img)
        height, width = arr.shape[:2]
        
        # Add horizontal lines
        for y in range(0, height, 3):
            if random.random() > 0.7:
                arr[y:y+1, :] = [200, 200, 200]
                
        img.putdata([tuple(pixel) for pixel in arr.reshape(-1, 3)])

    def generate_dataset(self, num_docs: int = 15):
        """Generate a dataset of synthetic images."""
        documents = []
        
        for i in range(num_docs):
            doc_id = f"img_{i:04d}"
            if random.random() > 0.5:
                doc = self.generate_business_card(doc_id)
            else:
                doc = self.generate_receipt(doc_id)
            documents.append(doc)
            
            # Save metadata
            meta_file = self.output_dir / f"{doc_id}.json"
            with open(meta_file, 'w') as f:
                json.dump(doc, f, indent=2)
                
        print(f"Generated {num_docs} image documents in {self.output_dir}")
        return documents

if __name__ == "__main__":
    output_dir = Path("data/raw/img")
    generator = ImageDataGenerator(output_dir)
    generator.generate_dataset(8)