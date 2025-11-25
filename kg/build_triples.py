#!/usr/bin/env python3
"""
RDF triple builder from extracted entities and relations.
Converts extracted information to semantic triples using the ontology.
Includes Neo4j integration for graph visualization.
"""

import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
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

    def _normalize_entity(self, entity: Any) -> Optional[Dict[str, Any]]:
        """Normalize entity to dict format, handling various input types."""
        if entity is None:
            return None
        
        if isinstance(entity, dict):
            return entity
        
        if isinstance(entity, str):
            # String entity - convert to dict
            return {
                "text": entity,
                "canonical_name": entity,
                "type": "CONCEPT",
                "entity_id": str(uuid.uuid4())
            }
        
        if isinstance(entity, (list, tuple)):
            # List/tuple entity - try to extract meaningful data
            if len(entity) >= 2:
                return {
                    "text": str(entity[0]),
                    "type": str(entity[1]) if len(entity) > 1 else "CONCEPT",
                    "canonical_name": str(entity[0]),
                    "entity_id": str(uuid.uuid4())
                }
            elif len(entity) == 1:
                return {
                    "text": str(entity[0]),
                    "canonical_name": str(entity[0]),
                    "type": "CONCEPT",
                    "entity_id": str(uuid.uuid4())
                }
            return None
        
        # Unknown type - try to convert to string
        try:
            return {
                "text": str(entity),
                "canonical_name": str(entity),
                "type": "CONCEPT",
                "entity_id": str(uuid.uuid4())
            }
        except Exception:
            logger.warning(f"Could not normalize entity of type {type(entity)}")
            return None

    def _extract_entities_from_doc(self, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract and normalize entities from document, handling various formats."""
        entities = []
        
        # Try linked_entities.resolved_entities first
        linked = doc.get("linked_entities")
        if isinstance(linked, dict):
            resolved = linked.get("resolved_entities", [])
            if isinstance(resolved, list):
                for e in resolved:
                    normalized = self._normalize_entity(e)
                    if normalized:
                        entities.append(normalized)
        
        # If no entities yet, try extracted_entities
        if not entities:
            extracted = doc.get("extracted_entities", [])
            if isinstance(extracted, list):
                for e in extracted:
                    normalized = self._normalize_entity(e)
                    if normalized:
                        entities.append(normalized)
        
        # If still no entities, try entities field
        if not entities:
            ents = doc.get("entities", [])
            if isinstance(ents, list):
                for e in ents:
                    normalized = self._normalize_entity(e)
                    if normalized:
                        entities.append(normalized)
        
        return entities

    def _extract_domain_entities_from_doc(self, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract and normalize domain entities from document."""
        entities = []
        
        domain_data = doc.get("domain_entities")
        
        if domain_data is None:
            return entities
        
        # Handle if domain_entities is a dict with 'entities' key
        if isinstance(domain_data, dict):
            domain_list = domain_data.get("entities", [])
        elif isinstance(domain_data, list):
            domain_list = domain_data
        else:
            logger.warning(f"Unexpected domain_entities type: {type(domain_data)}")
            return entities
        
        if not isinstance(domain_list, list):
            logger.warning(f"domain_entities list is not a list: {type(domain_list)}")
            return entities
        
        for item in domain_list:
            if isinstance(item, dict):
                entities.append(item)
            else:
                normalized = self._normalize_entity(item)
                if normalized:
                    entities.append(normalized)
        
        return entities

    def _extract_relations_from_doc(self, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract and normalize relations from document."""
        relations = []
        
        raw_relations = doc.get("extracted_relations", [])
        
        if not isinstance(raw_relations, list):
            if isinstance(raw_relations, dict):
                # Single relation as dict
                relations.append(raw_relations)
            return relations
        
        for rel in raw_relations:
            if isinstance(rel, dict):
                relations.append(rel)
            elif isinstance(rel, (list, tuple)) and len(rel) >= 3:
                # Relation as tuple/list: (subject, relation, object)
                relations.append({
                    "subject": str(rel[0]),
                    "relation": str(rel[1]),
                    "object": str(rel[2]),
                    "confidence": rel[3] if len(rel) > 3 else 0.5
                })
        
        return relations

    async def build_triples(
        self,
        documents: List[Dict[str, Any]],
        output_file: Path,
        ontology_file: Optional[Path] = None
    ) -> Dict[str, int]:
        """Build RDF triples from enriched documents.

        If an ontology_file is provided and exists, preload that ontology
        before adding instance data. Otherwise fall back to defining the
        core ontology locally.
        """
        graph = Graph()

        # Preload ontology if supplied
        if ontology_file and ontology_file.exists():
            try:
                graph.parse(str(ontology_file), format="turtle")
                logger.info(f"Loaded ontology from {ontology_file}")
            except Exception as e:
                logger.warning(
                    f"Failed to parse ontology file {ontology_file}: {e}. "
                    "Falling back to embedded core ontology."
                )
                self._define_ontology(graph)
        else:
            self._define_ontology(graph)

        # Bind namespaces
        graph.bind("kg", self.kg_ns)
        graph.bind("ent", self.entity_ns)
        graph.bind("doc", self.doc_ns)
        graph.bind("rdf", RDF)
        graph.bind("rdfs", RDFS)
        graph.bind("xsd", XSD)

        total_triples = 0
        entity_count = 0
        relation_count = 0

        # Data for Neo4j
        neo4j_nodes = []
        neo4j_relationships = []

        # Normalize documents input
        if not isinstance(documents, list):
            logger.error(f"Documents must be a list, got {type(documents)}")
            documents = []

        for doc_idx, doc in enumerate(documents):
            if not isinstance(doc, dict):
                logger.warning(f"Skipping non-dict document at index {doc_idx}: {type(doc)}")
                continue

            # Create document entity
            raw_doc_id = str(doc.get("doc_id", f"document_{doc_idx}"))
            safe_doc_id = quote(raw_doc_id, safe="-_.~")
            doc_uri = self.doc_ns[safe_doc_id]
            
            graph.add((doc_uri, RDF.type, self.kg_ns.Document))
            graph.add((doc_uri, RDFS.label, Literal(f"Document {raw_doc_id}")))
            graph.add((doc_uri, self.kg_ns.hasText, Literal(doc.get("content", ""))))
            graph.add((doc_uri, self.kg_ns.sourceType, Literal(doc.get("source_type", "unknown"))))

            created_at = doc.get("created_at")
            if created_at:
                graph.add((
                    doc_uri,
                    self.kg_ns.createdAt,
                    Literal(created_at, datatype=XSD.dateTime)
                ))

            # Neo4j document node
            content = doc.get("content", "")
            content_preview = (content[:100] + "...") if len(content) > 100 else content
            neo4j_nodes.append({
                "id": str(doc_uri),
                "labels": ["Document"],
                "properties": {
                    "doc_id": raw_doc_id,
                    "source_type": doc.get("source_type", "unknown"),
                    "content_preview": content_preview,
                    "created_at": created_at or ""
                }
            })

            # Process domain-specific entities
            domain_entities = self._extract_domain_entities_from_doc(doc)
            for entity in domain_entities:
                try:
                    entity_uri = await self.add_domain_entity(graph, entity, doc_uri)
                    if entity_uri:
                        entity_count += 1

                        # Add Neo4j entity node
                        neo4j_nodes.append({
                            "id": str(entity_uri),
                            "labels": [self._get_domain_label(entity.get("type", "Entity"))],
                            "properties": {
                                "name": self._get_entity_name(entity),
                                "entity_type": entity.get("type", "Entity"),
                                "confidence": entity.get("confidence", 0.9),
                                **{k: v for k, v in entity.get("fields", {}).items() 
                                   if isinstance(v, (str, int, float, bool))}
                            }
                        })

                        # Add Neo4j relationship: Document -> mentions -> Entity
                        neo4j_relationships.append({
                            "start_node": str(doc_uri),
                            "end_node": str(entity_uri),
                            "type": "MENTIONS",
                            "properties": {
                                "source": "domain_extraction",
                                "extraction_method": "domain_specific"
                            }
                        })
                except Exception as e:
                    logger.error(f"Error processing domain entity: {e}")
                    continue

            # Process generic NER entities
            entities = self._extract_entities_from_doc(doc)
            for entity in entities:
                try:
                    entity_uri = await self.add_entity(graph, entity, doc_uri)
                    if entity_uri:
                        entity_count += 1

                        # Add Neo4j entity node
                        neo4j_nodes.append({
                            "id": str(entity_uri),
                            "labels": [self._get_neo4j_label(entity.get("type", "Entity"))],
                            "properties": {
                                "name": entity.get("canonical_name", entity.get("text", "Unknown")),
                                "entity_type": entity.get("type", "Entity"),
                                "original_text": entity.get("original_text", ""),
                                "confidence": entity.get("confidence", 1.0)
                            }
                        })

                        # Add Neo4j relationship: Document -> mentions -> Entity
                        neo4j_relationships.append({
                            "start_node": str(doc_uri),
                            "end_node": str(entity_uri),
                            "type": "MENTIONS",
                            "properties": {
                                "source": "extraction",
                                "extraction_method": entity.get("extraction_method", "NER")
                            }
                        })
                except Exception as e:
                    logger.error(f"Error processing entity: {e}")
                    continue

            # Process relations
            relations = self._extract_relations_from_doc(doc)
            for relation in relations:
                try:
                    if await self.add_relation(graph, relation):
                        relation_count += 1

                        # Add Neo4j relationship between entities
                        subject_uri = await self.find_entity_uri(graph, relation.get("subject", ""))
                        object_uri = await self.find_entity_uri(graph, relation.get("object", ""))

                        if subject_uri and object_uri:
                            rel_type = relation.get("relation", "RELATED_TO")
                            neo4j_relationships.append({
                                "start_node": str(subject_uri),
                                "end_node": str(object_uri),
                                "type": rel_type.upper().replace(" ", "_"),
                                "properties": {
                                    "confidence": relation.get("confidence", 0.5),
                                    "evidence": relation.get("evidence", ""),
                                    "source_doc": raw_doc_id
                                }
                            })
                except Exception as e:
                    logger.error(f"Error processing relation: {e}")
                    continue

        total_triples = len(graph)

        # Save the graph
        try:
            graph.serialize(destination=str(output_file), format="turtle")
            logger.info(f"Built {total_triples} triples from {len(documents)} documents")
        except Exception as e:
            logger.error(f"Failed to serialize graph: {e}")

        # Load into Neo4j if available
        if self.neo4j_client:
            try:
                neo4j_stats = await self.neo4j_client.load_graph(neo4j_nodes, neo4j_relationships)
                logger.info(
                    f"Loaded {neo4j_stats['nodes']} nodes and "
                    f"{neo4j_stats['relationships']} relationships into Neo4j"
                )
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
        core_classes = [
            "Person", "Organization", "Place", "Event",
            "Concept", "Document", "Object", "Metric", "Date", "Entity"
        ]
        for cls in core_classes:
            graph.add((self.kg_ns[cls], RDF.type, OWL.Class))
            graph.add((self.kg_ns[cls], RDFS.subClassOf, OWL.Thing))

        # Core predicates
        predicates = [
            "WORKS_FOR", "LOCATED_IN", "PARTICIPATED_IN", "HAS_ROLE",
            "MENTIONS", "CREATED_BY", "ASSOCIATED_WITH", "PART_OF",
            "RELATED_TO", "USES", "OCCURS_AFTER", "OWNS", "HAS_RELATION",
            "hasText", "sourceType", "createdAt", "hasAlias",
            "extractedFrom", "mentions", "hasConfidence", "hasSourceText"
        ]
        for pred in predicates:
            graph.add((self.kg_ns[pred], RDF.type, OWL.ObjectProperty))

    def _get_neo4j_label(self, entity_type: str) -> str:
        """Convert entity type to Neo4j label."""
        if not entity_type:
            return "Entity"
        
        type_map = {
            "PERSON": "Person",
            "ORG": "Organization",
            "ORGANIZATION": "Organization",
            "PLACE": "Place",
            "LOCATION": "Place",
            "EVENT": "Event",
            "CONCEPT": "Concept",
            "OBJECT": "Object",
            "METRIC": "Metric",
            "DATE": "Date",
            "ENTITY": "Entity"
        }
        return type_map.get(entity_type.upper(), "Entity")

    def _get_domain_label(self, entity_type: str) -> str:
        """Convert domain entity type to Neo4j label."""
        if not entity_type:
            return "Entity"
        # Domain types are already in proper case from schema
        # But ensure first letter is capitalized
        return entity_type[0].upper() + entity_type[1:] if entity_type else "Entity"

    def _get_entity_name(self, entity: Dict[str, Any]) -> str:
        """Extract name from domain entity fields."""
        if not isinstance(entity, dict):
            return str(entity) if entity else "Unnamed"
        
        # Try direct name fields first
        for name_field in ["name", "canonical_name", "text", "title"]:
            val = entity.get(name_field)
            if val:
                return str(val)
        
        # Try fields dict
        fields = entity.get("fields", {})
        if isinstance(fields, dict):
            for name_field in ["name", "title", "company", "institution", "description"]:
                val = fields.get(name_field)
                if val:
                    return str(val)
        
        return entity.get("id", "Unnamed")

    async def add_domain_entity(
        self,
        graph: Graph,
        entity: Dict[str, Any],
        doc_uri: URIRef
    ) -> Optional[URIRef]:
        """Add a domain-specific entity to the graph with structured fields."""
        if not isinstance(entity, dict):
            logger.warning(f"Skipping non-dict domain entity: {type(entity)}")
            return None

        try:
            # Create entity URI
            entity_id = entity.get("id") or str(uuid.uuid4())
            safe_id = quote(str(entity_id), safe="-_.~")
            entity_uri = self.entity_ns[safe_id]

            # Add entity type (domain-specific class)
            entity_type = entity.get("type", "Entity")
            if entity_type:
                graph.add((entity_uri, RDF.type, self.kg_ns[entity_type]))
            else:
                graph.add((entity_uri, RDF.type, self.kg_ns.Entity))

            # Add label
            entity_name = self._get_entity_name(entity)
            graph.add((entity_uri, RDFS.label, Literal(entity_name)))

            # Link to document
            graph.add((entity_uri, self.kg_ns.extractedFrom, doc_uri))
            graph.add((doc_uri, self.kg_ns.mentions, entity_uri))

            # Add all structured fields as datatype properties
            fields = entity.get("fields", {})
            if isinstance(fields, dict):
                for field_name, field_value in fields.items():
                    if field_value is None:
                        continue
                    
                    # Convert field name to property URI
                    prop_name = "".join(word.capitalize() for word in str(field_name).split("_"))
                    prop_uri = self.kg_ns[f"has{prop_name}"]

                    # Handle different value types
                    if isinstance(field_value, list):
                        for item in field_value:
                            if item is not None:
                                graph.add((entity_uri, prop_uri, Literal(str(item))))
                    elif isinstance(field_value, dict):
                        graph.add((entity_uri, prop_uri, Literal(json.dumps(field_value))))
                    else:
                        graph.add((entity_uri, prop_uri, Literal(str(field_value))))

            # Add confidence
            confidence = entity.get("confidence", 0.9)
            try:
                conf_val = float(confidence)
            except (TypeError, ValueError):
                conf_val = 0.9
            graph.add((entity_uri, self.kg_ns.hasConfidence, Literal(conf_val, datatype=XSD.float)))

            # Add source text if available
            source_text = entity.get("source_text")
            if source_text:
                graph.add((entity_uri, self.kg_ns.hasSourceText, Literal(str(source_text))))

            return entity_uri

        except Exception as e:
            logger.error(f"Error adding domain entity {entity}: {e}")
            return None

    async def add_entity(
        self,
        graph: Graph,
        entity: Dict[str, Any],
        doc_uri: URIRef
    ) -> Optional[URIRef]:
        """Add an entity to the graph."""
        if not isinstance(entity, dict):
            logger.warning(f"Skipping non-dict entity: {type(entity)}")
            return None

        try:
            # Create entity URI
            entity_id = entity.get("entity_id") or entity.get("id") or str(uuid.uuid4())
            safe_id = quote(str(entity_id), safe="-_.~")
            entity_uri = self.entity_ns[safe_id]

            # Add entity type
            entity_type = str(entity.get("type", "Entity")).upper()
            type_mapping = {
                "PERSON": self.kg_ns.Person,
                "ORG": self.kg_ns.Organization,
                "ORGANIZATION": self.kg_ns.Organization,
                "PLACE": self.kg_ns.Place,
                "LOCATION": self.kg_ns.Place,
                "EVENT": self.kg_ns.Event,
                "OBJECT": self.kg_ns.Object,
                "METRIC": self.kg_ns.Metric,
                "DATE": self.kg_ns.Date,
            }
            rdf_type = type_mapping.get(entity_type, self.kg_ns.Concept)
            graph.add((entity_uri, RDF.type, rdf_type))

            # Add label
            canonical_name = entity.get("canonical_name") or entity.get("text") or "Unknown"
            graph.add((entity_uri, RDFS.label, Literal(str(canonical_name))))

            # Add aliases
            original_text = entity.get("original_text")
            if original_text and str(original_text) != str(canonical_name):
                graph.add((entity_uri, self.kg_ns.hasAlias, Literal(str(original_text))))

            # Link to document
            graph.add((entity_uri, self.kg_ns.extractedFrom, doc_uri))
            graph.add((doc_uri, self.kg_ns.mentions, entity_uri))

            # Add attributes
            attributes = entity.get("attributes", {})
            if isinstance(attributes, dict):
                for key, value in attributes.items():
                    if key == "role" and value:
                        graph.add((entity_uri, self.kg_ns.HAS_ROLE, Literal(str(value))))

            # Add confidence if present
            confidence = entity.get("confidence")
            if confidence is not None:
                try:
                    conf_val = float(confidence)
                    graph.add((entity_uri, self.kg_ns.hasConfidence, Literal(conf_val, datatype=XSD.float)))
                except (TypeError, ValueError):
                    pass

            return entity_uri

        except Exception as e:
            logger.error(f"Error adding entity {entity}: {e}")
            return None

    async def add_relation(self, graph: Graph, relation: Dict[str, Any]) -> bool:
        """Add a relation to the graph."""
        if not isinstance(relation, dict):
            logger.warning(f"Skipping non-dict relation: {type(relation)}")
            return False

        try:
            subject_name = relation.get("subject")
            object_name = relation.get("object")
            rel_type = relation.get("relation")

            if not all([subject_name, object_name, rel_type]):
                logger.debug(f"Incomplete relation: {relation}")
                return False

            # Find subject and object URIs
            subject_uri = await self.find_entity_uri(graph, str(subject_name))
            object_uri = await self.find_entity_uri(graph, str(object_name))

            if not subject_uri or not object_uri:
                logger.debug(f"Could not find URIs for relation: {subject_name} -> {object_name}")
                return False

            # Map relation types to predicates
            rel_type_upper = str(rel_type).upper().replace(" ", "_")
            relation_mapping = {
                "WORKS_FOR": self.kg_ns.WORKS_FOR,
                "LOCATED_IN": self.kg_ns.LOCATED_IN,
                "PARTICIPATED_IN": self.kg_ns.PARTICIPATED_IN,
                "HAS_ROLE": self.kg_ns.HAS_ROLE,
                "MENTIONS": self.kg_ns.MENTIONS,
                "CREATED_BY": self.kg_ns.CREATED_BY,
                "ASSOCIATED_WITH": self.kg_ns.ASSOCIATED_WITH,
                "PART_OF": self.kg_ns.PART_OF,
                "RELATED_TO": self.kg_ns.RELATED_TO,
                "USES": self.kg_ns.USES,
                "OCCURS_AFTER": self.kg_ns.OCCURS_AFTER,
                "OWNS": self.kg_ns.OWNS,
            }

            predicate = relation_mapping.get(rel_type_upper)
            
            if predicate:
                if rel_type_upper == "HAS_ROLE":
                    graph.add((subject_uri, predicate, Literal(str(object_name))))
                else:
                    graph.add((subject_uri, predicate, object_uri))
            else:
                # Use generic HAS_RELATION for unknown relation types
                # But also create a dynamic predicate
                dynamic_pred = self.kg_ns[rel_type_upper]
                graph.add((subject_uri, dynamic_pred, object_uri))

            return True

        except Exception as e:
            logger.error(f"Error adding relation {relation}: {e}")
            return False

    async def find_entity_uri(self, graph: Graph, entity_name: str) -> Optional[URIRef]:
        """Find entity URI by name in the graph."""
        if not entity_name:
            return None
        
        entity_name_str = str(entity_name)
        
        # Search by label
        for s, p, o in graph.triples((None, RDFS.label, Literal(entity_name_str))):
            return s
        
        # Search by alias
        for s, p, o in graph.triples((None, self.kg_ns.hasAlias, Literal(entity_name_str))):
            return s
        
        return None