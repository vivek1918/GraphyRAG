#!/usr/bin/env python3
"""Dynamic Ontology Generation & Merge Utilities.

Generates a dynamic ontology extension (dynamic.ttl) from enriched documents
and merges it with the core ontology (core.ttl) to produce updated_core.ttl.

Detection Logic:
 - New Classes: Any entity types not mapping to base classes
 - Datatype Properties: Attribute keys from entities (infers XSD types)
 - Object Properties: Relation predicates not already defined in base ontology

Functions:
 - build_dynamic_ontology(enriched_docs, dynamic_file="dynamic.ttl")
 - merge_ontologies(core_file="core.ttl", dynamic_file="dynamic.ttl", output_file="updated_core.ttl")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Iterable
from datetime import datetime

from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD
from loguru import logger

KG_NS = Namespace("http://kg.example.org/ontology/")

# Base classes & predicates already defined in the core ontology
BASE_CLASS_SYNONYMS = {
    "PERSON": "Person",
    "ORG": "Organization",
    "ORGANIZATION": "Organization",
    "PLACE": "Place",
    "EVENT": "Event",
    "CONCEPT": "Concept",
    "DOCUMENT": "Document",
}

BASE_CLASSES = set(BASE_CLASS_SYNONYMS.values())

BASE_OBJECT_PROPERTIES = {
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
}

__all__ = [
    "build_dynamic_ontology",
    "merge_ontologies",
]


def _pascal_case(name: str) -> str:
    tokens = [t for t in name.replace("_", " ").replace("-", " ").split() if t]
    return "".join(t.capitalize() for t in tokens) or "Entity"


def _infer_xsd_type(value: Any) -> Any:
    """Infer the XSD datatype for a Python value."""
    if isinstance(value, bool):
        return XSD.boolean
    if isinstance(value, int) and not isinstance(value, bool):  # bool is int subclass
        return XSD.integer
    if isinstance(value, float):
        return XSD.float
    if isinstance(value, (datetime,)):
        return XSD.dateTime
    # Try ISO datetime parsing
    if isinstance(value, str):
        try:
            # datetime.fromisoformat supports many ISO variants
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return XSD.dateTime
        except Exception:
            return XSD.string
    return XSD.string


def _update_datatype_consensus(existing: Any, new: Any) -> Any:
    """Unify datatype choices when multiple values for same property appear.
    Preference order (more specific first): boolean -> integer -> float -> dateTime -> string.
    Downgrade to XSD.string if conflicts cannot be resolved cleanly.
    """
    if existing == new:
        return existing
    priority = [XSD.boolean, XSD.integer, XSD.float, XSD.dateTime, XSD.string]
    if existing in priority and new in priority:
        # If one is string, choose the other unless both differ non-trivially
        if XSD.string in (existing, new):
            other = new if existing == XSD.string else existing
            return other
        # If numeric vs dateTime conflict, fallback to string
        if {existing, new} & {XSD.float, XSD.integer, XSD.boolean} and {existing, new} & {XSD.dateTime}:
            return XSD.string
        # Different numeric types -> float (widest for numbers)
        if {existing, new} <= {XSD.boolean, XSD.integer}:
            return XSD.integer  # keep integer if bool/int mix
        if {existing, new} <= {XSD.integer, XSD.float, XSD.boolean}:
            return XSD.float
    return XSD.string


def _iter_entities(enriched_docs: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for doc in enriched_docs:
        entities = doc.get("linked_entities", {}).get("resolved_entities", [])
        if not entities:
            entities = doc.get("extracted_entities", doc.get("entities", []))
        for e in entities or []:
            yield e


def _iter_relations(enriched_docs: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for doc in enriched_docs:
        for r in doc.get("extracted_relations", []) or []:
            yield r


def build_dynamic_ontology(enriched_docs: List[Dict[str, Any]], dynamic_file: str | Path = "dynamic.ttl") -> Dict[str, Any]:
    """Generate a dynamic ontology extension from enriched documents.

    Returns a summary dict of generated elements.
    """
    dynamic_path = Path(dynamic_file)
    g = Graph()
    g.bind("kg", KG_NS)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    new_classes = set()
    datatype_properties: Dict[str, Any] = {}
    object_properties = set()

    # Detect classes and datatype properties
    for entity in _iter_entities(enriched_docs):
        raw_type = str(entity.get("type", "Entity")).strip()
        normalized = raw_type.upper()
        mapped = BASE_CLASS_SYNONYMS.get(normalized)
        if not mapped:
            # Create PascalCase class name
            cls_name = _pascal_case(raw_type)
            if cls_name not in BASE_CLASSES:
                new_classes.add(cls_name)

        attributes = entity.get("attributes", {}) or {}
        for key, value in attributes.items():
            xsd_type = _infer_xsd_type(value)
            if key not in datatype_properties:
                datatype_properties[key] = xsd_type
            else:
                datatype_properties[key] = _update_datatype_consensus(datatype_properties[key], xsd_type)

    # Detect object properties from relations
    for rel in _iter_relations(enriched_docs):
        rel_name = str(rel.get("relation", "")).strip()
        if not rel_name:
            continue
        rel_name_upper = rel_name.upper()
        if rel_name_upper not in BASE_OBJECT_PROPERTIES:
            # Preserve original form but ensure valid fragment
            prop_fragment = rel_name_upper
            object_properties.add(prop_fragment)

    # Add new class declarations
    for cls in sorted(new_classes):
        g.add((KG_NS[cls], RDF.type, OWL.Class))
        g.add((KG_NS[cls], RDFS.label, Literal(cls)))

    # Add datatype properties
    for prop, dtype in sorted(datatype_properties.items()):
        g.add((KG_NS[prop], RDF.type, OWL.DatatypeProperty))
        g.add((KG_NS[prop], RDFS.range, dtype))
        g.add((KG_NS[prop], RDFS.label, Literal(prop)))

    # Add object properties
    for prop in sorted(object_properties):
        g.add((KG_NS[prop], RDF.type, OWL.ObjectProperty))
        g.add((KG_NS[prop], RDFS.label, Literal(prop)))

    g.serialize(destination=str(dynamic_path), format="turtle")
    logger.info(f"Dynamic ontology written to {dynamic_path}")

    summary = {
        "dynamic_file": str(dynamic_path),
        "new_classes": sorted(new_classes),
        "datatype_properties": {k: str(v) for k, v in datatype_properties.items()},
        "object_properties": sorted(object_properties),
        "triple_count": len(g),
    }
    logger.debug(f"Dynamic ontology summary: {summary}")
    return summary


def merge_ontologies(core_file: str | Path = "core.ttl", dynamic_file: str | Path = "dynamic.ttl", output_file: str | Path = "updated_core.ttl") -> Dict[str, Any]:
    """Merge core and dynamic ontologies, producing a unified ontology file.

    Returns a summary dict with counts.
    """
    core_path = Path(core_file)
    dynamic_path = Path(dynamic_file)
    output_path = Path(output_file)

    if not core_path.exists():
        raise FileNotFoundError(f"Core ontology not found: {core_path}")
    if not dynamic_path.exists():
        raise FileNotFoundError(f"Dynamic ontology not found: {dynamic_path}")

    core_g = Graph()
    core_g.parse(str(core_path), format="turtle")

    dyn_g = Graph()
    dyn_g.parse(str(dynamic_path), format="turtle")

    merged_g = Graph()

    # Preserve namespaces
    for prefix, ns in core_g.namespaces():
        merged_g.bind(prefix, ns)
    for prefix, ns in dyn_g.namespaces():
        merged_g.bind(prefix, ns)

    # Union add triples (rdflib Graph prevents duplicate storage automatically)
    for t in core_g:
        merged_g.add(t)
    for t in dyn_g:
        merged_g.add(t)

    merged_g.serialize(destination=str(output_path), format="turtle")
    logger.info(f"Merged ontology written to {output_path}")

    summary = {
        "core_file": str(core_path),
        "dynamic_file": str(dynamic_path),
        "output_file": str(output_path),
        "core_triples": len(core_g),
        "dynamic_triples": len(dyn_g),
        "merged_triples": len(merged_g),
    }
    logger.debug(f"Merge summary: {summary}")
    return summary
