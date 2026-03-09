#!/usr/bin/env python3
"""
Multi-format document classifier to identify domain/type and modality before extraction.
Supports rule-based, keyword-based, and LLM-based classification for text, audio, images, PDFs, and video.
"""

import re
import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from loguru import logger
from collections import Counter

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use system env vars only


class DocumentClassifier:
    """Classify documents into domain types and modalities for specialized extraction."""
    
    # Supported modalities and their file extensions
    MODALITIES = {
        'text': {
            'extensions': ['.txt', '.md', '.json', '.xml', '.csv', '.html', '.htm'],
            'keywords': ['document', 'text', 'content', 'article', 'report']
        },
        'audio': {
            'extensions': ['.wav', '.mp3', '.m4a', '.flac', '.aac', '.ogg', '.wma'],
            'keywords': ['audio', 'sound', 'recording', 'podcast', 'music', 'voice']
        },
        'image': {
            'extensions': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.svg'],
            'keywords': ['image', 'photo', 'picture', 'graphic', 'diagram', 'chart']
        },
        'pdf': {
            'extensions': ['.pdf'],
            'keywords': ['pdf', 'document', 'report', 'paper', 'manual']
        },
        'video': {
            'extensions': ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.mpeg'],
            'keywords': ['video', 'movie', 'film', 'clip', 'recording', 'footage']
        }
    }
    
    # General domains that work with any modality
    DOMAINS = {
        'resume': {
            'keywords': ['resume', 'cv', 'curriculum vitae', 'work experience', 
                        'education', 'skills', 'professional summary', 'references',
                        'accomplishments', 'certifications', 'languages', 'employment'],
            'patterns': [
                r'\b(?:skills?|technical skills?|core competencies)\b',
                r'\b(?:work experience|professional experience|employment history)\b',
                r'\b(?:education|academic background|qualifications)\b',
                r'\b(?:contact|email|phone|address)\b',
                r'\b(?:objective|summary|profile)\b'
            ],
            'supported_modalities': ['text', 'pdf', 'image']  # Can be scanned resumes
        },
        'research_paper': {
            'keywords': ['abstract', 'methodology', 'results', 'discussion',
                        'conclusion', 'references', 'bibliography', 'hypothesis',
                        'experiment', 'data analysis', 'literature review',
                        'doi', 'citation', 'journal', 'study', 'research'],
            'patterns': [
                r'\babstract\b.*?\n',
                r'\b(?:introduction|background)\b',
                r'\b(?:methodology|methods?|approach)\b',
                r'\b(?:results?|findings?)\b',
                r'\b(?:discussion|analysis)\b',
                r'\b(?:conclusion|future work)\b',
                r'\breferences\b|\bbibliography\b'
            ],
            'supported_modalities': ['text', 'pdf', 'image']  # Can be scanned papers
        },
        'business_report': {
            'keywords': ['executive summary', 'financial', 'revenue', 'profit',
                        'market analysis', 'stakeholder', 'quarter', 'fiscal year',
                        'roi', 'kpi', 'metrics', 'forecast', 'budget', 'business'],
            'patterns': [
                r'\b(?:executive summary|overview)\b',
                r'\b(?:financial|revenue|profit|loss)\b',
                r'\b(?:market|industry|sector)\b',
                r'\b(?:quarter|q[1-4]|fiscal year)\b',
                r'\b(?:recommendation|action items?)\b'
            ],
            'supported_modalities': ['text', 'pdf', 'image', 'audio', 'video']  # Can be presentations
        },
        'technical_documentation': {
            'keywords': ['api', 'function', 'class', 'method', 'parameter',
                        'return', 'example', 'usage', 'installation', 'configuration',
                        'syntax', 'command', 'endpoint', 'documentation', 'technical'],
            'patterns': [
                r'\b(?:api|endpoint|route)\b',
                r'\b(?:function|method|class)\b',
                r'\b(?:parameter|argument|return)\b',
                r'\b(?:example|usage|sample)\b',
                r'\b(?:install|setup|configuration)\b'
            ],
            'supported_modalities': ['text', 'pdf', 'image']  # Documentation files
        },
        'legal_document': {
            'keywords': ['whereas', 'hereby', 'pursuant', 'aforementioned',
                        'clause', 'section', 'agreement', 'contract', 'party',
                        'obligations', 'terms', 'conditions', 'liability', 'legal'],
            'patterns': [
                r'\b(?:whereas|hereby|pursuant)\b',
                r'\b(?:clause|section|article)\s+\d+',
                r'\b(?:agreement|contract|terms)\b',
                r'\b(?:party|parties)\b',
                r'\b(?:obligations?|liability|indemnification)\b'
            ],
            'supported_modalities': ['text', 'pdf', 'image']  # Scanned contracts
        },
        'medical_document': {
            'keywords': ['patient', 'diagnosis', 'treatment', 'symptoms',
                        'prescription', 'medical history', 'vital signs',
                        'prognosis', 'clinical', 'examination', 'medical'],
            'patterns': [
                r'\b(?:patient|subject)\b',
                r'\b(?:diagnosis|diagnosed with)\b',
                r'\b(?:treatment|therapy|medication)\b',
                r'\b(?:symptoms?|signs?)\b',
                r'\b(?:clinical|medical|health)\b'
            ],
            'supported_modalities': ['text', 'pdf', 'image']  # Medical records
        },
        'media_content': {
            'keywords': ['audio', 'video', 'image', 'photo', 'recording', 'footage',
                        'multimedia', 'visual', 'sound', 'music', 'film'],
            'patterns': [
                r'\b(?:audio|sound|recording)\b',
                r'\b(?:video|film|footage)\b',
                r'\b(?:image|photo|picture)\b',
                r'\b(?:duration|length|runtime)\b',
                r'\b(?:resolution|quality|format)\b'
            ],
            'supported_modalities': ['audio', 'image', 'video']  # Media files
        },
        'general': {
            'keywords': [],  # Catch-all domain
            'patterns': [],
            'supported_modalities': ['text', 'pdf', 'audio', 'image', 'video']  # All modalities
        }
    }
    
    def __init__(self, mode: str = "hybrid", config_path: Optional[Path] = None):
        """
        Initialize classifier.
        
        Args:
            mode: Classification mode ('rule', 'keyword', 'llm', 'hybrid')
            config_path: Path to settings.yaml for LLM config
        """
        self.mode = mode
        self.config = self._load_config(config_path)
        
        if mode in ['llm', 'hybrid']:
            self._setup_llm()
            
    def _load_config(self, config_path: Optional[Path]) -> Dict[str, Any]:
        """Load configuration file."""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "conf" / "settings.yaml"
            
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)
        return {}
        
    def _setup_llm(self):
        """Setup LLM for classification if needed."""
        system_mode = self.config.get('system', {}).get('mode', 'local')
        
        if system_mode == 'groq':
            try:
                import os
                from groq import Groq
                api_key = os.getenv('GROQ_API_KEY')
                if api_key:
                    self.llm_client = Groq(api_key=api_key)
                    self.llm_model = self.config.get('models', {}).get('llm', {}).get('groq', 'openai/gpt-oss-120b')
                    logger.info("Groq LLM initialized for document classification")
                else:
                    logger.warning("GROQ_API_KEY not found, falling back to rule-based classification")
                    self.llm_client = None
            except Exception as e:
                logger.warning(f"Could not initialize LLM: {e}")
                self.llm_client = None
        else:
            self.llm_client = None
            
    def classify(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify document into domain type and modality.
        
        Args:
            document: Document dict with 'content', 'metadata', 'file_path', etc.
            
        Returns:
            Classification result with domain, modality, confidence, and reasoning
        """
        content = document.get('content', '')
        metadata = document.get('metadata', {})
        file_path = document.get('file_path', '')
        
        # First, detect modality from file path and content
        modality_result = self._detect_modality(file_path, content, metadata)
        modality = modality_result['modality']
        
        # Then classify domain based on content and modality
        domain_result = self._classify_domain(content, modality, metadata)
        
        # Combine results
        result = {
            'domain': domain_result['domain'],
            'modality': modality,
            'confidence': domain_result['confidence'] * modality_result['confidence'],
            'reasoning': f"Domain: {domain_result['reasoning']}. Modality: {modality_result['reasoning']}",
            'domain_confidence': domain_result['confidence'],
            'modality_confidence': modality_result['confidence'],
            'classification_mode': self.mode,
            'supported_extraction': self._check_supported_extraction(domain_result['domain'], modality)
        }
        
        logger.info(f"Document classified as '{result['domain']}' ({result['modality']}) "
                   f"(confidence: {result['confidence']:.2f})")
        return result
        
    def _detect_modality(self, file_path: str, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Detect the modality (file type) of the document."""
        filename = metadata.get('filename', '') or os.path.basename(file_path) if file_path else ''
        
        # Try file extension first
        file_extension = self._get_file_extension(filename)
        extension_modality = self._classify_by_extension(file_extension)
        
        # Try content-based classification for text detection
        content_modality = self._classify_modality_by_content(content, metadata)
        
        # Combine results
        if extension_modality['modality'] == content_modality['modality']:
            return {
                'modality': extension_modality['modality'],
                'confidence': 0.95,
                'reasoning': f"File extension (.{file_extension}) and content analysis agree"
            }
        elif extension_modality['confidence'] > content_modality['confidence']:
            return extension_modality
        else:
            return content_modality
            
    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename."""
        if not filename:
            return ''
        return Path(filename).suffix.lower().lstrip('.')
        
    def _classify_by_extension(self, file_extension: str) -> Dict[str, Any]:
        """Classify modality by file extension."""
        for modality, config in self.MODALITIES.items():
            if f'.{file_extension}' in config['extensions']:
                return {
                    'modality': modality,
                    'confidence': 0.9,
                    'reasoning': f"File extension .{file_extension} matches {modality} format"
                }
        
        return {
            'modality': 'text',  # Default to text for unknown extensions
            'confidence': 0.5,
            'reasoning': f"Unknown file extension .{file_extension}, defaulting to text"
        }
        
    def _classify_modality_by_content(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Classify modality by analyzing content and metadata."""
        content_lower = content.lower() if content else ''
        
        # Check for modality-specific keywords in content and metadata
        modality_scores = {}
        
        for modality, config in self.MODALITIES.items():
            score = 0
            keywords = config['keywords']
            
            # Score based on keyword presence
            for keyword in keywords:
                if keyword in content_lower:
                    score += 1
            
            # Check metadata for modality hints
            if metadata.get('content_type'):
                content_type = metadata['content_type'].lower()
                if any(keyword in content_type for keyword in keywords):
                    score += 2
            
            modality_scores[modality] = score
        
        # Also check for binary content (likely not text)
        if content and len(content) > 1000 and not self._is_likely_text(content[:1000]):
            modality_scores['image'] += 2
            modality_scores['audio'] += 1
            modality_scores['video'] += 1
            modality_scores['text'] = max(0, modality_scores['text'] - 1)
        
        if not any(score > 0 for score in modality_scores.values()):
            return {
                'modality': 'text',
                'confidence': 0.6,
                'reasoning': 'No strong modality indicators, defaulting to text'
            }
            
        best_modality = max(modality_scores, key=modality_scores.get)
        max_score = modality_scores[best_modality]
        total_score = sum(modality_scores.values())
        confidence = max_score / total_score if total_score > 0 else 0.6
        
        return {
            'modality': best_modality,
            'confidence': confidence,
            'reasoning': f"Content analysis: {modality_scores[best_modality]} modality indicators"
        }
        
    def _is_likely_text(self, content_sample: str) -> bool:
        """Check if content sample is likely text (not binary)."""
        if not content_sample:
            return True
            
        # Count printable characters
        printable_count = sum(1 for char in content_sample if char.isprintable() or char in '\t\n\r')
        ratio = printable_count / len(content_sample)
        
        return ratio > 0.8  # If 80%+ is printable, likely text
        
    def _classify_domain(self, content: str, modality: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Classify document domain based on content and modality."""
        filename = metadata.get('filename', '').lower()
        file_hint = self._classify_by_filename(filename)
        
        # Apply appropriate classification strategy
        if self.mode == 'rule':
            result = self._classify_rule_based(content, modality)
        elif self.mode == 'keyword':
            result = self._classify_keyword_based(content, modality)
        elif self.mode == 'llm' and self.llm_client:
            result = self._classify_llm_based(content, modality, file_hint)
        else:  # hybrid
            result = self._classify_hybrid(content, modality, file_hint)
            
        # Adjust confidence based on modality support
        if result['domain'] in self.DOMAINS:
            supported_modalities = self.DOMAINS[result['domain']].get('supported_modalities', [])
            if modality not in supported_modalities:
                result['confidence'] *= 0.7  # Reduce confidence for unsupported modality
                result['reasoning'] += f" (note: {modality} modality not typically associated with {result['domain']})"
        
        return result
        
    def _classify_by_filename(self, filename: str) -> Optional[str]:
        """Quick classification hint from filename."""
        filename_lower = filename.lower()
        
        domain_hints = {
            'resume': ['resume', 'cv', 'curriculum'],
            'research_paper': ['paper', 'journal', 'article', 'research', 'thesis'],
            'business_report': ['report', 'financial', 'quarterly', 'annual', 'business'],
            'technical_documentation': ['api', 'doc', 'manual', 'guide', 'technical'],
            'legal_document': ['contract', 'agreement', 'legal', 'terms'],
            'medical_document': ['medical', 'patient', 'clinical', 'health'],
            'media_content': ['audio', 'video', 'image', 'photo', 'recording']
        }
        
        for domain, hints in domain_hints.items():
            if any(hint in filename_lower for hint in hints):
                return domain
        return None
        
    def _classify_rule_based(self, content: str, modality: str) -> Dict[str, Any]:
        """Classify using pattern matching."""
        content_lower = content.lower()
        scores = {}
        
        for domain, config in self.DOMAINS.items():
            if domain == 'general':
                continue
                
            score = 0
            patterns = config.get('patterns', [])
            
            for pattern in patterns:
                matches = len(re.findall(pattern, content_lower, re.IGNORECASE))
                score += matches
                
            scores[domain] = score
            
        if not scores or max(scores.values()) == 0:
            return {
                'domain': 'general',
                'confidence': 0.5,
                'reasoning': 'No strong domain patterns detected'
            }
            
        best_domain = max(scores, key=scores.get)
        total_matches = sum(scores.values())
        confidence = scores[best_domain] / total_matches if total_matches > 0 else 0.5
        
        return {
            'domain': best_domain,
            'confidence': min(confidence, 1.0),
            'reasoning': f'Pattern matching: {scores[best_domain]} patterns matched',
            'all_scores': scores
        }
        
    def _classify_keyword_based(self, content: str, modality: str) -> Dict[str, Any]:
        """Classify using keyword frequency."""
        content_lower = content.lower()
        scores = {}
        
        for domain, config in self.DOMAINS.items():
            if domain == 'general':
                continue
                
            keywords = config.get('keywords', [])
            score = sum(1 for kw in keywords if kw in content_lower)
            scores[domain] = score
            
        if not scores or max(scores.values()) == 0:
            return {
                'domain': 'general',
                'confidence': 0.5,
                'reasoning': 'No strong keyword matches'
            }
            
        best_domain = max(scores, key=scores.get)
        total_matches = sum(scores.values())
        confidence = scores[best_domain] / total_matches if total_matches > 0 else 0.5
        
        return {
            'domain': best_domain,
            'confidence': min(confidence, 1.0),
            'reasoning': f'Keyword matching: {scores[best_domain]} keywords found',
            'all_scores': scores
        }
        
    def _classify_llm_based(self, content: str, modality: str, file_hint: Optional[str] = None) -> Dict[str, Any]:
        """Classify using LLM (Groq)."""
        if not self.llm_client:
            logger.warning("LLM client not available, falling back to hybrid")
            return self._classify_hybrid(content, modality, file_hint)
            
        # Truncate content for API
        max_chars = 3000
        content_sample = content[:max_chars] if content else ''
        if content and len(content) > max_chars:
            content_sample += "\n...[truncated]..."
            
        domains_list = ', '.join([d for d in self.DOMAINS.keys() if d != 'general'])
        prompt = f"""Classify this {modality} content into one of these domains: {domains_list}, or 'general' if it doesn't fit any category.

Content type: {modality}
Content:
{content_sample}

Respond in JSON format:
{{"domain": "<domain_name>", "confidence": <0.0-1.0>, "reasoning": "<brief explanation>"}}"""

        if file_hint:
            prompt += f"\n\nFilename suggests: {file_hint}"
            
        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "You are a multi-modal document classification expert. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            import json
            # Handle markdown code blocks
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()
                
            result = json.loads(result_text)
            
            # Validate domain
            if result['domain'] not in self.DOMAINS and result['domain'] != 'general':
                logger.warning(f"LLM returned unknown domain: {result['domain']}, using hybrid fallback")
                return self._classify_hybrid(content, modality, file_hint)
                
            return result
            
        except Exception as e:
            logger.error(f"LLM classification failed: {e}, falling back to hybrid")
            return self._classify_hybrid(content, modality, file_hint)
            
    def _classify_hybrid(self, content: str, modality: str, file_hint: Optional[str] = None) -> Dict[str, Any]:
        """Combine multiple classification strategies."""
        # Get both rule and keyword based scores
        rule_result = self._classify_rule_based(content, modality)
        keyword_result = self._classify_keyword_based(content, modality)
        
        # If filename gives strong hint and matches top predictions, boost it
        if file_hint and file_hint in self.DOMAINS:
            if rule_result['domain'] == file_hint or keyword_result['domain'] == file_hint:
                return {
                    'domain': file_hint,
                    'confidence': 0.85,
                    'reasoning': f'Filename hint confirmed by content analysis'
                }
                
        # Average the confidences if same domain
        if rule_result['domain'] == keyword_result['domain']:
            confidence = (rule_result['confidence'] + keyword_result['confidence']) / 2
            return {
                'domain': rule_result['domain'],
                'confidence': confidence,
                'reasoning': f"Both rule and keyword methods agree on {rule_result['domain']}"
            }
            
        # Otherwise pick the higher confidence one
        if rule_result['confidence'] >= keyword_result['confidence']:
            return rule_result
        else:
            return keyword_result
            
    def _check_supported_extraction(self, domain: str, modality: str) -> bool:
        """Check if the domain-modality combination is supported for extraction."""
        if domain not in self.DOMAINS:
            return False
            
        supported_modalities = self.DOMAINS[domain].get('supported_modalities', [])
        return modality in supported_modalities or 'general' in supported_modalities


async def classify_document(document: Dict[str, Any], mode: str = "hybrid") -> Dict[str, Any]:
    """
    Convenience async function to classify a document.
    
    Args:
        document: Document dict
        mode: Classification mode
        
    Returns:
        Document dict with added 'domain_classification' field
    """
    classifier = DocumentClassifier(mode=mode)
    classification = classifier.classify(document)
    document['domain_classification'] = classification
    return document


def detect_modality_simple(file_path: str) -> str:
    """
    Simple modality detection from file path only.
    Useful for quick filtering before full classification.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Modality string
    """
    extension = Path(file_path).suffix.lower()
    
    extension_map = {
        '.txt': 'text', '.md': 'text', '.json': 'text', '.xml': 'text', '.csv': 'text',
        '.html': 'text', '.htm': 'text',
        '.wav': 'audio', '.mp3': 'audio', '.m4a': 'audio', '.flac': 'audio',
        '.aac': 'audio', '.ogg': 'audio', '.wma': 'audio',
        '.jpg': 'image', '.jpeg': 'image', '.png': 'image', '.gif': 'image',
        '.bmp': 'image', '.tiff': 'image', '.webp': 'image', '.svg': 'image',
        '.pdf': 'pdf',
        '.mp4': 'video', '.avi': 'video', '.mov': 'video', '.mkv': 'video',
        '.wmv': 'video', '.flv': 'video', '.webm': 'video', '.mpeg': 'video'
    }
    
    return extension_map.get(extension, 'text')