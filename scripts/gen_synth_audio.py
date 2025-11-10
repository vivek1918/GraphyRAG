#!/usr/bin/env python3
"""
Synthetic audio data generator using TTS or tone generation.
Generates business meeting recordings and announcements.
"""

import json
import random
import wave
from typing import Dict 
import struct
import math
from datetime import datetime
from pathlib import Path
from faker import Faker

fake = Faker()
random.seed(42)

class AudioDataGenerator:
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

    def generate_sine_wave(self, freq: float, duration: float, sample_rate: int = 44100) -> bytes:
        """Generate a sine wave audio signal."""
        samples = []
        for i in range(int(duration * sample_rate)):
            sample = math.sin(2 * math.pi * freq * i / sample_rate)
            samples.append(sample)
        return struct.pack('<' + ('h' * len(samples)), *[int(s * 32767) for s in samples])

    def generate_meeting_audio(self, doc_id: str) -> Dict:
        """Generate synthetic meeting audio with metadata."""
        participants = random.sample(self.people, 3)
        org = random.choice(self.organizations)
        topic = random.choice(["Q3 Planning", "Budget Review", "Product Launch", "Team Sync"])
        
        # Create transcript
        transcript_parts = []
        for person in participants:
            statements = [
                f"I think we should focus on the {topic} for {org}.",
                f"Based on our analysis, the metrics look positive.",
                f"Let's discuss the timeline for implementation.",
                f"I'll follow up with the team in {random.choice(self.places)}."
            ]
            transcript_parts.append(f"{person}: {random.choice(statements)}")
        
        transcript = " ".join(transcript_parts)
        
        # Generate simple audio (sine waves representing speech-like patterns)
        audio_data = b''
        sample_rate = 44100
        
        # Generate different tones for different "speakers"
        freqs = [220, 440, 660]  # Different pitches for different speakers
        for i, freq in enumerate(freqs):
            audio_data += self.generate_sine_wave(freq, 2.0, sample_rate)
            # Add small silence between speakers
            audio_data += self.generate_sine_wave(0, 0.5, sample_rate)
        
        # Save audio file
        audio_path = self.output_dir / f"{doc_id}.wav"
        with wave.open(str(audio_path), 'wb') as wav_file:
            wav_file.setnchannels(1)  # mono
            wav_file.setsampwidth(2)  # 2 bytes per sample
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
        
        return {
            "doc_id": doc_id,
            "type": "meeting_audio",
            "file_path": str(audio_path),
            "content": transcript,
            "duration": 8.0,  # 3 speakers * 2s + 2 silences * 0.5s
            "participants": participants,
            "entities": [
                {"text": org, "type": "ORG", "canonical_name": org},
                *[{"text": p, "type": "PERSON", "canonical_name": p} for p in participants]
            ],
            "relations": [
                {
                    "subject": participant,
                    "object": org,
                    "relation": "WORKS_FOR",
                    "evidence": f"{participant} mentioned {org}"
                }
                for participant in participants
            ]
        }

    def generate_announcement_audio(self, doc_id: str) -> Dict:
        """Generate synthetic announcement audio."""
        person = random.choice(self.people)
        org = random.choice(self.organizations)
        event = random.choice(["earnings call", "product launch", "conference", "webinar"])
        location = random.choice(self.places)
        
        transcript = f"Hello, this is {person} from {org}. We're excited to announce our upcoming {event} in {location}. Please join us for important updates."
        
        # Generate audio
        audio_data = b''
        sample_rate = 44100
        
        # Simulate speech with varying frequencies
        base_freq = 220
        for i, char in enumerate(transcript):
            if char.isalpha():
                # Vary frequency slightly for each character
                freq = base_freq + (i % 10) * 20
                audio_data += self.generate_sine_wave(freq, 0.05, sample_rate)
            else:
                # Short pause for spaces/punctuation
                audio_data += self.generate_sine_wave(0, 0.02, sample_rate)
        
        audio_path = self.output_dir / f"{doc_id}.wav"
        with wave.open(str(audio_path), 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
        
        return {
            "doc_id": doc_id,
            "type": "announcement",
            "file_path": str(audio_path),
            "content": transcript,
            "duration": len(transcript) * 0.05,  # Rough estimate
            "entities": [
                {"text": person, "type": "PERSON", "canonical_name": person},
                {"text": org, "type": "ORG", "canonical_name": org},
                {"text": location, "type": "PLACE", "canonical_name": location},
                {"text": event, "type": "EVENT", "canonical_name": event}
            ],
            "relations": [
                {
                    "subject": person,
                    "object": org,
                    "relation": "WORKS_FOR",
                    "evidence": f"{person} from {org}"
                },
                {
                    "subject": event,
                    "object": location,
                    "relation": "LOCATED_IN", 
                    "evidence": f"event in {location}"
                }
            ]
        }

    def generate_dataset(self, num_docs: int = 10):
        """Generate a dataset of synthetic audio files."""
        documents = []
        
        for i in range(num_docs):
            doc_id = f"audio_{i:04d}"
            if random.random() > 0.5:
                doc = self.generate_meeting_audio(doc_id)
            else:
                doc = self.generate_announcement_audio(doc_id)
            documents.append(doc)
            
            # Save metadata
            meta_file = self.output_dir / f"{doc_id}.json"
            with open(meta_file, 'w') as f:
                json.dump(doc, f, indent=2)
                
        print(f"Generated {num_docs} audio documents in {self.output_dir}")
        return documents

if __name__ == "__main__":
    output_dir = Path("data/raw/audio")
    generator = AudioDataGenerator(output_dir)
    generator.generate_dataset(6)