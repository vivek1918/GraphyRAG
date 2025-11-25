# RAG Chatbot with Knowledge Graph Visualization

A Streamlit-based web interface for the RAG chatbot that includes interactive knowledge graph visualization from Neo4j.

## Features

- 💬 **Interactive Chat Interface**: Ask questions about your PDF documents
- 🕸️ **Knowledge Graph Visualization**: Interactive visualization of entities and relationships
- 📊 **Real-time Statistics**: View document counts, node types, and relationship statistics
- 🔄 **Live Updates**: Refresh graph data and reload vector store on demand
- 📚 **Document Management**: View loaded PDF files and system status

## Prerequisites

1. **Neo4j Database** (Optional but recommended for graph visualization)
   - Download from: https://neo4j.com/download/
   - Start Neo4j Desktop or run Neo4j server
   - Default credentials: `neo4j/password`
   - Update credentials in `conf/settings.yaml` if needed

2. **PDF Documents**
   - Place your PDF files in `data/raw/pdf/` directory

3. **Environment Variables**
   - Set `GROQ_API_KEY` in your environment or `.env` file
   - Set `TOKENIZERS_PARALLELISM=false` to suppress warnings

## Installation

Install required packages:

```bash
pip install -r requirements.txt
```

Or install individually:

```bash
pip install streamlit plotly networkx neo4j PyPDF2 faiss-cpu langchain-community langchain-huggingface groq
```

## Quick Start

### 1. Generate Knowledge Graph (Optional)

First, run the demo pipeline to generate the knowledge graph in Neo4j:

```bash
python scripts/demo_pipeline.py
```

This will:
- Process all documents (PDFs, images, audio, video, text)
- Extract entities and relationships
- Load the knowledge graph into Neo4j

### 2. Launch Streamlit App

```bash
streamlit run streamlit_chatbot.py
```

Or with custom port:

```bash
streamlit run streamlit_chatbot.py --server.port 8501
```

The app will automatically:
- Connect to Neo4j (if available)
- Load your PDF documents
- Create/load the vector store for RAG

### 3. Use the Application

The app opens in your browser at: `http://localhost:8501`

**Left Panel - Chat Interface:**
- Type questions about your documents
- Get AI-powered answers based on document content
- View chat history
- Use quick action buttons for examples and system info

**Right Panel - Knowledge Graph:**
- View interactive graph visualization
- See entities (colored by type) and relationships
- Hover over nodes to see details
- Zoom and pan to explore the graph

**Sidebar:**
- System status indicators
- Document statistics
- Refresh graph data
- Reload vector store
- Clear chat history

## Example Questions

Try asking:
- "What is a cognitive distortion?"
- "What are the meditation techniques mentioned?"
- "Summarize the main topics in the documents"
- "What benefits are discussed?"
- "Explain the breathing exercises"

## Configuration

### Neo4j Settings

Edit `conf/settings.yaml`:

```yaml
kg:
  neo4j_url: "bolt://localhost:7687"
  neo4j_user: "neo4j"
  neo4j_password: "your-password"
```

### LLM Model

The chatbot uses Groq's LLM. Model is configured in `conf/settings.yaml`:

```yaml
models:
  llm:
    groq: "llama-3.1-8b-instant"
```

## Troubleshooting

### Chatbot Not Ready

**Issue**: Chatbot shows "Not Ready" status

**Solutions**:
1. Check if PDF files exist in `data/raw/pdf/`
2. Verify `GROQ_API_KEY` is set
3. Check error message in sidebar
4. Try clicking "Reload Vector Store"

### Neo4j Not Connected

**Issue**: Neo4j status shows "Not Connected"

**Solutions**:
1. Start Neo4j server/desktop
2. Verify connection settings in `conf/settings.yaml`
3. Test connection: `bolt://localhost:7687`
4. Check Neo4j credentials

### No Graph Data

**Issue**: Graph shows "No data available"

**Solutions**:
1. Run the demo pipeline first:
   ```bash
   python scripts/demo_pipeline.py
   ```
2. Click "Refresh Graph" button
3. Check Neo4j browser: `http://localhost:7474`

### Import Errors

**Issue**: Module not found errors

**Solutions**:
```bash
pip install --upgrade -r requirements.txt
```

### Tokenizer Warnings

**Issue**: Huggingface tokenizer fork warnings

**Solution**: App automatically sets `TOKENIZERS_PARALLELISM=false`

## Features Breakdown

### Chat Interface
- **Query Processing**: Uses RAG (Retrieval Augmented Generation)
- **Context Search**: FAISS similarity search with embeddings
- **Response Generation**: Groq LLM with context-aware prompts
- **Scope Control**: Answers only based on document content

### Knowledge Graph
- **Node Types**: Activities, Durations, Difficulties, Benefits, Times
- **Relationships**: HAS_DURATION, HAS_DIFFICULTY, PROVIDES_BENEFIT, etc.
- **Visualization**: Interactive Plotly graph with zoom/pan
- **Color Coding**: Different colors for different entity types
- **Size Coding**: Node size based on confidence scores

### Statistics Dashboard
- Total nodes and relationships
- Node type distribution
- Document counts
- Real-time updates

## Architecture

```
streamlit_chatbot.py
├── RAGChatbot (from chatbot.py)
│   ├── PDFProcessor: Text extraction
│   ├── VectorStore: FAISS embeddings
│   └── GroqLLM: Response generation
├── Neo4jConnection
│   ├── get_graph_data(): Fetch nodes/edges
│   └── get_stats(): Count statistics
└── create_knowledge_graph_viz()
    └── Interactive Plotly visualization
```

## Advanced Usage

### Custom Graph Queries

Modify `Neo4jConnection.get_graph_data()` to run custom Cypher queries:

```python
def get_specific_entities(self, entity_type: str):
    query = f"""
    MATCH (n {{type: '{entity_type}'}})
    RETURN n
    """
    # ... execute query
```

### Adding More Visualizations

The Streamlit app can be extended with:
- Document statistics charts
- Entity distribution pie charts
- Relationship type breakdowns
- Confidence score histograms

### Batch Processing

Process multiple PDFs by placing them in `data/raw/pdf/` and clicking "Reload Vector Store"

## Performance

- **Vector Store**: Created once, cached for fast queries
- **Graph Data**: Cached in session state, refreshable on demand
- **Response Time**: 1-3 seconds per query (depends on document size)
- **Graph Rendering**: Optimized with NetworkX layout (limited to 100 nodes)

## Development

### Running in Development Mode

```bash
streamlit run streamlit_chatbot.py --server.runOnSave true
```

### Debugging

Enable debug logging in `utils/logger.py` or check:
- Streamlit logs in terminal
- Neo4j logs in Neo4j Desktop
- Application logs (if configured)

## Security Notes

- ⚠️ Vector store uses `allow_dangerous_deserialization=True` for FAISS
- Only use with trusted data sources
- Keep `GROQ_API_KEY` secure (use `.env` file)
- Don't expose Neo4j password in code

## License

Part of the Knowledge Graph project.

## Support

For issues:
1. Check logs in terminal
2. Verify all prerequisites are met
3. Check Neo4j connection independently
4. Rebuild vector store if needed

## Next Steps

- Add more document types (images, audio, video)
- Implement user authentication
- Add document upload interface
- Export graph visualizations
- Advanced filtering and search
- Multi-language support
