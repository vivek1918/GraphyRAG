#!/usr/bin/env python3
"""
RDF triple builder from extracted entities and relations.
Converts extracted information to semantic triples using the ontology.
Includes Neo4j integration for graph visualization.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import quote
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, OWL, XSD
from loguru import logger


class TripleBuilder:
    """Builds RDF triples from extracted information."""

    def __init__(self):
        self.kg_ns = Namespace("http://kg.example.org/ontology/")
        self.entity_ns = Namespace("http://kg.example.org/entity/")
        self.doc_ns = Namespace("http://kg.example.org/document/")
        self.neo4j_client = None
        self._initialize_neo4j()

    def _initialize_neo4j(self):
        """Initialize Neo4j client if available."""
        try:
            from kg.neo4j_client import Neo4jClient
            self.neo4j_client = Neo4jClient()
            logger.info("Neo4j client initialized")
        except ImportError:
            logger.warning("Neo4j not available - graph visualization will be limited")
        except Exception as e:
            logger.warning(f"Neo4j initialization failed: {e}")

    async def build_triples(self, documents: List[Dict[str, Any]], output_file: Path, ontology_file: Optional[Path] = None) -> Dict[str, int]:
        """Build RDF triples from enriched documents.

        If an ontology_file is provided and exists, preload that ontology (including dynamic extensions)
        before adding instance data. Otherwise fall back to defining the core ontology locally.
        """
        graph = Graph()

        # Preload ontology (core + dynamic merged) if supplied
        if ontology_file and ontology_file.exists():
            try:
                graph.parse(str(ontology_file), format="turtle")
                logger.info(f"Loaded ontology from {ontology_file}")
            except Exception as e:
                logger.warning(f"Failed to parse ontology file {ontology_file}: {e}. Falling back to embedded core ontology.")

        # Bind namespaces
        graph.bind("kg", self.kg_ns)
        graph.bind("ent", self.entity_ns)
        graph.bind("doc", self.doc_ns)
        graph.bind("rdf", RDF)
        graph.bind("rdfs", RDFS)
        graph.bind("xsd", XSD)

        # Define ontology structure only if we did not preload one
        if not ontology_file or not ontology_file.exists():
            self._define_ontology(graph)

        total_triples = 0
        entity_count = 0
        relation_count = 0
        
        # Data for Neo4j
        neo4j_nodes = []
        neo4j_relationships = []

        for doc in documents:
            # Create document entity
            # Ensure a safe URI fragment (encode spaces and special characters)
            raw_doc_id = str(doc.get("doc_id", "document"))
            safe_doc_id = quote(raw_doc_id, safe="-_.~")
            doc_uri = self.doc_ns[safe_doc_id]
            graph.add((doc_uri, RDF.type, self.kg_ns.Document))
            graph.add((doc_uri, RDFS.label, Literal(f"Document {raw_doc_id}")))
            graph.add((doc_uri, self.kg_ns.hasText, Literal(doc.get("content", ""))))
            graph.add((doc_uri, self.kg_ns.sourceType, Literal(doc.get("source_type", "unknown"))))

            if doc.get("created_at"):
                graph.add((doc_uri, self.kg_ns.createdAt, Literal(doc["created_at"], datatype=XSD.dateTime)))

            # Neo4j document node
            neo4j_nodes.append({
                'id': str(doc_uri),
                'labels': ['Document'],
                'properties': {
                    'doc_id': raw_doc_id,
                    'source_type': doc.get('source_type', 'unknown'),
                    'content_preview': doc.get('content', '')[:100] + '...' if doc.get('content') else '',
                    'created_at': doc.get('created_at', '')
                }
            })

            # Process entities
            entities = doc.get("linked_entities", {}).get("resolved_entities", [])
            if not entities:  # fallback if not resolved_entities exists
                entities = doc.get("extracted_entities", doc.get("entities", []))

            for entity in entities:
                entity_uri = await self.add_entity(graph, entity, doc_uri)
                if entity_uri:
                    entity_count += 1
                    
                    # Add Neo4j entity node
                    neo4j_nodes.append({
                        'id': str(entity_uri),
                        'labels': [self._get_neo4j_label(entity.get('type', 'Entity'))],
                        'properties': {
                            'name': entity.get('canonical_name', entity.get('text', 'Unknown')),
                            'entity_type': entity.get('type', 'Entity'),
                            'original_text': entity.get('original_text', ''),
                            'confidence': entity.get('confidence', 1.0)
                        }
                    })
                    
                    # Add Neo4j relationship: Document -> mentions -> Entity
                    neo4j_relationships.append({
                        'start_node': str(doc_uri),
                        'end_node': str(entity_uri),
                        'type': 'MENTIONS',
                        'properties': {
                            'source': 'extraction',
                            'extraction_method': entity.get('extraction_method', 'NER')
                        }
                    })

            # Process relations
            relations = doc.get("extracted_relations", [])
            for relation in relations:
                if await self.add_relation(graph, relation):
                    relation_count += 1
                    
                    # Add Neo4j relationship between entities
                    subject_uri = await self.find_entity_uri(graph, relation['subject'])
                    object_uri = await self.find_entity_uri(graph, relation['object'])
                    
                    if subject_uri and object_uri:
                        neo4j_relationships.append({
                            'start_node': str(subject_uri),
                            'end_node': str(object_uri),
                            'type': relation['relation'].upper(),
                            'properties': {
                                'confidence': relation.get('confidence', 0.5),
                                'evidence': relation.get('evidence', ''),
                                'source_doc': doc['doc_id']
                            }
                        })

            total_triples = len(graph)

        # Save the graph
        graph.serialize(destination=str(output_file), format="turtle")
        logger.info(f"Built {total_triples} triples from {len(documents)} documents")

        # Load into Neo4j if available
        if self.neo4j_client:
            try:
                neo4j_stats = await self.neo4j_client.load_graph(neo4j_nodes, neo4j_relationships)
                logger.info(f"Loaded {neo4j_stats['nodes']} nodes and {neo4j_stats['relationships']} relationships into Neo4j")
            except Exception as e:
                logger.error(f"Failed to load data into Neo4j: {e}")

        return {
            "total_triples": total_triples,
            "entities": entity_count,
            "relations": relation_count,
            "documents": len(documents),
            "neo4j_nodes": len(neo4j_nodes),
            "neo4j_relationships": len(neo4j_relationships)
        }

    def _define_ontology(self, graph: Graph):
        """Define ontology classes and hierarchy."""
        # Core classes
        for cls in ["Person", "Organization", "Place", "Event", "Concept", "Document"]:
            graph.add((self.kg_ns[cls], RDF.type, OWL.Class))
            graph.add((self.kg_ns[cls], RDFS.subClassOf, OWL.Thing))

        # Core predicates
        for pred in [
            "WORKS_FOR",
            "LOCATED_IN",
            "PARTICIPATED_IN",
            "HAS_ROLE",
            "MENTIONS",
            "hasText",
            "sourceType",
            "createdAt",
            "hasAlias",
            "extractedFrom",
            "mentions",
        ]:
            graph.add((self.kg_ns[pred], RDF.type, OWL.ObjectProperty))

    def _get_neo4j_label(self, entity_type: str) -> str:
        """Convert entity type to Neo4j label."""
        type_map = {
            'PERSON': 'Person',
            'ORG': 'Organization',
            'ORGANIZATION': 'Organization',
            'PLACE': 'Place',
            'EVENT': 'Event',
            'CONCEPT': 'Concept'
        }
        return type_map.get(entity_type.upper(), 'Entity')

    async def add_entity(self, graph: Graph, entity: Dict[str, Any], doc_uri: URIRef) -> URIRef:
        """Add an entity to the graph."""
        try:
            # Create entity URI
            entity_id = entity.get("entity_id", str(uuid.uuid4()))
            entity_uri = self.entity_ns[entity_id]

            # Add entity type
            entity_type = entity.get("type", "Entity").upper()
            if entity_type == "PERSON":
                graph.add((entity_uri, RDF.type, self.kg_ns.Person))
            elif entity_type in ("ORG", "ORGANIZATION"):
                graph.add((entity_uri, RDF.type, self.kg_ns.Organization))
            elif entity_type == "PLACE":
                graph.add((entity_uri, RDF.type, self.kg_ns.Place))
            elif entity_type == "EVENT":
                graph.add((entity_uri, RDF.type, self.kg_ns.Event))
            else:
                graph.add((entity_uri, RDF.type, self.kg_ns.Concept))

            # Add label
            canonical_name = entity.get("canonical_name", entity.get("text", "Unknown"))
            graph.add((entity_uri, RDFS.label, Literal(canonical_name)))

            # Add aliases
            original_text = entity.get("original_text")
            if original_text and original_text != canonical_name:
                graph.add((entity_uri, self.kg_ns.hasAlias, Literal(original_text)))

            # Link to document
            graph.add((entity_uri, self.kg_ns.extractedFrom, doc_uri))
            graph.add((doc_uri, self.kg_ns.mentions, entity_uri))

            # Add attributes
            attributes = entity.get("attributes", {})
            for key, value in attributes.items():
                if key == "role" and value:
                    graph.add((entity_uri, self.kg_ns.HAS_ROLE, Literal(value)))

            return entity_uri

        except Exception as e:
            logger.error(f"Error adding entity {entity}: {e}")
            return None

    async def add_relation(self, graph: Graph, relation: Dict[str, Any]) -> bool:
        """Add a relation to the graph."""
        try:
            subject_name = relation.get("subject")
            object_name = relation.get("object")
            rel_type = relation.get("relation")

            if not all([subject_name, object_name, rel_type]):
                return False

            # Find subject and object URIs
            subject_uri = await self.find_entity_uri(graph, subject_name)
            object_uri = await self.find_entity_uri(graph, object_name)

            if not subject_uri or not object_uri:
                return False

            # Add relation based on type (uppercase predicates to match SPARQL)
            rel_type_upper = rel_type.upper()
            if rel_type_upper == "WORKS_FOR":
                graph.add((subject_uri, self.kg_ns.WORKS_FOR, object_uri))
            elif rel_type_upper == "LOCATED_IN":
                graph.add((subject_uri, self.kg_ns.LOCATED_IN, object_uri))
            elif rel_type_upper == "PARTICIPATED_IN":
                graph.add((subject_uri, self.kg_ns.PARTICIPATED_IN, object_uri))
            elif rel_type_upper == "HAS_ROLE":
                graph.add((subject_uri, self.kg_ns.HAS_ROLE, Literal(object_name)))
            elif rel_type_upper == "MENTIONS":
                graph.add((subject_uri, self.kg_ns.MENTIONS, object_uri))
            else:
                graph.add((subject_uri, self.kg_ns.HAS_RELATION, object_uri))

            return True

        except Exception as e:
            logger.error(f"Error adding relation {relation}: {e}")
            return False

    async def find_entity_uri(self, graph: Graph, entity_name: str) -> URIRef:
        """Find entity URI by name in the graph."""
        for s, p, o in graph.triples((None, RDFS.label, Literal(entity_name))):
            return s
        return None