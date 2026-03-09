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
    page_title="RAG Chatbot",
    page_icon="🤖",
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
    .metric-card {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

class Neo4jConnection:
    """Handle Neo4j database connections"""
    
    def __init__(self):
        try:
            from neo4j import GraphDatabase
            
            # Load configuration
            config_path = Path(__file__).parent / "conf" / "settings.yaml"
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            neo4j_config = config.get('kg', {})
            self.uri = neo4j_config.get('neo4j_url', 'bolt://localhost:7687')
            self.user = neo4j_config.get('neo4j_user', 'neo4j')
            self.password = neo4j_config.get('neo4j_password', 'password')
            
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.connected = True
            
        except ImportError:
            logger.warning("neo4j package not installed")
            self.connected = False
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self.connected = False
    
    def close(self):
        """Close the database connection"""
        if hasattr(self, 'driver'):
            self.driver.close()
    
    def get_graph_data(self) -> Dict[str, Any]:
        """Retrieve graph data from Neo4j"""
        if not self.connected:
            return {"nodes": [], "edges": []}
        
        try:
            with self.driver.session() as session:
                # Get all nodes
                nodes_result = session.run("""
                    MATCH (n)
                    RETURN n.id as id, n.name as name, n.type as type, 
                           n.modality as modality, n.confidence as confidence
                    LIMIT 100
                """)
                
                nodes = []
                for record in nodes_result:
                    # Skip nodes with missing required fields
                    if not record['id'] or not record['name'] or not record['type']:
                        continue
                    nodes.append({
                        'id': record['id'] or 'unknown',
                        'name': record['name'] or 'Unknown',
                        'type': record['type'] or 'Unknown',
                        'modality': record.get('modality') or 'unknown',
                        'confidence': record.get('confidence') or 0.5
                    })
                
                # Get all relationships
                edges_result = session.run("""
                    MATCH (a)-[r]->(b)
                    RETURN a.id as source, b.id as target, type(r) as relation,
                           r.confidence as confidence
                    LIMIT 200
                """)
                
                edges = []
                for record in edges_result:
                    # Skip edges with missing required fields
                    if not record['source'] or not record['target'] or not record['relation']:
                        continue
                    edges.append({
                        'source': record['source'],
                        'target': record['target'],
                        'relation': record['relation'] or 'RELATED_TO',
                        'confidence': record.get('confidence') or 0.5
                    })
                
                return {"nodes": nodes, "edges": edges}
                
        except Exception as e:
            logger.error(f"Error fetching graph data: {e}")
            return {"nodes": [], "edges": []}
    
    def get_stats(self) -> Dict[str, int]:
        """Get database statistics"""
        if not self.connected:
            return {"nodes": 0, "relationships": 0, "node_types": 0}
        
        try:
            with self.driver.session() as session:
                # Count nodes
                node_count = session.run("MATCH (n) RETURN count(n) as count").single()['count']
                
                # Count relationships
                rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
                
                # Count node types
                type_count = session.run("MATCH (n) RETURN count(DISTINCT n.type) as count").single()['count']
                
                return {
                    "nodes": node_count,
                    "relationships": rel_count,
                    "node_types": type_count
                }
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            return {"nodes": 0, "relationships": 0, "node_types": 0}

def create_knowledge_graph_viz(graph_data: Dict[str, Any]) -> go.Figure:
    """Create an interactive knowledge graph visualization using Plotly"""
    
    try:
        nodes = graph_data.get('nodes', [])
        edges = graph_data.get('edges', [])
        
        if not nodes:
            # Return empty figure with message
            fig = go.Figure()
            fig.add_annotation(
                text="No graph data available. Run the demo pipeline to generate knowledge graph.",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14)
            )
            return fig
        
        # Create NetworkX graph for layout
        G = nx.Graph()
        
        # Add nodes
        for node in nodes:
            if node.get('id'):
                G.add_node(node['id'], **node)
        
        # Add edges
        for edge in edges:
            if edge.get('source') and edge.get('target'):
                G.add_edge(edge['source'], edge['target'], relation=edge.get('relation', 'RELATED_TO'))
        
        # Use spring layout for positioning
        pos = nx.spring_layout(G, k=2, iterations=50)
        
        # Define colors for different node types
        color_map = {
            'ACTIVITY': '#1f77b4',
            'DURATION': '#ff7f0e',
            'DIFFICULTY': '#2ca02c',
            'BENEFIT': '#d62728',
            'TIME': '#9467bd',
            'default': '#7f7f7f'
        }
        
        # Create edge traces
        edge_traces = []
        for edge in edges:
            if edge.get('source') and edge.get('target') and edge['source'] in pos and edge['target'] in pos:
                x0, y0 = pos[edge['source']]
                x1, y1 = pos[edge['target']]
                
                edge_trace = go.Scatter(
                    x=[x0, x1, None],
                    y=[y0, y1, None],
                    mode='lines',
                    line=dict(width=1, color='#888'),
                    hoverinfo='text',
                    text=edge.get('relation', 'RELATED_TO'),
                    showlegend=False
                )
                edge_traces.append(edge_trace)
        
        # Create node trace
        node_x = []
        node_y = []
        node_text = []
        node_color = []
        node_size = []
        
        for node in nodes:
            if node.get('id') and node['id'] in pos:
                x, y = pos[node['id']]
                node_x.append(x)
                node_y.append(y)
                
                # Get safe values with None checks
                name = node.get('name') or 'Unknown'
                node_type = node.get('type') or 'Unknown'
                modality = node.get('modality') or 'unknown'
                confidence = node.get('confidence')
                if confidence is None:
                    confidence = 0.5
                
                # Node label
                node_text.append(
                    f"<b>{name}</b><br>"
                    f"Type: {node_type}<br>"
                    f"Modality: {modality}<br>"
                    f"Confidence: {confidence:.2f}"
                )
                
                # Node color based on type
                node_color.append(color_map.get(node_type, color_map['default']))
                
                # Node size based on confidence
                node_size.append(20 + confidence * 20)
        
        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode='markers+text',
            hoverinfo='text',
            text=[node.get('name', 'Unknown') for node in nodes if node.get('id') and node['id'] in pos],
            textposition="top center",
            textfont=dict(size=10),
            hovertext=node_text,
            marker=dict(
                size=node_size,
                color=node_color,
                line=dict(width=2, color='white')
            ),
            showlegend=False
        )
        
        # Create figure
        fig = go.Figure(data=edge_traces + [node_trace])
        
        fig.update_layout(
            title="Knowledge Graph Visualization",
            titlefont_size=16,
            showlegend=False,
            hovermode='closest',
            margin=dict(b=0, l=0, r=0, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor='white',
            height=600
        )
        
        return fig
    
    except Exception as e:
        logger.error(f"Error creating graph visualization: {e}")
        # Return error figure
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error creating graph visualization. Please check the logs.",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color='red')
        )
        return fig

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
    
    if 'neo4j' not in st.session_state:
        st.session_state.neo4j = Neo4jConnection()
    
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    if 'graph_data' not in st.session_state:
        if st.session_state.neo4j.connected:
            st.session_state.graph_data = st.session_state.neo4j.get_graph_data()
        else:
            st.session_state.graph_data = {"nodes": [], "edges": []}

def main():
    """Main Streamlit app"""
    
    # Initialize session state
    initialize_session_state()
    
    # Header
    st.markdown('<div class="main-header">🤖 RAG Chatbot with Knowledge Graph</div>', unsafe_allow_html=True)
    
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
        
        # Neo4j connection status
        if st.session_state.neo4j.connected:
            st.success("✅ Neo4j Connected")
            
            # Get and display stats
            stats = st.session_state.neo4j.get_stats()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Nodes", stats['nodes'])
                st.metric("Node Types", stats['node_types'])
            with col2:
                st.metric("Relations", stats['relationships'])
        else:
            st.warning("⚠️ Neo4j Not Connected")
            st.info("Run `python scripts/demo_pipeline.py` to create the knowledge graph")
        
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
        
        # Refresh buttons
        if st.button("🔄 Refresh Graph"):
            if st.session_state.neo4j.connected:
                st.session_state.graph_data = st.session_state.neo4j.get_graph_data()
                st.rerun()
        
        if st.button("🔄 Reload Vector Store"):
            if st.session_state.chatbot_ready:
                with st.spinner("Reprocessing PDFs..."):
                    st.session_state.chatbot.process_pdfs()
                st.success("Vector store reloaded!")
                st.rerun()
        
        if st.button("🗑️ Clear Chat History"):
            st.session_state.messages = []
            st.rerun()
    
    # Main content area - Two columns
    col1, col2 = st.columns([1, 1])
    
    # Left column - Chatbot
    with col1:
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
    
    # Right column - Knowledge Graph
    with col2:
        st.header("🕸️ Knowledge Graph")
        
        # Create and display graph
        if st.session_state.graph_data['nodes']:
            fig = create_knowledge_graph_viz(st.session_state.graph_data)
            st.plotly_chart(fig, use_container_width=True)
            
            # Graph statistics
            st.subheader("📈 Graph Statistics")
            col_stats1, col_stats2, col_stats3 = st.columns(3)
            
            with col_stats1:
                st.metric("Total Nodes", len(st.session_state.graph_data['nodes']))
            with col_stats2:
                st.metric("Total Edges", len(st.session_state.graph_data['edges']))
            with col_stats3:
                # Count unique node types
                node_types = set([n['type'] for n in st.session_state.graph_data['nodes']])
                st.metric("Node Types", len(node_types))
            
            # Show node types breakdown
            with st.expander("📊 Node Types Breakdown"):
                node_type_counts = {}
                for node in st.session_state.graph_data['nodes']:
                    node_type = node['type']
                    node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1
                
                for node_type, count in sorted(node_type_counts.items(), key=lambda x: x[1], reverse=True):
                    st.write(f"**{node_type}:** {count} nodes")
            
            # Show detailed graph data
            with st.expander("📋 View Graph Data"):
                tab1, tab2 = st.tabs(["Nodes", "Edges"])
                
                with tab1:
                    st.subheader("Nodes")
                    if st.session_state.graph_data['nodes']:
                        # Create a formatted table view
                        import pandas as pd
                        nodes_df = pd.DataFrame(st.session_state.graph_data['nodes'])
                        st.dataframe(
                            nodes_df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                'id': st.column_config.TextColumn('ID', width='medium'),
                                'name': st.column_config.TextColumn('Name', width='medium'),
                                'type': st.column_config.TextColumn('Type', width='small'),
                                'modality': st.column_config.TextColumn('Modality', width='small'),
                                'confidence': st.column_config.NumberColumn('Confidence', format="%.2f", width='small')
                            }
                        )
                        
                        # JSON view option
                        if st.checkbox("Show as JSON", key="nodes_json"):
                            st.json(st.session_state.graph_data['nodes'])
                    else:
                        st.info("No nodes available")
                
                with tab2:
                    st.subheader("Edges")
                    if st.session_state.graph_data['edges']:
                        # Create a formatted table view
                        edges_df = pd.DataFrame(st.session_state.graph_data['edges'])
                        st.dataframe(
                            edges_df,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                'source': st.column_config.TextColumn('Source', width='medium'),
                                'target': st.column_config.TextColumn('Target', width='medium'),
                                'relation': st.column_config.TextColumn('Relation', width='medium'),
                                'confidence': st.column_config.NumberColumn('Confidence', format="%.2f", width='small')
                            }
                        )
                        
                        # JSON view option
                        if st.checkbox("Show as JSON", key="edges_json"):
                            st.json(st.session_state.graph_data['edges'])
                    else:
                        st.info("No edges available")
        else:
            st.info("No knowledge graph data available.")
            st.write("To generate the knowledge graph:")
            st.code("python scripts/demo_pipeline.py", language="bash")
            
            # Show placeholder graph
            fig = create_knowledge_graph_viz(st.session_state.graph_data)
            st.plotly_chart(fig, use_container_width=True)
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            <small>RAG Chatbot with Neo4j Knowledge Graph Visualization | Built with Streamlit</small>
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
