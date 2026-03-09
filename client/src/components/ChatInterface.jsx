import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { ScrollArea } from './ui/scroll-area';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { sendChatMessage } from '../lib/api';

const ChatInterface = ({ onGraphDataUpdate }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const scrollRef = useRef(null);

  // Load chat history from localStorage on mount
  useEffect(() => {
    const savedMessages = localStorage.getItem('chatMessages');
    const savedSessionId = localStorage.getItem('chatSessionId');
    
    if (savedMessages) {
      try {
        setMessages(JSON.parse(savedMessages));
      } catch (error) {
        console.error('Failed to parse saved messages:', error);
      }
    }
    
    if (savedSessionId) {
      setSessionId(savedSessionId);
    }
  }, []);

  // Save messages to localStorage whenever they change
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem('chatMessages', JSON.stringify(messages));
    }
  }, [messages]);

  // Save sessionId to localStorage whenever it changes
  useEffect(() => {
    if (sessionId) {
      localStorage.setItem('chatSessionId', sessionId);
    }
  }, [sessionId]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await sendChatMessage(input, sessionId, 4);
      
      setSessionId(response.session_id);

      const assistantMessage = {
        role: 'assistant',
        content: response.response,
        timestamp: response.timestamp,
        relevantDocs: response.relevant_documents,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Update graph visualization if relevant data is available
      if (response.relevant_documents && response.relevant_documents.length > 0) {
        // Parse entities and relations from relevant documents for visualization
        onGraphDataUpdate?.({
          entities: extractEntities(response.relevant_documents),
          relations: extractRelations(response.relevant_documents),
        });
      }
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error while processing your request. Please try again.',
        timestamp: new Date().toISOString(),
        error: true,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const extractEntities = (documents) => {
    // Simple entity extraction for demo - you can enhance this
    const entities = new Set();
    documents.forEach((doc, index) => {
      const words = doc.split(' ').filter(w => w.length > 5);
      words.slice(0, 5).forEach((word, i) => {
        entities.add({
          id: `entity-${index}-${i}`,
          text: word,
          label: word,
        });
      });
    });
    return Array.from(entities);
  };

  const extractRelations = (documents) => {
    // Simple relation extraction for demo
    const relations = [];
    const entities = extractEntities(documents);
    for (let i = 0; i < entities.length - 1; i++) {
      relations.push({
        source: entities[i].id,
        target: entities[i + 1].id,
        type: 'RELATES_TO',
      });
    }
    return relations;
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setSessionId(null);
    localStorage.removeItem('chatMessages');
    localStorage.removeItem('chatSessionId');
    onGraphDataUpdate?.({
      entities: [],
      relations: [],
    });
  };

  return (
    <Card className="flex flex-col h-full">
      <CardHeader className="flex-shrink-0">
        <CardTitle className="flex items-center justify-between">
          <span>Chat Interface</span>
          {messages.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClearChat}
              className="text-xs"
            >
              Clear Chat
            </Button>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col p-4 overflow-scroll min-h-0">
        <div 
          className="flex-1 overflow-y-auto pr-2 mb-4 min-h-0" 
          style={{ 
            maxHeight: '100%',
            overflowY: 'scroll',
            scrollbarWidth: 'thin',
            scrollbarColor: '#3f3f46 #18181b'
          }}
        >
          <div className="space-y-4 pb-4">
            {messages.length === 0 && (
              <div className="text-center text-muted-foreground py-8">
                <p className="text-lg mb-2">👋 Welcome to Knowledge Graph RAG</p>
                <p className="text-sm">
                  Ask me anything about your documents!
                </p>
              </div>
            )}
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex ${
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-3 ${
                    message.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : message.error
                      ? 'bg-destructive text-destructive-foreground'
                      : 'bg-muted text-muted-foreground'
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
                  {message.relevantDocs && message.relevantDocs.length > 0 && (
                    <div className="mt-2 text-xs opacity-70">
                      <details>
                        <summary className="cursor-pointer">
                          {message.relevantDocs.length} relevant sources
                        </summary>
                        <div className="mt-2 space-y-1">
                          {message.relevantDocs.slice(0, 2).map((doc, i) => (
                            <div key={i} className="text-xs break-words">
                              {doc.substring(0, 100)}...
                            </div>
                          ))}
                        </div>
                      </details>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-muted text-muted-foreground rounded-lg px-4 py-2 flex items-center space-x-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm">Thinking...</span>
                </div>
              </div>
            )}
            <div ref={scrollRef} />
          </div>
        </div>

        <div className="flex space-x-2 flex-shrink-0">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask a question about your documents..."
            disabled={loading}
            className="flex-1"
          />
          <Button onClick={handleSend} disabled={loading || !input.trim()}>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default ChatInterface;
