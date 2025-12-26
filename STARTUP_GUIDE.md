# Knowledge Graph RAG - Complete Startup Guide

Quick guide to run both FastAPI backend and React frontend.

## Prerequisites

- Python 3.8+
- Node.js 16+
- Neo4j (optional, for full KG features)
- Fuseki (optional, for SPARQL queries)

## Quick Start (3 Steps)

### 1. Install Dependencies

```bash
# Backend
pip install -r requirements.txt

# Frontend
cd client
npm install
cd ..
```

### 2. Start Backend (Terminal 1)

```bash
uvicorn api:app --reload
```

Backend runs on: **http://localhost:8000**

### 3. Start Frontend (Terminal 2)

```bash
cd client
npm start
```

Frontend opens: **http://localhost:3000**

## Detailed Setup

### Backend Configuration

1. **Environment Variables** (optional):
```bash
export GROQ_API_KEY="your_groq_api_key"
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your_password"
```

2. **Start Services**:
```bash
# Neo4j (if installed)
neo4j start

# Fuseki (if installed)
./fuseki-server --update --mem /ds
```

3. **Start FastAPI**:
```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Configuration

1. **Environment File** (`.env`):
```env
REACT_APP_API_URL=http://localhost:8000
```

2. **Start React**:
```bash
cd client
npm start
```

The app automatically opens at http://localhost:3000.

## API Endpoints Overview

### Health & Status
- `GET /` - API information
- `GET /health` - Health check
- `GET /api/status` - System status

### Chat (RAG)
- `POST /api/chat` - Send chat message
- `GET /api/chat/history/{session_id}` - Get history
- `DELETE /api/chat/history` - Clear all history

### File Management
- `POST /api/files/upload?file_type={pdf|audio|image|video|text}` - Upload files
- `GET /api/files/list` - List uploaded files
- `DELETE /api/files/{type}/{filename}` - Delete file

### Pipeline
- `POST /api/pipeline/run` - Start demo pipeline
- `GET /api/pipeline/status` - Get current status
- `GET /api/pipeline/logs` - Get execution logs
- `POST /api/pipeline/stop` - Stop running pipeline

### Documents & Vector Store
- `POST /api/documents/upload` - Upload PDF
- `POST /api/documents/process` - Process PDFs
- `POST /api/vector-store/reload` - Reload vector store
- `GET /api/vector-store/search` - Vector search

Full API reference: [API_DOCUMENTATION.md](API_DOCUMENTATION.md)

## Testing the System

### 1. Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-01-24T12:00:00"
}
```

### 2. Chat Query

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is knowledge graph?"}'
```

### 3. Upload File

```bash
curl -X POST "http://localhost:8000/api/files/upload?file_type=pdf" \
  -F "files=@document.pdf"
```

### 4. Run Pipeline

```bash
curl -X POST http://localhost:8000/api/pipeline/run
```

## Frontend Features

### Chat Interface
1. Navigate to **Chat** tab
2. Type your question in the input field
3. View AI response and relevant documents
4. Graph updates automatically with extracted entities

### Graph Visualization
1. Navigate to **Graph** tab (or view in Chat tab)
2. Explore entity nodes and relationships
3. Use controls to zoom/pan
4. View minimap for overview

### File Upload
1. Navigate to **Upload** tab
2. Select file type (PDF, audio, image, video, text)
3. Drag & drop files or click to browse
4. Click "Upload Files" to process

### Pipeline Monitor
1. Navigate to **Pipeline** tab (or view in Upload tab)
2. Click "Start Pipeline" to begin processing
3. Monitor progress bar and logs in real-time
4. View results (documents, triples, entities, relations)
5. Click "Stop Pipeline" to halt execution

## Common Issues

### Backend Won't Start

**Issue**: `ModuleNotFoundError: No module named 'chatbot'`

**Solution**:
```bash
pip install -r requirements.txt
```

### Frontend Won't Connect

**Issue**: Network error when calling API

**Solution**:
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check `.env` file: `REACT_APP_API_URL=http://localhost:8000`
3. Restart React dev server: `npm start`

### CORS Errors

**Issue**: `Access-Control-Allow-Origin` error

**Solution**: Add your frontend URL to CORS in `api.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Graph Not Rendering

**Issue**: Graph component blank or not showing

**Solution**:
1. Check browser console for errors
2. Verify React Flow installed: `npm list reactflow`
3. Reinstall dependencies: `cd client && npm install`

## Production Deployment

### Backend (FastAPI)

```bash
# Using Gunicorn
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker api:app --bind 0.0.0.0:8000

# Using Docker
docker build -t kg-rag-backend .
docker run -p 8000:8000 kg-rag-backend
```

### Frontend (React)

```bash
# Build for production
cd client
npm run build

# Serve with static server
npx serve -s build -p 3000

# Or use Nginx
cp -r build/* /var/www/html/
```

## Environment Variables Reference

### Backend (.env or shell)
```bash
GROQ_API_KEY=gsk_...              # Groq API key for LLM
NEO4J_URI=bolt://localhost:7687   # Neo4j connection
NEO4J_USER=neo4j                  # Neo4j username
NEO4J_PASSWORD=password           # Neo4j password
FUSEKI_ENDPOINT=http://localhost:3030/ds  # Fuseki SPARQL endpoint
```

### Frontend (client/.env)
```bash
REACT_APP_API_URL=http://localhost:8000  # Backend API URL
```

## File Structure

```
Knowledge Graph/
├── api.py                    # FastAPI backend
├── chatbot.py                # RAG chatbot logic
├── requirements.txt          # Python dependencies
├── API_DOCUMENTATION.md      # Full API docs
├── API_QUICK_REFERENCE.md    # Quick API reference
├── STARTUP_GUIDE.md          # This file
│
├── client/                   # React frontend
│   ├── public/
│   ├── src/
│   │   ├── components/       # React components
│   │   │   ├── ui/           # shadcn components
│   │   │   ├── ChatInterface.jsx
│   │   │   ├── GraphVisualization.jsx
│   │   │   ├── FileUpload.jsx
│   │   │   └── PipelineMonitor.jsx
│   │   ├── lib/
│   │   │   ├── api.js        # API client
│   │   │   └── utils.js
│   │   ├── App.js            # Main app
│   │   └── index.js
│   ├── .env                  # Environment config
│   ├── package.json
│   └── CLIENT_SETUP.md       # Frontend docs
│
├── core/                     # Core modules
│   ├── chat_processor.py
│   └── graph_manager.py
├── extract/                  # Entity/relation extraction
├── ingest/                   # Document ingestion
├── kg/                       # Knowledge graph clients
├── rag/                      # RAG implementation
└── scripts/
    └── demo_pipeline.py      # Full pipeline script
```

## Next Steps

1. **Explore the UI**: Navigate through all tabs and test features
2. **Upload Documents**: Start with a few PDFs to build your knowledge graph
3. **Run Pipeline**: Execute the full pipeline to process documents
4. **Chat**: Ask questions about your documents
5. **Visualize**: Explore the knowledge graph

## Additional Resources

- **API Documentation**: [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- **API Quick Reference**: [API_QUICK_REFERENCE.md](API_QUICK_REFERENCE.md)
- **Frontend Setup**: [client/CLIENT_SETUP.md](client/CLIENT_SETUP.md)

## Support

For detailed API examples and integration guides, see:
- Full API docs with Python/JavaScript/React examples
- Component usage documentation in frontend README
- Troubleshooting guides in both backend and frontend docs

---

**Happy Knowledge Graphing! 🎉**
