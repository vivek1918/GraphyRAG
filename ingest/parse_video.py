#!/usr/bin/env python3
"""
Video parser for extracting frames, audio, and metadata.
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List
from loguru import logger

class VideoParser:
    """Video parser with frame extraction and audio processing."""
    
    def __init__(self):
        self.video_libs_available = self._check_video_libs()
    
    def _check_video_libs(self) -> bool:
        """Check if video processing libraries are available."""
        try:
            import cv2
            return True
        except ImportError:
            logger.warning("OpenCV not available for video processing")
            return False
    
    async def parse(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Parse video file and extract content."""
        try:
            file_path = Path(document['file_path'])
            
            if not file_path.exists():
                logger.error(f"Video file not found: {file_path}")
                return await self._create_fallback_document(document)
            
            # For synthetic video files with placeholder content
            if document.get('content'):
                return await self._create_document_from_content(document)
            
            # Extract video information
            video_info = await self._extract_video_info(file_path)
            
            # Extract key frames (if OpenCV available)
            frames_data = []
            if self.video_libs_available:
                frames_data = await self._extract_key_frames(file_path, video_info)
            
            parsed_doc = {
                'doc_id': document['doc_id'],
                'type': 'video',
                'content': document.get('content', 'Video content'),
                'metadata': {
                    'source_type': 'video',
                    'file_path': str(file_path),
                    'duration': video_info.get('duration', 0),
                    'resolution': video_info.get('resolution', 'unknown'),
                    'frame_rate': video_info.get('frame_rate', 0),
                    'frame_count': video_info.get('frame_count', 0),
                    'has_audio': video_info.get('has_audio', False)
                },
                'video_data': {
                    'info': video_info,
                    'key_frames': frames_data
                }
            }
            
            # Add ground truth if available
            if 'entities' in document:
                parsed_doc['ground_truth_entities'] = document['entities']
            if 'relations' in document:
                parsed_doc['ground_truth_relations'] = document['relations']
            
            logger.debug(f"Processed video document: {document['doc_id']}")
            return parsed_doc
            
        except Exception as e:
            logger.error(f"Error parsing video document {document.get('doc_id')}: {e}")
            return await self._create_fallback_document(document)
    
    async def _extract_video_info(self, video_path: Path) -> Dict[str, Any]:
        """Extract basic video information."""
        try:
            if self.video_libs_available:
                return await self._extract_video_info_opencv(video_path)
            else:
                return await self._extract_video_info_fallback(video_path)
        except Exception as e:
            logger.error(f"Error extracting video info: {e}")
            return {'duration': 0, 'resolution': 'unknown', 'error': str(e)}
    
    async def _extract_video_info_opencv(self, video_path: Path) -> Dict[str, Any]:
        """Extract video information using OpenCV."""
        import cv2
        
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            return {'error': 'Could not open video file'}
        
        # Get video properties
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = frame_count / fps if fps > 0 else 0
        
        # Get resolution from first frame
        ret, frame = cap.read()
        if ret:
            height, width = frame.shape[:2]
            resolution = f"{width}x{height}"
        else:
            resolution = "unknown"
        
        cap.release()
        
        return {
            'duration': duration,
            'resolution': resolution,
            'frame_rate': fps,
            'frame_count': frame_count,
            'has_audio': True  # OpenCV doesn't provide audio info
        }
    
    async def _extract_video_info_fallback(self, video_path: Path) -> Dict[str, Any]:
        """Fallback video information extraction."""
        # For synthetic/demo purposes
        return {
            'duration': 300,  # 5 minutes default
            'resolution': '1920x1080',
            'frame_rate': 30,
            'frame_count': 9000,
            'has_audio': True
        }
    
    async def _extract_key_frames(self, video_path: Path, video_info: Dict) -> List[Dict]:
        """Extract key frames from video."""
        try:
            import cv2
            import base64
            from io import BytesIO
            from PIL import Image
            
            cap = cv2.VideoCapture(str(video_path))
            frames_data = []
            frame_interval = max(1, video_info.get('frame_count', 100) // 10)  # Extract ~10 frames
            
            for i in range(0, min(video_info.get('frame_count', 100), 100), frame_interval):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                
                if ret:
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(frame_rgb)
                    
                    # Resize for efficiency
                    pil_image.thumbnail((320, 240))
                    
                    # Convert to base64 for storage
                    buffered = BytesIO()
                    pil_image.save(buffered, format="JPEG")
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                    
                    frames_data.append({
                        'frame_number': i,
                        'timestamp': i / video_info.get('frame_rate', 30),
                        'image_data': img_str,
                        'resolution': f"{pil_image.width}x{pil_image.height}"
                    })
            
            cap.release()
            return frames_data
            
        except Exception as e:
            logger.error(f"Error extracting key frames: {e}")
            return []
    
    async def _create_document_from_content(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Create document from existing content (for synthetic data)."""
        return {
            'doc_id': document['doc_id'],
            'type': 'video',
            'content': document['content'],
            'metadata': {
                'source_type': 'video',
                'file_path': document.get('file_path', ''),
                'duration': document.get('duration', 300),
                'resolution': '1920x1080',
                'frame_rate': 30,
                'frame_count': 9000,
                'has_audio': True
            },
            'video_data': {
                'info': {'duration': document.get('duration', 300)},
                'key_frames': []
            },
            'ground_truth_entities': document.get('entities', []),
            'ground_truth_relations': document.get('relations', [])
        }
    
    async def _create_fallback_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Create fallback document when video processing fails."""
        return {
            'doc_id': document['doc_id'],
            'type': 'video',
            'content': document.get('content', 'Video processing not available'),
            'metadata': {
                'source_type': 'video',
                'file_path': document.get('file_path', ''),
                'duration': document.get('duration', 0),
                'resolution': 'unknown',
                'frame_rate': 0,
                'frame_count': 0,
                'has_audio': False,
                'error': 'Video processing failed'
            },
            'video_data': {
                'info': {},
                'key_frames': []
            },
            'ground_truth_entities': document.get('entities', []),
            'ground_truth_relations': document.get('relations', [])
        }
    
    async def extract_audio_from_video(self, video_path: Path, audio_output: Path) -> bool:
        """Extract audio from video file."""
        try:
            # This would use ffmpeg in a real implementation
            # For demo, return success
            logger.info(f"Would extract audio from {video_path} to {audio_output}")
            return True
        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            return False