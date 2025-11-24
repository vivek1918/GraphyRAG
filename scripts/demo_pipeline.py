#!/usr/bin/env python3
"""
Enhanced demo pipeline for the semantic knowledge graph system.
Actually processes multi-modal file contents.
"""

import asyncio
import json
import time
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from loguru import logger

class DemoPipeline:
    def __init__(self, data_dir: Path = Path("data"), use_existing_data: bool = True):
        self.data_dir = data_dir
        self.raw_dir = data_dir / "raw"
        self.interim_dir = data_dir / "interim"
        self.processed_dir = data_dir / "processed"
        self.use_existing_data = use_existing_data
        
        # Create directories
        for dir_path in [self.raw_dir, self.interim_dir, self.processed_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            
    def _discover_existing_files(self) -> Dict[str, List[Dict]]:
        """Discover existing files in the raw data directory."""
        datasets = {}
        
        # Define modality directories and their file extensions
        modality_config = {
            'text': {
                'dir': self.raw_dir / "text",
                'extensions': ['.txt', '.md', '.json', '.xml', '.csv', '.html']
            },
            'audio': {
                'dir': self.raw_dir / "audio", 
                'extensions': ['.wav', '.mp3', '.m4a', '.flac', '.aac', '.ogg']
            },
            'image': {
                'dir': self.raw_dir / "img",
                'extensions': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
            },
            'pdf': {
                'dir': self.raw_dir / "pdf",
                'extensions': ['.pdf']
            },
            'video': {
                'dir': self.raw_dir / "video",
                'extensions': ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']
            }
        }
        
        for modality, config in modality_config.items():
            modality_dir = config['dir']
            datasets[modality] = []
            
            if modality_dir.exists():
                for ext in config['extensions']:
                    for file_path in modality_dir.glob(f"*{ext}"):
                        doc = {
                            "doc_id": f"{modality}_{file_path.stem}",
                            "type": f"{modality}_document",
                            "file_path": str(file_path),
                            "file_type": modality,
                            "file_name": file_path.name,
                            "title": file_path.stem,
                            "source": "existing_dataset",
                            "created_at": datetime.now().isoformat()
                        }
                        datasets[modality].append(doc)
                
                if datasets[modality]:
                    logger.info(f"Found {len(datasets[modality])} {modality} files in {modality_dir}")
            else:
                logger.warning(f"Directory not found: {modality_dir}")
        
        return datasets

    async def generate_data(self) -> Dict[str, List[Dict]]:
        """Load existing multi-modal data."""
        logger.info("Using existing multi-modal data from disk...")
        datasets = self._discover_existing_files()
        
        # Check if we found any data
        total_files = sum(len(docs) for docs in datasets.values())
        if total_files == 0:
            logger.warning("No existing files found. Creating minimal dataset...")
            datasets = self._create_minimal_dataset()
        else:
            logger.info(f"Loaded {total_files} files across {len(datasets)} modalities")
            
        return datasets

    async def preprocess_multimodal_data(self, datasets: Dict[str, List[Dict]]) -> List[Dict]:
        """Preprocess multi-modal data to extract text content."""
        logger.info("Preprocessing multi-modal data...")
        
        processed_docs = []
        
        for modality, docs in datasets.items():
            logger.info(f"Processing {len(docs)} {modality} documents...")
            
            for doc in docs:
                try:
                    # Actually process the file content
                    processed_doc = await self._process_file_content(doc)
                    processed_doc['source_type'] = modality
                    processed_doc['file_type'] = modality
                    processed_docs.append(processed_doc)
                    logger.debug(f"Processed {modality} document: {doc['doc_id']}")
                    
                except Exception as e:
                    logger.error(f"Error processing {modality} document {doc['doc_id']}: {e}")
                    # Create fallback document with filename analysis
                    fallback_doc = await self._analyze_filename(doc)
                    processed_docs.append(fallback_doc)
        
        # Save processed documents
        processed_file = self.interim_dir / "processed_documents.jsonl"
        with open(processed_file, 'w', encoding='utf-8') as f:
            for doc in processed_docs:
                f.write(json.dumps(doc) + '\n')
                
        logger.info(f"Processed {len(processed_docs)} documents across all modalities")
        return processed_docs

    async def _process_file_content(self, doc: Dict) -> Dict:
        """Actually process file content based on modality."""
        file_path = Path(doc['file_path'])
        modality = doc['file_type']
        
        if modality == 'text':
            return await self._process_text_file(doc, file_path)
        elif modality == 'pdf':
            return await self._process_pdf_file(doc, file_path)
        elif modality == 'image':
            return await self._process_image_file(doc, file_path)
        elif modality == 'audio':
            return await self._process_audio_file(doc, file_path)
        elif modality == 'video':
            return await self._process_video_file(doc, file_path)
        else:
            return await self._analyze_filename(doc)

    async def _process_text_file(self, doc: Dict, file_path: Path) -> Dict:
        """Process text files."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            doc['content'] = content
            doc['metadata'] = {
                'source_type': 'text',
                'processing_method': 'direct_read',
                'file_size': file_path.stat().st_size
            }
        except Exception as e:
            doc['content'] = f"Error reading text file: {str(e)}"
            doc['metadata'] = {'error': str(e)}
        return doc

    async def _process_pdf_file(self, doc: Dict, file_path: Path) -> Dict:
        """Process PDF files with basic text extraction."""
        try:
            # Try to extract text from PDF
            content = await self._extract_pdf_text(file_path)
            if content:
                doc['content'] = content
                doc['metadata'] = {
                    'source_type': 'pdf',
                    'processing_method': 'pdf_extraction',
                    'file_size': file_path.stat().st_size
                }
            else:
                doc = await self._analyze_filename(doc)
                doc['metadata']['processing_method'] = 'filename_analysis_only'
        except Exception as e:
            doc = await self._analyze_filename(doc)
            doc['metadata']['error'] = str(e)
        return doc

    async def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF files."""
        try:
            # Try PyPDF2 first
            import PyPDF2
            text = ""
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            return text.strip()
        except ImportError:
            logger.warning("PyPDF2 not installed for PDF text extraction")
        except Exception as e:
            logger.warning(f"PDF text extraction failed: {e}")
        
        return ""

    async def _process_image_file(self, doc: Dict, file_path: Path) -> Dict:
        """Process image files with filename analysis."""
        doc = await self._analyze_filename(doc)
        doc['metadata']['processing_method'] = 'filename_analysis'
        doc['metadata']['file_size'] = file_path.stat().st_size
        return doc

    async def _process_audio_file(self, doc: Dict, file_path: Path) -> Dict:
        """Process audio files with filename analysis."""
        doc = await self._analyze_filename(doc)
        doc['metadata']['processing_method'] = 'filename_analysis'
        doc['metadata']['file_size'] = file_path.stat().st_size
        return doc

    async def _process_video_file(self, doc: Dict, file_path: Path) -> Dict:
        """Process video files with filename analysis."""
        doc = await self._analyze_filename(doc)
        doc['metadata']['processing_method'] = 'filename_analysis'
        doc['metadata']['file_size'] = file_path.stat().st_size
        return doc

    async def _analyze_filename(self, doc: Dict) -> Dict:
        """Extract information from filename for entities."""
        filename = doc['file_name']
        title = doc['title']
        
        # Extract potential entities from filename
        content_parts = []
        
        # Common patterns in filenames
        patterns = {
            'duration': r'(\d+)\s*min\w*',
            'type': r'(meditation|yoga|guided|session|beginners|morning|stress|health|wellbeing)',
            'difficulty': r'(beginner|intermediate|advanced|simple|gentle)',
            'time': r'(morning|evening|daily)'
        }
        
        extracted_info = {}
        for key, pattern in patterns.items():
            matches = re.findall(pattern, filename.lower())
            if matches:
                extracted_info[key] = matches[0] if matches else matches
        
        # Build content from filename analysis
        content_parts.append(f"Title: {title}")
        if extracted_info.get('type'):
            content_parts.append(f"Type: {extracted_info['type']}")
        if extracted_info.get('duration'):
            content_parts.append(f"Duration: {extracted_info['duration']} minutes")
        if extracted_info.get('difficulty'):
            content_parts.append(f"Difficulty: {extracted_info['difficulty']}")
        if extracted_info.get('time'):
            content_parts.append(f"Recommended time: {extracted_info['time']}")
        
        doc['content'] = ". ".join(content_parts)
        doc['metadata'] = {
            'source_type': doc['file_type'],
            'processing_method': 'filename_analysis',
            'extracted_info': extracted_info
        }
        
        return doc

    async def extract_entities_relations(self, processed_docs: List[Dict]) -> List[Dict]:
        """Enhanced entity and relation extraction."""
        logger.info("Performing enhanced entity and relation extraction...")
        
        enriched_docs = []
        
        for doc in processed_docs:
            try:
                # Extract entities from content
                entities = await self._enhanced_entity_extraction(doc)
                
                # Extract relations
                relations = await self._enhanced_relation_extraction(doc, entities)
                
                doc['extracted_entities'] = entities
                doc['extracted_relations'] = relations
                doc['domain_classification'] = {
                    'domain': self._classify_domain(doc),
                    'confidence': 0.7,
                    'reasoning': 'Content and filename analysis'
                }
                
                enriched_docs.append(doc)
                logger.info(f"Extracted {len(entities)} entities and {len(relations)} relations from {doc['doc_id']}")
                
            except Exception as e:
                logger.error(f"Error extracting from {doc['doc_id']}: {e}")
                doc['extracted_entities'] = []
                doc['extracted_relations'] = []
                enriched_docs.append(doc)
        
        return enriched_docs

    async def _enhanced_entity_extraction(self, doc: Dict) -> List[Dict]:
        """Enhanced entity extraction from content and metadata."""
        content = doc.get('content', '')
        filename = doc.get('file_name', '')
        modality = doc.get('file_type', '')
        
        entities = []
        
        # Extract from content
        content_entities = await self._extract_entities_from_text(content)
        entities.extend(content_entities)
        
        # Extract from filename
        filename_entities = await self._extract_entities_from_filename(filename, modality)
        entities.extend(filename_entities)
        
        # Extract from metadata
        metadata = doc.get('metadata', {})
        if 'extracted_info' in metadata:
            info_entities = await self._extract_entities_from_metadata(metadata['extracted_info'])
            entities.extend(info_entities)
        
        return entities

    async def _extract_entities_from_text(self, text: str) -> List[Dict]:
        """Extract entities from text content."""
        entities = []
        
        patterns = {
            'ACTIVITY': [
                r'\b(meditation|yoga|breathing|mindfulness|relaxation)\b',
                r'\b(guided|session|practice|exercise)\b'
            ],
            'DURATION': [
                r'(\d+)\s*min\w*',
                r'duration\s*:\s*(\d+)',
                r'(\d+)\s*minutes?'
            ],
            'DIFFICULTY': [
                r'\b(beginner|intermediate|advanced|simple|gentle)\b',
                r'\b(easy|hard|challenging)\b'
            ],
            'BENEFIT': [
                r'\b(stress|relax|calm|focus|health|wellbeing|mind)\b',
                r'\b(anxiety|sleep|energy|peace)\b'
            ],
            'TIME': [
                r'\b(morning|evening|daily|night)\b'
            ]
        }
        
        for entity_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.finditer(pattern, text.lower())
                for match in matches:
                    entity_text = match.group(1) if match.groups() else match.group()
                    entities.append({
                        'text': entity_text,
                        'type': entity_type,
                        'start_char': match.start(),
                        'end_char': match.end(),
                        'confidence': 0.8,
                        'canonical_name': entity_text.title(),
                        'modality': 'text'
                    })
        
        return entities

    async def _extract_entities_from_filename(self, filename: str, modality: str) -> List[Dict]:
        """Extract entities from filename."""
        entities = []
        filename_lower = filename.lower()
        
        # Common entities in wellness filenames
        wellness_terms = {
            'ACTIVITY': ['yoga', 'meditation', 'mindfulness', 'breathing'],
            'DURATION': [r'(\d+)\s*min'],
            'DIFFICULTY': ['beginner', 'intermediate', 'advanced', 'simple', 'gentle'],
            'BENEFIT': ['stress', 'relax', 'calm', 'health', 'wellbeing'],
            'TIME': ['morning', 'evening', 'daily']
        }
        
        for entity_type, terms in wellness_terms.items():
            for term in terms:
                if re.search(term, filename_lower):
                    match = re.search(term, filename_lower)
                    entity_text = match.group(1) if match.groups() else term
                    entities.append({
                        'text': entity_text,
                        'type': entity_type,
                        'confidence': 0.9,
                        'canonical_name': entity_text.title(),
                        'modality': modality,
                        'source': 'filename'
                    })
        
        return entities

    async def _extract_entities_from_metadata(self, metadata: Dict) -> List[Dict]:
        """Extract entities from metadata."""
        entities = []
        
        type_map = {
            'duration': 'DURATION',
            'type': 'ACTIVITY',
            'difficulty': 'DIFFICULTY',
            'time': 'TIME'
        }
        
        for key, value in metadata.items():
            if key in type_map and value:
                entity_type = type_map[key]
                entities.append({
                    'text': str(value),
                    'type': entity_type,
                    'confidence': 0.9,
                    'canonical_name': str(value).title(),
                    'modality': 'metadata',
                    'source': 'extracted_info'
                })
        
        return entities

    async def _enhanced_relation_extraction(self, doc: Dict, entities: List[Dict]) -> List[Dict]:
        """Enhanced relation extraction."""
        relations = []
        content = doc.get('content', '').lower()
        
        # Group entities by type for easier relation building
        entities_by_type = {}
        for entity in entities:
            entity_type = entity['type']
            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []
            entities_by_type[entity_type].append(entity)
        
        # Create relations based on common wellness patterns
        activities = entities_by_type.get('ACTIVITY', [])
        durations = entities_by_type.get('DURATION', [])
        difficulties = entities_by_type.get('DIFFICULTY', [])
        benefits = entities_by_type.get('BENEFIT', [])
        times = entities_by_type.get('TIME', [])
        
        # Activity-Duration relations
        if activities and durations:
            for activity in activities[:2]:  # Limit to first 2 activities
                for duration in durations[:2]:
                    relations.append({
                        'subject': activity['text'],
                        'object': duration['text'],
                        'relation': 'HAS_DURATION',
                        'confidence': 0.8,
                        'evidence': f"Activity {activity['text']} has duration {duration['text']}",
                        'subject_type': 'ACTIVITY',
                        'object_type': 'DURATION'
                    })
        
        # Activity-Difficulty relations
        if activities and difficulties:
            for activity in activities[:2]:
                for difficulty in difficulties[:2]:
                    relations.append({
                        'subject': activity['text'],
                        'object': difficulty['text'],
                        'relation': 'HAS_DIFFICULTY',
                        'confidence': 0.7,
                        'evidence': f"Activity {activity['text']} is for {difficulty['text']} level",
                        'subject_type': 'ACTIVITY',
                        'object_type': 'DIFFICULTY'
                    })
        
        # Activity-Benefit relations
        if activities and benefits:
            for activity in activities[:2]:
                for benefit in benefits[:3]:
                    relations.append({
                        'subject': activity['text'],
                        'object': benefit['text'],
                        'relation': 'PROVIDES_BENEFIT',
                        'confidence': 0.6,
                        'evidence': f"Activity {activity['text']} provides {benefit['text']} benefit",
                        'subject_type': 'ACTIVITY',
                        'object_type': 'BENEFIT'
                    })
        
        # Activity-Time relations
        if activities and times:
            for activity in activities[:2]:
                for time in times[:2]:
                    relations.append({
                        'subject': activity['text'],
                        'object': time['text'],
                        'relation': 'RECOMMENDED_AT',
                        'confidence': 0.6,
                        'evidence': f"Activity {activity['text']} recommended at {time['text']}",
                        'subject_type': 'ACTIVITY',
                        'object_type': 'TIME'
                    })
        
        return relations

    def _classify_domain(self, doc: Dict) -> str:
        """Classify document domain based on content."""
        content = doc.get('content', '').lower()
        filename = doc.get('file_name', '').lower()
        
        wellness_terms = ['yoga', 'meditation', 'mindfulness', 'relaxation', 'stress', 'health']
        research_terms = ['study', 'research', 'paper', 'methodology', 'results']
        
        if any(term in content or term in filename for term in wellness_terms):
            return 'wellness'
        elif any(term in content or term in filename for term in research_terms):
            return 'research_paper'
        else:
            return 'general'
        
    async def load_into_neo4j(self, kg_data: Dict):
        """Load knowledge graph data into Neo4j."""
        try:
            from neo4j import GraphDatabase
            import yaml
            
            # Load configuration
            config_path = Path(__file__).parent.parent / "conf" / "settings.yaml"
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            neo4j_config = config.get('kg', {})
            uri = neo4j_config.get('neo4j_url', 'bolt://localhost:7687')
            user = neo4j_config.get('neo4j_user', 'neo4j')
            password = neo4j_config.get('neo4j_password', 'password')
            
            logger.info(f"Connecting to Neo4j at {uri}...")
            
            driver = GraphDatabase.driver(uri, auth=(user, password))
            
            # Clear existing data first
            with driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
                logger.info("Cleared existing Neo4j data")
            
            # Load new data
            nodes_created = 0
            relationships_created = 0
            
            with driver.session() as session:
                # Create nodes
                for item in kg_data["@graph"]:
                    if "@type" in item and "subject" not in item:  # It's a node
                        query = """
                        CREATE (n:%s {
                            id: $id,
                            name: $name,
                            type: $type,
                            modality: $modality,
                            confidence: $confidence,
                            sourceDocument: $sourceDocument
                        })
                        """ % item["@type"]
                        
                        session.run(query, {
                            'id': item["@id"],
                            'name': item["name"],
                            'type': item["@type"],
                            'modality': item.get("modality", "unknown"),
                            'confidence': item.get("confidence", 0.5),
                            'sourceDocument': item.get("sourceDocument", "unknown")
                        })
                        nodes_created += 1
                
                # Create relationships
                for item in kg_data["@graph"]:
                    if "subject" in item:  # It's a relationship
                        query = """
                        MATCH (a {id: $subject_id}), (b {id: $object_id})
                        CREATE (a)-[r:%s {
                            id: $rel_id,
                            confidence: $confidence,
                            evidence: $evidence,
                            sourceDocument: $sourceDocument
                        }]->(b)
                        """ % item["@type"]
                        
                        session.run(query, {
                            'subject_id': item["subject"],
                            'object_id': item["object"],
                            'rel_id': item["@id"],
                            'confidence': item.get("confidence", 0.5),
                            'evidence': item.get("evidence", ""),
                            'sourceDocument': item.get("sourceDocument", "unknown")
                        })
                        relationships_created += 1
            
            driver.close()
            logger.info(f"Loaded {nodes_created} nodes and {relationships_created} relationships into Neo4j")
            return nodes_created, relationships_created
            
        except ImportError:
            logger.error("neo4j package not installed. Run: pip install neo4j")
            return 0, 0
        except Exception as e:
            logger.error(f"Failed to load data into Neo4j: {e}")
            return 0, 0

    async def build_knowledge_graph(self, enriched_docs: List[Dict]):
        """Build knowledge graph representation and load into Neo4j."""
        logger.info("Building knowledge graph representation...")
        
        # Create a simple JSON-LD representation
        kg_data = {
            "@context": {
                "Activity": "http://schema.org/ExercisePlan",
                "Duration": "http://schema.org/Duration",
                "Difficulty": "http://schema.org/difficulty",
                "Benefit": "http://schema.org/benefits",
                "Time": "http://schema.org/timeRequired",
                "hasDuration": "http://schema.org/timeRequired",
                "hasDifficulty": "http://schema.org/difficulty",
                "providesBenefit": "http://schema.org/benefits",
                "recommendedAt": "http://schema.org/timeOfDay"
            },
            "@graph": []
        }
        
        entities_added = set()
        relations_added = set()
        
        for doc in enriched_docs:
            # Add entities
            for entity in doc.get('extracted_entities', []):
                entity_id = f"{entity['type']}_{hash(entity['text'])}"
                if entity_id not in entities_added:
                    kg_entity = {
                        "@id": entity_id,
                        "@type": entity['type'],
                        "name": entity['text'],
                        "modality": doc.get('file_type', 'text'),
                        "confidence": entity.get('confidence', 0.5),
                        "sourceDocument": doc['doc_id']
                    }
                    kg_data["@graph"].append(kg_entity)
                    entities_added.add(entity_id)
            
            # Add relations
            for relation in doc.get('extracted_relations', []):
                relation_id = f"rel_{hash(relation['subject'] + relation['object'] + relation['relation'])}"
                if relation_id not in relations_added:
                    subject_id = f"{relation['subject_type']}_{hash(relation['subject'])}"
                    object_id = f"{relation['object_type']}_{hash(relation['object'])}"
                    
                    kg_relation = {
                        "@id": relation_id,
                        "@type": relation['relation'],
                        "subject": subject_id,
                        "object": object_id,
                        "confidence": relation['confidence'],
                        "evidence": relation.get('evidence', ''),
                        "sourceDocument": doc['doc_id']
                    }
                    kg_data["@graph"].append(kg_relation)
                    relations_added.add(relation_id)
        
        # Save KG data to file
        kg_file = self.processed_dir / "knowledge_graph.json"
        with open(kg_file, 'w', encoding='utf-8') as f:
            json.dump(kg_data, f, indent=2)
        
        # Load into Neo4j
        nodes_created, relationships_created = await self.load_into_neo4j(kg_data)
        
        stats = {
            'total_entities': len(entities_added),
            'total_relations': len(relations_added),
            'total_triples': len(kg_data["@graph"]),
            'documents': len(enriched_docs),
            'neo4j_nodes': nodes_created,
            'neo4j_relationships': relationships_created
        }
        
        logger.info(f"Built knowledge graph with {stats['total_entities']} entities and {stats['total_relations']} relations")
        logger.info(f"Neo4j: {nodes_created} nodes and {relationships_created} relationships loaded")
        
        return stats

    async def demo_graph_rag(self, stats: Dict):
        """Enhanced demo with actual results."""
        kg_file = self.processed_dir / "knowledge_graph.json"
        
        print("\n" + "="*70)
        print("🤖 Enhanced Knowledge Graph Demo")
        print("="*70)
        print(f"\n📊 Results from your wellness dataset:")
        print(f"   • Entities extracted: {stats['total_entities']}")
        print(f"   • Relations found: {stats['total_relations']}")
        print(f"   • Neo4j nodes loaded: {stats.get('neo4j_nodes', 0)}")
        print(f"   • Neo4j relationships loaded: {stats.get('neo4j_relationships', 0)}")
        
        if kg_file.exists():
            with open(kg_file, 'r', encoding='utf-8') as f:
                kg_data = json.load(f)
            
            entities = [e for e in kg_data["@graph"] if "@type" in e and e["@type"] in ["ACTIVITY", "DURATION", "DIFFICULTY", "BENEFIT", "TIME"]]
            relations = [r for r in kg_data["@graph"] if "subject" in r]
            
            if entities:
                print(f"\n🏷️  Sample Entities:")
                for entity in entities[:5]:
                    print(f"   • {entity['@type']}: {entity['name']} (from {entity.get('modality', 'unknown')})")
            
            if relations:
                print(f"\n🔗 Sample Relations:")
                for relation in relations[:5]:
                    # Get readable names for subjects and objects
                    subject_name = next((e['name'] for e in entities if e['@id'] == relation['subject']), relation['subject'])
                    object_name = next((e['name'] for e in entities if e['@id'] == relation['object']), relation['object'])
                    print(f"   • {subject_name} → {relation['@type']} → {object_name}")
        
        print(f"\n💡 Check Neo4j Browser at: http://localhost:7474")
        print(f"   Query: MATCH (n) RETURN n LIMIT 25")
        print("\n" + "="*70)

    async def generate_report(self, stats: Dict[str, Any]):
        """Generate demo report."""
        logger.info("Generating demo report...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "pipeline_stats": stats,
            "components_used": [
                "FileDiscovery",
                "ContentExtraction", 
                "EnhancedEntityExtraction",
                "RelationExtraction",
                "JSONLD_KG"
            ],
            "status": "completed_enhanced",
            "note": "Enhanced pipeline with actual content processing and entity extraction"
        }
        
        report_file = self.processed_dir / "demo_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Demo report saved to {report_file}")

    async def run(self):
        """Run the enhanced demo pipeline."""
        logger.info("Starting Enhanced Demo Pipeline")
        start_time = time.time()
        
        try:
            # 1. Generate/Load multi-modal data
            datasets = await self.generate_data()
            
            # 2. Preprocess data with actual content extraction
            processed_docs = await self.preprocess_multimodal_data(datasets)
            
            # 3. Extract entities and relations
            enriched_docs = await self.extract_entities_relations(processed_docs)
            
            # 4. Build knowledge graph
            kg_stats = await self.build_knowledge_graph(enriched_docs)
            
            # 5. Demo capabilities with actual results
            # fixed
            await self.demo_graph_rag(kg_stats)

            
            # 6. Generate report
            await self.generate_report(kg_stats)
            
            elapsed_time = time.time() - start_time
            logger.success(f"Enhanced demo pipeline completed in {elapsed_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Demo pipeline failed: {e}")
            # Generate error report
            error_report = {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "status": "failed"
            }
            report_file = self.processed_dir / "error_report.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(error_report, f, indent=2)
            raise

async def main():
    """Main entry point for the demo pipeline."""
    # Configure logging
    from loguru import logger
    logger.remove()  # Remove default handler
    logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
    
    pipeline = DemoPipeline(use_existing_data=True)
    await pipeline.run()

if __name__ == "__main__":
    asyncio.run(main())