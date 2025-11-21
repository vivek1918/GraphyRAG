import yaml
import os
from typing import Dict, Any

class ConfigLoader:
    """Load configuration from YAML file"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Try to find config in default locations
            possible_paths = [
                "conf/settings.yaml",
                "config/settings.yml", 
                "./settings.yml"
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break
            
            if config_path is None:
                raise FileNotFoundError("Could not find settings.yml in default locations")
        
        self.config_path = config_path
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load YAML configuration file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
            
            # Override with environment variables
            config = self._override_with_env_vars(config)
            return config
            
        except Exception as e:
            raise Exception(f"Failed to load configuration from {self.config_path}: {e}")
    
    def _override_with_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Override config values with environment variables"""
        # Neo4j environment variables
        if os.getenv('NEO4J_URI'):
            config['kg']['neo4j_url'] = os.getenv('NEO4J_URI')
        if os.getenv('NEO4J_USERNAME'):
            config['kg']['neo4j_user'] = os.getenv('NEO4J_USERNAME')
        if os.getenv('NEO4J_PASSWORD'):
            config['kg']['neo4j_password'] = os.getenv('NEO4J_PASSWORD')
        
        # Groq environment variable
        groq_api_key = os.getenv('GROQ_API_KEY')
        if groq_api_key:
            # Ensure apis.groq section exists
            if 'apis' not in config:
                config['apis'] = {}
            if 'groq' not in config['apis']:
                config['apis']['groq'] = {}
            config['apis']['groq']['api_key'] = groq_api_key
        
        return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section"""
        return self.get(section, {})
    
    @property
    def all_config(self) -> Dict[str, Any]:
        """Get entire configuration"""
        return self._config

# Global config instance
_config_loader = None

def get_config(config_path: str = None) -> ConfigLoader:
    """Get or create global config instance"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader(config_path)
    return _config_loader