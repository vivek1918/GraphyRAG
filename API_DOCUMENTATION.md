# Knowledge Graph RAG API Documentation

## Overview

This FastAPI backend provides REST API endpoints for the Multi-modal Knowledge Graph RAG system. It enables document upload, processing, and intelligent question-answering using retrieval-augmented generation.

**Base URL**: `http://localhost:8000`

**Interactive Documentation**: 
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [API Endpoints](#api-endpoints)
   - [Health & Status](#health--status-endpoints)
   - [Chat & Query](#chat--query-endpoints)
   - [Multi-Modal File Upload](#multi-modal-file-upload-endpoints)
   - [Document Management](#document-management-endpoints)
   - [Vector Store](#vector-store-endpoints)
   - [Demo Pipeline](#demo-pipeline-endpoints)
   - [System Information](#system-information-endpoints)
4. [Request/Response Models](#requestresponse-models)
5. [Error Handling](#error-handling)
6. [Usage Examples](#usage-examples)

---

## Quick Start

### Starting the Server

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GROQ_API_KEY="your_api_key_here"

# Start the server
python api.py

# Or using uvicorn directly
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

### First API Call

```bash
# Check if server is running
curl http://localhost:8000/health

# Get system status
curl http://localhost:8000/api/status
```

---

## Authentication

Currently, the API does not require authentication. For production deployment, consider implementing:
- JWT token authentication
- API key validation
- OAuth2 integration

---

## API Endpoints

### Health & Status Endpoints

#### 1. Root Endpoint
**GET** `/`

Returns basic API information.

**Response:**
```json
{
  "name": "Knowledge Graph RAG API",
  "version": "1.0.0",
  "status": "running",
  "endpoints": {
    "docs": "/docs",
    "health": "/health",
    "status": "/api/status"
  }
}
```

---

#### 2. Health Check
**GET** `/health`

Checks if the API server is running and healthy.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-26T10:30:00.000Z",
  "chatbot_ready": true
}
```

---

#### 3. System Status
**GET** `/api/status`

Returns detailed system status including loaded documents and vector store state.

**Response:**
```json
{
  "status": "ready",
  "message": "System operational",
  "pdf_count": 5,
  "pdf_files": [
    "yoga_guide.pdf",
    "meditation_techniques.pdf",
    "wellness_handbook.pdf",
    "nutrition_basics.pdf",
    "exercise_routines.pdf"
  ],
  "vector_store_loaded": true
}
```

**Status Values:**
- `ready`: System is operational
- `initializing`: System is starting up
- `error`: System encountered an error

---

## 🎯 **New Features Summary**

### Multi-Modal Support
The API now supports uploading and processing files from **5 different modalities**:
- **PDF** documents (.pdf)
- **Audio** files (.mp3, .wav, .m4a, .flac, .ogg, .wma, .aac)
- **Image** files (.jpg, .jpeg, .png, .gif, .bmp, .tiff, .webp)
- **Video** files (.mp4, .avi, .mov, .mkv, .flv, .wmv, .webm, .m4v)
- **Text** files (.txt, .md, .csv, .json, .xml, .html, .log, .yaml, .yml)

### Demo Pipeline Integration
Execute the complete knowledge graph construction pipeline through the API with:
- Real-time log streaming
- Progress monitoring
- Background execution
- Comprehensive results reporting

---

### Chat & Query Endpoints

#### 4. Chat Query
**POST** `/api/chat`

Process a user query using RAG (Retrieval-Augmented Generation).

**Request Body:**
```json
{
  "query": "What are the benefits of meditation?",
  "session_id": "optional-session-id",
  "top_k": 4
}
```

**Request Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| query | string | Yes | - | User's question |
| session_id | string | No | auto-generated | Session ID for conversation history |
| top_k | integer | No | 4 | Number of relevant documents to retrieve (1-10) |

**Response:**
```json
{
  "response": "Meditation offers several benefits including stress reduction, improved focus, better emotional regulation, and enhanced mental clarity. According to the documents, regular meditation practice can...",
  "session_id": "abc123-def456-ghi789",
  "relevant_documents": [
    "Meditation is a practice that involves focusing the mind...",
    "Studies have shown that meditation reduces cortisol levels...",
    "The benefits of meditation include improved concentration...",
    "Regular meditation practice leads to structural changes..."
  ],
  "timestamp": "2025-12-26T10:35:00.000Z"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the benefits of meditation?",
    "top_k": 4
  }'
```

---

#### 5. Get Chat History
**GET** `/api/chat/history/{session_id}`

Retrieve conversation history for a specific session.

**Path Parameters:**
- `session_id` (string, required): Session identifier

**Response:**
```json
{
  "session_id": "abc123-def456-ghi789",
  "messages": [
    {
      "role": "user",
      "content": "What is yoga?",
      "timestamp": "2025-12-26T10:30:00.000Z"
    },
    {
      "role": "assistant",
      "content": "Yoga is a holistic practice that combines physical postures...",
      "timestamp": "2025-12-26T10:30:05.000Z"
    },
    {
      "role": "user",
      "content": "What are the benefits?",
      "timestamp": "2025-12-26T10:31:00.000Z"
    },
    {
      "role": "assistant",
      "content": "The benefits of yoga include improved flexibility...",
      "timestamp": "2025-12-26T10:31:03.000Z"
    }
  ]
}
```

**cURL Example:**
```bash
curl "http://localhost:8000/api/chat/history/abc123-def456-ghi789"
```

---

#### 6. Clear Chat History (Single Session)
**DELETE** `/api/chat/history/{session_id}`

Clear conversation history for a specific session.

**Path Parameters:**
- `session_id` (string, required): Session identifier

**Response:**
```json
{
  "message": "Chat history cleared for session abc123-def456-ghi789"
}
```

---

#### 7. Clear All Chat History
**DELETE** `/api/chat/history`

Clear all conversation histories for all sessions.

**Response:**
```json
{
  "message": "All chat histories cleared"
}
```

---

### Multi-Modal File Upload Endpoints

#### 16. Upload Multi-Modal Files
**POST** `/api/files/upload`

Upload multiple files for any modality (PDF, audio, image, video, text).

**Request:**
- Method: `multipart/form-data`
- Files parameter: `files` (array of files)
- Query parameter: `file_type` (string, required)

**File Types & Extensions:**
| Type | Supported Extensions |
|------|---------------------|
| pdf | .pdf |
| audio | .mp3, .wav, .m4a, .flac, .ogg, .wma, .aac |
| image | .jpg, .jpeg, .png, .gif, .bmp, .tiff, .webp |
| video | .mp4, .avi, .mov, .mkv, .flv, .wmv, .webm, .m4v |
| text | .txt, .md, .csv, .json, .xml, .html, .log, .yaml, .yml |

**Response:**
```json
{
  "success": true,
  "message": "Uploaded 3 file(s)",
  "uploaded_files": [
    {
      "filename": "research_paper.pdf",
      "file_type": "pdf",
      "size_bytes": 2458624
    },
    {
      "filename": "interview.mp3",
      "file_type": "audio",
      "size_bytes": 5242880
    },
    {
      "filename": "diagram.png",
      "file_type": "image",
      "size_bytes": 1048576
    }
  ],
  "failed_files": []
}
```

**cURL Example:**
```bash
# Upload PDF files
curl -X POST "http://localhost:8000/api/files/upload?file_type=pdf" \
  -F "files=@document1.pdf" \
  -F "files=@document2.pdf"

# Upload audio files
curl -X POST "http://localhost:8000/api/files/upload?file_type=audio" \
  -F "files=@interview.mp3" \
  -F "files=@podcast.wav"

# Upload image files
curl -X POST "http://localhost:8000/api/files/upload?file_type=image" \
  -F "files=@diagram.png" \
  -F "files=@chart.jpg"
```

**Python Example:**
```python
import requests

url = "http://localhost:8000/api/files/upload"

# Upload multiple PDFs
files = [
    ("files", open("doc1.pdf", "rb")),
    ("files", open("doc2.pdf", "rb"))
]
params = {"file_type": "pdf"}
response = requests.post(url, files=files, params=params)
print(response.json())

# Upload audio files
audio_files = [
    ("files", open("interview.mp3", "rb")),
    ("files", open("lecture.wav", "rb"))
]
params = {"file_type": "audio"}
response = requests.post(url, files=audio_files, params=params)
print(response.json())
```

---

#### 17. List All Files
**GET** `/api/files/list`

List all files across all modalities with metadata.

**Response:**
```json
{
  "total_files": 15,
  "files_by_type": {
    "pdf": [
      {
        "filename": "research_paper.pdf",
        "path": "/path/to/data/raw/pdf/research_paper.pdf",
        "size_bytes": 2458624,
        "uploaded_at": "2025-12-26T10:30:00.000Z"
      }
    ],
    "audio": [
      {
        "filename": "interview.mp3",
        "path": "/path/to/data/raw/audio/interview.mp3",
        "size_bytes": 5242880,
        "uploaded_at": "2025-12-26T11:00:00.000Z"
      }
    ],
    "image": [
      {
        "filename": "diagram.png",
        "path": "/path/to/data/raw/img/diagram.png",
        "size_bytes": 1048576,
        "uploaded_at": "2025-12-26T11:15:00.000Z"
      }
    ],
    "video": [],
    "text": []
  }
}
```

**cURL Example:**
```bash
curl "http://localhost:8000/api/files/list"
```

---

#### 18. Delete File by Type
**DELETE** `/api/files/{file_type}/{filename}`

Delete a file from any modality.

**Path Parameters:**
- `file_type` (string, required): Type of file (pdf, audio, image, video, text)
- `filename` (string, required): Name of the file to delete

**Response:**
```json
{
  "success": true,
  "message": "File 'old_recording.mp3' deleted successfully"
}
```

**cURL Examples:**
```bash
# Delete a PDF
curl -X DELETE "http://localhost:8000/api/files/pdf/old_document.pdf"

# Delete an audio file
curl -X DELETE "http://localhost:8000/api/files/audio/old_recording.mp3"

# Delete an image
curl -X DELETE "http://localhost:8000/api/files/image/old_chart.png"
```

---

### Document Management Endpoints

#### 8. List Documents
**GET** `/api/documents`

List all loaded PDF documents with metadata.

**Response:**
```json
[
  {
    "filename": "yoga_guide.pdf",
    "path": "/path/to/data/raw/pdf/yoga_guide.pdf",
    "size_bytes": 2458624,
    "uploaded_at": "2025-12-20T15:30:00.000Z"
  },
  {
    "filename": "meditation_techniques.pdf",
    "path": "/path/to/data/raw/pdf/meditation_techniques.pdf",
    "size_bytes": 1823456,
    Demo Pipeline Endpoints

#### 19. Run Complete Pipeline
**POST** `/api/pipeline/run`

Execute the complete knowledge graph construction pipeline.

**Request Body:**
```json
{
  "use_existing_data": true,
  "interactive_mode": false,
  "data_directory": null
}
```

**Request Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| use_existing_data | boolean | No | true | Use existing data files or generate synthetic |
| interactive_mode | boolean | No | false | Run in interactive query mode after completion |
| data_directory | string | No | null | Custom data directory path |

**Response:**
```json
{
  "running": true,
  "status": "initializing",
  "progress": 0,
  "message": "Initializing pipeline...",
  "logs": [],
  "start_time": "2025-12-26T12:00:00.000Z",
  "end_time": null,
  "results": null
}
```

**Pipeline Stages:**
1. **Data Loading** (0-30%): Load multi-modal files from disk
2. **Document Parsing** (30-40%): Extract text from all modalities
3. **Entity Extraction** (40-50%): Extract entities and relations using NLP
4. **Knowledge Graph Building** (50-70%): Create RDF triples and load to Neo4j/Fuseki
5. **RAG Indexing** (70-85%): Build FAISS vector index
6. **Report Generation** (85-100%): Generate comprehensive report

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{
    "use_existing_data": true,
    "interactive_mode": false
  }'
```

**Python Example:**
```python
import requests
import time

url = "http://localhost:8000/api/pipeline/run"
config = {
    "use_existing_data": True,
    "interactive_mode": False
}

# Start pipeline
response = requests.post(url, json=config)
print(f"Pipeline started: {response.json()}")

# Monitor progress
status_url = "http://localhost:8000/api/pipeline/status"
while True:
    status = requests.get(status_url).json()
    print(f"[{status['progress']}%] {status['message']}")
    
    if not status['running']:
        print(f"Pipeline finished: {status['status']}")
        if status['results']:
            print(f"Results: {status['results']}")
        break
    
    time.sleep(2)
```

---

#### 20. Get Pipeline Status
**GET** `/api/pipeline/status`

Get current pipeline execution status with progress and logs.

**Response:**
```json
{
  "running": true,
  "status": "processing",
  "progress": 65,
  "message": "Building knowledge graph...",
  "logs": [
    "2025-12-26 12:00:00 | INFO | Initializing pipeline...",
    "2025-12-26 12:00:05 | INFO | Loading data from disk...",
    "2025-12-26 12:00:10 | INFO | Found 25 documents across 4 modalities",
    "2025-12-26 12:00:15 | INFO | Parsing PDF documents...",
    "2025-12-26 12:01:00 | INFO | Extracting entities...",
    "2025-12-26 12:02:30 | INFO | Building knowledge graph..."
  ],
  "start_time": "2025-12-26T12:00:00.000Z",
  "end_time": null,
  "results": null
}
```

**Status Values:**
- `idle`: No pipeline running
- `initializing`: Starting up
- `processing`: Executing pipeline stages
- `completed`: Successfully finished
- `failed`: Encountered an error
- `stopping`: Termination requested

---

#### 21. Get Pipeline Logs
**GET** `/api/pipeline/logs`

Retrieve pipeline execution logs.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| lines | integer | 100 | Number of recent log lines (1-10000) |

**Response:**
```json
{
  "total_logs": 342,
  "returned_logs": 100,
  "logs": [
    "12:00:00 | INFO | Starting pipeline...",
    "12:00:05 | INFO | Loaded 15 PDF documents",
    "12:00:10 | INFO | Parsed document: research_paper.pdf",
    "..."
  ]
}
```

**cURL Example:**
```bash
# Get last 50 log lines
curl "http://localhost:8000/api/pipeline/logs?lines=50"

# Get all logs
curl "http://localhost:8000/api/pipeline/logs?lines=10000"
```

---

#### 22. Stream Pipeline Logs (Real-time)
**GET** `/api/pipeline/logs/stream`

Stream pipeline logs in real-time using Server-Sent Events (SSE).

**Response:** Continuous stream of log messages

**Usage Example (JavaScript):**
```javascript
const eventSource = new EventSource('http://localhost:8000/api/pipeline/logs/stream');

eventSource.onmessage = (event) => {
  console.log('Log:', event.data);
  
  // Display in UI
  const logDiv = document.getElementById('logs');
  logDiv.innerHTML += `<div>${event.data}</div>`;
  logDiv.scrollTop = logDiv.scrollHeight;
};

eventSource.onerror = (error) => {
  console.error('Stream error:', error);
  eventSource.close();
};

// Close stream when done
setTimeout(() => eventSource.close(), 300000); // 5 minutes
```

**Python Example:**
```python
import requests

url = "http://localhost:8000/api/pipeline/logs/stream"
response = requests.get(url, stream=True)

for line in response.iter_lines():
    if line:
        decoded_line = line.decode('utf-8')
        if decoded_line.startswith('data: '):
            log_message = decoded_line[6:]  # Remove 'data: ' prefix
            print(log_message)
```

---

#### 23. Stop Pipeline
**POST** `/api/pipeline/stop`

Request graceful termination of running pipeline.

**Response:**
```json
{
  "message": "Pipeline stop requested",
  "status": "stopping"
}
```

**Note:** Pipeline may take time to terminate gracefully.

---

#### 24. Clear Pipeline State
**DELETE** `/api/pipeline/clear`

Reset pipeline status and clear logs (only when pipeline is not running).

**Response:**
```json
{
  "message": "Pipeline state cleared successfully"
}
```

**Use Case:** Clear previous execution logs before starting a new pipeline run.

---

### "uploaded_at": "2025-12-21T09:15:00.000Z"
  }
]
```

---

#### 9. Upload Document
**POST** `/api/documents/upload`

Upload a new PDF document.

**Request:**
- Method: `multipart/form-data`
- File parameter: `file` (PDF file)
- Query parameter: `auto_process` (boolean, optional, default: false)

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| auto_process | boolean | No | false | Automatically process and index the document |

**Response:**
```json
{
  "success": true,
  "message": "Document uploaded successfully. Use /api/documents/process to index it.",
  "filename": "new_document.pdf",
  "document_id": "xyz789-abc123-def456"
}
```

**cURL Example:**
```bash
# Upload without auto-processing
curl -X POST "http://localhost:8000/api/documents/upload" \
  -F "file=@/path/to/document.pdf"

# Upload with auto-processing
curl -X POST "http://localhost:8000/api/documents/upload?auto_process=true" \
  -F "file=@/path/to/document.pdf"
```

**Python Example:**
```python
import requests

url = "http://localhost:8000/api/documents/upload"
files = {"file": open("document.pdf", "rb")}
params = {"auto_process": True}

response = requests.post(url, files=files, params=params)
print(response.json())
```

---

#### 10. Process Documents
**POST** `/api/documents/process`

Process all PDF documents and rebuild the vector store.

This endpoint:
1. Extracts text from all PDFs in the `data/raw/pdf` directory
2. Chunks the text into manageable pieces
3. Creates embeddings using sentence-transformers
4. Updates the FAISS vector store
5. Makes documents available for querying

**Note:** This is a resource-intensive operation that runs in the background.

**Response:**
```json
{
  "status": "processing",
  "message": "Document processing started in background",
  "documents_processed": 0,
  "total_chunks": 0
}
```

**Status Values:**
- `pending`: Waiting to start
- `processing`: Currently processing
- `completed`: Successfully completed
- `failed`: Processing failed

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/documents/process"
```

---

#### 11. Delete Document
**DELETE** `/api/documents/{filename}`

Delete a specific PDF document.

**Path Parameters:**
- `filename` (string, required): Name of the file to delete

**Response:**
```json
{
  "success": true,
  "message": "Document 'old_document.pdf' deleted. Run /api/documents/process to update vector store."
}
```

**cURL Example:**
```bash
curl -X DELETE "http://localhost:8000/api/documents/old_document.pdf"
```

**Important:** After deleting documents, run `/api/documents/process` to update the vector store.

---

### Vector Store Endpoints

#### 12. Reload Vector Store
**POST** `/api/vector-store/reload`

Reload the vector store from disk without reprocessing documents.

**Response:**
```json
{
  "success": true,
  "message": "Vector store reloaded successfully"
}
```

**Use Case:** Reload the vector store after external modifications or system restart.

---

#### 13. Vector Similarity Search
**GET** `/api/vector-store/search`

Perform vector similarity search without LLM processing.

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| query | string | Yes | - | Search query |
| k | integer | No | 4 | Number of results (1-20) |

**Response:**
```json
{
  "query": "meditation techniques",
  "results": [
    "Meditation techniques include mindfulness meditation, focused attention...",
    "Various meditation styles exist, each with unique benefits...",
    "Body scan meditation involves systematically focusing...",
    "Transcendental meditation uses mantras to achieve..."
  ],
  "count": 4
}
```

**cURL Example:**
```bash
curl "http://localhost:8000/api/vector-store/search?query=meditation%20techniques&k=5"
```

---

### System Information Endpoints

#### 14. Get System Information
**GET** `/api/system/info`

Get detailed system information including active sessions and model details.

**Response:**
```json
{
  "info": "📚 RAG PDF Chatbot\n==================================================\n• PDF Files Loaded: 5\n• Documents: yoga_guide.pdf, meditation_techniques.pdf, wellness_handbook.pdf...\n• Vector Database: FAISS\n• LLM: Groq Mixtral-8x7b\n\n💡 I can answer questions based ONLY on the provided PDF documents...",
  "active_sessions": 3,
  "model": "Groq Llama 3.1 8B Instant",
  "vector_db": "FAISS",
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
}
```

---

#### 15. Get System Configuration
**GET** `/api/system/config`

Get system configuration settings.

**Response:**
```json
{
  "pdf_directory": "data/raw/pdf",
  "vector_store_path": "data/vector_store/faiss_index",
  "model_name": "llama-3.1-8b-instant",
  "chunk_size": 1000,
  "chunk_overlap": 200
}
```

---

## Request/Response Models

### QueryRequest
```json
{
  "query": "string (required)",
  "session_id": "string (optional)",
  "top_k": "integer (optional, 1-10, default: 4)"
}
```

### QueryResponse
```json
{
  "response": "string",
  "session_id": "string",
  "relevant_documents": ["string"],
  "timestamp": "string (ISO 8601)"
}
```

### ChatMessage
```json
{
  "role": "string (user|assistant)",
  "content": "string",
  "timestamp": "string (ISO 8601)"
}
```

### SystemStatus
```json
{
  "status": "string (ready|initializing|error)",
  "message": "string",
  "pdf_count": "integer",
  "pdf_files": ["string"],
  "vector_store_loaded": "boolean"
}
```

### DocumentInfo
```json
{
  "filename": "string",
  "path": "string",
  "size_bytes": "integer (optional)",
  "uploaded_at": "string (ISO 8601, optional)"
}
```

---

## Error Handling

### Error Response Format
```json
{
  "error": "Error type",
  "detail": "Detailed error message"
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid input |
| 404 | Not Found - Resource doesn't exist |
| 500 | Internal Server Error |
| 503 | Service Unavailable - Chatbot not initialized |

### Common Errors

#### 503 Service Unavailable
```json
{
  "detail": "Chatbot not initialized"
}
```
**Solution:** Wait for system to initialize or check server logs.

#### 400 Bad Request
```json
{
  "detail": "Only PDF files are supported"
}
```
**Solution:** Upload only PDF files.

#### 404 Not Found
```json
{
  "detail": "Session not found"
}
```
**Solution:** Verify the session_id or create a new session.

---

## Usage Examples

### Example 1: Complete Chat Workflow

```python
import requests
import time

BASE_URL = "http://localhost:8000"

# 1. Check system status
status = requests.get(f"{BASE_URL}/api/status").json()
print(f"System Status: {status['status']}")
print(f"PDF Count: {status['pdf_count']}")

# 2. Upload a new document
with open("new_document.pdf", "rb") as f:
    files = {"file": f}
    upload_response = requests.post(
        f"{BASE_URL}/api/documents/upload?auto_process=true",
        files=files
    ).json()
    print(f"Upload: {upload_response['message']}")

# 3. Wait for processing (if auto_process=true)
time.sleep(5)

# 4. Start a chat session
query1 = {
    "query": "What is the main topic of the documents?",
    "top_k": 4
}
response1 = requests.post(f"{BASE_URL}/api/chat", json=query1).json()
session_id = response1['session_id']
print(f"\nQ: {query1['query']}")
print(f"A: {response1['response']}")

# 5. Continue conversation with same session
query2 = {
    "query": "Tell me more about that",
    "session_id": session_id,
    "top_k": 4
}
response2 = requests.post(f"{BASE_URL}/api/chat", json=query2).json()
print(f"\nQ: {query2['query']}")
print(f"A: {response2['response']}")

# 6. Get chat history
history = requests.get(f"{BASE_URL}/api/chat/history/{session_id}").json()
print(f"\nChat History: {len(history['messages'])} messages")

# 7. Clear history
requests.delete(f"{BASE_URL}/api/chat/history/{session_id}")
print("History cleared")
```

---

### Example 2: Document Management

```python
import requests

BASE_URL = "http://localhost:8000"

# List all documents
docs = requests.get(f"{BASE_URL}/api/documents").json()
print(f"Total documents: {len(docs)}")
for doc in docs:
    print(f"- {doc['filename']} ({doc['size_bytes'] / 1024:.2f} KB)")

# Delete a document
filename = "old_document.pdf"
delete_response = requests.delete(
    f"{BASE_URL}/api/documents/{filename}"
).json()
print(delete_response['message'])

# Reprocess documents after deletion
process_response = requests.post(
    f"{BASE_URL}/api/documents/process"
).json()
print(process_response['message'])
```

---

### Example 3: Vector Search Only

```python
import requests

BASE_URL = "http://localhost:8000"

# Perform vector search without LLM
search_params = {
    "query": "yoga benefits",
    "k": 5
}
results = requests.get(
    f"{BASE_URL}/api/vector-store/search",
    params=search_params
).json()

print(f"Found {results['count']} relevant chunks:")
for i, chunk in enumerate(results['results'], 1):
    print(f"\n{i}. {chunk[:200]}...")
```

---

### Example 4: JavaScript/TypeScript Frontend

```javascript
// API Client Class
class RAGChatbotAPI {
  constructor(baseURL = 'http://localhost:8000') {
    this.baseURL = baseURL;
    this.sessionId = null;
  }

  async chat(query, topK = 4) {
    const response = await fetch(`${this.baseURL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        session_id: this.sessionId,
        top_k: topK,
      }),
    });
    
    const data = await response.json();
    this.sessionId = data.session_id;
    return data;
  }

  async uploadDocument(file, autoProcess = false) {
    const formData = new FormData();
    formData.append('file', file);
    
    const url = `${this.baseURL}/api/documents/upload?auto_process=${autoProcess}`;
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });
    
    return await response.json();
  }

  async getSystemStatus() {
    const response = await fetch(`${this.baseURL}/api/status`);
    return await response.json();
  }

  async getChatHistory() {
    if (!this.sessionId) return null;
    
    const response = await fetch(
      `${this.baseURL}/api/chat/history/${this.sessionId}`
    );
    return await response.json();
  }

  async clearHistory() {
    if (!this.sessionId) return;
    
    await fetch(
      `${this.baseURL}/api/chat/history/${this.sessionId}`,
      { method: 'DELETE' }
    );
    this.sessionId = null;
  }
}

// Usage Example
const api = new RAGChatbotAPI();

// Check status
const status = await api.getSystemStatus();
console.log('System ready:', status.status === 'ready');

// Chat
const response = await api.chat('What are the benefits of meditation?');
console.log('Answer:', response.response);

// Upload document
const fileInput = document.querySelector('#file-input');
const file = fileInput.files[0];
await api.uploadDocument(file, true);

// Get history
const history = await api.getChatHistory();
console.log('Messages:', history.messages.length);
```

---

### Example 5: React Frontend Component

```jsx
import React, { useState, useEffect } from 'react';

const ChatInterface = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [systemStatus, setSystemStatus] = useState(null);

  const API_BASE = 'http://localhost:8000';

  useEffect(() => {
    // Check system status on mount
    fetch(`${API_BASE}/api/status`)
      .then(res => res.json())
      .then(data => setSystemStatus(data));
  }, []);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages([...messages, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: input,
          session_id: sessionId,
          top_k: 4,
        }),
      });

      const data = await response.json();
      setSessionId(data.session_id);

      const assistantMessage = {
        role: 'assistant',
        content: data.response,
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-interface">
      <div className="status-bar">
        {systemStatus && (
          <span>
            {systemStatus.status === 'ready' ? '✅' : '⚠️'} 
            {systemStatus.pdf_count} documents loaded
          </span>
        )}
      </div>

      <div className="messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <strong>{msg.role === 'user' ? 'You' : 'AI'}:</strong>
            <p>{msg.content}</p>
          </div>
        ))}
        {loading && <div className="loading">Thinking...</div>}
      </div>

      <div className="input-area">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="Ask a question..."
          disabled={loading}
        />
        <button onClick={sendMessage} disabled={loading}>
          Send
        </button>
      </div>
    </div>
  );
};

export default ChatInterface;
```

---

### Example 6: Complete Multi-Modal Pipeline Workflow

```python
import requests
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"

def upload_multimodal_files():
    """Upload files from multiple modalities"""
    
    # 1. Upload PDF documents
    pdf_files = [
        ("files", open("research_paper.pdf", "rb")),
        ("files", open("technical_report.pdf", "rb"))
    ]
    response = requests.post(
        f"{BASE_URL}/api/files/upload?file_type=pdf",
        files=pdf_files
    )
    print(f"✓ Uploaded PDFs: {response.json()['message']}")
    
    # 2. Upload audio files
    audio_files = [
        ("files", open("interview.mp3", "rb")),
        ("files", open("lecture.wav", "rb"))
    ]
    response = requests.post(
        f"{BASE_URL}/api/files/upload?file_type=audio",
        files=audio_files
    )
    print(f"✓ Uploaded Audio: {response.json()['message']}")
    
    # 3. Upload images
    image_files = [
        ("files", open("diagram.png", "rb")),
        ("files", open("chart.jpg", "rb"))
    ]
    response = requests.post(
        f"{BASE_URL}/api/files/upload?file_type=image",
        files=image_files
    )
    print(f"✓ Uploaded Images: {response.json()['message']}")
    
    # 4. Upload text files
    text_files = [
        ("files", open("notes.txt", "rb")),
        ("files", open("readme.md", "rb"))
    ]
    response = requests.post(
        f"{BASE_URL}/api/files/upload?file_type=text",
        files=text_files
    )
    print(f"✓ Uploaded Text: {response.json()['message']}")
    
    # 5. List all uploaded files
    response = requests.get(f"{BASE_URL}/api/files/list")
    files_info = response.json()
    print(f"\n📊 Total files uploaded: {files_info['total_files']}")
    for file_type, files in files_info['files_by_type'].items():
        if files:
            print(f"  - {file_type}: {len(files)} files")


def run_pipeline_with_monitoring():
    """Run pipeline and monitor progress"""
    
    print("\n🚀 Starting Knowledge Graph Pipeline...\n")
    
    # 1. Start pipeline
    config = {
        "use_existing_data": True,
        "interactive_mode": False,
        "data_directory": None
    }
    
    response = requests.post(f"{BASE_URL}/api/pipeline/run", json=config)
    if response.status_code == 200:
        print("✓ Pipeline started successfully")
    else:
        print(f"✗ Failed to start pipeline: {response.json()}")
        return
    
    # 2. Monitor progress
    print("\n📈 Monitoring progress...\n")
    
    while True:
        # Get status
        status = requests.get(f"{BASE_URL}/api/pipeline/status").json()
        
        # Display progress bar
        progress = status['progress']
        bar_length = 40
        filled = int(bar_length * progress / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        print(f"\r[{bar}] {progress}% - {status['message']}", end='', flush=True)
        
        # Check if finished
        if not status['running']:
            print()  # New line
            break
        
        time.sleep(2)
    
    # 3. Get final results
    final_status = requests.get(f"{BASE_URL}/api/pipeline/status").json()
    
    if final_status['status'] == 'completed':
        print("\n✅ Pipeline completed successfully!\n")
        
        results = final_status['results']
        if results:
            print("📊 Results Summary:")
            print(f"  - Documents processed: {results.get('documents_processed', 0)}")
            
            kg_stats = results.get('kg_stats', {})
            print(f"  - Total triples: {kg_stats.get('total_triples', 0)}")
            print(f"  - Entities: {kg_stats.get('entities', 0)}")
            print(f"  - Relations: {kg_stats.get('relations', 0)}")
            
            datasets = results.get('datasets', {})
            print(f"\n  Dataset breakdown:")
            for modality, count in datasets.items():
                print(f"    - {modality}: {count} files")
        
        # 4. Get execution logs
        logs_response = requests.get(f"{BASE_URL}/api/pipeline/logs?lines=50")
        logs = logs_response.json()
        
        print(f"\n📝 Last {logs['returned_logs']} log entries:")
        for log in logs['logs'][-10:]:  # Show last 10
            print(f"  {log}")
    
    else:
        print(f"\n❌ Pipeline failed: {final_status['message']}\n")
        
        # Get error logs
        logs_response = requests.get(f"{BASE_URL}/api/pipeline/logs?lines=100")
        error_logs = [log for log in logs_response.json()['logs'] if 'ERROR' in log]
        
        if error_logs:
            print("❌ Error logs:")
            for log in error_logs[-5:]:
                print(f"  {log}")


def query_knowledge_graph():
    """Query the constructed knowledge graph"""
    
    print("\n💬 Querying Knowledge Graph...\n")
    
    queries = [
        "What entities were extracted from the documents?",
        "What are the main topics discussed?",
        "Find all relationships between organizations and people",
        "Summarize the key findings"
    ]
    
    for query in queries:
        response = requests.post(
            f"{BASE_URL}/api/chat",
            json={"query": query, "top_k": 5}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"Q: {query}")
            print(f"A: {result['response'][:200]}...\n")
        else:
            print(f"✗ Query failed: {response.json()}\n")


def main():
    """Main workflow"""
    print("=" * 70)
    print("Multi-Modal Knowledge Graph Pipeline Workflow")
    print("=" * 70)
    
    # Step 1: Upload files
    print("\n📤 STEP 1: Uploading Multi-Modal Files")
    print("-" * 70)
    upload_multimodal_files()
    
    # Step 2: Run pipeline
    print("\n⚙️  STEP 2: Running Knowledge Graph Pipeline")
    print("-" * 70)
    run_pipeline_with_monitoring()
    
    # Step 3: Query results
    print("\n🔍 STEP 3: Querying Knowledge Graph")
    print("-" * 70)
    query_knowledge_graph()
    
    print("\n" + "=" * 70)
    print("✅ Workflow completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
```

**Output:**
```
======================================================================
Multi-Modal Knowledge Graph Pipeline Workflow
======================================================================

📤 STEP 1: Uploading Multi-Modal Files
----------------------------------------------------------------------
✓ Uploaded PDFs: Uploaded 2 file(s)
✓ Uploaded Audio: Uploaded 2 file(s)
✓ Uploaded Images: Uploaded 2 file(s)
✓ Uploaded Text: Uploaded 2 file(s)

📊 Total files uploaded: 8
  - pdf: 2 files
  - audio: 2 files
  - image: 2 files
  - text: 2 files

⚙️  STEP 2: Running Knowledge Graph Pipeline
----------------------------------------------------------------------
🚀 Starting Knowledge Graph Pipeline...

✓ Pipeline started successfully

📈 Monitoring progress...

[████████████████████████████████████████] 100% - Pipeline completed!

✅ Pipeline completed successfully!

📊 Results Summary:
  - Documents processed: 8
  - Total triples: 1,247
  - Entities: 342
  - Relations: 156

  Dataset breakdown:
    - pdf: 2 files
    - audio: 2 files
    - image: 2 files
    - text: 2 files

📝 Last 10 log entries:
  12:05:30 | INFO | Building knowledge graph...
  12:06:15 | INFO | Successfully loaded 1,247 triples into Fuseki
  12:06:20 | INFO | Building RAG index...
  12:06:45 | INFO | RAG index built successfully
  12:06:50 | INFO | Generating report...
  12:06:55 | INFO | Demo report saved
  12:07:00 | INFO | Pipeline completed successfully

🔍 STEP 3: Querying Knowledge Graph
----------------------------------------------------------------------
💬 Querying Knowledge Graph...

Q: What entities were extracted from the documents?
A: The system extracted 342 entities including 145 persons, 87 organizations, 56 locations, and 54 other entity types from the multi-modal documents...

Q: What are the main topics discussed?
A: The main topics include research methodologies, technical implementations, organizational structures, and key findings from various domains...

======================================================================
✅ Workflow completed successfully!
======================================================================
```

---

### Example 7: Real-Time Log Streaming (React Component)

```jsx
import React, { useState, useEffect } from 'react';

const PipelineMonitor = () => {
  const [status, setStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [isRunning, setIsRunning] = useState(false);

  const API_BASE = 'http://localhost:8000';

  // Start pipeline
  const startPipeline = async () => {
    const config = {
      use_existing_data: true,
      interactive_mode: false
    };

    const response = await fetch(`${API_BASE}/api/pipeline/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    });

    if (response.ok) {
      setIsRunning(true);
      startLogStream();
      monitorProgress();
    }
  };

  // Stream logs in real-time
  const startLogStream = () => {
    const eventSource = new EventSource(`${API_BASE}/api/pipeline/logs/stream`);

    eventSource.onmessage = (event) => {
      const logMessage = event.data;
      setLogs(prev => [...prev, logMessage]);
    };

    eventSource.onerror = () => {
      eventSource.close();
      setIsRunning(false);
    };
  };

  // Monitor progress
  const monitorProgress = () => {
    const interval = setInterval(async () => {
      const response = await fetch(`${API_BASE}/api/pipeline/status`);
      const data = await response.json();
      
      setStatus(data);
      
      if (!data.running) {
        clearInterval(interval);
        setIsRunning(false);
      }
    }, 2000);
  };

  return (
    <div className="pipeline-monitor">
      <h2>Knowledge Graph Pipeline Monitor</h2>
      
      {/* Control buttons */}
      <div className="controls">
        <button 
          onClick={startPipeline} 
          disabled={isRunning}
        >
          {isRunning ? 'Running...' : 'Start Pipeline'}
        </button>
      </div>

      {/* Progress bar */}
      {status && (
        <div className="progress-section">
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${status.progress}%` }}
            >
              {status.progress}%
            </div>
          </div>
          <p className="status-message">{status.message}</p>
        </div>
      )}

      {/* Real-time logs */}
      <div className="logs-container">
        <h3>Execution Logs</h3>
        <div className="logs-window">
          {logs.map((log, idx) => (
            <div key={idx} className="log-entry">
              {log}
            </div>
          ))}
        </div>
      </div>

      {/* Results */}
      {status && status.results && (
        <div className="results-section">
          <h3>Pipeline Results</h3>
          <div className="results-grid">
            <div className="result-card">
              <h4>Documents</h4>
              <p>{status.results.documents_processed}</p>
            </div>
            <div className="result-card">
              <h4>Triples</h4>
              <p>{status.results.kg_stats?.total_triples || 0}</p>
            </div>
            <div className="result-card">
              <h4>Entities</h4>
              <p>{status.results.kg_stats?.entities || 0}</p>
            </div>
            <div className="result-card">
              <h4>Relations</h4>
              <p>{status.results.kg_stats?.relations || 0}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PipelineMonitor;
```

---

## Production Deployment Considerations

### Security
1. **Add Authentication**: Implement JWT or API key authentication
2. **Rate Limiting**: Add request rate limiting to prevent abuse
3. **CORS Configuration**: Restrict allowed origins in production
4. **Input Validation**: Sanitize all user inputs
5. **File Upload Security**: Validate file types and scan for malware

### Performance
1. **Caching**: Implement Redis for caching frequent queries
2. **Async Processing**: Use Celery for long-running tasks
3. **Load Balancing**: Deploy multiple instances behind a load balancer
4. **Database**: Consider using PostgreSQL for persistent session storage

### Monitoring
1. **Logging**: Implement structured logging with ELK stack
2. **Metrics**: Add Prometheus metrics for monitoring
3. **Error Tracking**: Use Sentry for error tracking
4. **Health Checks**: Implement comprehensive health check endpoints

### Scalability
1. **Containerization**: Use Docker for consistent deployment
2. **Orchestration**: Deploy with Kubernetes for auto-scaling
3. **CDN**: Use CDN for static assets
4. **Database Replication**: Implement read replicas for database

---

## Environment Variables

```bash
# Required
GROQ_API_KEY=your_groq_api_key_here

# Optional
API_HOST=0.0.0.0
API_PORT=8000
PDF_DIRECTORY=data/raw/pdf
VECTOR_STORE_PATH=data/vector_store/faiss_index
LOG_LEVEL=INFO
TOKENIZERS_PARALLELISM=false
```

---

## Running with Docker

### Dockerfile
```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml
```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

### Run
```bash
docker-compose up -d
```

---

## Support

For issues or questions:
- Check the interactive API documentation at `/docs`
- Review server logs for error messages
- Ensure all dependencies are installed
- Verify environment variables are set correctly

---

## Changelog

### Version 1.0.0 (2025-12-26)
- Initial release
- Chat endpoints with session management
- Document upload and processing
- Vector store operations
- System information endpoints
- Complete API documentation
