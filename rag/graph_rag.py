#!/usr/bin/env python3
"""
GraphRAG implementation combining vector search with knowledge graph reasoning.
"""

import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger

class GraphRAG:
    """GraphRAG system for natural language querying."""
    
    def __init__(self):
        self.vector_store = None
        self.fuseki_client = None
        self.setup_components()
        
    def setup_components(self):
        """Setup vector store and KG client."""
        from kg.fuseki_client import FusekiClient
        from rag.index_docs import DocumentIndexer
        
        self.fuseki_client = FusekiClient()
        # In practice, you'd initialize the vector store here
        
    async def query(self, question: str) -> Dict[str, Any]:
        """Answer natural language question using GraphRAG."""
        logger.info(f"Processing question: {question}")
        
        try:
            # Step 1: Retrieve relevant documents/text chunks
            text_context = await self.retrieve_text_context(question)
            
            # Step 2: Retrieve relevant subgraph from KG
            kg_context = await self.retrieve_kg_context(question)
            
            # Step 3: Generate answer using combined context
            answer = await self.generate_answer(question, text_context, kg_context)
            
            return answer
            
        except Exception as e:
            logger.error(f"Error in GraphRAG query: {e}")
            return {
                "answer": "I couldn't process your question at the moment.",
                "sources": [],
                "confidence": 0.0
            }
    
    async def retrieve_text_context(self, question: str) -> List[Dict[str, Any]]:
        """Retrieve relevant text chunks using vector search."""
        # This would use the vector store in practice
        # For demo, return empty context
        return []
    
    async def retrieve_kg_context(self, question: str) -> Dict[str, Any]:
        """Retrieve relevant subgraph from knowledge graph."""
        # Convert question to SPARQL or use graph traversal
        # For demo, use simple pattern matching
        
        q_lower = question.lower()
        if "works for" in q_lower:
            # Extract organization name (naive heuristic: everything after 'for')
            try:
                org_part = question.split("for", 1)[1].strip().rstrip('?')
                # Allow multi-word organization; trim excessive punctuation
                org_label = org_part[:100]
            except Exception:
                org_label = ""
            if org_label:
                sparql_query = f"""
                PREFIX : <http://kg.example.org/ontology/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                SELECT ?person ?personName
                WHERE {{
                    ?person a :Person ;
                            rdfs:label ?personName ;
                            :WORKS_FOR ?org .
                    ?org a :Organization ;
                         rdfs:label "{org_label}" .
                }}
                LIMIT 25
                """
                results = await self.fuseki_client.query(sparql_query)
                return {"type": "person_org", "results": results, "org": org_label}
        
        return {"type": "general", "results": []}
    
    async def generate_answer(self, question: str, text_context: List[Dict], kg_context: Dict) -> Dict[str, Any]:
        """Generate answer using combined context."""
        # In practice, this would use an LLM
        # For demo, use simple template-based answers
        
        # Fuseki returns JSON with structure: {'head':..., 'results': {'bindings': [...]}}
        bindings = []
        raw_results = kg_context.get("results")
        if isinstance(raw_results, dict):
            bindings = raw_results.get('results', {}).get('bindings', [])

        if kg_context.get("type") == "person_org" and bindings:
            people = []
            for b in bindings:
                # Each binding is a dict: {'person': {...}, 'personName': {'type': 'literal', 'value': 'John Smith'}}
                name_binding = b.get('personName') or b.get('name')
                if name_binding and isinstance(name_binding, dict):
                    people.append(name_binding.get('value'))
            if people:
                org_label = kg_context.get('org', 'the organization')
                return {
                    "answer": f"People who work for {org_label}: {', '.join(sorted(set(people)))}",
                    "sources": bindings[:5],  # limit sources
                    "confidence": 0.8
                }
        
        return {
            "answer": "I found some information in the knowledge graph, but couldn't generate a specific answer for your question.",
            "sources": bindings[:5],
            "confidence": 0.5
        }