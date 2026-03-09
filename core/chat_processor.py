from groq import Groq
import json
import re
from typing import Dict, Any, List
from utils.config_loader import get_config
from utils.logger import setup_logger
from core.graph_manager import GraphManager

logger = setup_logger(__name__)

class ChatProcessor:
    """
    Generalized chatbot processor that understands natural language
    and converts it to graph traversals
    """
    
    def __init__(self, config_path: str = None):
        self.config = get_config(config_path)
        self.graph_manager = GraphManager(config_path)
        
        # Get API configuration
        api_config = self.config.get_section('apis.groq')
        groq_api_key = api_config.get('api_key')
        
        if not groq_api_key:
            # Try to get from environment directly as fallback
            import os
            groq_api_key = os.getenv('GROQ_API_KEY')
            
        if not groq_api_key:
            raise ValueError(
                "Groq API key not found. Please either:\n"
                "1. Set GROQ_API_KEY environment variable, or\n"
                "2. Add 'api_key: your_key' to apis.groq section in settings.yml"
            )
        
        self.groq_client = Groq(api_key=groq_api_key)
        self.llm_model = self.config.get('models.llm.groq', 'llama-3.3-70b-versatile')
        
        logger.info(f"ChatProcessor initialized with model: {self.llm_model}")
    
    def analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """Analyze user query to determine intent and extract parameters"""
        prompt = f"""
        Analyze the following user query and extract structured information for graph database querying.
        
        User Query: "{query}"
        
        Extract and return as JSON:
        - "intent": Primary intent (find_nodes, find_relationships, traverse_path, count_entities, get_properties, general_query)
        - "target_entities": Array of entity types or labels mentioned
        - "properties": Object with property names and values to search for
        - "relationships": Array of relationship types mentioned
        - "constraints": Array of constraints or filters
        - "is_count_query": Boolean indicating if this is a counting query
        - "is_structural_query": Boolean indicating if this is about graph structure
        
        Examples:
        - "Find all people who work at Google" → {{"intent": "find_nodes", "target_entities": ["Person"], "properties": {{"company": "Google"}}}}
        - "How are Alice and Bob connected?" → {{"intent": "traverse_path", "target_entities": ["Alice", "Bob"], "is_structural_query": true}}
        - "Count all projects in the database" → {{"intent": "count_entities", "target_entities": ["Project"], "is_count_query": true}}
        
        IMPORTANT: Be specific about entity types. If the query mentions "people", use "Person". If it mentions "companies", use "Company".
        
        Return only valid JSON:
        """
        
        try:
            logger.info(f"Sending query to LLM for analysis: {query}")
            chat_completion = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.llm_model,
                temperature=0.1,
                max_tokens=512,
                response_format={"type": "json_object"}
            )
            
            response = chat_completion.choices[0].message.content
            logger.info(f"LLM analysis response: {response}")
            return json.loads(response)
        
        except Exception as e:
            logger.error(f"Error analyzing query intent: {e}")
            return {
                "intent": "general_query",
                "target_entities": [],
                "properties": {},
                "relationships": [],
                "constraints": [],
                "is_count_query": False,
                "is_structural_query": False
            }
    
    def generate_cypher_query(self, intent_analysis: Dict[str, Any]) -> str:
        """Generate Cypher query based on intent analysis"""
        intent = intent_analysis.get('intent', 'general_query')
        
        logger.info(f"Generating Cypher for intent: {intent}")
        logger.info(f"Intent analysis: {intent_analysis}")
        
        if intent == 'find_nodes':
            query = self._generate_find_nodes_query(intent_analysis)
        elif intent == 'find_relationships':
            query = self._generate_find_relationships_query(intent_analysis)
        elif intent == 'traverse_path':
            query = self._generate_traverse_path_query(intent_analysis)
        elif intent == 'count_entities':
            query = self._generate_count_query(intent_analysis)
        elif intent == 'get_properties':
            query = self._generate_property_query(intent_analysis)
        else:
            query = self._generate_exploratory_query(intent_analysis)
        
        logger.info(f"Generated Cypher query: {query}")
        return query
    
    def _generate_find_nodes_query(self, analysis: Dict[str, Any]) -> str:
        """Generate query to find specific nodes"""
        entities = analysis.get('target_entities', [])
        properties = analysis.get('properties', {})
        
        if entities:
            entity_label = entities[0]  # Use first entity type
            where_clauses = []
            
            for prop, value in properties.items():
                where_clauses.append(f"toLower(n.`{prop}`) CONTAINS toLower(${prop})")
            
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            query = f"""
            MATCH (n:{entity_label})
            WHERE {where_clause}
            RETURN 
                elementId(n) as id,
                labels(n) as labels,
                properties(n) as properties
            LIMIT 20
            """
        else:
            # Generic node search
            query = """
            MATCH (n)
            WHERE any(prop in keys(n) WHERE toLower(toString(n[prop])) CONTAINS toLower($search_term))
            RETURN 
                elementId(n) as id,
                labels(n) as labels,
                properties(n) as properties
            LIMIT 20
            """
        
        return query
    
    def _generate_find_relationships_query(self, analysis: Dict[str, Any]) -> str:
        """Generate query to find relationships"""
        entities = analysis.get('target_entities', [])
        relationships = analysis.get('relationships', [])
        
        if len(entities) >= 2:
            # Find path between two entities
            query = """
            MATCH path = (a)-[r*..3]-(b)
            WHERE any(label in labels(a) WHERE toLower(label) CONTAINS toLower($entity1))
            AND any(label in labels(b) WHERE toLower(label) CONTAINS toLower($entity2))
            RETURN 
                [node in nodes(path) | {
                    id: elementId(node),
                    labels: labels(node),
                    properties: properties(node)
                }] as nodes,
                [rel in relationships(path) | {
                    type: type(rel),
                    properties: properties(rel)
                }] as relationships
            LIMIT 10
            """
        else:
            # Find nodes with specific relationships
            rel_type = relationships[0] if relationships else ""
            query = """
            MATCH (a)-[r]-(b)
            WHERE type(r) CONTAINS $rel_type
            RETURN 
                elementId(a) as start_id,
                labels(a) as start_labels,
                properties(a) as start_properties,
                type(r) as relationship_type,
                elementId(b) as end_id,
                labels(b) as end_labels,
                properties(b) as end_properties
            LIMIT 15
            """
        
        return query
    
    def _generate_traverse_path_query(self, analysis: Dict[str, Any]) -> str:
        """Generate path traversal query"""
        entities = analysis.get('target_entities', [])
        
        if len(entities) >= 2:
            query = """
            MATCH path = shortestPath((a)-[*..5]-(b))
            WHERE any(prop in keys(a) WHERE toLower(toString(a[prop])) CONTAINS toLower($entity1))
            AND any(prop in keys(b) WHERE toLower(toString(b[prop])) CONTAINS toLower($entity2))
            RETURN 
                [node in nodes(path) | {
                    id: elementId(node),
                    labels: labels(node),
                    name: coalesce(node.name, node.title, node.id, 'Unknown')
                }] as path_nodes,
                [rel in relationships(path) | type(rel)] as path_relationships,
                length(path) as path_length
            """
        else:
            query = """
            MATCH (start)
            WHERE any(prop in keys(start) WHERE toLower(toString(start[prop])) CONTAINS toLower($entity))
            CALL apoc.path.subgraphAll(start, {maxLevel: 3})
            YIELD nodes, relationships
            RETURN 
                [node in nodes | {
                    id: elementId(node),
                    labels: labels(node),
                    name: coalesce(node.name, node.title, node.id, 'Unknown')
                }] as nodes,
                [rel in relationships | type(rel)] as relationships
            """
        
        return query
    
    def _generate_count_query(self, analysis: Dict[str, Any]) -> str:
        """Generate counting query"""
        entities = analysis.get('target_entities', [])
        
        if entities:
            entity_label = entities[0]
            query = f"MATCH (n:{entity_label}) RETURN count(n) as count"
        else:
            query = "MATCH (n) RETURN count(n) as total_count"
        
        return query
    
    def _generate_property_query(self, analysis: Dict[str, Any]) -> str:
        """Generate property-based query"""
        properties = analysis.get('properties', {})
        
        where_clauses = []
        for prop, value in properties.items():
            where_clauses.append(f"toLower(n.`{prop}`) CONTAINS toLower(${prop})")
        
        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        query = f"""
        MATCH (n)
        WHERE {where_clause}
        RETURN 
            elementId(n) as id,
            labels(n) as labels,
            properties(n) as properties
        LIMIT 15
        """
        
        return query
    
    def _generate_exploratory_query(self, analysis: Dict[str, Any]) -> str:
        """Generate exploratory query for general questions"""
        return """
        MATCH (n)
        WITH n, rand() as r
        ORDER BY r
        RETURN 
            elementId(n) as id,
            labels(n) as labels,
            properties(n) as properties
        LIMIT 10
        """
    
    def format_graph_response(self, results: List[Dict[str, Any]], intent_analysis: Dict[str, Any]) -> str:
        """Format graph query results into natural language response"""
        if not results:
            return "I couldn't find any matching results in the graph database."
        
        intent = intent_analysis.get('intent', 'general_query')
        
        if intent == 'count_entities':
            count = results[0].get('count', results[0].get('total_count', 0))
            entities = intent_analysis.get('target_entities', ['items'])
            entity_name = entities[0] if entities else 'items'
            return f"I found {count} {entity_name} in the database."
        
        elif intent == 'traverse_path':
            if 'path_nodes' in results[0]:
                path_info = results[0]
                nodes = path_info.get('path_nodes', [])
                relationships = path_info.get('path_relationships', [])
                
                if not nodes:
                    return "No path found between the specified entities."
                
                path_description = " → ".join([
                    f"{node.get('name', 'Unknown')} [{', '.join(node.get('labels', []))}]" 
                    for node in nodes
                ])
                
                return f"Path found: {path_description}\nRelationships: {', '.join(relationships)}"
        
        # General result formatting
        response_parts = ["Here's what I found in the graph database:"]
        
        for i, result in enumerate(results[:5], 1):  # Limit to 5 results
            if 'labels' in result and 'properties' in result:
                labels = result['labels']
                properties = result['properties']
                
                # Find the most descriptive property for display
                name = properties.get('name') or properties.get('title') or properties.get('id') or 'Unknown'
                
                response_parts.append(f"{i}. {name} ({', '.join(labels)})")
                
                # Add key properties (excluding name/title/id)
                key_props = {k: v for k, v in properties.items() 
                           if k not in ['name', 'title', 'id'] and v is not None}
                if key_props:
                    prop_str = ", ".join([f"{k}: {v}" for k, v in list(key_props.items())[:3]])
                    response_parts.append(f"   Properties: {prop_str}")
        
        if len(results) > 5:
            response_parts.append(f"\n... and {len(results) - 5} more results.")
        
        return "\n".join(response_parts)
    
    def process_query(self, user_query: str) -> str:
        """Main method to process user query and return response"""
        try:
            logger.info(f"Processing query: '{user_query}'")
            
            # Step 1: Analyze query intent
            intent_analysis = self.analyze_query_intent(user_query)
            logger.info(f"Query analysis result: {intent_analysis}")
            
            # Step 2: Generate Cypher query
            cypher_query = self.generate_cypher_query(intent_analysis)
            logger.info(f"Final Cypher query: {cypher_query}")
            
            # Step 3: Extract query parameters
            query_params = self._extract_query_parameters(intent_analysis, user_query)
            logger.info(f"Query parameters: {query_params}")
            
            # Step 4: Execute query
            results = self.graph_manager.execute_query(cypher_query, query_params)
            logger.info(f"Query execution returned {len(results)} results")
            
            if results:
                logger.info(f"First result sample: {results[0]}")
            
            # Step 5: Format response
            response = self.format_graph_response(results, intent_analysis)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            return f"I encountered an error while processing your query: {str(e)}"
    
    def _extract_query_parameters(self, intent_analysis: Dict[str, Any], user_query: str) -> Dict[str, Any]:
        """Extract parameters for Cypher query execution"""
        params = {}
        entities = intent_analysis.get('target_entities', [])
        properties = intent_analysis.get('properties', {})
        
        # Add properties as parameters
        params.update(properties)
        
        # Add entity names as parameters
        if entities:
            if len(entities) >= 1:
                params['entity1'] = entities[0]
            if len(entities) >= 2:
                params['entity2'] = entities[1]
            if len(entities) >= 1 and 'entity' not in params:
                params['entity'] = entities[0]
        
        # Add relationship type if specified
        relationships = intent_analysis.get('relationships', [])
        if relationships:
            params['rel_type'] = relationships[0]
        
        # Add search term for generic searches
        if not params and user_query:
            # Extract potential search terms from query
            words = user_query.split()[:3]  # Use first 3 words as search term
            params['search_term'] = ' '.join(words)
        
        return params