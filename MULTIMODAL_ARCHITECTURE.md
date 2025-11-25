# Multi-Modal Knowledge Graph Extraction Architecture

## Overview

This system supports extraction of structured data from **5 document formats** (PDF, Audio, Image, Video, Text) with consistent JSON output for downstream NER and Relation Extraction.

## Architecture

### Design Pattern: Modular Extractors + Coordinator

```
┌─────────────────────────────────────────────────────────────┐
│                   MultiModalProcessor                        │
│                     (Coordinator)                            │
└─────────┬─────────────────────────────────────────┬─────────┘
          │                                         │
          ▼                                         ▼
┌──────────────────────┐                 ┌──────────────────────┐
│   BaseExtractor      │                 │  Format Routing      │
│  (Abstract Base)     │◄────────────────┤  • Audio → Audio     │
└──────────┬───────────┘                 │  • Image → Image     │
           │                             │  • Video → Video     │
           │ Inheritance                 │  • Text → Text       │
           │                             │  • PDF → Legacy      │
           ▼                             └──────────────────────┘
┌───────────────────────────────────────────────────────────────┐
│                    Concrete Extractors                         │
├─────────────┬─────────────┬─────────────┬──────────────┬──────┤
│AudioExtractor│ImageExtractor│VideoExtractor│TextExtractor│PDF   │
└─────────────┴─────────────┴─────────────┴──────────────┴──────┘
```

### Base Extractor Features

All extractors inherit from `BaseExtractor` which provides:

- **Entity Hints**: Pattern-based (PERSON, ORG, PLACE, DATE, EMAIL, PHONE, URL) + optional LLM
- **Quality Assessment**: Confidence, completeness, text quality metrics
- **Content Cleaning**: Normalize whitespace, remove control chars
- **Standardized Output**: `(content, segments, modality_data)` tuple
- **Statistics**: Word/sentence counts, unique word ratio

## Format-Specific Extractors

### 1. Audio Extractor (`extract/audio_extractor.py`)

**Supported Formats**: `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`, `.wma`, `.aac`

**Extraction Chain** (4 fallback methods):

1. **OpenAI Whisper (Local)** - Fast, confidence=0.9, requires `openai-whisper`
2. **Groq Whisper API** - Cloud-based, requires GROQ_API_KEY
3. **AssemblyAI** - Commercial, requires ASSEMBLYAI_API_KEY
4. **Google Speech-to-Text** - Enterprise, requires `google-cloud-speech`

**Output**:

```python
{
    'content': 'Full transcript text...',
    'content_segments': [
        {
            'segment_id': 'audio_seg_0',
            'segment_type': 'sentence',
            'content': 'First sentence.',
            'start_time': 0.0,
            'end_time': 3.5
        },
        ...
    ],
    'modality_specific_data': {
        'duration_seconds': 120.5,
        'transcription_method': 'whisper_local',
        'words_per_minute': 150,
        'audio_quality': 'high',  # high/medium/low/poor based on WPM
        'has_speech': True
    }
}
```

**Quality Metrics**:

- **High quality**: 100-200 WPM
- **Medium quality**: 80-100 or 200-250 WPM
- **Low quality**: 50-80 or 250-300 WPM
- **Poor quality**: <50 or >300 WPM

### 2. Image Extractor (`extract/image_extractor.py`)

**Supported Formats**: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tiff`, `.webp`

**Extraction Chain** (3 OCR methods + Vision):

1. **Tesseract OCR** - Fast, reliable, DPI=300, includes preprocessing
2. **EasyOCR** - Better for complex/multi-language text
3. **PaddleOCR** - High accuracy fallback
4. **LLM Vision** - Groq vision model for image description (always attempted if enabled)

**Image Preprocessing**:

- Contrast enhancement (1.5x)
- Sharpness enhancement (2.0x)
- Median filtering for noise reduction

**Output**:

```python
{
    'content': 'Extracted Text: ...\n\nImage Description: ...',
    'content_segments': [
        {
            'segment_id': 'img_text',
            'segment_type': 'ocr_text',
            'content': 'Extracted text from OCR...',
            'position': 0
        },
        {
            'segment_id': 'img_desc',
            'segment_type': 'vision_description',
            'content': 'LLM-generated image description...',
            'position': 1
        }
    ],
    'modality_specific_data': {
        'ocr_method': 'tesseract',
        'has_vision_description': True,
        'text_coverage': 'high',  # high/medium/low/minimal
        'image_width': 1920,
        'image_height': 1080,
        'aspect_ratio': 1.78,
        'megapixels': 2.07
    }
}
```

**Text Coverage Classification**:

- **High**: >100 chars per 250k pixels
- **Medium**: 50-100 chars per 250k pixels
- **Low**: 10-50 chars per 250k pixels
- **Minimal**: <10 chars per 250k pixels

### 3. Video Extractor (`extract/video_extractor.py`)

**Supported Formats**: `.mp4`, `.avi`, `.mov`, `.mkv`, `.flv`, `.wmv`, `.webm`, `.m4v`

**Processing Pipeline**:

1. **Extract Audio Track** - Using `moviepy`, save to temp WAV
2. **Transcribe Audio** - Delegates to `AudioExtractor` for consistency
3. **Sample Key Frames** - Every 30s (configurable), max 10 frames
4. **Analyze Frames** - Brightness, scene type, optional LLM description
5. **Combine Content** - Merge transcript + frame timestamps

**Output**:

```python
{
    'content': 'Video Transcript: ...\n\nFrame Analysis: [00:00] Scene description...',
    'content_segments': [
        {
            'segment_id': 'video_audio',
            'segment_type': 'transcript',
            'content': 'Full audio transcript...',
            'position': 0
        },
        {
            'segment_id': 'frame_30',
            'segment_type': 'frame_description',
            'content': 'Frame at 00:30 shows...',
            'timestamp': 30.0,
            'position': 1
        },
        ...
    ],
    'modality_specific_data': {
        'duration_seconds': 300.0,
        'has_audio': True,
        'num_frames_analyzed': 10,
        'fps': 30.0,
        'codec': 'h264',
        'resolution': '1920x1080'
    }
}
```

**Frame Sampling**:

- Default: 1 frame every 30 seconds
- Maximum: 10 frames per video
- Configurable via `frame_interval` parameter

**Scene Detection**:

- **Bright**: Average pixel brightness >200
- **Dark**: Average pixel brightness <50
- **Normal**: Everything else

### 4. Text Extractor (`extract/text_extractor.py`)

**Supported Formats**: `.txt`, `.md`, `.csv`, `.json`, `.xml`, `.html`, `.log`, `.yaml`, `.py`, `.js`, `.java`, etc.

**Encoding Detection** (6 fallback encodings):

1. UTF-8
2. Latin-1 (ISO-8859-1)
3. CP1252 (Windows-1252)
4. ISO-8859-1
5. ASCII
6. UTF-8 with `errors='ignore'` (lossy)

**Structure Detection**:

- **Extension-based**: `.md`/`.rst` → markdown, `.py`/`.js` → code, `.log` → log
- **Content-based**: Checks for headers (`#`), code patterns (`def`, `class`), log patterns (`ERROR:`)

**Segmentation Strategies**:

| Structure | Method                  | Behavior                                                |
| --------- | ----------------------- | ------------------------------------------------------- |
| Markdown  | `_segment_markdown()`   | Split by headers (`#`, `##`, `###`), preserve hierarchy |
| Code      | `_segment_code()`       | Split by function/class definitions                     |
| Log       | `_segment_log()`        | Chunk by 10-line groups                                 |
| Plain     | `_segment_paragraphs()` | Split by double-newline                                 |

**Output**:

```python
{
    'content': 'Full text content...',
    'content_segments': [
        {
            'segment_id': 'txt_seg_0',
            'segment_type': 'paragraph',  # or 'heading', 'function', 'log_chunk'
            'content': 'Segment text...',
            'position': 0
        },
        ...
    ],
    'modality_specific_data': {
        'encoding': 'utf-8',
        'file_structure': 'markdown',  # markdown/code/log/structured/plain
        'is_code': False,
        'estimated_reading_time': 5.2,  # minutes at 200 WPM
        'num_lines': 150
    }
}
```

### 5. PDF Extractor (Legacy Implementation)

**Supported Formats**: `.pdf`

**Extraction Methods**:

- `pdfplumber` (preferred) or `PyPDF2` (fallback)
- Page-based segmentation
- Document type inference (resume, research_paper, invoice, legal_document, etc.)

**Output**: Same structure as other extractors

## Standardized JSON Output

All extractors produce documents with this structure:

```python
{
    # Original fields preserved
    'doc_id': 'unique_document_id',
    'file_path': '/path/to/file.ext',
    'file_type': 'audio',  # audio/image/video/text/pdf

    # Extracted content
    'content': 'Main text for NER extraction...',

    # Structured segments
    'content_segments': [
        {
            'segment_id': 'format_seg_0',
            'segment_type': 'sentence|paragraph|frame|etc',
            'content': 'Segment text...',
            'position': 0,
            # Format-specific fields (timestamps, page numbers, etc.)
        }
    ],

    # Format-specific metadata
    'modality_specific_data': {
        # Varies by format (duration, dimensions, encoding, etc.)
    },

    # Pre-identified entities (helps downstream NER)
    'extracted_entities_hints': [
        {
            'text': 'John Doe',
            'label': 'PERSON',
            'confidence': 0.9,
            'method': 'pattern',  # pattern or llm
            'start': 10,
            'end': 18
        }
    ],

    # Extraction metadata
    'metadata': {
        'extraction_status': 'success',  # success/failed
        'file_size': 1024000,  # bytes
        'content_length': 5000,  # chars
        'num_segments': 10,
        'processing_time': 2.5,  # seconds
        'extractor_used': 'audio_extractor'
    },

    # Quality assessment
    'extraction_quality': {
        'success': True,
        'confidence': 0.9,  # 0.0-1.0
        'completeness': 0.85,  # 0.0-1.0
        'content_length': 5000,
        'num_segments': 10
    },

    'processed_at': '2024-01-15T10:30:00'
}
```

## Configuration

### Environment Variables

```bash
# Required for LLM enhancements
export GROQ_API_KEY="your_groq_api_key"

# Optional: Commercial transcription services
export ASSEMBLYAI_API_KEY="your_assemblyai_key"

# Optional: Google Cloud Speech-to-Text
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"
```

### Dependencies

**Core Dependencies** (always required):

```bash
pip install loguru Pillow pytesseract
```

**Audio Processing**:

```bash
pip install openai-whisper pydub mutagen
# Optional: assemblyai google-cloud-speech
```

**Image Processing**:

```bash
pip install easyocr paddleocr
```

**Video Processing**:

```bash
pip install moviepy opencv-python
```

**PDF Processing** (already installed):

```bash
pip install PyPDF2 pdfplumber
```

## Usage

### Basic Usage

```python
from extract.multimodal_processor import MultiModalProcessor

# Initialize processor
processor = MultiModalProcessor(groq_api_key="your_key")

# Process a document
document = {
    'doc_id': 'example_001',
    'file_path': '/path/to/file.mp3',
    'file_type': 'audio'
}

result = await processor.process_document(document)

# Access extracted content
print(result['content'])  # Main text
print(result['content_segments'])  # Structured segments
print(result['extracted_entities_hints'])  # Pre-identified entities
```

### Pipeline Integration

```python
from scripts.demo_pipeline import ResumePipeline

pipeline = ResumePipeline()

# Automatically discovers and processes files from:
# - data/raw/pdf/
# - data/raw/audio/
# - data/raw/image/
# - data/raw/video/
# - data/raw/text/ (or data/raw/img/ for images)

await pipeline.run()
```

## Quality Thresholds

All extractors enforce minimum quality thresholds:

- **Minimum characters**: 50
- **Minimum words**: 10
- **Optimal characters**: 500 (for 100% completeness score)

Documents failing these thresholds will have lower confidence scores.

## Error Handling

Each extractor has multiple fallback methods. If all methods fail:

1. Logs warning with error details
2. Returns document with `extraction_status='failed'`
3. Empty content and segments
4. Error message in metadata
5. Quality metrics show `success=False`, `confidence=0.0`

## Troubleshooting

### Audio Issues

**Problem**: "No module named 'whisper'"

```bash
pip install openai-whisper
```

**Problem**: Low quality transcription (WPM <50 or >300)

- Check audio file quality
- Try different transcription method
- Ensure audio has clear speech

### Image Issues

**Problem**: "Tesseract not found"

```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# Windows
Download from https://github.com/UB-Mannheim/tesseract/wiki
```

**Problem**: Low text coverage

- Image may have minimal text (e.g., photos)
- Try enabling vision description: `use_llm_vision=True`

### Video Issues

**Problem**: "MoviePy not installed"

```bash
pip install moviepy
```

**Problem**: No audio track extracted

- Video may not have audio track
- Check `has_audio` in modality_specific_data
- Only visual frame analysis will be performed

### Text Issues

**Problem**: Encoding errors

- Text extractor tries 6 encodings automatically
- If all fail, check file is actually text-based
- Try opening in text editor to verify encoding

## Performance Notes

### Processing Times (approximate)

| Format | File Size | Processing Time | Bottleneck                       |
| ------ | --------- | --------------- | -------------------------------- |
| PDF    | 1 MB      | 2-5s            | Text extraction                  |
| Audio  | 5 min     | 30-60s          | Transcription (Whisper)          |
| Image  | 1920x1080 | 1-3s            | OCR                              |
| Video  | 10 min    | 2-5 min         | Frame extraction + transcription |
| Text   | 100 KB    | <1s             | I/O                              |

### Optimization Tips

1. **Audio**: Use Groq API for faster cloud transcription
2. **Image**: Reduce image resolution before OCR if >2 megapixels
3. **Video**: Adjust `frame_interval` (default 30s) to sample fewer frames
4. **Text**: Use `max_file_size` to skip very large files

## Testing

### Sample Data

Place test files in:

```
data/raw/
├── audio/
│   ├── interview.mp3
│   └── lecture.wav
├── img/  (or image/)
│   ├── document_scan.jpg
│   └── screenshot.png
├── video/
│   ├── presentation.mp4
│   └── tutorial.mov
├── text/ (if available, or use pdf/)
│   ├── notes.txt
│   └── article.md
└── pdf/
    └── resume.pdf
```

### Run Full Pipeline

```bash
cd "Knowledge Graph"
python scripts/demo_pipeline.py
```

This will:

1. Discover all files in data/raw/\*
2. Process each with appropriate extractor
3. Run NER on extracted content
4. Extract relations between entities
5. Build knowledge graph in Neo4j and Fuseki

## Architecture Benefits

1. **Modularity**: Each format has dedicated extractor with specialized logic
2. **Consistency**: All extractors return same JSON structure
3. **Reliability**: Multiple fallback methods per format
4. **Quality**: Pre-extraction entity hints improve downstream NER
5. **Extensibility**: Easy to add new formats by extending BaseExtractor
6. **Maintainability**: Changes to one format don't affect others

## Future Enhancements

- [ ] Add `.docx` / `.pptx` support via `python-docx` / `python-pptx`
- [ ] Implement PDF OCR for scanned documents
- [ ] Add speaker diarization for audio (identify who's speaking)
- [ ] Scene change detection for video
- [ ] Table extraction from images/PDFs
- [ ] Multi-language support (currently English-focused)
- [ ] Batch processing with parallel extraction

## References

- **Whisper**: https://github.com/openai/whisper
- **Tesseract**: https://github.com/tesseract-ocr/tesseract
- **EasyOCR**: https://github.com/JaidedAI/EasyOCR
- **PaddleOCR**: https://github.com/PaddlePaddle/PaddleOCR
- **MoviePy**: https://zulko.github.io/moviepy/
