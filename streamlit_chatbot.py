#!/usr/bin/env python3
"""
Streamlit-based RAG Chatbot
"""

import os
import sys
from pathlib import Path
import streamlit as st

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from chatbot import RAGChatbot
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Page configuration
st.set_page_config(
    page_title="Chatbot",
    page_icon="",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .stChatMessage {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 10px;
        margin: 5px 0;
    }
    .stChatMessage p {
        color: #000000 !important;
        font-size: 1rem;
    }
    [data-testid="stChatMessageContent"] {
        color: #000000 !important;
    }
    [data-testid="stMarkdownContainer"] p {
        color: #000000 !important;
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """Initialize Streamlit session state"""
    if 'chatbot' not in st.session_state:
        try:
            st.session_state.chatbot = RAGChatbot()
            st.session_state.chatbot_ready = True
        except Exception as e:
            st.session_state.chatbot = None
            st.session_state.chatbot_ready = False
            st.session_state.error = str(e)
    
    if 'messages' not in st.session_state:
        st.session_state.messages = []

def main():
    """Main Streamlit app"""
    
    # Initialize session state
    initialize_session_state()
    
    # Header
    st.markdown('<div class="main-header">🤖 Graph Mind Chatbot</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("📊 System Status")
        
        # Check if chatbot is ready
        if st.session_state.chatbot_ready:
            st.success("✅ Chatbot Ready")
        else:
            st.error("❌ Chatbot Not Ready")
            if 'error' in st.session_state:
                st.error(f"Error: {st.session_state.error}")
        
        st.markdown("---")
        
        # PDF files info
        if st.session_state.chatbot_ready:
            try:
                pdf_files = st.session_state.chatbot.pdf_processor.load_pdfs()
                st.header("📚 Loaded Documents")
                st.write(f"**{len(pdf_files)} PDF files**")
                for pdf in pdf_files:
                    st.text(f"• {os.path.basename(pdf)}")
            except Exception as e:
                st.warning("No PDF files found")
        
        st.markdown("---")
        
        # Action buttons
        if st.button("🔄 Reload Vector Store"):
            if st.session_state.chatbot_ready:
                with st.spinner("Reprocessing PDFs..."):
                    st.session_state.chatbot.process_pdfs()
                st.success("Vector store reloaded!")
                st.rerun()
        
        if st.button("🗑️ Clear Chat History"):
            st.session_state.messages = []
            st.rerun()
    
    # Main content - Chat Interface
    st.header("💬 Chat Interface")
    
    # Display chat messages
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask a question about your documents..."):
        if not st.session_state.chatbot_ready:
            st.error("Chatbot is not ready. Please check the error message in the sidebar.")
        else:
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = st.session_state.chatbot.process_query(prompt)
                st.markdown(response)
            
            # Add assistant message
            st.session_state.messages.append({"role": "assistant", "content": response})
            
            st.rerun()
    
    # Quick action buttons
    st.markdown("---")
    st.subheader("💡 Quick Actions")
    
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📖 Show Examples"):
            examples = [
                "What is a cognitive distortion?",
                "What are the meditation techniques?",
                "Summarize the main topics in the documents",
                "What are the benefits mentioned?"
            ]
            st.info("**Example Questions:**\n\n" + "\n".join([f"• {ex}" for ex in examples]))
    
    with col_b:
        if st.button("ℹ️ System Info"):
            if st.session_state.chatbot_ready:
                info = st.session_state.chatbot.get_system_info()
                st.text(info)
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            <small> Chatbot | Built with Streamlit</small>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    # Set environment variable to suppress tokenizer warnings
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {e}")
        logger.error(f"Application error: {e}")
