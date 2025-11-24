from neo4j import GraphDatabase
from utils.config_loader import get_config
from utils.logger import setup_logger
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

logger = setup_logger(__name__)


class GraphManager:
    """
    Generalized graph database manager for chatbot operations.
    Handles graph traversal, query generation, and relationship analysis.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config = get_config(config_path)
        self.neo4j_config = self.config.get_section('kg')
        
        neo4j_url = self.neo4j_config.get('neo4j_url', 'bolt://localhost:7687')
        neo4j_user = self.neo4j_config.get('neo4j_user', 'neo4j')
        neo4j_password = self.neo4j_config.get('neo4j_password', 'password')
        self.database = self.neo4j_config.get('neo4j_database', 'neo4j')
        
        logger.info(f"Connecting to Neo4j at: {neo4j_url}")
        
        self.driver = GraphDatabase.driver(
            neo4j_url,
            auth=(neo4j_user, neo4j_password),
            max_connection_lifetime=3600,
            max_connection_pool_size=50,
            connection_acquisition_timeout=60
        )
        
        # Verify connection
        self._verify_connectivity()

    def _verify_connectivity(self) -> None:
        """Verify database connectivity on initialization"""
        try:
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1").single()
            logger.info("Neo4j connection verified successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    @contextmanager
    def _get_session(self):
        """Context manager for database sessions"""
        session = self.driver.session(database=self.database)
        try:
            yield session
        finally:
            session.close()

    def close(self) -> None:
        """Close the database driver"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def execute_query(
        self, 
        query: str, 
        parameters: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query and return results
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of result records as dictionaries
        """
        with self._get_session() as session:
            try:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                logger.error(f"Query: {query}")
                logger.error(f"Parameters: {parameters}")
                raise

    def get_node_types(self) -> List[str]:
        """Get all node labels in the graph"""
        query = "CALL db.labels() YIELD label RETURN label"
        results = self.execute_query(query)
        return [r['label'] for r in results]

    def get_relationship_types(self) -> List[str]:
        """Get all relationship types in the graph"""
        query = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
        results = self.execute_query(query)
        return [r['relationshipType'] for r in results]

    def find_nodes_by_property(
        self,
        property_name: str,
        property_value: str,
        node_type: Optional[str] = None,
        limit: int = 10,
        exact_match: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Find nodes by property value with optional fuzzy matching
        
        Args:
            property_name: Property to search
            property_value: Value to search for
            node_type: Optional label filter
            limit: Maximum results
            exact_match: Use exact match instead of CONTAINS
            
        Returns:
            List of matching nodes with metadata
        """
        label_filter = f":{node_type}" if node_type else ""
        comparison = "=" if exact_match else "CONTAINS"
        
        query = f"""
        MATCH (n{label_filter})
        WHERE n.`{property_name}` IS NOT NULL
          AND toLower(toString(n.`{property_name}`)) {comparison} toLower($value)
        RETURN elementId(n) as id, 
               labels(n) as labels, 
               properties(n) as properties
        LIMIT $limit
        """
        
        return self.execute_query(query, {
            'value': property_value,
            'limit': limit
        })

    def traverse_from_node(
        self,
        node_id: str,
        max_depth: int = 2,
        relationship_filter: Optional[str] = None,
        label_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Traverse graph from a specific node using APOC
        
        Args:
            node_id: Starting node element ID
            max_depth: Maximum traversal depth
            relationship_filter: APOC relationship filter (e.g., ">TYPE|TYPE2")
            label_filter: APOC label filter (e.g., "+Label|-Label")
            
        Returns:
            Dictionary with nodes and relationships
        """
        query = """
        MATCH (start)
        WHERE elementId(start) = $node_id
        CALL apoc.path.subgraphAll(start, {
            maxLevel: $max_depth,
            relationshipFilter: $rel_filter,
            labelFilter: $label_filter
        })
        YIELD nodes, relationships
        RETURN [n in nodes | {
            id: elementId(n),
            labels: labels(n),
            properties: properties(n)
        }] as nodes,
        [r in relationships | {
            id: elementId(r),
            type: type(r),
            start: elementId(startNode(r)),
            end: elementId(endNode(r)),
            properties: properties(r)
        }] as relationships
        """
        
        results = self.execute_query(query, {
            'node_id': node_id,
            'max_depth': max_depth,
            'rel_filter': relationship_filter,
            'label_filter': label_filter
        })
        
        return results[0] if results else {'nodes': [], 'relationships': []}

    def get_connected_nodes(
        self,
        node_id: str,
        relationship_type: Optional[str] = None,
        direction: str = "both"
    ) -> List[Dict[str, Any]]:
        """
        Get nodes connected to a specific node
        
        Args:
            node_id: Node element ID
            relationship_type: Optional relationship type filter
            direction: "incoming", "outgoing", or "both"
            
        Returns:
            List of connected nodes with relationship info
        """
        # Build direction pattern
        direction_map = {
            "incoming": "<-[r%s]-",
            "outgoing": "-[r%s]->",
            "both": "-[r%s]-"
        }
        
        rel_pattern = f":`{relationship_type}`" if relationship_type else ""
        arrow = direction_map.get(direction.lower(), "-[r%s]-") % rel_pattern
        
        query = f"""
        MATCH (start){arrow}(connected)
        WHERE elementId(start) = $node_id
        RETURN DISTINCT elementId(connected) as id,
               labels(connected) as labels,
               properties(connected) as properties,
               type(r) as relationship_type,
               properties(r) as relationship_properties
        """
        
        return self.execute_query(query, {'node_id': node_id})

    def pattern_search(
        self,
        pattern_description: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for patterns in the graph based on text matching
        
        Args:
            pattern_description: Search term
            limit: Maximum results
            
        Returns:
            List of matching nodes
        """
        query = """
        MATCH (n)
        WHERE any(label in labels(n) WHERE toLower(label) CONTAINS toLower($pattern))
           OR any(prop in keys(n) WHERE toLower(toString(n[prop])) CONTAINS toLower($pattern))
        RETURN elementId(n) as id,
               labels(n) as labels,
               properties(n) as properties
        LIMIT $limit
        """
        
        return self.execute_query(query, {
            'pattern': pattern_description,
            'limit': limit
        })

    def get_graph_statistics(self) -> Dict[str, Any]:
        """
        Get overall graph statistics using APOC
        
        Returns:
            Dictionary with graph metrics
        """
        query = """
        CALL apoc.meta.stats()
        YIELD nodeCount, relCount, labels, relTypesCount
        RETURN nodeCount, 
               relCount as relationshipCount, 
               labels, 
               relTypesCount
        """
        
        results = self.execute_query(query)
        return results[0] if results else {}

    def get_schema_visualization(self) -> Dict[str, Any]:
        """
        Get graph schema for visualization
        
        Returns:
            Dictionary with node types and relationship patterns
        """
        query = """
        CALL apoc.meta.schema()
        YIELD value
        RETURN value
        """
        
        results = self.execute_query(query)
        return results[0]['value'] if results else {}

    def batch_execute(
        self,
        query: str,
        parameters_list: List[Dict],
        batch_size: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Execute queries in batches for better performance
        
        Args:
            query: Cypher query with parameters
            parameters_list: List of parameter dictionaries
            batch_size: Number of operations per batch
            
        Returns:
            Combined results from all batches
        """
        all_results = []
        
        with self._get_session() as session:
            for i in range(0, len(parameters_list), batch_size):
                batch = parameters_list[i:i + batch_size]
                
                try:
                    with session.begin_transaction() as tx:
                        for params in batch:
                            result = tx.run(query, params)
                            all_results.extend([dict(record) for record in result])
                        tx.commit()
                except Exception as e:
                    logger.error(f"Batch execution failed at batch {i//batch_size}: {e}")
                    raise
        
        return all_results

    def get_shortest_path(
        self,
        start_node_id: str,
        end_node_id: str,
        max_depth: int = 5,
        relationship_types: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find shortest path between two nodes
        
        Args:
            start_node_id: Starting node element ID
            end_node_id: Ending node element ID
            max_depth: Maximum path length
            relationship_types: Optional list of allowed relationship types
            
        Returns:
            Path information or None if no path exists
        """
        rel_filter = ""
        if relationship_types:
            rel_filter = ":" + "|".join(f"`{rt}`" for rt in relationship_types)
        
        query = f"""
        MATCH (start), (end)
        WHERE elementId(start) = $start_id AND elementId(end) = $end_id
        MATCH path = shortestPath((start)-[{rel_filter}*..{max_depth}]-(end))
        RETURN [n in nodes(path) | {{
            id: elementId(n),
            labels: labels(n),
            properties: properties(n)
        }}] as nodes,
        [r in relationships(path) | {{
            type: type(r),
            properties: properties(r)
        }}] as relationships,
        length(path) as path_length
        """
        
        results = self.execute_query(query, {
            'start_id': start_node_id,
            'end_id': end_node_id
        })
        
        return results[0] if results else None