#!/usr/bin/env python3
"""
RAG-based PDF Chatbot
Processes PDF files and answers questions using FAISS vector database and Groq LLM
"""

import os
import sys
import logging
import glob
from typing import List, Dict, Any
from utils.config_loader import get_config
from utils.logger import setup_logger

# Setup logger first
logger = setup_logger(__name__)

load_dotenv = None
try:
    from dotenv import load_dotenv as _load_dotenv
    load_dotenv = _load_dotenv
    load_dotenv()  # Load environment variables from .env file if present
    logger.info("Environment variables loaded from .env file")
except ImportError:
    logger.warning("python-dotenv not installed, skipping .env loading")

class PDFProcessor:
    """Handles PDF loading and text extraction"""
    
    def __init__(self, config_path: str = None):
        self.config = get_config(config_path)
        self.pdf_directory = "data/raw/pdf"
        
    def load_pdfs(self) -> List[str]:
        """Load all PDF files from directory"""
        pdf_files = glob.glob(os.path.join(self.pdf_directory, "*.pdf"))
        if not pdf_files:
            raise FileNotFoundError(f"No PDF files found in {self.pdf_directory}")
        return pdf_files
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from a single PDF file"""
        try:
            import PyPDF2
            text = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
            return ""
    
    def chunk_text(self, text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - chunk_overlap
        return chunks

class VectorStore:
    """Manages FAISS vector database"""
    
    def __init__(self, config_path: str = None):
        self.config = get_config(config_path)
        self.vector_store = None
        self.embeddings = None
        self.index_path = "data/vector_store/faiss_index"
        
    def initialize_embeddings(self):
        """Initialize embedding model"""
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'}
            )
            logger.info("Initialized HuggingFaceEmbeddings successfully")
        except ImportError as e:
            logger.warning(f"langchain_huggingface not available: {e}")
            try:
                # Try alternative import
                from langchain.embeddings import HuggingFaceEmbeddings
                self.embeddings = HuggingFaceEmbeddings(
                    model_name="sentence-transformers/all-MiniLM-L6-v2",
                    model_kwargs={'device': 'cpu'}
                )
                logger.info("Initialized HuggingFaceEmbeddings from langchain.embeddings")
            except ImportError:
                # Create a wrapper for SentenceTransformer to make it compatible with LangChain
                from sentence_transformers import SentenceTransformer
                from langchain.embeddings.base import Embeddings
                logger.info("Using SentenceTransformer with custom wrapper")
                
                class SentenceTransformerWrapper(Embeddings):
                    """Wrapper to make SentenceTransformer compatible with LangChain"""
                    def __init__(self, model_name='all-MiniLM-L6-v2'):
                        self.model = SentenceTransformer(model_name)
                    
                    def embed_documents(self, texts):
                        """Embed a list of documents"""
                        embeddings = self.model.encode(texts, convert_to_numpy=True)
                        return embeddings.tolist()
                    
                    def embed_query(self, text):
                        """Embed a single query"""
                        embedding = self.model.encode([text], convert_to_numpy=True)
                        return embedding[0].tolist()
                
                self.embeddings = SentenceTransformerWrapper()
    
    def create_vector_store(self, documents: List[str]):
        """Create FAISS vector store from documents"""
        try:
            import faiss
            from langchain_community.vectorstores import FAISS
            
            if self.embeddings is None:
                self.initialize_embeddings()
            
            # Create vector store
            self.vector_store = FAISS.from_texts(documents, self.embeddings)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            self.vector_store.save_local(self.index_path)
            logger.info(f"Vector store created with {len(documents)} documents")
            
        except Exception as e:
            logger.error(f"Error creating vector store: {e}")
            raise
    
    def load_vector_store(self):
        """Load existing vector store"""
        try:
            from langchain_community.vectorstores import FAISS
            
            if self.embeddings is None:
                self.initialize_embeddings()
            
            if os.path.exists(self.index_path):
                self.vector_store = FAISS.load_local(
                    self.index_path, 
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info("Vector store loaded successfully")
            else:
                logger.warning("No existing vector store found")
                
        except Exception as e:
            logger.error(f"Error loading vector store: {e}")
            raise
    
    def similarity_search(self, query: str, k: int = 4) -> List[str]:
        """Search for similar documents"""
        if self.vector_store is None:
            self.load_vector_store()
        
        if self.vector_store is None:
            return []
        
        try:
            results = self.vector_store.similarity_search(query, k=k)
            return [doc.page_content for doc in results]
        except Exception as e:
            logger.error(f"Error in similarity search: {e}")
            return []

class GroqLLM:
    """Handles interactions with Groq API"""
    
    def __init__(self, config_path: str = None):
        self.config = get_config(config_path)
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable not set")
        
        # Get model from config, fallback to llama-3.1-8b-instant
        self.model_name = self.config.get('models', {}).get('llm', {}).get('groq', 'llama-3.1-8b-instant')
    
    def generate_response(self, prompt: str, context: str, question: str) -> str:
        """Generate response using Groq API with RAG context"""
        try:
            import groq
            
            client = groq.Groq(api_key=self.api_key)
            
            system_prompt = """You are a helpful AI assistant that answers questions based ONLY on the provided context. 
            Follow these rules strictly:
            1. ONLY use information from the provided context to answer questions
            2. If the context doesn't contain relevant information, say "I cannot answer this question based on the available documents."
            3. Do not use any external knowledge or make assumptions
            4. If the question is unclear or outside the context scope, politely decline to answer
            5. Keep answers concise and directly based on the context
            6. Do not mention that you're using context or following rules in your response"""
            
            user_message = f"""Context: {context}

Question: {question}

Based ONLY on the context above, please answer the question. If the answer cannot be found in the context, politely decline to answer."""

            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1,
                max_tokens=1024
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error calling Groq API: {e}")
            return f"I apologize, but I encountered an error while processing your question: {str(e)}"

class RAGChatbot:
    """
    Main RAG chatbot class that processes PDFs and answers questions
    using FAISS vector database and Groq LLM
    """
    
    def __init__(self, config_path: str = None):
        try:
            self.config = get_config(config_path)
            logger.info("Configuration loaded successfully")
            
            # Initialize components
            self.pdf_processor = PDFProcessor(config_path)
            self.vector_store = VectorStore(config_path)
            self.llm = GroqLLM(config_path)
            
            # Check if vector store exists, otherwise create it
            self.initialize_system()
            
            logger.info("RAG Chatbot initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG chatbot: {e}")
            raise
    
    def initialize_system(self):
        """Initialize or load the vector database"""
        try:
            self.vector_store.load_vector_store()
            
            # If no vector store exists, process PDFs and create one
            if self.vector_store.vector_store is None:
                print("No existing vector store found. Processing PDFs...")
                self.process_pdfs()
            else:
                print("Vector store loaded successfully!")
                
        except Exception as e:
            logger.error(f"Error initializing system: {e}")
            raise
    
    def process_pdfs(self):
        """Process all PDFs and create vector store"""
        try:
            pdf_files = self.pdf_processor.load_pdfs()
            all_chunks = []
            
            print(f"Found {len(pdf_files)} PDF files. Processing...")
            
            for pdf_file in pdf_files:
                print(f"Processing: {os.path.basename(pdf_file)}")
                text = self.pdf_processor.extract_text_from_pdf(pdf_file)
                if text.strip():
                    chunks = self.pdf_processor.chunk_text(text)
                    all_chunks.extend(chunks)
                    print(f"  - Extracted {len(chunks)} chunks")
                else:
                    print(f"  - No text extracted from {pdf_file}")
            
            if not all_chunks:
                raise ValueError("No text could be extracted from any PDF files")
            
            print(f"Creating vector store with {len(all_chunks)} text chunks...")
            self.vector_store.create_vector_store(all_chunks)
            print("Vector store created successfully!")
            
        except Exception as e:
            logger.error(f"Error processing PDFs: {e}")
            raise
    
    def get_system_info(self) -> str:
        """Get information about the RAG system"""
        try:
            pdf_files = self.pdf_processor.load_pdfs()
            pdf_names = [os.path.basename(pdf) for pdf in pdf_files]
            
            info = [
                "📚 RAG PDF Chatbot",
                "=" * 50,
                f"• PDF Files Loaded: {len(pdf_files)}",
                f"• Documents: {', '.join(pdf_names[:5])}{'...' if len(pdf_names) > 5 else ''}",
                f"• Vector Database: FAISS",
                f"• LLM: Groq Mixtral-8x7b",
                "",
                "💡 I can answer questions based ONLY on the provided PDF documents.",
                "I will politely decline questions outside the document scope.",
                "",
                "📖 Example questions:",
                "• 'What are the main topics discussed in the documents?'",
                "• 'Summarize the key findings from the research'",
                "• 'What methods were used in the study?'",
                "• 'List the important conclusions'",
                "",
                "⚠️  I will NOT answer questions about:",
                "• Topics not covered in the PDFs",
                "• General knowledge outside the documents",
                "• Current events or recent developments",
                "• Personal opinions or external information"
            ]
            
            return "\n".join(info)
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return f"System information unavailable: {e}"
    
    def process_query(self, query: str) -> str:
        """Process a user query using RAG pipeline"""
        try:
            # Search for relevant context
            relevant_docs = self.vector_store.similarity_search(query, k=4)
            context = "\n\n".join(relevant_docs)
            
            if not context.strip():
                return "I cannot answer this question as I don't have relevant information in my documents."
            
            # Generate response using LLM
            response = self.llm.generate_response("", context, query)
            
            # Additional check to ensure response stays within context
            if self.is_out_of_scope(response, query):
                return "I cannot answer this question based on the available documents. Please ask questions related to the content of the PDF files."
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return f"I apologize, but I encountered an error while processing your question: {str(e)}"
    
    def is_out_of_scope(self, response: str, query: str) -> bool:
        """Check if response is potentially out of scope"""
        out_of_scope_indicators = [
            "I don't have information",
            "not in the provided context",
            "based on my knowledge",
            "as an AI",
            "in general",
            "typically",
            "usually",
            "outside the context",
            "beyond the provided",
            "not mentioned in"
        ]
        
        response_lower = response.lower()
        return any(indicator in response_lower for indicator in out_of_scope_indicators)
    
    def interactive_chat(self):
        """Start interactive chatbot session"""
        print("🤖 RAG PDF Chatbot")
        print("=" * 50)
        print(self.get_system_info())
        print("=" * 50)
        print("\nType 'exit' to quit, 'info' for system info, 'help' for examples")
        print("Type 'reload' to reprocess PDFs\n")
        
        while True:
            try:
                user_input = input("💬 You: ").strip()
                
                if user_input.lower() in ['exit', 'quit']:
                    print("Goodbye! 👋")
                    break
                
                elif user_input.lower() in ['info', 'information']:
                    print("\n" + self.get_system_info() + "\n")
                    continue
                
                elif user_input.lower() in ['help', 'examples']:
                    self.show_examples()
                    continue
                
                elif user_input.lower() == 'reload':
                    print("Reprocessing PDFs...")
                    self.process_pdfs()
                    continue
                
                elif not user_input:
                    continue
                
                # Process the query
                print("🔍 Searching documents...")
                response = self.process_query(user_input)
                
                print(f"\n🤖 Bot: {response}\n")
                
            except KeyboardInterrupt:
                print("\n\nExiting chatbot. Goodbye! 👋")
                break
            except Exception as e:
                logger.error(f"Chatbot error: {e}")
                print(f"❌ Sorry, I encountered an error: {e}\n")
    
    def show_examples(self):
        """Show example queries"""
        examples = [
            "DOCUMENT-BASED QUESTIONS:",
            "  • 'What is the main topic of the documents?'",
            "  • 'Summarize the key points from the research'",
            "  • 'What methods were used in the study?'",
            "  • 'List the main findings or conclusions'",
            "",
            "SPECIFIC INFORMATION:",
            "  • 'Find information about [specific topic]'",
            "  • 'What does the document say about [concept]?'",
            "  • 'Extract data about [subject]'",
            "",
            "COMPARISON:",
            "  • 'Compare different approaches mentioned'",
            "  • 'What are the advantages and disadvantages discussed?'",
            "",
            "QUESTIONS I CANNOT ANSWER:",
            "  • Current events or news",
            "  • General knowledge questions",
            "  • Topics outside the PDF content",
            "  • Personal opinions",
            "  • Future predictions"
        ]
        
        print("\n" + "\n".join(examples) + "\n")

def main():
    """Main entry point"""
    try:
        # Check if config path is provided as command line argument
        config_path = None
        if len(sys.argv) > 1:
            config_path = sys.argv[1]
            print(f"Using config from: {config_path}")
        
        # Create necessary directories
        os.makedirs("data/raw/pdf", exist_ok=True)
        os.makedirs("data/vector_store", exist_ok=True)
        
        chatbot = RAGChatbot(config_path)
        chatbot.interactive_chat()
        
    except Exception as e:
        logger.error(f"Failed to start RAG chatbot: {e}")
        print(f"❌ Failed to start RAG chatbot: {e}")
        print("\nPlease ensure:")
        print("1. Your settings.yml file exists in conf/ folder")
        print("2. PDF files are placed in data/raw/pdf/ directory")
        print("3. GROQ_API_KEY environment variable is set")
        print("4. Required packages are installed: PyPDF2, faiss-cpu, langchain, sentence-transformers, groq")
        print("\nInstall required packages:")
        print("pip install PyPDF2 faiss-cpu langchain sentence-transformers groq")
        sys.exit(1)

if __name__ == "__main__":
    main()