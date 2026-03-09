# API Quick Reference

## 🚀 Quick Start

```bash
# Start server
python api.py

# Or with uvicorn
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

**Interactive Docs**: http://localhost:8000/docs

---

## 📡 All API Endpoints (24 Total)

### ✅ Health & Status (3)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information |
| GET | `/health` | Health check |
| GET | `/api/status` | System status |

### 💬 Chat & Query (4)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Process chat query with RAG |
| GET | `/api/chat/history/{session_id}` | Get chat history |
| DELETE | `/api/chat/history/{session_id}` | Clear session history |
| DELETE | `/api/chat/history` | Clear all histories |

### 📁 Multi-Modal Files (3)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/files/upload?file_type={type}` | Upload multi-modal files |
| GET | `/api/files/list` | List all files by type |
| DELETE | `/api/files/{type}/{filename}` | Delete file |

**Supported Types**: `pdf`, `audio`, `image`, `video`, `text`

### 📄 Document Management (4)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/documents` | List PDF documents |
| POST | `/api/documents/upload` | Upload PDF |
| POST | `/api/documents/process` | Process all PDFs |
| DELETE | `/api/documents/{filename}` | Delete PDF |

### 🔍 Vector Store (2)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/vector-store/reload` | Reload vector store |
| GET | `/api/vector-store/search?query={q}&k={n}` | Vector similarity search |

### ⚙️ Demo Pipeline (6)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/pipeline/run` | Run complete pipeline |
| GET | `/api/pipeline/status` | Get pipeline status |
| GET | `/api/pipeline/logs?lines={n}` | Get pipeline logs |
| GET | `/api/pipeline/logs/stream` | Stream logs (SSE) |
| POST | `/api/pipeline/stop` | Stop pipeline |
| DELETE | `/api/pipeline/clear` | Clear pipeline state |

### ℹ️ System Info (2)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/system/info` | Detailed system info |
| GET | `/api/system/config` | System configuration |

---

## 🔥 Common Usage Patterns

### 1. Upload & Process Documents

```bash
# Upload PDF
curl -X POST "http://localhost:8000/api/documents/upload?auto_process=true" \
  -F "file=@document.pdf"

# Or upload multiple files by type
curl -X POST "http://localhost:8000/api/files/upload?file_type=pdf" \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf"

# Process all PDFs
curl -X POST "http://localhost:8000/api/documents/process"
```

### 2. Chat with Documents

```bash
# Send query
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the main findings?",
    "top_k": 4
  }'
```

### 3. Run Complete Pipeline

```bash
# Start pipeline
curl -X POST "http://localhost:8000/api/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{
    "use_existing_data": true,
    "interactive_mode": false
  }'

# Check status
curl "http://localhost:8000/api/pipeline/status"

# Get logs
curl "http://localhost:8000/api/pipeline/logs?lines=50"
```

### 4. Multi-Modal File Upload

```bash
# Upload audio files
curl -X POST "http://localhost:8000/api/files/upload?file_type=audio" \
  -F "files=@interview.mp3" \
  -F "files=@lecture.wav"

# Upload images
curl -X POST "http://localhost:8000/api/files/upload?file_type=image" \
  -F "files=@diagram.png" \
  -F "files=@chart.jpg"

# List all files
curl "http://localhost:8000/api/files/list"
```

---

## 🐍 Python Client Examples

### Quick Chat

```python
import requests

response = requests.post(
    "http://localhost:8000/api/chat",
    json={"query": "What is this about?", "top_k": 4}
)
print(response.json()['response'])
```

### Upload Multiple Files

```python
import requests

# Upload PDFs
files = [
    ("files", open("doc1.pdf", "rb")),
    ("files", open("doc2.pdf", "rb"))
]
response = requests.post(
    "http://localhost:8000/api/files/upload?file_type=pdf",
    files=files
)
print(response.json())
```

### Monitor Pipeline

```python
import requests
import time

# Start pipeline
config = {"use_existing_data": True}
requests.post("http://localhost:8000/api/pipeline/run", json=config)

# Monitor progress
while True:
    status = requests.get("http://localhost:8000/api/pipeline/status").json()
    print(f"[{status['progress']}%] {status['message']}")
    
    if not status['running']:
        break
    
    time.sleep(2)

print("Results:", status['results'])
```

---

## 📊 File Type Support

### PDF Documents
**Extensions**: `.pdf`  
**Endpoint**: `/api/files/upload?file_type=pdf`  
**Directory**: `data/raw/pdf/`

### Audio Files
**Extensions**: `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`, `.wma`, `.aac`  
**Endpoint**: `/api/files/upload?file_type=audio`  
**Directory**: `data/raw/audio/`

### Image Files
**Extensions**: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tiff`, `.webp`  
**Endpoint**: `/api/files/upload?file_type=image`  
**Directory**: `data/raw/img/`

### Video Files
**Extensions**: `.mp4`, `.avi`, `.mov`, `.mkv`, `.flv`, `.wmv`, `.webm`, `.m4v`  
**Endpoint**: `/api/files/upload?file_type=video`  
**Directory**: `data/raw/video/`

### Text Files
**Extensions**: `.txt`, `.md`, `.csv`, `.json`, `.xml`, `.html`, `.log`, `.yaml`, `.yml`  
**Endpoint**: `/api/files/upload?file_type=text`  
**Directory**: `data/raw/text/`

---

## 🔄 Pipeline Workflow

```
1. Upload Files → /api/files/upload
         ↓
2. Start Pipeline → /api/pipeline/run
         ↓
3. Monitor Progress → /api/pipeline/status
         ↓
4. View Logs → /api/pipeline/logs
         ↓
5. Query Results → /api/chat
```

**Pipeline Stages**:
1. Data Loading (0-30%)
2. Document Parsing (30-40%)
3. Entity Extraction (40-50%)
4. Knowledge Graph Building (50-70%)
5. RAG Indexing (70-85%)
6. Report Generation (85-100%)

---

## ⚡ Response Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request (invalid input) |
| 404 | Not Found |
| 409 | Conflict (pipeline already running) |
| 500 | Internal Server Error |
| 503 | Service Unavailable (chatbot not initialized) |

---

## 🎯 Key Features

✅ **Multi-Modal Support**: PDF, Audio, Image, Video, Text  
✅ **RAG Chatbot**: Context-aware question answering  
✅ **Knowledge Graph**: Neo4j + Fuseki integration  
✅ **Vector Search**: FAISS similarity search  
✅ **Pipeline Execution**: Complete KG construction workflow  
✅ **Real-Time Logs**: SSE streaming for live updates  
✅ **Session Management**: Conversation history tracking  
✅ **Background Processing**: Non-blocking operations  

---

## 📚 Full Documentation

See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for:
- Detailed endpoint descriptions
- Complete request/response schemas
- Code examples (Python, JavaScript, React)
- Error handling
- Production deployment guide

---

## 🆘 Common Issues

### Chatbot Not Initialized
**Error**: `503 Service Unavailable`  
**Solution**: Wait for startup to complete or check logs

### Pipeline Already Running
**Error**: `409 Conflict`  
**Solution**: Check `/api/pipeline/status` or stop current pipeline

### Invalid File Type
**Error**: `400 Bad Request`  
**Solution**: Verify file extension matches expected type

### File Not Found
**Error**: `404 Not Found`  
**Solution**: List files first using `/api/files/list`

---

## 🔧 Environment Variables

```bash
export GROQ_API_KEY="your_api_key"
export API_HOST="0.0.0.0"
export API_PORT="8000"
export LOG_LEVEL="INFO"
```

---

## 📞 Support

- API Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health
