#!/usr/bin/env python3
"""
Graph Retrieval-Augmented Generation (GraphRAG) system.
Combines graph queries with vector search for enhanced retrieval.
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
from loguru import logger
import json

from kg.fuseki_client import FusekiClient
from rag.retrievers import VectorRetriever, GraphRetriever, HybridRetriever


class GraphRAG:
    """Graph-based RAG system combining semantic and graph search."""
    
    def __init__(self, index_path: Optional[Path] = None):
        self.fuseki_client = FusekiClient()
        self.vector_retriever = VectorRetriever(indexer=None)  # Will initialize with real indexer later
        self.graph_retriever = GraphRetriever(self.fuseki_client)
        self.hybrid_retriever = HybridRetriever([self.vector_retriever, self.graph_retriever])
        self.index_path = index_path or Path("data/processed/rag_index.json")
        self._load_index()
        
    def _load_index(self):
        """Load RAG index if available."""
        try:
            if self.index_path.exists():
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    self.index_data = json.load(f)
                logger.info(f"Loaded RAG index with {len(self.index_data.get('documents', []))} documents")
            else:
                logger.warning(f"RAG index not found at {self.index_path}")
                self.index_data = {"documents": [], "entities": {}, "relations": []}
        except Exception as e:
            logger.error(f"Failed to load RAG index: {e}")
            self.index_data = {"documents": [], "entities": {}, "relations": []}
    
    async def query(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """Process a question using GraphRAG."""
        logger.info(f"Processing question: {question}")
        
        try:
            # Step 1: Extract entities from question
            entities = self._extract_query_entities(question)
            logger.debug(f"Extracted entities from query: {entities}")
            
            # Step 2: Query knowledge graph for related entities and relations
            graph_results = await self._query_graph(entities, question)
            logger.debug(f"Graph query returned {len(graph_results)} results")
            
            # Step 3: Search in local index for context
            context_results = self._search_local_index(question, entities, top_k)
            logger.debug(f"Local search returned {len(context_results)} results")
            
            # Step 4: Combine and format results
            answer = self._generate_answer(question, graph_results, context_results)
            
            return {
                "question": question,
                "answer": answer["text"],
                "sources": graph_results + context_results,
                "context": context_results,
                "confidence": answer.get("confidence", 0.5)
            }
            
        except Exception as e:
            logger.error(f"GraphRAG query failed: {e}")
            return {
                "question": question,
                "answer": f"Error processing query: {str(e)}",
                "sources": [],
                "context": [],
                "confidence": 0.0
            }
    
    def _extract_query_entities(self, question: str) -> List[str]:
        """Extract potential entity names from question."""
        # Simple heuristic: look for capitalized phrases
        import re
        
        # Look for capitalized words (potential names)
        words = question.split()
        entities = []
        current_entity = []
        
        for word in words:
            # Remove punctuation
            clean_word = re.sub(r'[^\w\s]', '', word)
            if clean_word and clean_word[0].isupper() and clean_word.lower() not in [
                'what', 'who', 'where', 'when', 'why', 'how', 'does', 'is', 'are', 'the'
            ]:
                current_entity.append(clean_word)
            else:
                if current_entity:
                    entities.append(' '.join(current_entity))
                    current_entity = []
        
        if current_entity:
            entities.append(' '.join(current_entity))
        
        logger.debug(f"Extracted entities: {entities}")
        return entities
    
    async def _query_graph(self, entities: List[str], question: str) -> List[Dict[str, Any]]:
        """Query the knowledge graph for relevant information."""
        results = []
        
        try:
            for entity_name in entities:
                # Query 1: Find entity and its properties
                entity_query = f"""
                PREFIX kg: <http://kg.example.org/ontology/>
                PREFIX ent: <http://kg.example.org/entity/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT DISTINCT ?entity ?label ?type ?prop ?value
                WHERE {{
                    ?entity rdfs:label ?label .
                    ?entity a ?type .
                    OPTIONAL {{ ?entity ?prop ?value }}
                    FILTER(CONTAINS(LCASE(?label), LCASE("{entity_name}")))
                }}
                LIMIT 20
                """
                
                entity_results = await self.fuseki_client.query(entity_query)
                if entity_results and isinstance(entity_results, dict):
                    bindings = entity_results.get('results', {}).get('bindings', [])
                    for binding in bindings:
                        results.append({
                            "type": "entity",
                            "entity": binding.get('label', {}).get('value', ''),
                            "entity_type": binding.get('type', {}).get('value', '').split('/')[-1],
                            "property": binding.get('prop', {}).get('value', '').split('/')[-1] if 'prop' in binding else None,
                            "value": binding.get('value', {}).get('value', '') if 'value' in binding else None,
                            "text": self._format_entity_info(binding)
                        })
                
                # Query 2: Find relations involving this entity
                relations_query = f"""
                PREFIX kg: <http://kg.example.org/ontology/>
                PREFIX ent: <http://kg.example.org/entity/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX rel: <http://kg.example.org/relation/>
                
                SELECT DISTINCT ?rel ?relType ?subj ?subjLabel ?obj ?objLabel ?confidence ?evidence
                WHERE {{
                    ?rel a kg:Relation ;
                         kg:relationType ?relType ;
                         kg:hasSubject ?subj ;
                         kg:hasObject ?obj .
                    ?subj rdfs:label ?subjLabel .
                    ?obj rdfs:label ?objLabel .
                    OPTIONAL {{ ?rel kg:confidence ?confidence }}
                    OPTIONAL {{ ?rel kg:evidence ?evidence }}
                    FILTER(CONTAINS(LCASE(?subjLabel), LCASE("{entity_name}")) || 
                           CONTAINS(LCASE(?objLabel), LCASE("{entity_name}")))
                }}
                LIMIT 20
                """
                
                relation_results = await self.fuseki_client.query(relations_query)
                if relation_results and isinstance(relation_results, dict):
                    bindings = relation_results.get('results', {}).get('bindings', [])
                    for binding in bindings:
                        results.append({
                            "type": "relation",
                            "subject": binding.get('subjLabel', {}).get('value', ''),
                            "relation": binding.get('relType', {}).get('value', ''),
                            "object": binding.get('objLabel', {}).get('value', ''),
                            "confidence": float(binding.get('confidence', {}).get('value', 0.5)),
                            "evidence": binding.get('evidence', {}).get('value', ''),
                            "text": self._format_relation_info(binding)
                        })
        
        except Exception as e:
            logger.error(f"Graph query failed: {e}")
        
        return results
    
    def _search_local_index(self, question: str, entities: List[str], top_k: int) -> List[Dict[str, Any]]:
        """Search local RAG index for relevant context."""
        results = []
        
        try:
            # Search in indexed documents
            docs = self.index_data.get('documents', [])
            for doc in docs:
                score = self._calculate_relevance(question, entities, doc)
                if score > 0.3:  # Threshold
                    results.append({
                        "type": "document",
                        "doc_id": doc.get('doc_id', ''),
                        "content": doc.get('content', '')[:200] + '...',
                        "score": score,
                        "text": doc.get('content', '')[:200] + '...'
                    })
            
            # Search in entity index
            entity_index = self.index_data.get('entities', {})
            for entity_name in entities:
                for indexed_entity, info in entity_index.items():
                    if entity_name.lower() in indexed_entity.lower():
                        results.append({
                            "type": "entity_info",
                            "entity": indexed_entity,
                            "info": info,
                            "text": f"{indexed_entity}: {json.dumps(info)}"
                        })
            
            # Sort by score and limit
            results.sort(key=lambda x: x.get('score', 0.5), reverse=True)
            return results[:top_k]
            
        except Exception as e:
            logger.error(f"Local index search failed: {e}")
            return []
    
    def _calculate_relevance(self, question: str, entities: List[str], doc: Dict) -> float:
        """Calculate relevance score between query and document."""
        score = 0.0
        content = doc.get('content', '').lower()
        question_lower = question.lower()
        
        # Check entity mentions
        for entity in entities:
            if entity.lower() in content:
                score += 0.3
        
        # Check keyword overlap
        question_words = set(question_lower.split())
        content_words = set(content.split())
        overlap = len(question_words & content_words)
        score += min(overlap * 0.1, 0.5)
        
        return min(score, 1.0)
    
    def _format_entity_info(self, binding: Dict) -> str:
        """Format entity information for display."""
        label = binding.get('label', {}).get('value', 'Unknown')
        entity_type = binding.get('type', {}).get('value', '').split('/')[-1]
        prop = binding.get('prop', {}).get('value', '').split('/')[-1] if 'prop' in binding else None
        value = binding.get('value', {}).get('value', '') if 'value' in binding else None
        
        if prop and value and prop not in ['type', 'label']:
            return f"{label} ({entity_type}): {prop} = {value}"
        return f"{label} is a {entity_type}"
    
    def _format_relation_info(self, binding: Dict) -> str:
        """Format relation information for display."""
        subj = binding.get('subjLabel', {}).get('value', 'Unknown')
        rel = binding.get('relType', {}).get('value', 'related to')
        obj = binding.get('objLabel', {}).get('value', 'Unknown')
        evidence = binding.get('evidence', {}).get('value', '')
        
        # Convert relation to readable format
        rel_readable = rel.replace('_', ' ').lower()
        
        result = f"{subj} {rel_readable} {obj}"
        if evidence:
            result += f" (Evidence: {evidence[:100]}...)"
        
        return result
    
    def _generate_answer(self, question: str, graph_results: List[Dict], 
                        context_results: List[Dict]) -> Dict[str, Any]:
        """Generate answer from combined results."""
        if not graph_results and not context_results:
            return {
                "text": "I couldn't find any relevant information in the knowledge graph for your question.",
                "confidence": 0.0
            }
        
        # Prioritize relation results for specific questions
        relations = [r for r in graph_results if r.get('type') == 'relation']
        entities = [r for r in graph_results if r.get('type') == 'entity']
        
        answer_parts = []
        
        # Build answer from relations
        if relations:
            answer_parts.append("Based on the knowledge graph:")
            for rel in relations[:5]:  # Top 5 relations
                answer_parts.append(f"  • {rel['text']}")
        
        # Add entity information
        if entities:
            if not relations:
                answer_parts.append("I found information about:")
            for ent in entities[:5]:  # Top 5 entities
                if ent.get('property') and ent.get('value'):
                    answer_parts.append(f"  • {ent['text']}")
        
        # Add context if no graph results
        if not answer_parts and context_results:
            answer_parts.append("From the documents:")
            for ctx in context_results[:3]:
                answer_parts.append(f"  • {ctx['text']}")
        
        if not answer_parts:
            return {
                "text": "I found some information in the knowledge graph, but couldn't generate a specific answer for your question.",
                "confidence": 0.3
            }
        
        confidence = 0.8 if relations else (0.6 if entities else 0.4)
        
        return {
            "text": "\n".join(answer_parts),
            "confidence": confidence
        }