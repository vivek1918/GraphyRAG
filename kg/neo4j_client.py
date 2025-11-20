#!/usr/bin/env python3
"""
Neo4j client for graph storage and visualization.
"""

import json
from typing import List, Dict, Any, Optional
from loguru import logger

class Neo4jClient:
    """Client for Neo4j graph database."""
    
    def __init__(self, 
                 uri: str = "bolt://localhost:7687",
                 username: str = "neo4j",
                 password: str = "password"):
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None
        self._initialize_driver()
    
    def _initialize_driver(self):
        """Initialize Neo4j driver."""
        try:
            from neo4j import GraphDatabase
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password)
            )
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info("Neo4j driver initialized successfully")
        except ImportError:
            logger.error("Neo4j Python driver not installed. Install with: pip install neo4j")
            self.driver = None
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j driver: {e}")
            self.driver = None
    
    async def load_graph(self, nodes: List[Dict], relationships: List[Dict]) -> Dict[str, int]:
        """Load nodes and relationships into Neo4j."""
        if not self.driver:
            logger.warning("Neo4j driver not available")
            return {"nodes": 0, "relationships": 0}
        
        try:
            with self.driver.session() as session:
                # Clear existing data (optional - comment out to keep existing data)
                session.run("MATCH (n) DETACH DELETE n")
                
                # Load nodes
                node_count = 0
                for node in nodes:
                    try:
                        self._create_node(session, node)
                        node_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to create node {node.get('id')}: {e}")
                
                # Load relationships
                rel_count = 0
                for rel in relationships:
                    try:
                        self._create_relationship(session, rel)
                        rel_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to create relationship: {e}")
                
                logger.info(f"Loaded {node_count} nodes and {rel_count} relationships into Neo4j")
                return {"nodes": node_count, "relationships": rel_count}
                
        except Exception as e:
            logger.error(f"Error loading graph into Neo4j: {e}")
            return {"nodes": 0, "relationships": 0}
    
    def _create_node(self, session, node: Dict):
        """Create a node in Neo4j."""
        labels = ":".join(node['labels'])
        properties = self._format_properties(node['properties'])
        
        query = f"""
        MERGE (n:{labels} {{id: $id}})
        SET n += $properties
        """
        
        session.run(query, id=node['id'], properties=node['properties'])
    
    def _create_relationship(self, session, relationship: Dict):
        """Create a relationship in Neo4j."""
        query = f"""
        MATCH (a {{id: $start_id}}), (b {{id: $end_id}})
        MERGE (a)-[r:{relationship['type']}]->(b)
        SET r += $properties
        """
        
        session.run(
            query, 
            start_id=relationship['start_node'],
            end_id=relationship['end_node'],
            properties=relationship.get('properties', {})
        )
    
    def _format_properties(self, properties: Dict) -> str:
        """Format properties for Cypher query."""
        if not properties:
            return "{}"
        
        formatted = []
        for key, value in properties.items():
            if isinstance(value, str):
                escaped = value.replace("'", "\\'")
                formatted.append(f"{key}: '{escaped}'")
            elif isinstance(value, bool):
                # Cypher expects lower-case true/false
                formatted.append(f"{key}: {str(value).lower()}")
            else:
                # Use json.dumps for numbers, lists, dicts to produce valid literal
                formatted.append(f"{key}: {json.dumps(value)}")
        
        return "{" + ", ".join(formatted) + "}"
    
    async def run_query(self, query: str, **params) -> List[Dict]:
        """Run a Cypher query and return results."""
        if not self.driver:
            return []
        
        try:
            with self.driver.session() as session:
                result = session.run(query, **params)
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Neo4j query failed: {e}")
            return []
    
    async def get_graph_stats(self) -> Dict[str, Any]:
        """Get graph statistics from Neo4j."""
        queries = {
            "node_counts": "MATCH (n) RETURN labels(n) AS labels, count(*) AS count",
            "relationship_counts": "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count",
            "graph_size": "MATCH (n) RETURN count(n) AS node_count"
        }
        
        stats = {}
        for name, query in queries.items():
            stats[name] = await self.run_query(query)
        
        return stats
    
    async def export_visualization_data(self, output_path: str) -> Dict[str, Any]:
        """Export data for visualization."""
        # Get sample of each node type with their relationships
        visualization_data = {}
        
        # Get all node labels
        labels_query = "CALL db.labels() YIELD label RETURN label"
        labels = await self.run_query(labels_query)
        
        for label_record in labels:
            label = label_record['label']
            
            # Get sample nodes of this label with their relationships
            sample_query = f"""
            MATCH (n:{label})
            OPTIONAL MATCH (n)-[r]->(m)
            WITH n, collect({{type: type(r), end_node: m.id, end_label: labels(m)[0]}}) as out_rels
            OPTIONAL MATCH (p)-[r2]->(n)
            WITH n, out_rels, collect({{type: type(r2), start_node: p.id, start_label: labels(p)[0]}}) as in_rels
            RETURN n.id as id, n.name as name, labels(n) as labels, 
                   properties(n) as properties, out_rels, in_rels
            LIMIT 10
            """
            
            nodes = await self.run_query(sample_query)
            visualization_data[label] = nodes
        
        # Save to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(visualization_data, f, indent=2, default=str)
        
        logger.info(f"Visualization data exported to {output_path}")
        return visualization_data
    
    def close(self):
        """Close the Neo4j driver."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j driver closed")