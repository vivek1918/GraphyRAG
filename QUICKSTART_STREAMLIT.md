# Quick Start Guide - Streamlit RAG Chatbot

## 🚀 Fastest Way to Get Started

### Step 1: Set Up Environment

```bash
# Set your Groq API key
export GROQ_API_KEY="your-groq-api-key-here"

# Or create a .env file:
echo "GROQ_API_KEY=your-groq-api-key-here" > .env
```

### Step 2: Launch the App

**Option A - Using the launch script (recommended):**
```bash
./launch_streamlit.sh
```

**Option B - Direct command:**
```bash
export TOKENIZERS_PARALLELISM=false
streamlit run streamlit_chatbot.py
```

### Step 3: Access the App

Open your browser to: **http://localhost:8501**

That's it! 🎉

---

## 📊 Optional: Generate Knowledge Graph

To see the graph visualization, run the demo pipeline first:

```bash
# Make sure Neo4j is running
python scripts/demo_pipeline.py
```

Then refresh the graph in the Streamlit app or restart it.

---

## 💬 Try These Questions

Once the app is running, try:
- "What is a cognitive distortion?"
- "What are the meditation techniques?"
- "Summarize the documents"
- "What benefits are mentioned?"

---

## 🔧 Troubleshooting

### Problem: "Chatbot Not Ready"
**Solution:** 
1. Make sure PDF files are in `data/raw/pdf/`
2. Check that GROQ_API_KEY is set
3. Click "Reload Vector Store" button

### Problem: "Neo4j Not Connected"
**Solution:**
1. This is OK for basic chat functionality
2. To see graphs: Start Neo4j and run `python scripts/demo_pipeline.py`

### Problem: Import errors
**Solution:**
```bash
pip install streamlit plotly networkx neo4j
```

---

## 📁 Project Structure

```
.
├── streamlit_chatbot.py     # Main Streamlit app
├── chatbot.py                # RAG chatbot backend
├── launch_streamlit.sh       # Easy launch script
├── data/
│   ├── raw/pdf/             # Put your PDFs here
│   └── vector_store/        # Auto-generated
└── conf/
    └── settings.yaml         # Configuration
```

---

## 🎯 Features at a Glance

✅ **Chat Interface** - Ask questions about your documents  
✅ **Knowledge Graph** - Visualize entities and relationships  
✅ **Statistics** - View document and graph metrics  
✅ **Live Updates** - Refresh graph and reload documents  
✅ **Clean UI** - Modern, responsive design  

---

## 📞 Need Help?

1. Check STREAMLIT_README.md for detailed documentation
2. Verify all prerequisites are installed
3. Check logs in the terminal for errors

---

**Enjoy your RAG Chatbot! 🤖**
