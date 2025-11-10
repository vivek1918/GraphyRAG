#!/usr/bin/env python3
"""
Fuseki SPARQL client for interacting with the RDF store.
"""

import aiohttp
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

class FusekiClient:
    """Client for Apache Jena Fuseki SPARQL endpoint."""
    
    def __init__(self, base_url: str = "http://localhost:3030", dataset: str = "kg"):
        self.base_url = base_url
        self.dataset = dataset
        self.sparql_endpoint = f"{base_url}/{dataset}/sparql"
        self.data_endpoint = f"{base_url}/{dataset}/data"
        
    async def load_triples(self, ttl_file: Path) -> bool:
        """Load Turtle file into Fuseki."""
        try:
            with open(ttl_file, 'rb') as f:
                data = f.read()
            
            async with aiohttp.ClientSession() as session:
                headers = {'Content-Type': 'text/turtle'}
                async with session.post(
                    self.data_endpoint,
                    data=data,
                    headers=headers
                ) as response:
                    if response.status in [200, 201]:
                        logger.info(f"Successfully loaded triples from {ttl_file}")
                        return True
                    else:
                        logger.error(f"Failed to load triples: {response.status} - {await response.text()}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error loading triples: {e}")
            return False
    
    async def query(self, sparql_query: str) -> List[Dict[str, Any]]:
        """Execute SPARQL query and return results."""
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    'query': sparql_query,
                    'format': 'json'
                }
                
                async with session.get(self.sparql_endpoint, params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        return self.parse_sparql_results(result)
                    else:
                        logger.error(f"SPARQL query failed: {response.status} - {await response.text()}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error executing SPARQL query: {e}")
            return []
    
    def parse_sparql_results(self, result: Dict) -> List[Dict[str, Any]]:
        """Parse SPARQL JSON results into simple dicts."""
        bindings = result.get('results', {}).get('bindings', [])
        parsed_results = []
        
        for binding in bindings:
            parsed_binding = {}
            for var_name, value_info in binding.items():
                parsed_binding[var_name] = value_info.get('value')
            parsed_results.append(parsed_binding)
            
        return parsed_results
    
    async def health_check(self) -> bool:
        """Check if Fuseki is running and healthy."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/$/ping") as response:
                    return response.status == 200
        except:
            return False