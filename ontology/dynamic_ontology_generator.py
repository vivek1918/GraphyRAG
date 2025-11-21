#!/usr/bin/env python3
"""Dynamic Ontology Generation Utilities.

Generates standalone ontology files from enriched documents, grouped by dataset type.
Each dataset gets its own complete ontology without requiring a core ontology merge.

Detection Logic:
 - Classes: All entity types (both base class synonyms and newly discovered types)
 - Datatype Properties: Attribute keys from entities (infers XSD types)
 - Object Properties: Relation predicates (both base and new)

Functions:
 - build_dynamic_ontology(enriched_docs, dynamic_file="dynamic.ttl")
   Creates a standalone dynamic ontology extension
 - build_dataset_ontologies(enriched_docs, core_file="core.ttl", output_dir="ontology")
   Creates separate standalone ontologies per dataset (grouped by source_type)
 - merge_ontologies(core_file="core.ttl", dynamic_file="dynamic.ttl", output_file="updated_core.ttl")
   Legacy function for merging ontologies (kept for backward compatibility)
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
    # Domain-specific classes (resume)
    "SKILL": "Skill",
    "WORKEXPERIENCE": "WorkExperience",
    "WORK_EXPERIENCE": "WorkExperience",
    "EDUCATION": "Education",
    "CERTIFICATION": "Certification",
    "PROJECT": "Project",
    # Domain-specific classes (research paper)
    "RESEARCHPAPER": "ResearchPaper",
    "RESEARCH_PAPER": "ResearchPaper",
    "AUTHOR": "Author",
    "METHODOLOGY": "Methodology",
    "FINDING": "Finding",
    "CITATION": "Citation",
    "RESEARCHTOPIC": "ResearchTopic",
    "RESEARCH_TOPIC": "ResearchTopic",
    # Domain-specific classes (business)
    "BUSINESSREPORT": "BusinessReport",
    "BUSINESS_REPORT": "BusinessReport",
    "COMPANY": "Company",
    "FINANCIALMETRIC": "FinancialMetric",
    "FINANCIAL_METRIC": "FinancialMetric",
    "MARKETSEGMENT": "MarketSegment",
    "MARKET_SEGMENT": "MarketSegment",
    "RECOMMENDATION": "Recommendation",
    # Domain-specific classes (technical)
    "TECHNICALDOCUMENTATION": "TechnicalDocumentation",
    "TECHNICAL_DOCUMENTATION": "TechnicalDocumentation",
    "API": "API",
    "ENDPOINT": "Endpoint",
    "PARAMETER": "Parameter",
    # Domain-specific classes (legal)
    "LEGALDOCUMENT": "LegalDocument",
    "LEGAL_DOCUMENT": "LegalDocument",
    "PARTY": "Party",
    "CLAUSE": "Clause",
    "OBLIGATION": "Obligation",
    # Domain-specific classes (medical)
    "MEDICALDOCUMENT": "MedicalDocument",
    "MEDICAL_DOCUMENT": "MedicalDocument",
    "PATIENT": "Patient",
    "DIAGNOSIS": "Diagnosis",
    "TREATMENT": "Treatment",
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
    # Domain-specific properties (resume)
    "HAS_SKILL",
    "WORKED_AT",
    "STUDIED_AT",
    "HAS_CERTIFICATION",
    "USED_SKILL",
    "AT_COMPANY",
    # Domain-specific properties (research)
    "AUTHORED_BY",
    "CITES",
    "USES_METHODOLOGY",
    "HAS_FINDING",
    "STUDIES_TOPIC",
    "AFFILIATED_WITH",
    # Domain-specific properties (business)
    "HAS_METRIC",
    "OPERATES_IN_SECTOR",
    "COMPETES_WITH",
    # Domain-specific properties (technical)
    "HAS_ENDPOINT",
    "ACCEPTS_PARAMETER",
    # Domain-specific properties (legal)
    "PARTY_TO",
    "HAS_CLAUSE",
    "HAS_OBLIGATION",
    # Domain-specific properties (medical)
    "HAS_CONDITION",
    "TREATED_WITH",
    "PRESCRIBED_TO",
}

__all__ = [
    "build_dynamic_ontology",
    "merge_ontologies",
    "build_dataset_ontologies",
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


def build_dataset_ontologies(
    enriched_docs: List[Dict[str, Any]],
    core_file: str | Path = "ontology/core.ttl",
    output_dir: str | Path = "ontology"
) -> Dict[str, Path]:
    """Generate completely separate ontology files per dataset (grouped by source_type).

    For each source_type group:
      - Build a standalone ontology with all discovered classes and properties
      - No merging with core - each ontology is independent
      - Add owl:versionInfo with timestamp and document count
      - Include both base classes (from BASE_CLASS_SYNONYMS) and new discovered classes

    Returns a mapping: { group_name: Path(dataset_ontology_file) }
    Also creates a combined union ontology 'combined_ontology.ttl' for convenience.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Group documents by source_type
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for doc in enriched_docs:
        gname = doc.get("source_type", "unknown") or "unknown"
        groups.setdefault(gname, []).append(doc)

    dataset_files: Dict[str, Path] = {}
    combined_graph = Graph()
    combined_graph.bind("kg", KG_NS)
    combined_graph.bind("owl", OWL)
    combined_graph.bind("rdfs", RDFS)
    combined_graph.bind("xsd", XSD)

    for group_name, docs in groups.items():
        # Create standalone ontology for this dataset
        dataset_g = Graph()
        dataset_g.bind("kg", KG_NS)
        dataset_g.bind("owl", OWL)
        dataset_g.bind("rdfs", RDFS)
        dataset_g.bind("xsd", XSD)

        # Track all classes used (base + new)
        all_classes = set()
        datatype_properties: Dict[str, Any] = {}
        object_properties = set()

        # Detect classes and datatype properties
        for entity in _iter_entities(docs):
            raw_type = str(entity.get("type", "Entity")).strip()
            normalized = raw_type.upper()
            mapped = BASE_CLASS_SYNONYMS.get(normalized)
            if mapped:
                all_classes.add(mapped)
            else:
                # Create PascalCase class name
                cls_name = _pascal_case(raw_type)
                all_classes.add(cls_name)

            attributes = entity.get("attributes", {}) or {}
            for key, value in attributes.items():
                xsd_type = _infer_xsd_type(value)
                if key not in datatype_properties:
                    datatype_properties[key] = xsd_type
                else:
                    datatype_properties[key] = _update_datatype_consensus(datatype_properties[key], xsd_type)

        # Detect object properties from relations
        for rel in _iter_relations(docs):
            rel_name = str(rel.get("relation", "")).strip()
            if not rel_name:
                continue
            rel_name_upper = rel_name.upper()
            # Include both base and new properties
            if rel_name_upper in BASE_OBJECT_PROPERTIES:
                object_properties.add(rel_name_upper)
            else:
                object_properties.add(rel_name_upper)

        # Add ontology metadata
        ont_uri = KG_NS[f"Ontology_{group_name}"]
        dataset_g.add((ont_uri, RDF.type, OWL.Ontology))
        dataset_g.add((ont_uri, OWL.versionInfo, Literal(f"{group_name}-{datetime.now().isoformat()}")))
        dataset_g.add((ont_uri, RDFS.comment, Literal(f"Standalone ontology for {group_name} dataset with {len(docs)} documents")))

        # Add all class declarations
        for cls in sorted(all_classes):
            dataset_g.add((KG_NS[cls], RDF.type, OWL.Class))
            dataset_g.add((KG_NS[cls], RDFS.label, Literal(cls)))

        # Add datatype properties
        for prop, dtype in sorted(datatype_properties.items()):
            dataset_g.add((KG_NS[prop], RDF.type, OWL.DatatypeProperty))
            dataset_g.add((KG_NS[prop], RDFS.range, dtype))
            dataset_g.add((KG_NS[prop], RDFS.label, Literal(prop)))

        # Add object properties
        for prop in sorted(object_properties):
            dataset_g.add((KG_NS[prop], RDF.type, OWL.ObjectProperty))
            dataset_g.add((KG_NS[prop], RDFS.label, Literal(prop)))

        # Save standalone dataset ontology
        dataset_file = out_dir / f"dataset_{group_name}_ontology.ttl"
        dataset_g.serialize(destination=str(dataset_file), format="turtle")
        dataset_files[group_name] = dataset_file
        
        logger.info(f"Created standalone ontology for {group_name}: {len(all_classes)} classes, "
                   f"{len(datatype_properties)} datatype properties, {len(object_properties)} object properties")

        # Add to combined graph
        for t in dataset_g:
            combined_graph.add(t)

    # Create combined ontology
    combined_file = out_dir / "combined_ontology.ttl"
    combined_ont_uri = KG_NS["CombinedOntology"]
    combined_graph.add((combined_ont_uri, RDF.type, OWL.Ontology))
    combined_graph.add((combined_ont_uri, OWL.versionInfo, Literal(f"combined-{datetime.now().isoformat()}")))
    combined_graph.add((combined_ont_uri, RDFS.comment, Literal(f"Union of {len(dataset_files)} dataset ontologies")))
    combined_graph.serialize(destination=str(combined_file), format="turtle")
    dataset_files["__combined__"] = combined_file

    logger.info(f"Created {len(dataset_files)-1} standalone dataset ontologies + combined ontology")
    return dataset_files
