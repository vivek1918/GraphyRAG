import yaml
import os
from typing import Dict, Any

def get_config(config_path: str = None) -> Dict[str, Any]:
    """Load configuration from YAML file"""
    if config_path is None:
        config_path = "conf/settings.yml"
    
    if not os.path.exists(config_path):
        # Return default config
        return {
            'rag': {
                'pdf_directory': 'data/raw/pdf',
                'vector_store_path': 'data/vector_store/faiss_index',
                'chunk_size': 1000,
                'chunk_overlap': 200,
                'similarity_top_k': 4
            },
            'groq': {
                'model': 'llama-3.3-70b-versatile',
                'temperature': 0.1,
                'max_tokens': 1024
            },
            'embeddings': {
                'model': 'sentence-transformers/all-MiniLM-L6-v2'
            }
        }
    
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)