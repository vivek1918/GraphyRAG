#!/usr/bin/env python3
"""
Generalized Graph Database Chatbot
Can answer questions by traversing any graph database structure
"""

import os
import sys
import logging
from utils.config_loader import get_config
from utils.logger import setup_logger
from core.chat_processor import ChatProcessor
from core.graph_manager import GraphManager

# Setup logger first
logger = setup_logger(__name__)

class GraphChatbot:
    """
    Main chatbot class that provides interactive interface
    for querying graph databases using natural language
    """
    
    def __init__(self, config_path: str = None):
        try:
            self.config = get_config(config_path)
            logger.info("Configuration loaded successfully")
            
            # Test graph connection first
            self.graph_manager = GraphManager(config_path)
            logger.info("Graph manager initialized")
            
            # Test graph connectivity
            self.test_graph_connection()
            
            self.chat_processor = ChatProcessor(config_path)
            logger.info("Chatbot initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize chatbot: {e}")
            raise
    
    def test_graph_connection(self):
        """Test if we can connect to the graph database"""
        try:
            # Test basic connectivity
            node_types = self.graph_manager.get_node_types()
            rel_types = self.graph_manager.get_relationship_types()
            stats = self.graph_manager.get_graph_statistics()
            
            logger.info(f"Connected to graph successfully!")
            logger.info(f"Node types: {node_types}")
            logger.info(f"Relationship types: {rel_types}")
            logger.info(f"Graph stats: {stats}")
            
        except Exception as e:
            logger.error(f"Graph connection test failed: {e}")
            raise
    
    def get_graph_info(self) -> str:
        """Get information about the graph database"""
        try:
            stats = self.graph_manager.get_graph_statistics()
            node_types = self.graph_manager.get_node_types()
            rel_types = self.graph_manager.get_relationship_types()
            
            info = [
                "📊 Graph Database Information:",
                f"• Total Nodes: {stats.get('nodeCount', 'N/A')}",
                f"• Total Relationships: {stats.get('relationshipCount', 'N/A')}",
                f"• Node Types: {', '.join(node_types[:10])}{'...' if len(node_types) > 10 else ''}",
                f"• Relationship Types: {', '.join(rel_types[:10])}{'...' if len(rel_types) > 10 else ''}",
                "",
                "You can ask me questions like:",
                "• 'Find all people who work at Google'",
                "• 'How many projects are in the database?'",
                "• 'Show me nodes connected to marketing department'",
                "• 'What is the relationship between Alice and Bob?'",
                "• 'Find nodes with property status active'"
            ]
            
            return "\n".join(info)
        except Exception as e:
            logger.error(f"Error getting graph info: {e}")
            return f"Could not retrieve graph information: {e}"
    
    def interactive_chat(self):
        """Start interactive chatbot session"""
        print("🤖 Graph Database Chatbot")
        print("=" * 50)
        print(self.get_graph_info())
        print("=" * 50)
        print("\nType 'exit' to quit, 'info' for graph info, 'help' for examples")
        print("Type 'debug' to see query processing details\n")
        
        while True:
            try:
                user_input = input("💬 You: ").strip()
                
                if user_input.lower() in ['exit', 'quit']:
                    print("Goodbye! 👋")
                    break
                
                elif user_input.lower() in ['info', 'information']:
                    print("\n" + self.get_graph_info() + "\n")
                    continue
                
                elif user_input.lower() in ['help', 'examples']:
                    self.show_examples()
                    continue
                
                elif user_input.lower() == 'debug':
                    self.debug_mode = not getattr(self, 'debug_mode', False)
                    status = "ON" if self.debug_mode else "OFF"
                    print(f"🔧 Debug mode: {status}")
                    continue
                
                elif not user_input:
                    continue
                
                # Process the query
                print("🔄 Processing your query...")
                response = self.chat_processor.process_query(user_input)
                
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
            "FINDING ENTITIES:",
            "  • 'Find all Person nodes'",
            "  • 'Show me Project entities'",
            "  • 'Find nodes with status active'",
            "",
            "COUNTING:",
            "  • 'How many users are there?'",
            "  • 'Count all products'",
            "  • 'Number of departments'",
            "",
            "RELATIONSHIPS:",
            "  • 'Who works at Google?'",
            "  • 'Find connections between Alice and Bob'",
            "  • 'Show me relationships for marketing'",
            "",
            "PROPERTIES:",
            "  • 'Find nodes with email containing gmail.com'",
            "  • 'Show me entities created in 2024'",
            "  • 'Find items with price greater than 100'",
            "",
            "EXPLORATION:",
            "  • 'What types of nodes exist?'",
            "  • 'Show me some sample data'",
            "  • 'What relationships are available?'",
            "",
            "DEBUG:",
            "  • Type 'debug' to toggle detailed query logging"
        ]
        
        print("\n" + "\n".join(examples) + "\n")
    
    def single_query(self, query: str) -> str:
        """Process a single query and return response"""
        return self.chat_processor.process_query(query)

def main():
    """Main entry point"""
    try:
        # Check if config path is provided as command line argument
        config_path = None
        if len(sys.argv) > 1:
            config_path = sys.argv[1]
            print(f"Using config from: {config_path}")
        
        chatbot = GraphChatbot(config_path)
        chatbot.interactive_chat()
        
    except Exception as e:
        logger.error(f"Failed to start chatbot: {e}")
        print(f"❌ Failed to start chatbot: {e}")
        print("\nPlease ensure:")
        print("1. Your settings.yml file exists in conf/ folder")
        print("2. Neo4j database is running and accessible")
        print("3. GROQ_API_KEY environment variable is set")
        print("4. Neo4j password is correct")
        sys.exit(1)
    finally:
        if 'chatbot' in locals():
            chatbot.graph_manager.close()

if __name__ == "__main__":
    main()