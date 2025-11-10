#!/usr/bin/env python3
"""
Document indexing module for vector storage and retrieval.
"""

import json
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

class DocumentIndexer:
    """Indexes documents for vector-based retrieval."""
    
    def __init__(self, index_dir: Path = Path("data/processed/rag_index")):
        self.index_dir = index_dir
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        self.vector_store = None
        self.embedding_model = None
        self.documents = []
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize vector store and embedding model."""
        try:
            # Try to use sentence transformers
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Initialized sentence transformer for embeddings")
        except ImportError:
            logger.warning("Sentence transformers not available, using fallback")
            self.embedding_model = None
        
        try:
            # Try FAISS for vector storage
            import faiss
            self.use_faiss = True
            logger.info("FAISS available for vector storage")
        except ImportError:
            self.use_faiss = False
            logger.warning("FAISS not available, using simple storage")
    
    async def build_index(self, documents: List[Dict[str, Any]]):
        """Build vector index from documents."""
        try:
            logger.info(f"Building index for {len(documents)} documents")
            
            # Chunk documents
            chunks = await self._chunk_documents(documents)
            logger.info(f"Created {len(chunks)} chunks from documents")
            
            # Generate embeddings
            embeddings = await self._generate_embeddings([chunk['text'] for chunk in chunks])
            logger.info(f"Generated embeddings for {len(embeddings)} chunks")
            
            # Build vector index
            await self._build_vector_index(chunks, embeddings)
            
            # Store metadata
            await self._store_metadata(documents, chunks)
            
            logger.info("Document index built successfully")
            
        except Exception as e:
            logger.error(f"Error building document index: {e}")
            raise
    
    async def _chunk_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Split documents into chunks for indexing."""
        chunks = []
        
        for doc in documents:
            doc_id = doc['doc_id']
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})
            
            if not content:
                continue
            
            # Simple chunking by sentences/paragraphs
            doc_chunks = await self._split_text(content, chunk_size=500, overlap=50)
            
            for i, chunk_text in enumerate(doc_chunks):
                chunk_id = f"{doc_id}_chunk_{i}"
                chunks.append({
                    'chunk_id': chunk_id,
                    'doc_id': doc_id,
                    'text': chunk_text,
                    'metadata': {
                        'source_type': metadata.get('source_type', 'unknown'),
                        'chunk_index': i,
                        'total_chunks': len(doc_chunks)
                    }
                })
        
        return chunks
    
    async def _split_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # If this isn't the first chunk, include overlap
            if start > 0:
                start = max(0, start - overlap)
            
            # Avoid breaking in the middle of a sentence if possible
            if end < len(text):
                # Look for sentence end
                sentence_ends = ['.', '!', '?', '\n\n']
                for end_pos in range(end, min(end + 100, len(text))):
                    if text[end_pos] in sentence_ends:
                        end = end_pos + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end
            if start >= len(text):
                break
        
        return chunks
    
    async def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts."""
        if self.embedding_model:
            try:
                embeddings = self.embedding_model.encode(texts)
                return embeddings.tolist()
            except Exception as e:
                logger.error(f"Error generating embeddings: {e}")
        
        # Fallback: simple TF-IDF like representation
        return await self._generate_fallback_embeddings(texts)
    
    async def _generate_fallback_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate fallback embeddings when no model is available."""
        import numpy as np
        from collections import Counter
        import re
        
        # Simple word frequency based embeddings
        all_words = set()
        for text in texts:
            words = re.findall(r'\w+', text.lower())
            all_words.update(words)
        
        vocab = list(all_words)
        word_to_idx = {word: i for i, word in enumerate(vocab)}
        
        embeddings = []
        for text in texts:
            words = re.findall(r'\w+', text.lower())
            counter = Counter(words)
            
            embedding = [0.0] * len(vocab)
            for word, count in counter.items():
                if word in word_to_idx:
                    embedding[word_to_idx[word]] = count
            
            # Normalize
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = [x / norm for x in embedding]
            
            embeddings.append(embedding)
        
        return embeddings
    
    async def _build_vector_index(self, chunks: List[Dict], embeddings: List[List[float]]):
        """Build vector index using available backend."""
        if self.use_faiss and embeddings:
            await self._build_faiss_index(chunks, embeddings)
        else:
            await self._build_simple_index(chunks, embeddings)
    
    async def _build_faiss_index(self, chunks: List[Dict], embeddings: List[List[float]]):
        """Build FAISS vector index."""
        try:
            import faiss
            import numpy as np
            
            # Convert to numpy array
            emb_array = np.array(embeddings).astype('float32')
            
            # Create FAISS index
            dimension = emb_array.shape[1]
            index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
            
            # Normalize for cosine similarity
            faiss.normalize_L2(emb_array)
            index.add(emb_array)
            
            # Save index and chunks
            faiss.write_index(index, str(self.index_dir / "vector_index.faiss"))
            
            with open(self.index_dir / "chunks.json", 'w') as f:
                json.dump(chunks, f, indent=2)
            
            logger.info(f"Built FAISS index with {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Error building FAISS index: {e}")
            await self._build_simple_index(chunks, embeddings)
    
    async def _build_simple_index(self, chunks: List[Dict], embeddings: List[List[float]]):
        """Build simple in-memory index."""
        index_data = {
            'chunks': chunks,
            'embeddings': embeddings,
            'metadata': {
                'total_chunks': len(chunks),
                'embedding_dim': len(embeddings[0]) if embeddings else 0,
                'index_type': 'simple'
            }
        }
        
        with open(self.index_dir / "simple_index.pkl", 'wb') as f:
            pickle.dump(index_data, f)
        
        logger.info(f"Built simple index with {len(chunks)} chunks")
    
    async def _store_metadata(self, documents: List[Dict], chunks: List[Dict]):
        """Store document and chunk metadata."""
        metadata = {
            'documents': [
                {
                    'doc_id': doc['doc_id'],
                    'type': doc.get('type', 'unknown'),
                    'source_type': doc.get('metadata', {}).get('source_type', 'unknown'),
                    'chunk_count': len([c for c in chunks if c['doc_id'] == doc['doc_id']])
                }
                for doc in documents
            ],
            'total_chunks': len(chunks),
            'index_timestamp': json.dumps(str(__import__('datetime').datetime.now()))
        }
        
        with open(self.index_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
    
    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents/chunks."""
        try:
            if self.use_faiss:
                return await self._search_faiss(query, top_k)
            else:
                return await self._search_simple(query, top_k)
        except Exception as e:
            logger.error(f"Error searching index: {e}")
            return []
    
    async def _search_faiss(self, query: str, top_k: int) -> List[Dict]:
        """Search using FAISS index."""
        try:
            import faiss
            import numpy as np
            
            # Load index
            index_path = self.index_dir / "vector_index.faiss"
            chunks_path = self.index_dir / "chunks.json"
            
            if not index_path.exists() or not chunks_path.exists():
                return []
            
            index = faiss.read_index(str(index_path))
            with open(chunks_path, 'r') as f:
                chunks = json.load(f)
            
            # Generate query embedding
            query_embedding = await self._generate_embeddings([query])[0]
            query_array = np.array([query_embedding]).astype('float32')
            faiss.normalize_L2(query_array)
            
            # Search
            scores, indices = index.search(query_array, top_k)
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < len(chunks):
                    results.append({
                        'chunk': chunks[idx],
                        'score': float(score),
                        'type': 'vector'
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error in FAISS search: {e}")
            return await self._search_simple(query, top_k)
    
    async def _search_simple(self, query: str, top_k: int) -> List[Dict]:
        """Search using simple similarity."""
        try:
            index_path = self.index_dir / "simple_index.pkl"
            if not index_path.exists():
                return []
            
            with open(index_path, 'rb') as f:
                index_data = pickle.load(f)
            
            chunks = index_data['chunks']
            embeddings = index_data['embeddings']
            
            if not chunks or not embeddings:
                return []
            
            # Generate query embedding
            query_embedding = await self._generate_embeddings([query])[0]
            
            # Calculate similarities
            similarities = []
            for i, chunk_embedding in enumerate(embeddings):
                similarity = await self._cosine_similarity(query_embedding, chunk_embedding)
                similarities.append((similarity, i))
            
            # Sort by similarity
            similarities.sort(reverse=True)
            
            results = []
            for score, idx in similarities[:top_k]:
                results.append({
                    'chunk': chunks[idx],
                    'score': score,
                    'type': 'vector'
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error in simple search: {e}")
            return []
    
    async def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math
        
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    async def get_index_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        try:
            metadata_path = self.index_dir / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {}