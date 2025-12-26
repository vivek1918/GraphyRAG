#!/usr/bin/env python3
"""
FastAPI Backend for RAG Chatbot
Provides REST API endpoints for document processing and question answering
"""

import os
import sys
import uuid
import asyncio
import io
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from contextlib import redirect_stdout, redirect_stderr
import threading
import queue

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import shutil

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from chatbot import RAGChatbot
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Knowledge Graph RAG API",
    description="Multi-modal Knowledge Graph construction and RAG retrieval system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this based on your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global chatbot instance
chatbot_instance = None
chat_sessions = {}  # Store chat history per session

# Pipeline state tracking
pipeline_status = {
    "running": False,
    "status": "idle",
    "progress": 0,
    "message": "No pipeline running",
    "logs": [],
    "start_time": None,
    "end_time": None,
    "results": None
}
pipeline_log_queue = queue.Queue()


# ============================================================================
# Pydantic Models (Request/Response Schemas)
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for chat queries"""
    query: str = Field(..., description="User's question or query")
    session_id: Optional[str] = Field(None, description="Chat session ID for maintaining conversation history")
    top_k: int = Field(4, ge=1, le=10, description="Number of relevant documents to retrieve")


class QueryResponse(BaseModel):
    """Response model for chat queries"""
    response: str = Field(..., description="AI-generated response")
    session_id: str = Field(..., description="Chat session ID")
    relevant_documents: List[str] = Field(default_factory=list, description="Relevant document chunks used for context")
    timestamp: str = Field(..., description="Response timestamp")


class ChatMessage(BaseModel):
    """Chat message model"""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: str = Field(..., description="Message timestamp")


class ChatHistory(BaseModel):
    """Chat history model"""
    session_id: str
    messages: List[ChatMessage]


class SystemStatus(BaseModel):
    """System status model"""
    status: str = Field(..., description="System status: 'ready', 'initializing', 'error'")
    message: str = Field(..., description="Status message")
    pdf_count: int = Field(0, description="Number of PDF files loaded")
    pdf_files: List[str] = Field(default_factory=list, description="List of loaded PDF files")
    vector_store_loaded: bool = Field(False, description="Whether vector store is loaded")


class DocumentInfo(BaseModel):
    """Document information model"""
    filename: str
    path: str
    size_bytes: Optional[int] = None
    uploaded_at: Optional[str] = None


class UploadResponse(BaseModel):
    """Document upload response"""
    success: bool
    message: str
    filename: str
    document_id: Optional[str] = None


class ProcessingStatus(BaseModel):
    """Document processing status"""
    status: str = Field(..., description="Processing status: 'pending', 'processing', 'completed', 'failed'")
    message: str
    documents_processed: int = 0
    total_chunks: int = 0


class PipelineConfig(BaseModel):
    """Pipeline configuration model"""
    use_existing_data: bool = Field(True, description="Use existing data or generate synthetic")
    interactive_mode: bool = Field(False, description="Run in interactive mode for queries")
    data_directory: Optional[str] = Field(None, description="Custom data directory path")


class PipelineStatus(BaseModel):
    """Pipeline execution status"""
    running: bool = Field(..., description="Whether pipeline is currently running")
    status: str = Field(..., description="Pipeline status: 'idle', 'initializing', 'processing', 'completed', 'failed'")
    progress: int = Field(0, ge=0, le=100, description="Progress percentage")
    message: str = Field(..., description="Current status message")
    logs: List[str] = Field(default_factory=list, description="Pipeline execution logs")
    start_time: Optional[str] = Field(None, description="Pipeline start time")
    end_time: Optional[str] = Field(None, description="Pipeline end time")
    results: Optional[Dict[str, Any]] = Field(None, description="Pipeline results")


class FileUploadRequest(BaseModel):
    """Multi-modal file upload information"""
    filename: str
    file_type: str = Field(..., description="File type: 'pdf', 'audio', 'image', 'video', 'text'")
    size_bytes: int


class MultiModalUploadResponse(BaseModel):
    """Multi-modal upload response"""
    success: bool
    message: str
    uploaded_files: List[FileUploadRequest]
    failed_files: List[Dict[str, str]] = Field(default_factory=list)


class GraphNode(BaseModel):
    """Graph node model"""
    id: str = Field(..., description="Node ID")
    label: str = Field(..., description="Node label/name")
    type: str = Field(..., description="Node type/category")


class GraphRelation(BaseModel):
    """Graph relation model"""
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    type: str = Field(..., description="Relation type")


class GraphDataResponse(BaseModel):
    """Graph data response model"""
    entities: List[GraphNode] = Field(default_factory=list, description="List of graph nodes")
    relations: List[GraphRelation] = Field(default_factory=list, description="List of graph relations")
    node_count: int = Field(0, description="Total number of nodes")
    relation_count: int = Field(0, description="Total number of relations")


# ============================================================================
# Helper Functions
# ============================================================================

class LogCapture:
    """Capture logs from loguru and standard output"""
    def __init__(self):
        self.logs = []
        self.buffer = io.StringIO()
    
    def write(self, message):
        if message.strip():
            self.logs.append(message.strip())
            pipeline_log_queue.put(message.strip())
    
    def flush(self):
        pass
    
    def get_logs(self):
        return self.logs


async def run_demo_pipeline_task(config: PipelineConfig):
    """Run demo pipeline in background with log capture"""
    global pipeline_status
    
    try:
        # Update status
        pipeline_status["running"] = True
        pipeline_status["status"] = "initializing"
        pipeline_status["progress"] = 0
        pipeline_status["message"] = "Initializing pipeline..."
        pipeline_status["logs"] = []
        pipeline_status["start_time"] = datetime.utcnow().isoformat()
        pipeline_status["end_time"] = None
        pipeline_status["results"] = None
        
        # Import demo pipeline
        from scripts.demo_pipeline import DemoPipeline
        
        # Create log capture
        log_capture = LogCapture()
        
        # Configure loguru to capture logs
        from loguru import logger as demo_logger
        demo_logger.add(log_capture, format="{time:HH:mm:ss} | {level} | {message}")
        
        pipeline_status["status"] = "processing"
        pipeline_status["progress"] = 10
        pipeline_status["message"] = "Starting demo pipeline..."
        
        # Initialize pipeline
        data_dir = Path(config.data_directory) if config.data_directory else Path("data")
        pipeline = DemoPipeline(
            data_dir=data_dir,
            use_existing_data=config.use_existing_data
        )
        
        pipeline_status["progress"] = 20
        pipeline_status["message"] = "Pipeline initialized, starting execution..."
        
        # Run pipeline (capture stdout/stderr)
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        
        try:
            sys.stdout = log_capture
            sys.stderr = log_capture
            
            # Execute pipeline stages
            pipeline_status["progress"] = 30
            pipeline_status["message"] = "Generating/loading data..."
            datasets = await pipeline.generate_data()
            
            pipeline_status["progress"] = 40
            pipeline_status["message"] = "Parsing documents..."
            parsed_docs = await pipeline.parse_documents(datasets)
            
            pipeline_status["progress"] = 50
            pipeline_status["message"] = "Extracting entities and relations..."
            enriched_docs = await pipeline.extract_entities_relations(parsed_docs)
            
            pipeline_status["progress"] = 70
            pipeline_status["message"] = "Building knowledge graph..."
            kg_stats = await pipeline.build_knowledge_graph(enriched_docs)
            
            pipeline_status["progress"] = 85
            pipeline_status["message"] = "Building RAG index..."
            await pipeline.build_rag_index(enriched_docs)
            
            pipeline_status["progress"] = 95
            pipeline_status["message"] = "Generating report..."
            await pipeline.generate_report(kg_stats)
            
            pipeline_status["progress"] = 100
            pipeline_status["status"] = "completed"
            pipeline_status["message"] = "Pipeline completed successfully!"
            pipeline_status["results"] = {
                "kg_stats": kg_stats,
                "documents_processed": len(enriched_docs),
                "datasets": {k: len(v) for k, v in datasets.items()}
            }
            
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        
        # Store logs
        pipeline_status["logs"] = log_capture.get_logs()
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        pipeline_status["status"] = "failed"
        pipeline_status["message"] = f"Pipeline failed: {str(e)}"
        pipeline_status["logs"].append(f"ERROR: {str(e)}")
    
    finally:
        pipeline_status["running"] = False
        pipeline_status["end_time"] = datetime.utcnow().isoformat()


# ============================================================================
# Startup and Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize chatbot on startup"""
    global chatbot_instance
    try:
        logger.info("Initializing RAG Chatbot...")
        
        # Create necessary directories
        os.makedirs("data/raw/pdf", exist_ok=True)
        os.makedirs("data/vector_store", exist_ok=True)
        
        chatbot_instance = RAGChatbot()
        logger.info("RAG Chatbot initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize chatbot: {e}")
        chatbot_instance = None


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down API server...")


# ============================================================================
# Health and Status Endpoints
# ============================================================================

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API information"""
    return {
        "name": "Knowledge Graph RAG API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "status": "/api/status"
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "chatbot_ready": chatbot_instance is not None
    }


@app.get("/api/status", response_model=SystemStatus, tags=["System"])
async def get_system_status():
    """Get system status and information"""
    if chatbot_instance is None:
        return SystemStatus(
            status="error",
            message="Chatbot not initialized",
            pdf_count=0,
            pdf_files=[],
            vector_store_loaded=False
        )
    
    try:
        pdf_files = chatbot_instance.pdf_processor.load_pdfs()
        pdf_names = [os.path.basename(pdf) for pdf in pdf_files]
        
        return SystemStatus(
            status="ready",
            message="System operational",
            pdf_count=len(pdf_files),
            pdf_files=pdf_names,
            vector_store_loaded=chatbot_instance.vector_store.vector_store is not None
        )
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return SystemStatus(
            status="error",
            message=str(e),
            pdf_count=0,
            pdf_files=[],
            vector_store_loaded=False
        )


# ============================================================================
# Chat and Query Endpoints
# ============================================================================

@app.post("/api/chat", response_model=QueryResponse, tags=["Chat"])
async def chat(request: QueryRequest):
    """
    Process a chat query and return AI-generated response
    
    This endpoint performs RAG (Retrieval-Augmented Generation):
    1. Searches for relevant document chunks using vector similarity
    2. Uses retrieved context to generate accurate responses
    3. Maintains conversation history per session
    """
    if chatbot_instance is None:
        raise HTTPException(status_code=503, detail="Chatbot not initialized")
    
    try:
        # Generate or use existing session ID
        session_id = request.session_id or str(uuid.uuid4())
        
        # Initialize session if new
        if session_id not in chat_sessions:
            chat_sessions[session_id] = []
        
        # Get relevant documents
        relevant_docs = chatbot_instance.vector_store.similarity_search(
            request.query, 
            k=request.top_k
        )
        
        # Process query
        response = chatbot_instance.process_query(request.query)
        
        # Store in chat history
        timestamp = datetime.utcnow().isoformat()
        chat_sessions[session_id].extend([
            {"role": "user", "content": request.query, "timestamp": timestamp},
            {"role": "assistant", "content": response, "timestamp": timestamp}
        ])
        
        return QueryResponse(
            response=response,
            session_id=session_id,
            relevant_documents=relevant_docs,
            timestamp=timestamp
        )
        
    except Exception as e:
        logger.error(f"Error processing chat query: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.get("/api/chat/history/{session_id}", response_model=ChatHistory, tags=["Chat"])
async def get_chat_history(session_id: str):
    """Get chat history for a specific session"""
    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return ChatHistory(
        session_id=session_id,
        messages=[
            ChatMessage(**msg) for msg in chat_sessions[session_id]
        ]
    )


@app.delete("/api/chat/history/{session_id}", tags=["Chat"])
async def clear_chat_history(session_id: str):
    """Clear chat history for a specific session"""
    if session_id in chat_sessions:
        del chat_sessions[session_id]
        return {"message": f"Chat history cleared for session {session_id}"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@app.delete("/api/chat/history", tags=["Chat"])
async def clear_all_chat_history():
    """Clear all chat histories"""
    chat_sessions.clear()
    return {"message": "All chat histories cleared"}


# ============================================================================
# Multi-Modal File Upload Endpoints
# ============================================================================

@app.post("/api/files/upload", response_model=MultiModalUploadResponse, tags=["Files"])
async def upload_multimodal_files(
    files: List[UploadFile] = File(...),
    file_type: str = Query(..., description="File type: 'pdf', 'audio', 'image', 'video', 'text'")
):
    """
    Upload multiple files for any modality (PDF, audio, image, video, text)
    
    - **files**: List of files to upload
    - **file_type**: Target modality type
    
    Supported file types:
    - pdf: .pdf
    - audio: .mp3, .wav, .m4a, .flac, .ogg, .wma, .aac
    - image: .jpg, .jpeg, .png, .gif, .bmp, .tiff, .webp
    - video: .mp4, .avi, .mov, .mkv, .flv, .wmv, .webm, .m4v
    - text: .txt, .md, .csv, .json, .xml, .html, .log, .yaml, .yml
    """
    
    # Define file type extensions
    valid_extensions = {
        'pdf': ['.pdf'],
        'audio': ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.wma', '.aac'],
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'],
        'video': ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v'],
        'text': ['.txt', '.md', '.csv', '.json', '.xml', '.html', '.log', '.yaml', '.yml']
    }
    
    if file_type not in valid_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file_type. Must be one of: {', '.join(valid_extensions.keys())}"
        )
    
    # Determine target directory
    directory_map = {
        'pdf': 'data/raw/pdf',
        'audio': 'data/raw/audio',
        'image': 'data/raw/img',
        'video': 'data/raw/video',
        'text': 'data/raw/text'
    }
    
    target_dir = directory_map[file_type]
    os.makedirs(target_dir, exist_ok=True)
    
    uploaded_files = []
    failed_files = []
    
    for file in files:
        try:
            # Validate file extension
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in valid_extensions[file_type]:
                failed_files.append({
                    "filename": file.filename,
                    "error": f"Invalid extension '{file_ext}' for type '{file_type}'. Expected: {', '.join(valid_extensions[file_type])}"
                })
                continue
            
            # Save file
            file_path = os.path.join(target_dir, file.filename)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            uploaded_files.append(FileUploadRequest(
                filename=file.filename,
                file_type=file_type,
                size_bytes=file_size
            ))
            
            logger.info(f"Uploaded {file_type} file: {file.filename} ({file_size} bytes)")
            
        except Exception as e:
            logger.error(f"Failed to upload {file.filename}: {e}")
            failed_files.append({
                "filename": file.filename,
                "error": str(e)
            })
    
    success = len(uploaded_files) > 0
    message = f"Uploaded {len(uploaded_files)} file(s)"
    if failed_files:
        message += f", {len(failed_files)} failed"
    
    return MultiModalUploadResponse(
        success=success,
        message=message,
        uploaded_files=uploaded_files,
        failed_files=failed_files
    )


@app.get("/api/files/list", tags=["Files"])
async def list_all_files():
    """
    List all files across all modalities
    """
    directory_map = {
        'pdf': 'data/raw/pdf',
        'audio': 'data/raw/audio',
        'image': 'data/raw/img',
        'video': 'data/raw/video',
        'text': 'data/raw/text'
    }
    
    all_files = {}
    
    for file_type, directory in directory_map.items():
        if not os.path.exists(directory):
            all_files[file_type] = []
            continue
        
        files = []
        for file_path in Path(directory).iterdir():
            if file_path.is_file():
                stat = os.stat(file_path)
                files.append({
                    "filename": file_path.name,
                    "path": str(file_path),
                    "size_bytes": stat.st_size,
                    "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        all_files[file_type] = files
    
    total_count = sum(len(files) for files in all_files.values())
    
    return {
        "total_files": total_count,
        "files_by_type": all_files
    }


@app.delete("/api/files/{file_type}/{filename}", tags=["Files"])
async def delete_file(file_type: str, filename: str):
    """
    Delete a file from any modality
    """
    directory_map = {
        'pdf': 'data/raw/pdf',
        'audio': 'data/raw/audio',
        'image': 'data/raw/img',
        'video': 'data/raw/video',
        'text': 'data/raw/text'
    }
    
    if file_type not in directory_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file_type. Must be one of: {', '.join(directory_map.keys())}"
        )
    
    target_dir = directory_map[file_type]
    file_path = os.path.join(target_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Security check
    if not os.path.abspath(file_path).startswith(os.path.abspath(target_dir)):
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    try:
        os.remove(file_path)
        logger.info(f"Deleted {file_type} file: {filename}")
        return {
            "success": True,
            "message": f"File '{filename}' deleted successfully"
        }
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Document Management Endpoints
# ============================================================================

@app.get("/api/documents", response_model=List[DocumentInfo], tags=["Documents"])
async def list_documents():
    """List all loaded PDF documents"""
    if chatbot_instance is None:
        raise HTTPException(status_code=503, detail="Chatbot not initialized")
    
    try:
        pdf_files = chatbot_instance.pdf_processor.load_pdfs()
        documents = []
        
        for pdf_path in pdf_files:
            stat = os.stat(pdf_path)
            documents.append(DocumentInfo(
                filename=os.path.basename(pdf_path),
                path=pdf_path,
                size_bytes=stat.st_size,
                uploaded_at=datetime.fromtimestamp(stat.st_mtime).isoformat()
            ))
        
        return documents
        
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/upload", response_model=UploadResponse, tags=["Documents"])
async def upload_document(
    file: UploadFile = File(...),
    auto_process: bool = Query(False, description="Automatically process and index the document")
):
    """
    Upload a PDF document
    
    - **file**: PDF file to upload
    - **auto_process**: If True, automatically processes and indexes the document
    """
    if chatbot_instance is None:
        raise HTTPException(status_code=503, detail="Chatbot not initialized")
    
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Save file to PDF directory
        pdf_directory = "data/raw/pdf"
        os.makedirs(pdf_directory, exist_ok=True)
        
        file_path = os.path.join(pdf_directory, file.filename)
        
        # Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Document uploaded: {file.filename}")
        
        # Auto-process if requested
        if auto_process:
            # This will be handled by the process endpoint
            return UploadResponse(
                success=True,
                message=f"Document uploaded and queued for processing",
                filename=file.filename,
                document_id=str(uuid.uuid4())
            )
        
        return UploadResponse(
            success=True,
            message=f"Document uploaded successfully. Use /api/documents/process to index it.",
            filename=file.filename,
            document_id=str(uuid.uuid4())
        )
        
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/process", response_model=ProcessingStatus, tags=["Documents"])
async def process_documents(background_tasks: BackgroundTasks):
    """
    Process all PDF documents and rebuild vector store
    
    This operation:
    1. Extracts text from all PDFs in the data/raw/pdf directory
    2. Chunks the text into manageable pieces
    3. Creates embeddings and updates the vector store
    4. Makes documents available for querying
    
    Note: This is a resource-intensive operation
    """
    if chatbot_instance is None:
        raise HTTPException(status_code=503, detail="Chatbot not initialized")
    
    try:
        # Process in background
        def process_task():
            try:
                chatbot_instance.process_pdfs()
                logger.info("Document processing completed")
            except Exception as e:
                logger.error(f"Error in background processing: {e}")
        
        background_tasks.add_task(process_task)
        
        return ProcessingStatus(
            status="processing",
            message="Document processing started in background",
            documents_processed=0,
            total_chunks=0
        )
        
    except Exception as e:
        logger.error(f"Error starting document processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/documents/{filename}", tags=["Documents"])
async def delete_document(filename: str):
    """Delete a specific PDF document"""
    if chatbot_instance is None:
        raise HTTPException(status_code=503, detail="Chatbot not initialized")
    
    try:
        pdf_directory = "data/raw/pdf"
        file_path = os.path.join(pdf_directory, filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Security check - ensure file is in the correct directory
        if not os.path.abspath(file_path).startswith(os.path.abspath(pdf_directory)):
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        os.remove(file_path)
        logger.info(f"Document deleted: {filename}")
        
        return {
            "success": True,
            "message": f"Document '{filename}' deleted. Run /api/documents/process to update vector store."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Vector Store Endpoints
# ============================================================================

@app.post("/api/vector-store/reload", tags=["Vector Store"])
async def reload_vector_store():
    """Reload the vector store from disk"""
    if chatbot_instance is None:
        raise HTTPException(status_code=503, detail="Chatbot not initialized")
    
    try:
        chatbot_instance.vector_store.load_vector_store()
        return {
            "success": True,
            "message": "Vector store reloaded successfully"
        }
    except Exception as e:
        logger.error(f"Error reloading vector store: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/vector-store/search", tags=["Vector Store"])
async def vector_search(
    query: str = Query(..., description="Search query"),
    k: int = Query(4, ge=1, le=20, description="Number of results to return")
):
    """
    Perform vector similarity search
    
    Returns the most similar document chunks without LLM processing
    """
    if chatbot_instance is None:
        raise HTTPException(status_code=503, detail="Chatbot not initialized")
    
    try:
        results = chatbot_instance.vector_store.similarity_search(query, k=k)
        
        return {
            "query": query,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Error performing vector search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Knowledge Graph Endpoints
# ============================================================================

@app.get("/api/graph/data", response_model=GraphDataResponse, tags=["Knowledge Graph"])
async def get_graph_data(
    limit: int = Query(300, ge=1, le=1000, description="Maximum number of nodes to return")
):
    """
    Get nodes and relations from Neo4j knowledge graph
    
    Returns entities (nodes) and their relationships for visualization.
    Limited to specified number of nodes for performance.
    """
    try:
        from kg.neo4j_client import Neo4jClient
        
        # Initialize Neo4j client
        neo4j_client = Neo4jClient()
        
        if not neo4j_client.driver:
            logger.warning("Neo4j driver not available")
            return GraphDataResponse(
                entities=[],
                relations=[],
                node_count=0,
                relation_count=0
            )
        
        # First, check if there are any nodes at all
        count_query = "MATCH (n) RETURN count(n) as total"
        count_result = await neo4j_client.run_query(count_query)
        total_nodes = count_result[0].get('total', 0) if count_result else 0
        
        logger.info(f"Total nodes in Neo4j database: {total_nodes}")
        
        if total_nodes == 0:
            logger.warning("Neo4j database is empty. No nodes found.")
            neo4j_client.close()
            return GraphDataResponse(
                entities=[],
                relations=[],
                node_count=0,
                relation_count=0
            )
        
        # Query for nodes with flexible property handling
        node_query = f"""
        MATCH (n)
        WITH n, labels(n)[0] as label, 
             COALESCE(n.id, n.name, n.title, n.text, toString(id(n))) as node_id,
             COALESCE(n.name, n.title, n.text, n.label, labels(n)[0]) as node_name
        RETURN node_id, node_name, label
        LIMIT {limit}
        """
        
        nodes_result = await neo4j_client.run_query(node_query)
        logger.info(f"Query returned {len(nodes_result)} nodes")
        
        entities = []
        node_ids = set()
        
        for idx, record in enumerate(nodes_result):
            node_id = record.get('node_id')
            node_name = record.get('node_name', 'Unknown')
            node_type = record.get('label', 'Entity')
            
            # Ensure we have a valid ID
            if node_id is None:
                node_id = f"node-{idx}"
            else:
                node_id = str(node_id)
            
            # Ensure we have a valid name
            if not node_name or node_name == 'Unknown':
                node_name = f"{node_type}-{idx}"
            
            entities.append(GraphNode(
                id=node_id,
                label=str(node_name),
                type=str(node_type)
            ))
            node_ids.add(node_id)
            
            logger.debug(f"Added node: id={node_id}, label={node_name}, type={node_type}")
        
        logger.info(f"Processed {len(entities)} entities")
        
        # Query for relationships between the retrieved nodes
        relation_query = f"""
        MATCH (n)
        WITH n, COALESCE(n.id, n.name, n.title, n.text, toString(id(n))) as node_id
        WHERE node_id IN $node_ids
        WITH collect(n) as nodes
        UNWIND nodes as source
        MATCH (source)-[r]->(target)
        WHERE target IN nodes
        WITH source, r, target,
             COALESCE(source.id, source.name, source.title, source.text, toString(id(source))) as source_id,
             COALESCE(target.id, target.name, target.title, target.text, toString(id(target))) as target_id
        RETURN toString(source_id) as source, toString(target_id) as target, type(r) as type
        LIMIT 1000
        """
        
        relations_result = await neo4j_client.run_query(
            relation_query, 
            node_ids=list(node_ids)
        )
        
        logger.info(f"Relationship query returned {len(relations_result)} relations")
        
        relations = []
        for record in relations_result:
            source_id = str(record.get('source', ''))
            target_id = str(record.get('target', ''))
            rel_type = record.get('type', 'RELATED_TO')
            
            if source_id and target_id and source_id in node_ids and target_id in node_ids:
                relations.append(GraphRelation(
                    source=source_id,
                    target=target_id,
                    type=str(rel_type)
                ))
                logger.debug(f"Added relation: {source_id} -> {target_id} ({rel_type})")
        
        neo4j_client.close()
        
        logger.info(f"Returning {len(entities)} nodes and {len(relations)} relations")
        
        return GraphDataResponse(
            entities=entities,
            relations=relations,
            node_count=len(entities),
            relation_count=len(relations)
        )
        
    except ImportError as ie:
        logger.error(f"Neo4j client import error: {ie}")
        raise HTTPException(
            status_code=503, 
            detail="Neo4j client not available. Ensure Neo4j is configured."
        )
    except Exception as e:
        logger.error(f"Error fetching graph data from Neo4j: {e}", exc_info=True)
        # Return empty graph data instead of error for better UX
        return GraphDataResponse(
            entities=[],
            relations=[],
            node_count=0,
            relation_count=0
        )


# ============================================================================
# System Information Endpoints
# ============================================================================

@app.get("/api/system/info", tags=["System"])
async def get_system_info():
    """Get detailed system information"""
    if chatbot_instance is None:
        raise HTTPException(status_code=503, detail="Chatbot not initialized")
    
    try:
        info = chatbot_instance.get_system_info()
        
        return {
            "info": info,
            "active_sessions": len(chat_sessions),
            "model": "Groq Llama 3.1 8B Instant",
            "vector_db": "FAISS",
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
        }
        
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system/config", tags=["System"])
async def get_system_config():
    """Get system configuration"""
    if chatbot_instance is None:
        raise HTTPException(status_code=503, detail="Chatbot not initialized")
    
    try:
        return {
            "pdf_directory": chatbot_instance.pdf_processor.pdf_directory,
            "vector_store_path": chatbot_instance.vector_store.index_path,
            "model_name": chatbot_instance.llm.model_name,
            "chunk_size": 1000,
            "chunk_overlap": 200
        }
        
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Demo Pipeline Endpoints
# ============================================================================

@app.post("/api/pipeline/run", response_model=PipelineStatus, tags=["Pipeline"])
async def run_pipeline(
    config: PipelineConfig,
    background_tasks: BackgroundTasks
):
    """
    Run the complete demo pipeline
    
    This executes the full knowledge graph construction pipeline:
    1. Load/generate multi-modal data (PDF, audio, video, image, text)
    2. Parse documents and extract text
    3. Extract entities and relations
    4. Build knowledge graph (Neo4j + Fuseki)
    5. Create RAG index with FAISS
    6. Generate comprehensive report
    
    **Note**: This is a long-running operation. Use /api/pipeline/status to monitor progress.
    """
    global pipeline_status
    
    if pipeline_status["running"]:
        raise HTTPException(
            status_code=409,
            detail="Pipeline is already running. Check /api/pipeline/status for progress."
        )
    
    # Start pipeline in background
    background_tasks.add_task(run_demo_pipeline_task, config)
    
    return PipelineStatus(**pipeline_status)


@app.get("/api/pipeline/status", response_model=PipelineStatus, tags=["Pipeline"])
async def get_pipeline_status():
    """
    Get current pipeline execution status
    
    Returns:
    - running: Whether pipeline is executing
    - status: Current status (idle, initializing, processing, completed, failed)
    - progress: Completion percentage (0-100)
    - message: Current operation message
    - logs: Captured execution logs
    - start_time: When pipeline started
    - end_time: When pipeline finished (if completed)
    - results: Pipeline results (if completed)
    """
    # Get any new logs from queue
    while not pipeline_log_queue.empty():
        try:
            log = pipeline_log_queue.get_nowait()
            if log not in pipeline_status["logs"]:
                pipeline_status["logs"].append(log)
        except queue.Empty:
            break
    
    return PipelineStatus(**pipeline_status)


@app.get("/api/pipeline/logs", tags=["Pipeline"])
async def get_pipeline_logs(
    lines: int = Query(100, ge=1, le=10000, description="Number of recent log lines to return")
):
    """
    Get pipeline execution logs
    
    Returns the most recent log lines from pipeline execution.
    """
    logs = pipeline_status.get("logs", [])
    recent_logs = logs[-lines:] if len(logs) > lines else logs
    
    return {
        "total_logs": len(logs),
        "returned_logs": len(recent_logs),
        "logs": recent_logs
    }


@app.get("/api/pipeline/logs/stream", tags=["Pipeline"])
async def stream_pipeline_logs():
    """
    Stream pipeline logs in real-time (Server-Sent Events)
    
    Use this endpoint to receive live log updates while pipeline is running.
    """
    async def event_generator():
        last_log_count = 0
        
        while True:
            # Check for new logs
            current_logs = pipeline_status.get("logs", [])
            
            if len(current_logs) > last_log_count:
                # Send new logs
                for log in current_logs[last_log_count:]:
                    yield f"data: {log}\n\n"
                last_log_count = len(current_logs)
            
            # Send status update
            if pipeline_status["running"]:
                status_msg = f"[{pipeline_status['progress']}%] {pipeline_status['message']}"
                yield f"data: {status_msg}\n\n"
            
            # Break if pipeline finished
            if not pipeline_status["running"] and pipeline_status["status"] in ["completed", "failed"]:
                yield f"data: Pipeline finished with status: {pipeline_status['status']}\n\n"
                break
            
            await asyncio.sleep(1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@app.post("/api/pipeline/stop", tags=["Pipeline"])
async def stop_pipeline():
    """
    Stop the currently running pipeline
    
    Note: This is a graceful stop request. The pipeline may take time to terminate.
    """
    global pipeline_status
    
    if not pipeline_status["running"]:
        raise HTTPException(status_code=400, detail="No pipeline is currently running")
    
    # Set status to indicate stop requested
    pipeline_status["status"] = "stopping"
    pipeline_status["message"] = "Stop requested, terminating pipeline..."
    
    return {
        "message": "Pipeline stop requested",
        "status": pipeline_status["status"]
    }


@app.delete("/api/pipeline/clear", tags=["Pipeline"])
async def clear_pipeline_state():
    """
    Clear pipeline state and logs
    
    Resets pipeline status to idle state. Only works when pipeline is not running.
    """
    global pipeline_status
    
    if pipeline_status["running"]:
        raise HTTPException(
            status_code=409,
            detail="Cannot clear state while pipeline is running"
        )
    
    # Reset pipeline status
    pipeline_status["status"] = "idle"
    pipeline_status["progress"] = 0
    pipeline_status["message"] = "No pipeline running"
    pipeline_status["logs"] = []
    pipeline_status["start_time"] = None
    pipeline_status["end_time"] = None
    pipeline_status["results"] = None
    
    # Clear log queue
    while not pipeline_log_queue.empty():
        try:
            pipeline_log_queue.get_nowait()
        except queue.Empty:
            break
    
    return {
        "message": "Pipeline state cleared successfully"
    }


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Set environment variable to suppress tokenizer warnings
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    
    # Run server
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
