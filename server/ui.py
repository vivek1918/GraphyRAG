#!/usr/bin/env python3
"""
Simple web UI for the Knowledge Graph system.
Provides a browser interface for querying and exploring the KG.
"""

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
from pathlib import Path
from typing import Dict, Any

from server.api import KnowledgeGraphAPI

class KnowledgeGraphUI:
    """Web UI for the Knowledge Graph system."""
    
    def __init__(self):
        self.app = FastAPI(title="Knowledge Graph UI")
        self.api = KnowledgeGraphAPI()
        
        # Setup templates and static files
        self.templates_path = Path("server/templates")
        self.static_path = Path("server/static")
        
        # Create directories if they don't exist
        self.templates_path.mkdir(parents=True, exist_ok=True)
        self.static_path.mkdir(parents=True, exist_ok=True)
        
        self.templates = Jinja2Templates(directory=str(self.templates_path))
        
        # Mount static files
        self.app.mount("/static", StaticFiles(directory=str(self.static_path)), name="static")
        
        self.setup_routes()
        self._create_default_templates()
    
    def _create_default_templates(self):
        """Create default HTML templates if they don't exist."""
        index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Semantic Knowledge Graph</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            padding: 30px;
        }
        
        @media (max-width: 768px) {
            .main-content {
                grid-template-columns: 1fr;
            }
        }
        
        .query-section, .results-section {
            background: #f8f9fa;
            padding: 25px;
            border-radius: 10px;
            border: 1px solid #e9ecef;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #2c3e50;
        }
        
        input, select, textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #3498db;
        }
        
        textarea {
            height: 120px;
            resize: vertical;
        }
        
        .btn {
            background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        .btn:hover {
            transform: translateY(-2px);
        }
        
        .btn:active {
            transform: translateY(0);
        }
        
        .results {
            margin-top: 20px;
        }
        
        .result-item {
            background: white;
            padding: 20px;
            margin-bottom: 15px;
            border-radius: 8px;
            border-left: 4px solid #3498db;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .result-item h4 {
            color: #2c3e50;
            margin-bottom: 10px;
        }
        
        .result-item p {
            color: #7f8c8d;
            line-height: 1.6;
        }
        
        .confidence {
            display: inline-block;
            background: #e74c3c;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            margin-top: 10px;
        }
        
        .confidence.high {
            background: #27ae60;
        }
        
        .confidence.medium {
            background: #f39c12;
        }
        
        .tab-container {
            margin-top: 30px;
        }
        
        .tabs {
            display: flex;
            border-bottom: 2px solid #e9ecef;
            margin-bottom: 20px;
        }
        
        .tab {
            padding: 15px 25px;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            transition: all 0.3s;
        }
        
        .tab.active {
            border-bottom-color: #3498db;
            color: #3498db;
            font-weight: 600;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .stat-number {
            font-size: 2.5em;
            font-weight: bold;
            color: #3498db;
            margin-bottom: 10px;
        }
        
        .stat-label {
            color: #7f8c8d;
            font-size: 0.9em;
        }
        
        .loading {
            text-align: center;
            padding: 20px;
            color: #7f8c8d;
        }
        
        .error {
            background: #e74c3c;
            color: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔮 Semantic Knowledge Graph</h1>
            <p>Explore and query your knowledge graph through natural language</p>
        </div>
        
        <div class="main-content">
            <div class="query-section">
                <h2>Query the Knowledge Graph</h2>
                <form id="queryForm" onsubmit="submitQuery(event)">
                    <div class="form-group">
                        <label for="query">Your Question:</label>
                        <textarea 
                            id="query" 
                            placeholder="e.g., Who works for TechCorp? What events happened in New York?"
                            required></textarea>
                    </div>
                    
                    <div class="form-group">
                        <label for="retriever">Retrieval Method:</label>
                        <select id="retriever">
                            <option value="hybrid">Hybrid (Recommended)</option>
                            <option value="vector">Vector Search</option>
                            <option value="graph">Knowledge Graph</option>
                            <option value="multimodal">Multi-modal</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="top_k">Number of Results:</label>
                        <input type="number" id="top_k" value="5" min="1" max="20">
                    </div>
                    
                    <button type="submit" class="btn">Ask the Knowledge Graph</button>
                </form>
                
                <div id="loading" class="loading" style="display: none;">
                    <p>🔍 Searching knowledge graph...</p>
                </div>
                
                <div id="error" class="error" style="display: none;"></div>
            </div>
            
            <div class="results-section">
                <h2>Results</h2>
                <div id="results" class="results">
                    <p>Enter a query to see results here...</p>
                </div>
            </div>
        </div>
        
        <div class="tab-container">
            <div class="tabs">
                <div class="tab active" onclick="switchTab('analytics')">Analytics</div>
                <div class="tab" onclick="switchTab('sparql')">SPARQL Query</div>
                <div class="tab" onclick="switchTab('entities')">Entities</div>
                <div class="tab" onclick="switchTab('relations')">Relations</div>
            </div>
            
            <div id="analytics" class="tab-content active">
                <h3>Knowledge Graph Analytics</h3>
                <div class="stats-grid" id="statsGrid">
                    <div class="stat-card">
                        <div class="stat-number">-</div>
                        <div class="stat-label">Total Entities</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">-</div>
                        <div class="stat-label">Total Relations</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">-</div>
                        <div class="stat-label">Documents</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">-</div>
                        <div class="stat-label">Entity Types</div>
                    </div>
                </div>
                <canvas id="analyticsChart" width="400" height="200"></canvas>
            </div>
            
            <div id="sparql" class="tab-content">
                <h3>SPARQL Query Interface</h3>
                <div class="form-group">
                    <label for="sparqlQuery">SPARQL Query:</label>
                    <textarea id="sparqlQuery" placeholder="PREFIX : <http://kg.example.org/ontology/>
SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"></textarea>
                </div>
                <button class="btn" onclick="executeSparql()">Execute SPARQL</button>
                <div id="sparqlResults"></div>
            </div>
            
            <div id="entities" class="tab-content">
                <h3>Entity Browser</h3>
                <div class="form-group">
                    <label for="entityType">Filter by Type:</label>
                    <select id="entityType" onchange="loadEntities()">
                        <option value="">All Types</option>
                        <option value="Person">Person</option>
                        <option value="Organization">Organization</option>
                        <option value="Place">Place</option>
                        <option value="Event">Event</option>
                    </select>
                </div>
                <div id="entitiesList"></div>
            </div>
            
            <div id="relations" class="tab-content">
                <h3>Relation Browser</h3>
                <div class="form-group">
                    <label for="relationType">Filter by Type:</label>
                    <select id="relationType" onchange="loadRelations()">
                        <option value="">All Types</option>
                        <option value="worksFor">Works For</option>
                        <option value="locatedIn">Located In</option>
                        <option value="participatedIn">Participated In</option>
                    </select>
                </div>
                <div id="relationsList"></div>
            </div>
        </div>
    </div>

    <script>
        let analyticsChart = null;
        
        // Tab switching
        function switchTab(tabName) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Remove active class from all tabs
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
            
            // Load data for the tab
            if (tabName === 'analytics') {
                loadAnalytics();
            } else if (tabName === 'entities') {
                loadEntities();
            } else if (tabName === 'relations') {
                loadRelations();
            }
        }
        
        // Query submission
        async function submitQuery(event) {
            event.preventDefault();
            
            const query = document.getElementById('query').value;
            const retriever = document.getElementById('retriever').value;
            const top_k = document.getElementById('top_k').value;
            
            // Show loading
            document.getElementById('loading').style.display = 'block';
            document.getElementById('error').style.display = 'none';
            
            try {
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        query: query,
                        retriever_type: retriever,
                        top_k: parseInt(top_k)
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    displayResults(data.data);
                } else {
                    showError(data.error || 'Query failed');
                }
            } catch (error) {
                showError('Network error: ' + error.message);
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }
        
        // Display results
        function displayResults(data) {
            const resultsDiv = document.getElementById('results');
            
            let html = `
                <div class="result-item">
                    <h4>Answer</h4>
                    <p>${data.answer}</p>
                    <span class="confidence ${getConfidenceClass(data.confidence)}">
                        Confidence: ${(data.confidence * 100).toFixed(1)}%
                    </span>
                </div>
            `;
            
            if (data.sources && data.sources.length > 0) {
                html += `<div class="result-item">
                    <h4>Sources</h4>
                    <ul>`;
                data.sources.forEach(source => {
                    html += `<li>${source}</li>`;
                });
                html += `</ul></div>`;
            }
            
            if (data.retrieved_data && data.retrieved_data.length > 0) {
                html += `<div class="result-item">
                    <h4>Retrieved Information</h4>`;
                data.retrieved_data.forEach(item => {
                    html += `
                    <div style="margin-bottom: 15px; padding: 10px; background: #f8f9fa; border-radius: 5px;">
                        <p><strong>${item.type}</strong>: ${item.content}</p>
                        <small>Score: ${item.score.toFixed(3)} | Source: ${item.retriever}</small>
                    </div>`;
                });
                html += `</div>`;
            }
            
            resultsDiv.innerHTML = html;
        }
        
        // SPARQL execution
        async function executeSparql() {
            const query = document.getElementById('sparqlQuery').value;
            const resultsDiv = document.getElementById('sparqlResults');
            
            try {
                const response = await fetch('/api/sparql', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ query: query })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    resultsDiv.innerHTML = `
                        <div class="result-item">
                            <h4>Results (${data.data.count})</h4>
                            <pre>${JSON.stringify(data.data.results, null, 2)}</pre>
                        </div>
                    `;
                } else {
                    resultsDiv.innerHTML = `<div class="error">Error: ${data.error}</div>`;
                }
            } catch (error) {
                resultsDiv.innerHTML = `<div class="error">Network error: ${error.message}</div>`;
            }
        }
        
        // Load analytics
        async function loadAnalytics() {
            try {
                const response = await fetch('/api/analytics');
                const data = await response.json();
                
                if (data.success) {
                    updateAnalyticsDisplay(data.data);
                }
            } catch (error) {
                console.error('Error loading analytics:', error);
            }
        }
        
        // Load entities
        async function loadEntities() {
            const type = document.getElementById('entityType').value;
            const entitiesDiv = document.getElementById('entitiesList');
            
            try {
                const url = type ? `/api/entities?entity_type=${type}&limit=50` : '/api/entities?limit=50';
                const response = await fetch(url);
                const data = await response.json();
                
                if (data.success) {
                    let html = '<div class="result-item"><h4>Entities</h4>';
                    data.data.entities.forEach(entity => {
                        html += `<p><strong>${entity.label}</strong> (${entity.type})</p>`;
                    });
                    html += `</div>`;
                    entitiesDiv.innerHTML = html;
                }
            } catch (error) {
                entitiesDiv.innerHTML = `<div class="error">Error loading entities: ${error.message}</div>`;
            }
        }
        
        // Load relations
        async function loadRelations() {
            const type = document.getElementById('relationType').value;
            const relationsDiv = document.getElementById('relationsList');
            
            try {
                const url = type ? `/api/relations?relation_type=${type}&limit=50` : '/api/relations?limit=50';
                const response = await fetch(url);
                const data = await response.json();
                
                if (data.success) {
                    let html = '<div class="result-item"><h4>Relations</h4>';
                    data.data.relations.forEach(rel => {
                        html += `<p><strong>${rel.subjectLabel}</strong> → ${rel.predicate} → <strong>${rel.objectLabel}</strong></p>`;
                    });
                    html += `</div>`;
                    relationsDiv.innerHTML = html;
                }
            } catch (error) {
                relationsDiv.innerHTML = `<div class="error">Error loading relations: ${error.message}</div>`;
            }
        }
        
        // Update analytics display
        function updateAnalyticsDisplay(data) {
            // This would parse the analytics data and update charts
            // For now, just show some placeholder stats
            document.querySelector('#statsGrid .stat-number').innerHTML = '100+';
        }
        
        // Helper functions
        function getConfidenceClass(confidence) {
            if (confidence > 0.7) return 'high';
            if (confidence > 0.4) return 'medium';
            return '';
        }
        
        function showError(message) {
            document.getElementById('error').textContent = message;
            document.getElementById('error').style.display = 'block';
        }
        
        // Load analytics on page load
        document.addEventListener('DOMContentLoaded', function() {
            loadAnalytics();
        });
    </script>
</body>
</html>
        """
        
        (self.templates_path / "index.html").write_text(index_html)
    
    def setup_routes(self):
        """Setup UI routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def read_root(request: Request):
            return self.templates.TemplateResponse("index.html", {"request": request})
        
        # Mount API routes under /api
        self.app.include_router(self.api.app, prefix="/api")
    
    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the UI server."""
        import uvicorn
        uvicorn.run(self.app, host=host, port=port)

# Create and run the application
app = KnowledgeGraphUI().app

if __name__ == "__main__":
    ui = KnowledgeGraphUI()
    ui.run()