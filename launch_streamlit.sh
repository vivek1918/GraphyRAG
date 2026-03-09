#!/bin/bash
# Launch script for Streamlit RAG Chatbot

# Set environment variable to suppress tokenizer warnings
export TOKENIZERS_PARALLELISM=false

# Check if .env file exists
if [ -f .env ]; then
    echo "✅ Loading environment variables from .env file"
    source .env
else
    echo "⚠️  No .env file found. Make sure GROQ_API_KEY is set in your environment."
fi

# Check if GROQ_API_KEY is set
if [ -z "$GROQ_API_KEY" ]; then
    echo "❌ ERROR: GROQ_API_KEY is not set!"
    echo "Please set it in your .env file or environment:"
    echo "export GROQ_API_KEY='your-api-key-here'"
    exit 1
fi

# Check if PDF files exist
if [ ! -d "data/raw/pdf" ] || [ -z "$(ls -A data/raw/pdf/*.pdf 2>/dev/null)" ]; then
    echo "⚠️  WARNING: No PDF files found in data/raw/pdf/"
    echo "Please add PDF files to data/raw/pdf/ directory"
    echo ""
fi

# Check if Neo4j is running (optional)
echo "🔍 Checking Neo4j connection..."
if command -v cypher-shell &> /dev/null; then
    if cypher-shell -u neo4j -p password "RETURN 1" &> /dev/null; then
        echo "✅ Neo4j is running"
    else
        echo "⚠️  Neo4j not accessible (optional for basic chat)"
    fi
else
    echo "ℹ️  cypher-shell not found (Neo4j connection will be checked by app)"
fi

# Launch Streamlit
echo ""
echo "🚀 Launching Streamlit RAG Chatbot..."
echo "📍 URL: http://localhost:8501"
echo "Press Ctrl+C to stop"
echo ""

streamlit run streamlit_chatbot.py --server.port 8501 --server.headless true
