#!/usr/bin/env python3
"""
FastAPI server for the Knowledge Graph system.
Provides REST API for querying and managing the KG.
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncio
import uvicorn
from loguru import logger

from kg.fuseki_client import FusekiClient
from rag.graph_rag import GraphRAG
from rag.retrievers import VectorRetriever, GraphRetriever, HybridRetriever, MultiModalRetriever
from rag.index_docs import DocumentIndexer

# Pydantic models for API
class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    retriever_type: str = "hybrid"  # vector, graph, hybrid, multimodal

class SPARQLRequest(BaseModel):
    query: str
    format: str = "json"

class DocumentRequest(BaseModel):
    doc_id: str
    include_entities: bool = True
    include_relations: bool = True

class IndexRequest(BaseModel):
    force_rebuild: bool = False

class APIResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    message: Optional[str] = None

class KnowledgeGraphAPI:
    """Knowledge Graph API server."""
    
    def __init__(self):
        self.app = FastAPI(
            title="Semantic Knowledge Graph API",
            description="REST API for querying and managing the knowledge graph",
            version="1.0.0"
        )
        
        # Initialize components
        self.fuseki_client = FusekiClient()
        self.graph_rag = GraphRAG()
        self.indexer = DocumentIndexer()
        
        # Setup retrievers
        self.vector_retriever = VectorRetriever(self.indexer)
        self.graph_retriever = GraphRetriever(self.fuseki_client)
        self.hybrid_retriever = HybridRetriever([
            self.vector_retriever, 
            self.graph_retriever
        ])
        self.multimodal_retriever = MultiModalRetriever(
            self.vector_retriever, 
            self.graph_retriever
        )
        
        self.setup_middleware()
        self.setup_routes()
    
    def setup_middleware(self):
        """Setup CORS and other middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # In production, restrict this
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def setup_routes(self):
        """Setup API routes."""
        
        @self.app.get("/")
        async def root():
            return {
                "message": "Semantic Knowledge Graph API",
                "version": "1.0.0",
                "endpoints": {
                    "health": "/health",
                    "query": "/query",
                    "sparql": "/sparql",
                    "entities": "/entities",
                    "relations": "/relations",
                    "documents": "/documents/{doc_id}",
                    "index": "/index"
                }
            }
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            try:
                # Check Fuseki connection
                fuseki_healthy = await self.fuseki_client.health_check()
                
                # Check index status
                index_stats = await self.indexer.get_index_stats()
                
                return APIResponse(
                    success=fuseki_healthy,
                    data={
                        "fuseki_available": fuseki_healthy,
                        "index_status": "healthy" if index_stats else "unknown",
                        "index_stats": index_stats
                    },
                    message="Service status checked"
                )
            except Exception as e:
                return APIResponse(
                    success=False,
                    error=str(e),
                    message="Health check failed"
                )
        
        @self.app.post("/query")
        async def natural_language_query(request: QueryRequest):
            """Natural language query endpoint."""
            try:
                # Select retriever based on request
                if request.retriever_type == "vector":
                    retriever = self.vector_retriever
                elif request.retriever_type == "graph":
                    retriever = self.graph_retriever
                elif request.retriever_type == "multimodal":
                    retriever = self.multimodal_retriever
                else:  # hybrid default
                    retriever = self.hybrid_retriever
                
                # Retrieve relevant information
                retrieved_data = await retriever.retrieve(
                    request.query, 
                    top_k=request.top_k
                )
                
                # Use GraphRAG for answer generation
                answer = await self.graph_rag.query(request.query)
                
                return APIResponse(
                    success=True,
                    data={
                        "query": request.query,
                        "answer": answer.get("answer", "No answer generated"),
                        "sources": answer.get("sources", []),
                        "retrieved_data": retrieved_data,
                        "confidence": answer.get("confidence", 0.0)
                    },
                    message="Query processed successfully"
                )
                
            except Exception as e:
                logger.error(f"Query processing error: {e}")
                return APIResponse(
                    success=False,
                    error=str(e),
                    message="Query processing failed"
                )
        
        @self.app.post("/sparql")
        async def sparql_query(request: SPARQLRequest):
            """Direct SPARQL query endpoint."""
            try:
                results = await self.fuseki_client.query(request.query)
                
                return APIResponse(
                    success=True,
                    data={
                        "query": request.query,
                        "results": results,
                        "count": len(results)
                    },
                    message="SPARQL query executed successfully"
                )
                
            except Exception as e:
                logger.error(f"SPARQL query error: {e}")
                return APIResponse(
                    success=False,
                    error=str(e),
                    message="SPARQL query failed"
                )
        
        @self.app.get("/entities")
        async def get_entities(
            entity_type: Optional[str] = Query(None),
            limit: int = Query(50, le=1000),
            offset: int = Query(0)
        ):
            """Get entities from knowledge graph."""
            try:
                # Build SPARQL query based on parameters
                if entity_type:
                    sparql_query = f"""
                    PREFIX : <http://kg.example.org/ontology/>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    
                    SELECT ?entity ?label ?type
                    WHERE {{
                        ?entity a :{entity_type} ;
                                rdfs:label ?label .
                        BIND("{entity_type}" as ?type)
                    }}
                    ORDER BY ?label
                    LIMIT {limit}
                    OFFSET {offset}
                    """
                else:
                    sparql_query = f"""
                    PREFIX : <http://kg.example.org/ontology/>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    
                    SELECT ?entity ?label ?type
                    WHERE {{
                        ?entity a ?type ;
                                rdfs:label ?label .
                        FILTER(STRSTARTS(STR(?type), "http://kg.example.org/ontology/"))
                    }}
                    ORDER BY ?label
                    LIMIT {limit}
                    OFFSET {offset}
                    """
                
                results = await self.fuseki_client.query(sparql_query)
                
                return APIResponse(
                    success=True,
                    data={
                        "entities": results,
                        "total_count": len(results),
                        "parameters": {
                            "entity_type": entity_type,
                            "limit": limit,
                            "offset": offset
                        }
                    },
                    message="Entities retrieved successfully"
                )
                
            except Exception as e:
                logger.error(f"Entities retrieval error: {e}")
                return APIResponse(
                    success=False,
                    error=str(e),
                    message="Entities retrieval failed"
                )
        
        @self.app.get("/relations")
        async def get_relations(
            relation_type: Optional[str] = Query(None),
            limit: int = Query(50, le=1000),
            offset: int = Query(0)
        ):
            """Get relations from knowledge graph."""
            try:
                # Build SPARQL query
                if relation_type:
                    sparql_query = f"""
                    PREFIX : <http://kg.example.org/ontology/>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    
                    SELECT ?subject ?subjectLabel ?predicate ?object ?objectLabel
                    WHERE {{
                        ?subject :{relation_type} ?object .
                        ?subject rdfs:label ?subjectLabel .
                        ?object rdfs:label ?objectLabel .
                        BIND(:"{relation_type}" as ?predicate)
                    }}
                    LIMIT {limit}
                    OFFSET {offset}
                    """
                else:
                    sparql_query = f"""
                    PREFIX : <http://kg.example.org/ontology/>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    
                    SELECT ?subject ?subjectLabel ?predicate ?object ?objectLabel
                    WHERE {{
                        ?subject ?predicate ?object .
                        ?subject rdfs:label ?subjectLabel .
                        ?object rdfs:label ?objectLabel .
                        FILTER(STRSTARTS(STR(?predicate), "http://kg.example.org/ontology/"))
                    }}
                    LIMIT {limit}
                    OFFSET {offset}
                    """
                
                results = await self.fuseki_client.query(sparql_query)
                
                return APIResponse(
                    success=True,
                    data={
                        "relations": results,
                        "total_count": len(results),
                        "parameters": {
                            "relation_type": relation_type,
                            "limit": limit,
                            "offset": offset
                        }
                    },
                    message="Relations retrieved successfully"
                )
                
            except Exception as e:
                logger.error(f"Relations retrieval error: {e}")
                return APIResponse(
                    success=False,
                    error=str(e),
                    message="Relations retrieval failed"
                )
        
        @self.app.get("/documents/{doc_id}")
        async def get_document(doc_id: str, include_entities: bool = True, include_relations: bool = True):
            """Get document information and its extracted content."""
            try:
                # This would typically query a document store
                # For demo, return basic information
                
                document_data = {
                    "doc_id": doc_id,
                    "type": "unknown",
                    "content": "Document content would be here",
                    "metadata": {}
                }
                
                # Add entities if requested
                if include_entities:
                    # Query entities for this document
                    sparql_query = f"""
                    PREFIX : <http://kg.example.org/ontology/>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    
                    SELECT ?entity ?label ?type
                    WHERE {{
                        ?entity :extractedFrom :{doc_id} ;
                                rdfs:label ?label ;
                                a ?type .
                    }}
                    """
                    entities = await self.fuseki_client.query(sparql_query)
                    document_data["entities"] = entities
                
                # Add relations if requested
                if include_relations:
                    # Query relations involving entities from this document
                    sparql_query = f"""
                    PREFIX : <http://kg.example.org/ontology/>
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    
                    SELECT ?subject ?subjectLabel ?predicate ?object ?objectLabel
                    WHERE {{
                        ?subject :extractedFrom :{doc_id} ;
                                ?predicate ?object .
                        ?subject rdfs:label ?subjectLabel .
                        ?object rdfs:label ?objectLabel .
                        FILTER(STRSTARTS(STR(?predicate), "http://kg.example.org/ontology/"))
                    }}
                    """
                    relations = await self.fuseki_client.query(sparql_query)
                    document_data["relations"] = relations
                
                return APIResponse(
                    success=True,
                    data=document_data,
                    message="Document information retrieved"
                )
                
            except Exception as e:
                logger.error(f"Document retrieval error: {e}")
                return APIResponse(
                    success=False,
                    error=str(e),
                    message="Document retrieval failed"
                )
        
        @self.app.post("/index")
        async def rebuild_index(background_tasks: BackgroundTasks, request: IndexRequest = None):
            """Rebuild the document index."""
            try:
                if request and request.force_rebuild:
                    # In a real implementation, this would trigger index rebuilding
                    background_tasks.add_task(self._rebuild_index_async)
                    return APIResponse(
                        success=True,
                        message="Index rebuild started in background"
                    )
                else:
                    index_stats = await self.indexer.get_index_stats()
                    return APIResponse(
                        success=True,
                        data={"index_stats": index_stats},
                        message="Index status retrieved"
                    )
                    
            except Exception as e:
                logger.error(f"Index operation error: {e}")
                return APIResponse(
                    success=False,
                    error=str(e),
                    message="Index operation failed"
                )
        
        @self.app.get("/analytics")
        async def get_analytics():
            """Get knowledge graph analytics."""
            try:
                # Run analytical queries
                with open("kg/queries/analytics.sparql", "r") as f:
                    analytics_queries = f.read()
                
                # Split queries and execute
                queries = analytics_queries.split('#')
                analytics_results = {}
                
                for i, query in enumerate(queries):
                    if query.strip() and not query.strip().startswith('Knowledge Graph Analytics'):
                        try:
                            results = await self.fuseki_client.query(query)
                            analytics_results[f"query_{i}"] = {
                                "description": query.split('\n')[0].strip('# ').strip(),
                                "results": results
                            }
                        except Exception as e:
                            logger.warning(f"Analytics query {i} failed: {e}")
                
                return APIResponse(
                    success=True,
                    data=analytics_results,
                    message="Analytics data retrieved"
                )
                
            except Exception as e:
                logger.error(f"Analytics error: {e}")
                return APIResponse(
                    success=False,
                    error=str(e),
                    message="Analytics retrieval failed"
                )
    
    async def _rebuild_index_async(self):
        """Background task to rebuild index."""
        try:
            logger.info("Starting background index rebuild...")
            # This would load documents and rebuild the index
            # For demo, we'll just log
            await asyncio.sleep(2)  # Simulate work
            logger.info("Background index rebuild completed")
        except Exception as e:
            logger.error(f"Background index rebuild failed: {e}")
    
    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the API server."""
        uvicorn.run(self.app, host=host, port=port)

# Create and run the application
app = KnowledgeGraphAPI().app

if __name__ == "__main__":
    api = KnowledgeGraphAPI()
    api.run()