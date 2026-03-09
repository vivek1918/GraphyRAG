import React, { useState } from 'react';
import { Database, MessageSquare, Upload, Activity } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import ChatInterface from './components/ChatInterface';
import GraphVisualization from './components/GraphVisualization';
import FileUpload from './components/FileUpload';
import PipelineMonitor from './components/PipelineMonitor';
import './App.css';

function App() {
  const [chatGraphData, setChatGraphData] = useState({
    entities: [],
    relations: [],
  });

  const handleGraphDataUpdate = (data) => {
    setChatGraphData(data);
  };

  const handleUploadSuccess = () => {
    console.log('Files uploaded successfully');
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Database className="h-8 w-8" />
              <div>
                <h1 className="text-2xl font-bold">Knowledge Graph RAG</h1>
                <p className="text-sm text-muted-foreground">
                  Multi-modal Knowledge Graph Construction & Retrieval
                </p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
        <Tabs defaultValue="chat" className="space-y-6">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="chat" className="flex items-center space-x-2">
              <MessageSquare className="h-4 w-4" />
              <span>Chat</span>
            </TabsTrigger>
            <TabsTrigger value="graph" className="flex items-center space-x-2">
              <Database className="h-4 w-4" />
              <span>Graph</span>
            </TabsTrigger>
            <TabsTrigger value="upload" className="flex items-center space-x-2">
              <Upload className="h-4 w-4" />
              <span>Upload</span>
            </TabsTrigger>
            <TabsTrigger value="pipeline" className="flex items-center space-x-2">
              <Activity className="h-4 w-4" />
              <span>Pipeline</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="chat" className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[700px]">
              <ChatInterface onGraphDataUpdate={handleGraphDataUpdate} />
              <GraphVisualization graphData={chatGraphData} skipAutoFetch={true} />
            </div>
          </TabsContent>

          <TabsContent value="graph" className="space-y-4">
            <div className="h-[700px]">
              <GraphVisualization />
            </div>
          </TabsContent>

          <TabsContent value="upload" className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <FileUpload onUploadSuccess={handleUploadSuccess} />
              <PipelineMonitor />
            </div>
          </TabsContent>

          <TabsContent value="pipeline" className="space-y-4">
            <div className="max-w-3xl mx-auto">
              <PipelineMonitor />
            </div>
          </TabsContent>
        </Tabs>
      </main>

      {/* Footer */}
      <footer className="border-t border-border mt-12 py-6">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>Knowledge Graph RAG System • Built with React, FastAPI & Neo4j</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
