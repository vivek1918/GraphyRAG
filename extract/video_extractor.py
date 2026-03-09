#!/usr/bin/env python3
"""
Video extractor that combines audio transcription and frame analysis:
1. Extract audio track from video
2. Transcribe audio using AudioExtractor
3. Sample key frames and generate descriptions
4. Combine transcript + frame analysis with timestamps

Follows the same JSON output structure as other extractors.
"""

import os
import tempfile
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger

from extract.base_extractor import BaseExtractor


class VideoExtractor(BaseExtractor):
    """
    Extract transcript and frame descriptions from videos.
    Supports: MP4, AVI, MOV, MKV, FLV, WMV, etc.
    """
    
    def __init__(self, groq_api_key: Optional[str] = None, config: Optional[Dict] = None):
        super().__init__(groq_api_key, config)
        
        # Video-specific configuration
        self.supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v']
        self.frame_sample_rate = self.config.get('frame_sample_rate', 30)  # Sample every N seconds
        self.max_frames = self.config.get('max_frames', 10)
        self.extract_audio_format = 'wav'
        
        logger.info(f"VideoExtractor initialized (frame sampling: every {self.frame_sample_rate}s, max {self.max_frames} frames)")
    
    async def extract(self, file_path: str, document: Dict[str, Any]) -> Tuple[str, List[Dict], Dict]:
        """
        Extract transcript and frame analysis from video.
        
        Returns:
            (combined_content, segments, modality_data)
        """
        logger.info(f"[VideoExtractor] Processing: {Path(file_path).name}")
        
        file_info = self.get_file_info(file_path)
        if not file_info['exists']:
            logger.error(f"Video file not found: {file_path}")
            return "", [], {'error': 'File not found'}
        
        if file_info['extension'].lower() not in self.supported_formats:
            logger.warning(f"Unsupported video format: {file_info['extension']}")
            return "", [], {'error': f"Unsupported format: {file_info['extension']}"}
        
        start_time = datetime.now()
        
        # Step 1: Get video properties
        video_props = await self._get_video_properties(file_path)
        duration = video_props.get('duration', 0.0)
        
        # Step 2: Extract audio track
        audio_path = await self._extract_audio_track(file_path)
        
        # Step 3: Transcribe audio using AudioExtractor
        transcript = ""
        audio_method = "none"
        if audio_path:
            transcript, audio_method = await self._transcribe_audio(audio_path)
            # Clean up temp audio file
            if audio_path != file_path and os.path.exists(audio_path):
                try:
                    os.unlink(audio_path)
                except:
                    pass
        
        # Step 4: Extract and analyze key frames
        frame_descriptions = await self._analyze_key_frames(file_path, duration)
        
        # Step 5: Combine content
        combined_content = self._combine_video_content(transcript, frame_descriptions)
        
        # Step 6: Create time-aligned segments
        segments = self._create_video_segments(transcript, frame_descriptions, duration)
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Prepare modality-specific data
        modality_data = {
            'transcript': transcript,
            'transcript_method': audio_method,
            'frame_descriptions': frame_descriptions,
            'video_properties': video_props,
            'duration_seconds': duration,
            'duration_formatted': self.format_duration(duration),
            'has_audio': len(transcript.strip()) > 0,
            'frame_count': len(frame_descriptions),
            'processing_time_seconds': processing_time
        }
        
        logger.info(f"✓ Video processed: transcript={len(transcript)} chars, {len(frame_descriptions)} frames analyzed")
        
        return combined_content, segments, modality_data
    
    async def _get_video_properties(self, file_path: str) -> Dict[str, Any]:
        """Extract video file properties."""
        props = {
            'duration': 0.0,
            'width': None,
            'height': None,
            'fps': None,
            'codec': None,
            'has_audio': False
        }
        
        try:
            from moviepy.editor import VideoFileClip
            
            with VideoFileClip(file_path) as video:
                props.update({
                    'duration': video.duration,
                    'width': video.w,
                    'height': video.h,
                    'fps': video.fps,
                    'has_audio': video.audio is not None
                })
        except ImportError:
            logger.debug("moviepy not installed: pip install moviepy")
        except Exception as e:
            logger.warning(f"Could not extract video properties: {e}")
        
        return props
    
    async def _extract_audio_track(self, file_path: str) -> Optional[str]:
        """
        Extract audio track from video to temporary file.
        
        Returns:
            Path to extracted audio file or None
        """
        try:
            from moviepy.editor import VideoFileClip
            
            # Create temp file
            temp_audio = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=f'.{self.extract_audio_format}'
            )
            temp_audio_path = temp_audio.name
            temp_audio.close()
            
            # Extract audio
            with VideoFileClip(file_path) as video:
                if video.audio:
                    video.audio.write_audiofile(
                        temp_audio_path,
                        logger=None,  # Suppress moviepy logs
                        verbose=False
                    )
                    logger.info(f"✓ Audio track extracted to {temp_audio_path}")
                    return temp_audio_path
                else:
                    logger.warning("Video has no audio track")
                    return None
                    
        except ImportError:
            logger.debug("moviepy not installed for audio extraction")
            return None
        except Exception as e:
            logger.warning(f"Audio extraction failed: {e}")
            return None
    
    async def _transcribe_audio(self, audio_path: str) -> Tuple[str, str]:
        """
        Transcribe extracted audio using AudioExtractor.
        
        Returns:
            (transcript, method_name)
        """
        try:
            # Import AudioExtractor
            from extract.audio_extractor import AudioExtractor
            
            # Create AudioExtractor instance
            audio_extractor = AudioExtractor(
                groq_api_key=os.getenv('GROQ_API_KEY'),
                config=self.config
            )
            
            # Extract transcript
            transcript, segments, modality_data = await audio_extractor.extract(
                audio_path,
                {'file_path': audio_path, 'file_type': 'audio'}
            )
            
            method = modality_data.get('extraction_method', 'unknown')
            logger.info(f"✓ Video audio transcribed using {method}")
            return transcript, method
            
        except Exception as e:
            logger.warning(f"Audio transcription failed: {e}")
            return "", "failed"
    
    async def _analyze_key_frames(self, file_path: str, duration: float) -> List[Dict[str, Any]]:
        """
        Extract and analyze key frames from video.
        
        Returns:
            List of frame analysis dicts with timestamps
        """
        if duration <= 0:
            return []
        
        try:
            from moviepy.editor import VideoFileClip
            from PIL import Image
            import numpy as np
            
            frame_analyses = []
            
            # Calculate frame timestamps
            frame_times = self._calculate_frame_times(duration)
            
            with VideoFileClip(file_path) as video:
                for idx, timestamp in enumerate(frame_times):
                    try:
                        # Extract frame at timestamp
                        frame = video.get_frame(timestamp)
                        
                        # Convert to PIL Image
                        image = Image.fromarray(np.uint8(frame))
                        
                        # Analyze frame
                        analysis = await self._analyze_frame(image, timestamp, idx)
                        frame_analyses.append(analysis)
                        
                    except Exception as e:
                        logger.warning(f"Failed to analyze frame at {timestamp}s: {e}")
            
            logger.info(f"✓ Analyzed {len(frame_analyses)} key frames")
            return frame_analyses
            
        except ImportError:
            logger.debug("moviepy/PIL not installed for frame extraction")
            return []
        except Exception as e:
            logger.warning(f"Frame analysis failed: {e}")
            return []
    
    def _calculate_frame_times(self, duration: float) -> List[float]:
        """Calculate timestamps for frame sampling."""
        if duration <= 0:
            return []
        
        # Sample frames at regular intervals
        num_frames = min(
            self.max_frames,
            int(duration / self.frame_sample_rate) + 1
        )
        
        if num_frames <= 1:
            return [duration / 2]  # Single frame at midpoint
        
        # Distribute frames evenly across video
        interval = duration / (num_frames + 1)
        return [interval * (i + 1) for i in range(num_frames)]
    
    async def _analyze_frame(self, image, timestamp: float, frame_index: int) -> Dict[str, Any]:
        """
        Analyze a single frame.
        
        Returns:
            Frame analysis dict
        """
        analysis = {
            'frame_index': frame_index,
            'timestamp': timestamp,
            'timestamp_formatted': self.format_duration(timestamp),
            'description': '',
            'brightness': 0.0,
            'dominant_colors': []
        }
        
        try:
            # Calculate brightness
            import numpy as np
            frame_array = np.array(image)
            brightness = np.mean(frame_array)
            analysis['brightness'] = round(float(brightness), 2)
            
            # Detect scene change (simplified)
            if brightness > 200:
                analysis['scene_type'] = 'bright'
            elif brightness < 50:
                analysis['scene_type'] = 'dark'
            else:
                analysis['scene_type'] = 'normal'
            
            # Generate description if Groq available
            if self.groq_client:
                # Save temp image for analysis
                temp_img = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                image.save(temp_img.name)
                
                try:
                    # Use ImageExtractor for description
                    from extract.image_extractor import ImageExtractor
                    img_extractor = ImageExtractor(groq_api_key=os.getenv('GROQ_API_KEY'))
                    description = await img_extractor._generate_vision_description(temp_img.name, "")
                    analysis['description'] = description[:200]  # Truncate
                finally:
                    os.unlink(temp_img.name)
        
        except Exception as e:
            logger.debug(f"Frame analysis details failed: {e}")
        
        return analysis
    
    def _combine_video_content(self, transcript: str, frame_descriptions: List[Dict]) -> str:
        """Combine transcript and frame descriptions."""
        parts = []
        
        if transcript and transcript.strip():
            parts.append(f"Video Transcript:\n{transcript}")
        
        if frame_descriptions:
            frame_texts = []
            for frame in frame_descriptions:
                time_str = frame.get('timestamp_formatted', '00:00')
                desc = frame.get('description', 'No description')
                if desc and desc != 'No description':
                    frame_texts.append(f"[{time_str}] {desc}")
            
            if frame_texts:
                parts.append(f"Frame Analysis:\n" + "\n".join(frame_texts))
        
        if not parts:
            return "No content extracted from video"
        
        return "\n\n".join(parts)
    
    def _create_video_segments(
        self,
        transcript: str,
        frame_descriptions: List[Dict],
        duration: float
    ) -> List[Dict[str, Any]]:
        """Create time-aligned segments combining transcript and frames."""
        segments = []
        
        # Add transcript as first segment if available
        if transcript and transcript.strip():
            segments.append(self.create_segment(
                segment_id="video_transcript",
                segment_type="transcript",
                content=transcript,
                position=0,
                metadata={
                    'start_time': 0.0,
                    'end_time': duration,
                    'duration': duration
                }
            ))
        
        # Add frame descriptions as segments
        for frame in frame_descriptions:
            desc = frame.get('description', '')
            if desc:
                segments.append(self.create_segment(
                    segment_id=f"video_frame_{frame['frame_index']}",
                    segment_type="frame_description",
                    content=desc,
                    position=frame['frame_index'] + 1,
                    metadata={
                        'timestamp': frame['timestamp'],
                        'timestamp_formatted': frame['timestamp_formatted'],
                        'scene_type': frame.get('scene_type', 'normal'),
                        'brightness': frame.get('brightness', 0.0)
                    }
                ))
        
        return segments
