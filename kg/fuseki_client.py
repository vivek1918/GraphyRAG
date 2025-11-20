#!/usr/bin/env python3
"""
Fuseki SPARQL client for interacting with the RDF store.
"""
import os
import json
import asyncio
from pathlib import Path
from typing import Any, Dict, Optional, Union

import requests
from requests.auth import HTTPBasicAuth
from loguru import logger
import aiohttp

class FusekiClient:
    """Client for Apache Jena Fuseki SPARQL endpoint."""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        dataset: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 60,
    ):
        self.base_url = (base_url or os.getenv("FUSEKI_URL", "http://localhost:3030")).rstrip("/")
        self.dataset = (dataset or os.getenv("FUSEKI_DATASET", "kg")).strip("/")

        self.username = username or os.getenv("FUSEKI_USER")
        self.password = password or os.getenv("FUSEKI_PASSWORD")

        self.session = requests.Session()
        if self.username and self.password:
            self.session.auth = HTTPBasicAuth(self.username, self.password)

        self.sparql_endpoint = f"{self.base_url}/{self.dataset}/sparql"
        self.update_endpoint = f"{self.base_url}/{self.dataset}/update"
        self.data_endpoint = f"{self.base_url}/{self.dataset}/data"
        self.timeout = timeout

    def _try_alt_sparql(self) -> None:
        alt = f"{self.base_url}/{self.dataset}/query"
        try:
            r = self.session.get(alt, params={"query": "ASK{}"}, timeout=10)
            if r.status_code < 400:
                self.sparql_endpoint = alt
        except Exception:
            pass

    async def load_triples(
        self,
        source: Union[str, bytes, Path],
        content_type: str = "text/turtle",
        graph: Optional[str] = None
    ) -> bool:
        """
        Load triples into Fuseki Graph Store.
        source: TTL/N-Triples string, bytes, or Path to a file.
        """
        if isinstance(source, Path):
            if not source.exists():
                logger.error(f"Triple file not found: {source}")
                return False
            # Read as text (TTL / RDF serialization)
            data = source.read_text(encoding="utf-8")
        elif isinstance(source, bytes):
            data = source
        elif isinstance(source, str):
            # If looks like a path and exists, treat as file
            p = Path(source)
            data = p.read_text(encoding="utf-8") if p.exists() else source
        else:
            logger.error("Unsupported source type for triples load")
            return False

        params: Dict[str, Any] = {}
        if graph:
            params["graph"] = graph

        def _post():
            return self.session.post(
                self.data_endpoint,
                params=params,
                data=data,
                headers={"Content-Type": content_type},
                timeout=self.timeout,
            )

        try:
            resp = await asyncio.to_thread(_post)
            if resp.status_code >= 400:
                logger.error(f"Failed to load triples: {resp.status_code} - {resp.text[:500]}")
                return False
            logger.info("Triples loaded into Fuseki")
            return True
        except Exception as e:
            logger.error(f"Error loading triples: {e}")
            return False

    async def update(self, sparql_update: str) -> bool:
        def _post():
            return self.session.post(
                self.update_endpoint,
                data={"update": sparql_update},
                timeout=self.timeout
            )
        try:
            resp = await asyncio.to_thread(_post)
            if resp.status_code >= 400:
                logger.error(f"SPARQL Update failed: {resp.status_code} - {resp.text[:500]}")
                return False
            return True
        except Exception as e:
            logger.error(f"SPARQL Update error: {e}")
            return False

    async def query(
        self,
        sparql: str,
        accept: str = "application/sparql-results+json"
    ) -> Optional[Dict[str, Any]]:
        def _get(endpoint: str):
            return self.session.get(
                endpoint,
                params={"query": sparql, "format": "json"},
                headers={"Accept": accept},
                timeout=self.timeout,
            )

        try:
            resp = await asyncio.to_thread(_get, self.sparql_endpoint)
            if resp.status_code == 404:
                self._try_alt_sparql()
                resp = await asyncio.to_thread(_get, self.sparql_endpoint)
            if resp.status_code >= 400:
                logger.error(f"Error executing SPARQL query: {resp.status_code} - {resp.text[:500]}")
                return None
            if "json" in accept:
                return resp.json()
            return {"raw": resp.text}
        except Exception as e:
            logger.error(f"Error executing SPARQL query: {e}")
            return None

    async def health_check(self) -> bool:
        try:
            async with aiohttp.ClientSession(auth=aiohttp.BasicAuth(self.username, self.password) if (self.username and self.password) else None) as session:
                async with session.get(f"{self.base_url}/$/ping") as response:
                    return response.status == 200
        except Exception:
            return False