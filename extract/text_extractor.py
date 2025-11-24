#!/usr/bin/env python3
"""
Text extractor with encoding detection and paragraph segmentation.
Handles various text encodings and formats.

Follows the same JSON output structure as other extractors.
"""

import os
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

from extract.base_extractor import BaseExtractor


class TextExtractor(BaseExtractor):
    """
    Extract and structure text from plain text files.
    Supports: TXT, MD, CSV, JSON, XML, HTML, LOG, etc.
    """
    
    def __init__(self, groq_api_key: Optional[str] = None, config: Optional[Dict] = None):
        super().__init__(groq_api_key, config)
        
        # Text-specific configuration
        self.supported_formats = [
            '.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm',
            '.log', '.yaml', '.yml', '.ini', '.cfg', '.conf', '.rst',
            '.tex', '.py', '.js', '.java', '.cpp', '.c', '.h', '.sh'
        ]
        self.encoding_fallbacks = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'ascii']
        self.max_file_size_mb = self.config.get('max_file_size_mb', 10)
        
        logger.info(f"TextExtractor initialized with {len(self.encoding_fallbacks)} encoding fallbacks")
    
    async def extract(self, file_path: str, document: Dict[str, Any]) -> Tuple[str, List[Dict], Dict]:
        """
        Extract text with encoding detection and paragraph segmentation.
        
        Returns:
            (text_content, segments, modality_data)
        """
        logger.info(f"[TextExtractor] Processing: {Path(file_path).name}")
        
        file_info = self.get_file_info(file_path)
        if not file_info['exists']:
            logger.error(f"Text file not found: {file_path}")
            return "", [], {'error': 'File not found'}
        
        if file_info['extension'].lower() not in self.supported_formats:
            logger.warning(f"Unsupported text format: {file_info['extension']}")
            # Try to read anyway as plain text
        
        # Check file size
        if file_info['size_mb'] > self.max_file_size_mb:
            logger.warning(f"File too large: {file_info['size_mb']}MB > {self.max_file_size_mb}MB limit")
            return "", [], {'error': f"File too large: {file_info['size_mb']}MB"}
        
        start_time = datetime.now()
        
        # Try multiple encodings
        content, encoding_used = await self._read_with_encoding_fallback(file_path)
        
        if not content:
            logger.error(f"Failed to read file with any encoding")
            return "", [], {'error': 'Failed to decode file'}
        
        # Clean the text
        content = self.clean_text(content)
        
        # Detect file type and structure
        file_structure = self._detect_file_structure(content, file_info['extension'])
        
        # Create segments (paragraphs, sections, or lines)
        segments = self._create_text_segments(content, file_structure)
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Prepare modality-specific data
        modality_data = {
            'encoding': encoding_used,
            'file_structure': file_structure,
            'line_count': content.count('\n') + 1,
            'paragraph_count': len([s for s in segments if s['segment_type'] == 'paragraph']),
            'estimated_reading_time': self._estimate_reading_time(content),
            'contains_code': self._detect_code(content, file_info['extension']),
            'processing_time_seconds': processing_time
        }
        
        logger.info(f"✓ Text extracted: {len(content)} chars, {len(segments)} segments, encoding={encoding_used}")
        
        return content, segments, modality_data
    
    async def _read_with_encoding_fallback(self, file_path: str) -> Tuple[str, str]:
        """
        Try multiple encodings to read the file.
        
        Returns:
            (content, encoding_used)
        """
        for encoding in self.encoding_fallbacks:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                logger.debug(f"✓ Successfully read file with {encoding} encoding")
                return content, encoding
            except UnicodeDecodeError:
                logger.debug(f"Failed to decode with {encoding}, trying next...")
                continue
            except Exception as e:
                logger.warning(f"Error reading with {encoding}: {e}")
                continue
        
        # Last resort: read as binary and decode with errors='replace'
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            logger.warning("Used lossy UTF-8 decoding with character replacement")
            return content, "utf-8 (lossy)"
        except Exception as e:
            logger.error(f"All encoding attempts failed: {e}")
            return "", "failed"
    
    def _detect_file_structure(self, content: str, extension: str) -> str:
        """
        Detect the structure/format of the text file.
        
        Returns:
            Structure type: 'markdown', 'code', 'log', 'structured', 'plain'
        """
        ext_lower = extension.lower()
        
        # Check by extension first
        if ext_lower in ['.md', '.markdown', '.rst']:
            return "markdown"
        elif ext_lower in ['.py', '.js', '.java', '.cpp', '.c', '.h', '.sh', '.go', '.rs']:
            return "code"
        elif ext_lower in ['.log']:
            return "log"
        elif ext_lower in ['.json', '.xml', '.yaml', '.yml', '.csv', '.ini', '.cfg']:
            return "structured_data"
        elif ext_lower in ['.html', '.htm']:
            return "html"
        
        # Check by content patterns
        content_lower = content.lower()
        
        # Check for markdown indicators
        if any(pattern in content for pattern in ['# ', '## ', '### ', '```', '**', '* ']):
            return "markdown"
        
        # Check for code indicators
        if any(pattern in content for pattern in ['def ', 'function ', 'class ', 'import ', 'package ', '{', '}']):
            code_density = sum(1 for char in content if char in '{}();') / len(content) if len(content) > 0 else 0
            if code_density > 0.01:  # More than 1% special code characters
                return "code"
        
        # Check for log patterns
        if any(pattern in content_lower for pattern in ['error:', 'warning:', 'info:', 'debug:', 'timestamp']):
            return "log"
        
        return "plain_text"
    
    def _create_text_segments(self, content: str, file_structure: str) -> List[Dict[str, Any]]:
        """
        Segment text based on structure.
        
        Returns:
            List of text segments
        """
        segments = []
        
        if file_structure == "markdown":
            segments = self._segment_markdown(content)
        elif file_structure == "code":
            segments = self._segment_code(content)
        elif file_structure == "log":
            segments = self._segment_log(content)
        else:
            segments = self._segment_paragraphs(content)
        
        return segments
    
    def _segment_paragraphs(self, content: str) -> List[Dict[str, Any]]:
        """Segment by paragraphs (double newline)."""
        paragraphs = content.split('\n\n')
        segments = []
        
        for idx, para in enumerate(paragraphs):
            para = para.strip()
            if para and len(para) > 10:  # Skip very short paragraphs
                segments.append(self.create_segment(
                    segment_id=f"text_para_{idx}",
                    segment_type="paragraph",
                    content=para,
                    position=idx,
                    metadata={
                        'line_count': para.count('\n') + 1
                    }
                ))
        
        return segments
    
    def _segment_markdown(self, content: str) -> List[Dict[str, Any]]:
        """Segment markdown by headers and paragraphs."""
        lines = content.split('\n')
        segments = []
        current_section = []
        current_header = None
        segment_idx = 0
        
        for line in lines:
            if line.startswith('#'):
                # Save previous section
                if current_section:
                    section_content = '\n'.join(current_section).strip()
                    if section_content:
                        segments.append(self.create_segment(
                            segment_id=f"md_section_{segment_idx}",
                            segment_type="markdown_section",
                            content=section_content,
                            position=segment_idx,
                            metadata={'header': current_header}
                        ))
                        segment_idx += 1
                
                # Start new section
                current_header = line.strip()
                current_section = [line]
            else:
                current_section.append(line)
        
        # Save last section
        if current_section:
            section_content = '\n'.join(current_section).strip()
            if section_content:
                segments.append(self.create_segment(
                    segment_id=f"md_section_{segment_idx}",
                    segment_type="markdown_section",
                    content=section_content,
                    position=segment_idx,
                    metadata={'header': current_header}
                ))
        
        return segments if segments else self._segment_paragraphs(content)
    
    def _segment_code(self, content: str) -> List[Dict[str, Any]]:
        """Segment code by functions/classes (simplified)."""
        lines = content.split('\n')
        segments = []
        current_block = []
        block_type = None
        segment_idx = 0
        
        for line in lines:
            line_stripped = line.strip()
            
            # Detect function/class definitions
            if any(keyword in line_stripped for keyword in ['def ', 'function ', 'class ', 'public ', 'private ']):
                # Save previous block
                if current_block and len(current_block) > 2:
                    block_content = '\n'.join(current_block)
                    segments.append(self.create_segment(
                        segment_id=f"code_block_{segment_idx}",
                        segment_type="code_block",
                        content=block_content,
                        position=segment_idx,
                        metadata={'block_type': block_type}
                    ))
                    segment_idx += 1
                
                # Start new block
                block_type = line_stripped.split()[0] if line_stripped else "code"
                current_block = [line]
            else:
                current_block.append(line)
        
        # Save last block
        if current_block and len(current_block) > 2:
            block_content = '\n'.join(current_block)
            segments.append(self.create_segment(
                segment_id=f"code_block_{segment_idx}",
                segment_type="code_block",
                content=block_content,
                position=segment_idx,
                metadata={'block_type': block_type}
            ))
        
        return segments if segments else self._segment_paragraphs(content)
    
    def _segment_log(self, content: str) -> List[Dict[str, Any]]:
        """Segment log files by entries."""
        lines = content.split('\n')
        segments = []
        
        # Group every 10 lines as a segment (simple approach)
        for idx in range(0, len(lines), 10):
            chunk = '\n'.join(lines[idx:idx+10])
            if chunk.strip():
                segments.append(self.create_segment(
                    segment_id=f"log_entry_{idx//10}",
                    segment_type="log_chunk",
                    content=chunk,
                    position=idx//10,
                    metadata={'start_line': idx, 'end_line': min(idx+10, len(lines))}
                ))
        
        return segments
    
    def _estimate_reading_time(self, content: str) -> str:
        """Estimate reading time assuming 200 words per minute."""
        word_count = len(content.split())
        minutes = word_count / 200
        
        if minutes < 1:
            return "< 1 minute"
        elif minutes < 60:
            return f"{int(minutes)} minutes"
        else:
            hours = int(minutes / 60)
            mins = int(minutes % 60)
            return f"{hours}h {mins}m"
    
    def _detect_code(self, content: str, extension: str) -> bool:
        """Detect if file contains code."""
        code_extensions = ['.py', '.js', '.java', '.cpp', '.c', '.h', '.sh', '.go', '.rs', '.php', '.rb']
        
        if extension.lower() in code_extensions:
            return True
        
        # Check for code patterns
        code_indicators = ['def ', 'function ', 'class ', 'import ', 'package ', 'public ', 'private ', 'void ']
        return any(indicator in content for indicator in code_indicators)
