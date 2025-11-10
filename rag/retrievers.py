#!/usr/bin/env python3
"""
Retriever classes for different retrieval strategies.
"""

import json
from typing import List, Dict, Any, Optional
from loguru import logger

class BaseRetriever:
    """Base class for all retrievers."""
    
    def __init__(self, name: str = "base"):
        self.name = name
    
    async def retrieve(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Retrieve relevant information for query."""
        raise NotImplementedError


class VectorRetriever(BaseRetriever):
    """Vector-based retriever using semantic similarity."""
    
    def __init__(self, indexer):
        super().__init__("vector")
        self.indexer = indexer
    
    async def retrieve(self, query: str, top_k: int = 5, **kwargs) -> List[Dict[str, Any]]:
        """Retrieve using vector similarity."""
        try:
            results = await self.indexer.search(query, top_k)
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'content': result['chunk']['text'],
                    'metadata': result['chunk']['metadata'],
                    'score': result['score'],
                    'type': 'text_chunk',
                    'retriever': self.name
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error in vector retrieval: {e}")
            return []


class GraphRetriever(BaseRetriever):
    """Knowledge graph-based retriever."""
    
    def __init__(self, fuseki_client):
        super().__init__("graph")
        self.fuseki_client = fuseki_client
    
    async def retrieve(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Retrieve using knowledge graph queries."""
        try:
            # Convert query to SPARQL or use entity extraction
            entities = await self._extract_entities_from_query(query)
            graph_results = []
            
            for entity in entities:
                entity_results = await self._query_entity_subgraph(entity)
                graph_results.extend(entity_results)
            
            # Deduplicate and format
            unique_results = await self._deduplicate_graph_results(graph_results)
            
            return unique_results[:kwargs.get('top_k', 5)]
            
        except Exception as e:
            logger.error(f"Error in graph retrieval: {e}")
            return []
    
    async def _extract_entities_from_query(self, query: str) -> List[str]:
        """Extract potential entities from query."""
        # Simple entity extraction for demo
        # In practice, you'd use NER here
        entities = []
        words = query.split()
        
        # Look for capitalized words (simple heuristic)
        for word in words:
            if len(word) > 2 and word[0].isupper():
                entities.append(word)
        
        return entities
    
    async def _query_entity_subgraph(self, entity: str) -> List[Dict[str, Any]]:
        """Query subgraph around an entity."""
        sparql_query = f"""
        PREFIX : <http://kg.example.org/ontology/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        
        SELECT ?entity ?label ?relation ?relatedEntity ?relatedLabel
        WHERE {{
          ?entity rdfs:label ?label .
          ?entity ?relation ?relatedEntity .
          ?relatedEntity rdfs:label ?relatedLabel .
          FILTER(STRSTARTS(STR(?relation), "http://kg.example.org/ontology/"))
          FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{entity.lower()}")))
        }}
        LIMIT 10
        """
        
        try:
            results = await self.fuseki_client.query(sparql_query)
            formatted_results = []
            
            for result in results:
                formatted_results.append({
                    'content': f"{result.get('label')} {result.get('relation').split('/')[-1]} {result.get('relatedLabel')}",
                    'metadata': {
                        'entity': result.get('entity'),
                        'relation': result.get('relation'),
                        'related_entity': result.get('relatedEntity'),
                        'source': 'knowledge_graph'
                    },
                    'score': 0.8,  # Default confidence for graph results
                    'type': 'graph_relation',
                    'retriever': self.name
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error querying graph for entity {entity}: {e}")
            return []
    
    async def _deduplicate_graph_results(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicate graph results."""
        seen = set()
        unique_results = []
        
        for result in results:
            key = result['content']
            if key not in seen:
                seen.add(key)
                unique_results.append(result)
        
        return unique_results


class HybridRetriever(BaseRetriever):
    """Hybrid retriever combining multiple strategies."""
    
    def __init__(self, retrievers: List[BaseRetriever]):
        super().__init__("hybrid")
        self.retrievers = retrievers
    
    async def retrieve(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Retrieve using multiple strategies and combine results."""
        all_results = []
        
        # Retrieve from all strategies
        for retriever in self.retrievers:
            try:
                results = await retriever.retrieve(query, **kwargs)
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Error in {retriever.name} retriever: {e}")
        
        # Rank and combine results
        combined_results = await self._rank_and_combine(all_results, **kwargs)
        
        return combined_results
    
    async def _rank_and_combine(self, results: List[Dict], **kwargs) -> List[Dict]:
        """Rank and combine results from multiple retrievers."""
        # Simple combination: sort by score and deduplicate
        seen_content = set()
        ranked_results = []
        
        # Sort by score
        results.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        for result in results:
            content_key = result['content'][:100]  # Use first 100 chars as key
            if content_key not in seen_content:
                seen_content.add(content_key)
                ranked_results.append(result)
        
        # Apply top_k limit
        top_k = kwargs.get('top_k', 10)
        return ranked_results[:top_k]


class MultiModalRetriever(BaseRetriever):
    """Multi-modal retriever for different content types."""
    
    def __init__(self, vector_retriever: VectorRetriever, graph_retriever: GraphRetriever):
        super().__init__("multimodal")
        self.vector_retriever = vector_retriever
        self.graph_retriever = graph_retriever
    
    async def retrieve(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Retrieve multi-modal information."""
        text_results = await self.vector_retriever.retrieve(query, **kwargs)
        graph_results = await self.graph_retriever.retrieve(query, **kwargs)
        
        # Combine with different weights
        combined = []
        
        # Text results get base scores
        for result in text_results:
            combined.append(result)
        
        # Graph results get boosted scores for certain query types
        for result in graph_results:
            # Boost graph results for relationship queries
            if any(word in query.lower() for word in ['relationship', 'connected', 'works with', 'related to']):
                result['score'] = min(1.0, result.get('score', 0) + 0.2)
            combined.append(result)
        
        # Sort by score
        combined.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        # Apply diversity: ensure mix of result types
        final_results = await self._ensure_diversity(combined, **kwargs)
        
        return final_results
    
    async def _ensure_diversity(self, results: List[Dict], **kwargs) -> List[Dict]:
        """Ensure diversity in result types."""
        text_results = [r for r in results if r.get('type') == 'text_chunk']
        graph_results = [r for r in results if r.get('type') == 'graph_relation']
        
        top_k = kwargs.get('top_k', 10)
        diversified = []
        
        # Take top results from each category
        max_per_type = max(1, top_k // 2)
        
        diversified.extend(text_results[:max_per_type])
        diversified.extend(graph_results[:max_per_type])
        
        # Fill remaining slots with highest scoring overall
        remaining_slots = top_k - len(diversified)
        if remaining_slots > 0:
            all_results = sorted(results, key=lambda x: x.get('score', 0), reverse=True)
            for result in all_results:
                if result not in diversified and len(diversified) < top_k:
                    diversified.append(result)
        
        return diversified[:top_k]