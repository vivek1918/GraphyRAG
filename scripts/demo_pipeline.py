#!/usr/bin/env python3
"""
End-to-end demo pipeline for the semantic knowledge graph system.
Orchestrates data generation, processing, extraction, and KG building.
"""

import asyncio
import json
import time
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

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
            
        # Initialize components (import here to avoid circular imports)
        self._initialize_components()

    def _initialize_components(self):
        """Initialize all pipeline components."""
        try:
            # Synthetic generators kept optional; not used when use_existing_data=True
            if not self.use_existing_data:
                from scripts.gen_synth_text import TextDataGenerator
                from scripts.gen_synth_pdfs import PDFDataGenerator
                from scripts.gen_synth_images import ImageDataGenerator
                from scripts.gen_synth_audio import AudioDataGenerator
                from scripts.gen_synth_video import VideoDataGenerator

            from ingest.parse_text import TextParser
            from ingest.parse_pdf import PDFParser
            from ingest.parse_image_ocr import ImageParser
            from ingest.parse_audio_asr import AudioParser
            from ingest.parse_video import VideoParser

            from extract.ner import NERExtractor
            from extract.relation_extraction import RelationExtractor
            from extract.linker import EntityLinker

            from kg.build_triples import TripleBuilder
            from kg.fuseki_client import FusekiClient

            from rag.index_docs import DocumentIndexer
            from rag.graph_rag import GraphRAG
            
            if not self.use_existing_data:
                self.generators = {
                    'text': TextDataGenerator(self.raw_dir / "text"),
                    'pdf': PDFDataGenerator(self.raw_dir / "pdf"), 
                    'image': ImageDataGenerator(self.raw_dir / "img"),
                    'audio': AudioDataGenerator(self.raw_dir / "audio"),
                    'video': VideoDataGenerator(self.raw_dir / "video")
                }
            else:
                self.generators = {}  # Not used

            self.parsers = {
                'text': TextParser(),
                'pdf': PDFParser(),
                'image': ImageParser(),
                'audio': AudioParser(),
                'video': VideoParser()
            }
            
            self.extractors = {
                'ner': NERExtractor(),
                'relation': RelationExtractor(),
                'linker': EntityLinker()
            }
            
            self.kg_builder = TripleBuilder()
            self.fuseki_client = FusekiClient()
            self.indexer = DocumentIndexer()
            self.graph_rag = GraphRAG()
            
        except ImportError as e:
            logger.error(f"Failed to initialize components: {e}")
            raise

    def _find_pdf_dir(self) -> Path:
        # Prefer data/raw/pdf if populated, else data/pdf
        candidates = [self.raw_dir / "pdf", self.data_dir / "pdf"]
        for c in candidates:
            if c.exists() and any(c.glob("*.pdf")):
                return c
        # Fallback: create raw/pdf
        target = self.raw_dir / "pdf"
        target.mkdir(parents=True, exist_ok=True)
        return target

    def load_existing_pdfs(self) -> list[dict]:
        pdf_dir = self._find_pdf_dir()
        pdf_docs: list[dict] = []
        for f in sorted(pdf_dir.glob("*.pdf")):
            pdf_docs.append({
                "doc_id": f.stem,
                "type": "pdf_document",
                "file_path": str(f),        # used by PDFParser
                "title": f.stem,
                "source": "existing_dataset",
                "created_at": datetime.now().isoformat()
            })
        if not pdf_docs:
            logger.warning(f"No PDF files found in {pdf_dir}")
        else:
            logger.info(f"Loaded {len(pdf_docs)} existing PDF files from {pdf_dir}")
        return pdf_docs

    async def generate_data(self) -> Dict[str, List[Dict]]:
        """Load existing PDFs (and optionally other types) or generate synthetic."""
        if self.use_existing_data:
            logger.info("Using existing data from disk (PDFs only).")
            datasets: Dict[str, List[Dict]] = {}
            datasets['pdf'] = self.load_existing_pdfs()
            # Optional: load other modalities similarly if needed
            return datasets
        
        logger.info("Generating synthetic datasets...")
        
        datasets = {}
        
        try:
            # Generate text data
            datasets['text'] = self.generators['text'].generate_dataset(20)
            logger.info(f"Generated {len(datasets['text'])} text documents")
            
            # Generate PDFs
            datasets['pdf'] = self.generators['pdf'].generate_dataset(5)
            logger.info(f"Generated {len(datasets['pdf'])} PDF documents")
            
            # Generate images
            datasets['image'] = self.generators['image'].generate_dataset(4)
            logger.info(f"Generated {len(datasets['image'])} image documents")
            
            # Generate audio
            datasets['audio'] = self.generators['audio'].generate_dataset(3)
            logger.info(f"Generated {len(datasets['audio'])} audio documents")
            
            # Generate video
            datasets['video'] = self.generators['video'].generate_dataset(2)
            logger.info(f"Generated {len(datasets['video'])} video documents")
            
        except Exception as e:
            logger.error(f"Error generating data: {e}")
            # Create minimal dataset for demo
            datasets = self._create_minimal_dataset()
        
        return datasets

    def _create_minimal_dataset(self) -> Dict[str, List[Dict]]:
        """Create a minimal dataset when generators fail."""
        logger.info("Creating minimal dataset for demo...")
        
        minimal_text = [{
            "doc_id": "demo_doc_001",
            "type": "news_article",
            "content": "John Smith, the CEO of TechCorp Inc, announced the new product launch in New York. The event featured Maria Garcia from Global Bank.",
            "title": "TechCorp Product Launch",
            "source": "Demo Source",
            "created_at": datetime.now().isoformat(),
            "entities": [
                {"text": "John Smith", "type": "PERSON", "canonical_name": "John Smith"},
                {"text": "TechCorp Inc", "type": "ORG", "canonical_name": "TechCorp Inc"},
                {"text": "New York", "type": "PLACE", "canonical_name": "New York"},
                {"text": "Maria Garcia", "type": "PERSON", "canonical_name": "Maria Garcia"},
                {"text": "Global Bank", "type": "ORG", "canonical_name": "Global Bank"}
            ],
            "relations": [
                {"subject": "John Smith", "object": "TechCorp Inc", "relation": "WORKS_FOR", "evidence": "CEO of TechCorp Inc"},
                {"subject": "John Smith", "object": "TechCorp Inc", "relation": "HAS_ROLE", "evidence": "CEO of TechCorp Inc"}
            ]
        }]
        
        return {'text': minimal_text}

    async def parse_documents(self, datasets: Dict[str, List[Dict]]) -> List[Dict]:
        """Parse all documents to extract text content."""
        logger.info("Parsing documents...")
        
        parsed_docs = []
        
        for doc_type, docs in datasets.items():
            parser = self.parsers.get(doc_type)
            if not parser:
                logger.warning(f"No parser for document type: {doc_type}")
                # Use text parser as fallback
                parser = self.parsers['text']
                
            for doc in docs:
                try:
                    parsed_doc = await parser.parse(doc)
                    parsed_doc['source_type'] = doc_type
                    parsed_docs.append(parsed_doc)
                    logger.debug(f"Parsed {doc_type} document: {doc['doc_id']}")
                except Exception as e:
                    logger.error(f"Error parsing {doc_type} document {doc['doc_id']}: {e}")
                    # Create basic parsed document
                    basic_doc = {
                        'doc_id': doc['doc_id'],
                        'type': doc_type,
                        'content': doc.get('content', ''),
                        'metadata': {'source_type': doc_type},
                        'source_type': doc_type
                    }
                    parsed_docs.append(basic_doc)
        
        # Save parsed documents
        parsed_file = self.interim_dir / "parsed_documents.jsonl"
        with open(parsed_file, 'w', encoding='utf-8') as f:
            for doc in parsed_docs:
                f.write(json.dumps(doc) + '\n')
                
        logger.info(f"Parsed {len(parsed_docs)} documents total")
        return parsed_docs

    async def extract_entities_relations(self, parsed_docs: List[Dict]) -> List[Dict]:
        """Extract entities and relations from parsed documents."""
        logger.info("Extracting entities and relations...")

        enriched_docs: List[Dict] = []
        total = len(parsed_docs)
        total_entities = 0
        total_relations = 0
        t0 = time.perf_counter()

        for idx, doc in enumerate(parsed_docs, start=1):
            doc_id = doc.get("doc_id", f"doc_{idx}")
            content_len = len(doc.get("content", "") or "")
            try:
                # NER
                logger.info(f"[{idx}/{total}] NER start: {doc_id} (chars={content_len})")
                t_ner = time.perf_counter()
                entities = await self.extractors['ner'].extract(doc)
                ner_dt = time.perf_counter() - t_ner
                doc['extracted_entities'] = entities
                total_entities += len(entities or [])
                logger.info(f"[{idx}/{total}] NER done: {doc_id} in {ner_dt:.2f}s, entities={len(entities or [])}")

                # Relation Extraction
                logger.info(f"[{idx}/{total}] RE start:  {doc_id}")
                t_re = time.perf_counter()
                relations = await self.extractors['relation'].extract(doc)
                re_dt = time.perf_counter() - t_re
                doc['extracted_relations'] = relations
                total_relations += len(relations or [])
                logger.info(f"[{idx}/{total}] RE done:  {doc_id} in {re_dt:.2f}s, relations={len(relations or [])}")

                # Entity Linking
                logger.info(f"[{idx}/{total}] Link start: {doc_id}")
                t_link = time.perf_counter()
                linked_entities = await self.extractors['linker'].link(doc)
                link_dt = time.perf_counter() - t_link
                doc['linked_entities'] = linked_entities
                if isinstance(linked_entities, dict) and 'linked_entities' in linked_entities:
                    link_count = len(linked_entities['linked_entities'] or [])
                elif isinstance(linked_entities, list):
                    link_count = len(linked_entities)
                else:
                    link_count = 0
                logger.info(f"[{idx}/{total}] Link done: {doc_id} in {link_dt:.2f}s, linked={link_count}")

                enriched_docs.append(doc)
                logger.debug(f"Extracted from {doc_id}: entities={len(entities or [])}, relations={len(relations or [])}")
            except Exception as e:
                logger.error(f"[{idx}/{total}] Extraction error in {doc_id}: {e}")
                doc['extracted_entities'] = []
                doc['extracted_relations'] = []
                doc['linked_entities'] = {'linked_entities': []}
                enriched_docs.append(doc)
            finally:
                if idx % 5 == 0 or idx == total:
                    elapsed = time.perf_counter() - t0
                    logger.info(f"Progress: {idx}/{total} docs, elapsed={elapsed:.2f}s, total_entities={total_entities}, total_relations={total_relations}")

        # Dynamic Ontology Generation & Merge
        try:
            from ontology.dynamic_ontology_generator import (
                build_dynamic_ontology,
                merge_ontologies,
            )

            dynamic_file = self.processed_dir / "dynamic.ttl"
            core_file = Path("ontology/core.ttl")
            updated_core_file = self.processed_dir / "updated_core.ttl"

            build_dynamic_ontology(enriched_docs, dynamic_file)
            logger.info("Dynamic ontology generated")
            merge_ontologies(core_file, dynamic_file, updated_core_file)
            logger.info("Core ontology updated and merged")
            # Store path for subsequent KG build step
            self.updated_core_file = updated_core_file
        except Exception as e:
            logger.error(f"Dynamic ontology step failed: {e}")
            self.updated_core_file = Path("ontology/core.ttl")  # fallback

        enriched_file = self.interim_dir / "enriched_documents.jsonl"
        with open(enriched_file, 'w', encoding='utf-8') as f:
            for doc in enriched_docs:
                f.write(json.dumps(doc) + '\n')

        elapsed = time.perf_counter() - t0
        logger.info(
            f"Processed {len(enriched_docs)} documents with extraction in {elapsed:.2f}s "
            f"(entities={total_entities}, relations={total_relations})"
        )
        return enriched_docs

    async def build_knowledge_graph(self, enriched_docs: List[Dict]):
        """Build knowledge graph from extracted entities and relations."""
        logger.info("Building knowledge graph...")
        
        try:
            # Convert to RDF triples
            triples_file = self.processed_dir / "knowledge_graph.ttl"
            # Select ontology file (dynamic merged if available)
            ontology_file = getattr(self, "updated_core_file", Path("ontology/core.ttl"))
            stats = await self.kg_builder.build_triples(enriched_docs, triples_file, ontology_file=ontology_file)
            
            # Load into Fuseki
            success = await self.fuseki_client.load_triples(triples_file)
            
            if success:
                logger.info(f"Successfully loaded {stats['total_triples']} triples into Fuseki")
                
                # Run sample queries
                await self.run_sample_queries()
            else:
                logger.warning("Failed to load triples into Fuseki (Fuseki might not be running)")
                stats = {'total_triples': 0, 'entities': 0, 'relations': 0, 'documents': len(enriched_docs)}
                
        except Exception as e:
            logger.error(f"Error building knowledge graph: {e}")
            stats = {'total_triples': 0, 'entities': 0, 'relations': 0, 'documents': len(enriched_docs)}
            
        return stats

    async def run_sample_queries(self):
        """Run sample SPARQL queries to demonstrate KG capabilities."""
        logger.info("Running sample SPARQL queries...")
        
        queries = [
            {
                "name": "All Persons",
                "query": """
                PREFIX : <http://kg.example.org/ontology/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?person ?name
                WHERE {
                    ?person a :Person ;
                            rdfs:label ?name .
                }
                LIMIT 10
                """
            },
            {
                "name": "Person-Organization Relations", 
                "query": """
                PREFIX : <http://kg.example.org/ontology/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?person ?org ?relation
                WHERE {
                    ?person a :Person ;
                            rdfs:label ?personName .
                    ?org a :Organization ;
                         rdfs:label ?orgName .
                    ?person ?relation ?org .
                    FILTER(STRSTARTS(STR(?relation), "http://kg.example.org/ontology/"))
                }
                LIMIT 10
                """
            }
        ]
        
        for query_info in queries:
            try:
                results = await self.fuseki_client.query(query_info["query"])
                if not results:
                    logger.info(f"Query '{query_info['name']}': 0 results")
                    continue
                bindings = []
                if isinstance(results, dict):
                    bindings = results.get('results', {}).get('bindings', [])
                count = len(bindings)
                logger.info(f"Query '{query_info['name']}': {count} results")
                if count:
                    logger.info(f"Sample results: {bindings[:2]}")
            except Exception as e:
                logger.warning(f"Query '{query_info['name']}' failed: {e}")

    async def build_rag_index(self, enriched_docs: List[Dict]):
        """Build RAG vector index from documents."""
        logger.info("Building RAG index...")
        
        try:
            await self.indexer.build_index(enriched_docs)
            logger.info("RAG index built successfully")
        except Exception as e:
            logger.error(f"Error building RAG index: {e}")

    async def demo_graph_rag(self):
        """Demonstrate GraphRAG capabilities."""
        logger.info("Demonstrating GraphRAG...")
        
        questions = [
            "Who works for TechCorp?",
            "What events happened in New York?",
            "Find people who are CEOs"
        ]
        
        for question in questions:
            try:
                answer = await self.graph_rag.query(question)
                logger.info(f"Q: {question}")
                logger.info(f"A: {answer['answer']}")
                if answer.get('sources'):
                    logger.info(f"Sources: {len(answer['sources'])} entities/citations")
            except Exception as e:
                logger.error(f"GraphRAG query failed for '{question}': {e}")

    async def generate_report(self, stats: Dict[str, Any]):
        """Generate demo report."""
        logger.info("Generating demo report...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "pipeline_stats": stats,
            "components_used": list(self.generators.keys()) + list(self.parsers.keys()) + list(self.extractors.keys()),
            "status": "completed"
        }
        
        report_file = self.processed_dir / "demo_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
            
        logger.info(f"Demo report saved to {report_file}")

    async def run(self):
        """Run the complete demo pipeline."""
        logger.info("Starting Semantic KG Demo Pipeline")
        start_time = time.time()
        
        try:
            # 1. Generate data
            datasets = await self.generate_data()
            
            # 2. Parse documents
            parsed_docs = await self.parse_documents(datasets)
            
            # 3. Extract entities and relations
            enriched_docs = await self.extract_entities_relations(parsed_docs)
            
            # 4. Build knowledge graph
            kg_stats = await self.build_knowledge_graph(enriched_docs)
            
            # 5. Build RAG index
            await self.build_rag_index(enriched_docs)
            
            # 6. Demo GraphRAG
            await self.demo_graph_rag()
            
            # 7. Generate report
            await self.generate_report(kg_stats)
            
            elapsed_time = time.time() - start_time
            logger.success(f"Demo pipeline completed in {elapsed_time:.2f} seconds")
            
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