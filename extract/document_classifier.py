#!/usr/bin/env python3
"""
Document classifier to identify domain/type before extraction.
Supports rule-based, keyword-based, and LLM-based classification.
"""

import re
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from loguru import logger
from collections import Counter

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use system env vars only


class DocumentClassifier:
    """Classify documents into domain types for specialized extraction."""
    
    DOMAINS = {
        'resume': {
            'keywords': ['resume', 'cv', 'curriculum vitae', 'work experience', 
                        'education', 'skills', 'professional summary', 'references',
                        'accomplishments', 'certifications', 'languages'],
            'patterns': [
                r'\b(?:skills?|technical skills?|core competencies)\b',
                r'\b(?:work experience|professional experience|employment history)\b',
                r'\b(?:education|academic background|qualifications)\b',
                r'\b(?:contact|email|phone|address)\b',
                r'\b(?:objective|summary|profile)\b'
            ]
        },
        'research_paper': {
            'keywords': ['abstract', 'methodology', 'results', 'discussion',
                        'conclusion', 'references', 'bibliography', 'hypothesis',
                        'experiment', 'data analysis', 'literature review',
                        'doi', 'citation', 'journal'],
            'patterns': [
                r'\babstract\b.*?\n',
                r'\b(?:introduction|background)\b',
                r'\b(?:methodology|methods?|approach)\b',
                r'\b(?:results?|findings?)\b',
                r'\b(?:discussion|analysis)\b',
                r'\b(?:conclusion|future work)\b',
                r'\breferences\b|\bbibliography\b'
            ]
        },
        'business_report': {
            'keywords': ['executive summary', 'financial', 'revenue', 'profit',
                        'market analysis', 'stakeholder', 'quarter', 'fiscal year',
                        'roi', 'kpi', 'metrics', 'forecast', 'budget'],
            'patterns': [
                r'\b(?:executive summary|overview)\b',
                r'\b(?:financial|revenue|profit|loss)\b',
                r'\b(?:market|industry|sector)\b',
                r'\b(?:quarter|q[1-4]|fiscal year)\b',
                r'\b(?:recommendation|action items?)\b'
            ]
        },
        'technical_documentation': {
            'keywords': ['api', 'function', 'class', 'method', 'parameter',
                        'return', 'example', 'usage', 'installation', 'configuration',
                        'syntax', 'command', 'endpoint', 'documentation'],
            'patterns': [
                r'\b(?:api|endpoint|route)\b',
                r'\b(?:function|method|class)\b',
                r'\b(?:parameter|argument|return)\b',
                r'\b(?:example|usage|sample)\b',
                r'\b(?:install|setup|configuration)\b'
            ]
        },
        'legal_document': {
            'keywords': ['whereas', 'hereby', 'pursuant', 'aforementioned',
                        'clause', 'section', 'agreement', 'contract', 'party',
                        'obligations', 'terms', 'conditions', 'liability'],
            'patterns': [
                r'\b(?:whereas|hereby|pursuant)\b',
                r'\b(?:clause|section|article)\s+\d+',
                r'\b(?:agreement|contract|terms)\b',
                r'\b(?:party|parties)\b',
                r'\b(?:obligations?|liability|indemnification)\b'
            ]
        },
        'medical_document': {
            'keywords': ['patient', 'diagnosis', 'treatment', 'symptoms',
                        'prescription', 'medical history', 'vital signs',
                        'prognosis', 'clinical', 'examination'],
            'patterns': [
                r'\b(?:patient|subject)\b',
                r'\b(?:diagnosis|diagnosed with)\b',
                r'\b(?:treatment|therapy|medication)\b',
                r'\b(?:symptoms?|signs?)\b',
                r'\b(?:clinical|medical|health)\b'
            ]
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
        Classify document into domain type.
        
        Args:
            document: Document dict with 'content', 'metadata', etc.
            
        Returns:
            Classification result with domain, confidence, and reasoning
        """
        content = document.get('content', '')
        metadata = document.get('metadata', {})
        
        # Try filename-based classification first
        filename = metadata.get('filename', '').lower()
        file_hint = self._classify_by_filename(filename)
        
        # Apply appropriate classification strategy
        if self.mode == 'rule':
            result = self._classify_rule_based(content)
        elif self.mode == 'keyword':
            result = self._classify_keyword_based(content)
        elif self.mode == 'llm' and self.llm_client:
            result = self._classify_llm_based(content, file_hint)
        else:  # hybrid
            result = self._classify_hybrid(content, file_hint)
            
        # Add metadata
        result['filename_hint'] = file_hint
        result['classification_mode'] = self.mode
        
        logger.info(f"Document classified as '{result['domain']}' (confidence: {result['confidence']:.2f})")
        return result
        
    def _classify_by_filename(self, filename: str) -> Optional[str]:
        """Quick classification hint from filename."""
        if any(term in filename for term in ['resume', 'cv']):
            return 'resume'
        elif any(term in filename for term in ['paper', 'journal', 'article']):
            return 'research_paper'
        elif any(term in filename for term in ['report', 'financial', 'quarterly']):
            return 'business_report'
        elif any(term in filename for term in ['api', 'doc', 'manual', 'guide']):
            return 'technical_documentation'
        elif any(term in filename for term in ['contract', 'agreement', 'legal']):
            return 'legal_document'
        elif any(term in filename for term in ['medical', 'patient', 'clinical']):
            return 'medical_document'
        return None
        
    def _classify_rule_based(self, content: str) -> Dict[str, Any]:
        """Classify using pattern matching."""
        content_lower = content.lower()
        scores = {}
        
        for domain, config in self.DOMAINS.items():
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
        
    def _classify_keyword_based(self, content: str) -> Dict[str, Any]:
        """Classify using keyword frequency."""
        content_lower = content.lower()
        scores = {}
        
        for domain, config in self.DOMAINS.items():
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
        
    def _classify_llm_based(self, content: str, file_hint: Optional[str] = None) -> Dict[str, Any]:
        """Classify using LLM (Groq)."""
        if not self.llm_client:
            logger.warning("LLM client not available, falling back to hybrid")
            return self._classify_hybrid(content, file_hint)
            
        # Truncate content for API
        max_chars = 3000
        content_sample = content[:max_chars]
        if len(content) > max_chars:
            content_sample += "\n...[truncated]..."
            
        domains_list = ', '.join(self.DOMAINS.keys())
        prompt = f"""Classify this document into one of these domains: {domains_list}, or 'general' if it doesn't fit any category.

Document content:
{content_sample}

Respond in JSON format:
{{"domain": "<domain_name>", "confidence": <0.0-1.0>, "reasoning": "<brief explanation>"}}"""

        if file_hint:
            prompt += f"\n\nFilename suggests: {file_hint}"
            
        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "You are a document classification expert. Respond only with valid JSON."},
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
                return self._classify_hybrid(content, file_hint)
                
            return result
            
        except Exception as e:
            logger.error(f"LLM classification failed: {e}, falling back to hybrid")
            return self._classify_hybrid(content, file_hint)
            
    def _classify_hybrid(self, content: str, file_hint: Optional[str] = None) -> Dict[str, Any]:
        """Combine multiple classification strategies."""
        # Get both rule and keyword based scores
        rule_result = self._classify_rule_based(content)
        keyword_result = self._classify_keyword_based(content)
        
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
