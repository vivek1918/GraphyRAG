from neo4j import GraphDatabase
from utils.config_loader import get_config
from utils.logger import setup_logger
from typing import List, Dict, Any

logger = setup_logger(__name__)

class GraphManager:
    """
    Generalized graph database manager for chatbot operations
    Handles graph traversal, query generation, and relationship analysis
    """
    
    def __init__(self, config_path: str = None):
        self.config = get_config(config_path)
        self.neo4j_config = self.config.get_section('kg')
        
        neo4j_url = self.neo4j_config.get('neo4j_url', 'bolt://localhost:7687')
        neo4j_user = self.neo4j_config.get('neo4j_user', 'neo4j')
        neo4j_password = self.neo4j_config.get('neo4j_password', 'password')
        
        logger.info(f"Connecting to Neo4j at: {neo4j_url}")
        
        self.driver = GraphDatabase.driver(
            neo4j_url,
            auth=(neo4j_user, neo4j_password)
        )
    
    def close(self):
        if self.driver:
            self.driver.close()
    
    def execute_query(self, query: str, parameters: Dict = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results"""
        with self.driver.session(database=self.neo4j_config.get('neo4j_database', 'neo4j')) as session:
            try:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                logger.error(f"Query: {query}")
                logger.error(f"Parameters: {parameters}")
                return []
    
    def get_node_types(self) -> List[str]:
        """Get all node types in the graph"""
        query = """
        CALL db.labels() YIELD label
        RETURN label
        """
        results = self.execute_query(query)
        return [result['label'] for result in results]
    
    def get_relationship_types(self) -> List[str]:
        """Get all relationship types in the graph"""
        query = """
        CALL db.relationshipTypes() YIELD relationshipType
        RETURN relationshipType
        """
        results = self.execute_query(query)
        return [result['relationshipType'] for result in results]
    
    def find_nodes_by_property(self, property_name: str, property_value: str, 
                             node_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Find nodes by property value"""
        if node_type:
            query = f"""
            MATCH (n:{node_type})
            WHERE toLower(n.`{property_name}`) CONTAINS toLower($value)
            RETURN n, labels(n) as types
            LIMIT $limit
            """
        else:
            query = """
            MATCH (n)
            WHERE toLower(n.`{property_name}`) CONTAINS toLower($value)
            RETURN n, labels(n) as types
            LIMIT $limit
            """.format(property_name=property_name)
        
        return self.execute_query(query, {
            'value': property_value,
            'limit': limit
        })
    
    def traverse_from_node(self, node_id: str, max_depth: int = 2) -> Dict[str, Any]:
        """Traverse graph from a specific node"""
        query = """
        MATCH (start)
        WHERE elementId(start) = $node_id
        CALL apoc.path.subgraphAll(start, {
            maxLevel: $max_depth,
            relationshipFilter: null,
            labelFilter: null
        })
        YIELD nodes, relationships
        RETURN 
            [node in nodes | {
                id: elementId(node),
                labels: labels(node),
                properties: properties(node)
            }] as nodes,
            [rel in relationships | {
                id: elementId(rel),
                type: type(rel),
                start: elementId(startNode(rel)),
                end: elementId(endNode(rel)),
                properties: properties(rel)
            }] as relationships
        """
        
        results = self.execute_query(query, {
            'node_id': node_id,
            'max_depth': max_depth
        })
        
        return results[0] if results else {'nodes': [], 'relationships': []}
    
    def get_connected_nodes(self, node_id: str, relationship_type: str = None) -> List[Dict[str, Any]]:
        """Get nodes connected to a specific node"""
        if relationship_type:
            query = """
            MATCH (start)-[r:`{relationship_type}`]-(connected)
            WHERE elementId(start) = $node_id
            RETURN 
                elementId(connected) as id,
                labels(connected) as labels,
                properties(connected) as properties,
                type(r) as relationship_type
            """.format(relationship_type=relationship_type)
        else:
            query = """
            MATCH (start)-[r]-(connected)
            WHERE elementId(start) = $node_id
            RETURN 
                elementId(connected) as id,
                labels(connected) as labels,
                properties(connected) as properties,
                type(r) as relationship_type
            """
        
        return self.execute_query(query, {'node_id': node_id})
    
    def pattern_search(self, pattern_description: str) -> List[Dict[str, Any]]:
        """Search for patterns in the graph based on natural language description"""
        query = """
        MATCH (n)
        WHERE any(label in labels(n) WHERE toLower(label) CONTAINS toLower($pattern))
        OR any(prop in keys(n) WHERE toLower(toString(n[prop])) CONTAINS toLower($pattern))
        RETURN 
            elementId(n) as id,
            labels(n) as labels,
            properties(n) as properties
        LIMIT 20
        """
        
        return self.execute_query(query, {'pattern': pattern_description})
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """Get overall graph statistics"""
        query = """
        CALL apoc.meta.stats() YIELD 
            nodeCount, 
            relationshipCount, 
            labels, 
            relTypesCount
        RETURN 
            nodeCount, 
            relationshipCount, 
            labels, 
            relTypesCount
        """
        
        results = self.execute_query(query)
        return results[0] if results else {}