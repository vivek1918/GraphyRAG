import React, { useState, useEffect } from 'react';
import { Play, Square, Trash2, Loader2 } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { ScrollArea } from './ui/scroll-area';
import {
  runPipeline,
  getPipelineStatus,
  stopPipeline,
  clearPipelineState,
} from '../lib/api';

const PipelineMonitor = () => {
  const [status, setStatus] = useState(null);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    fetchStatus();
  }, []);

  useEffect(() => {
    let interval;
    if (polling) {
      interval = setInterval(fetchStatus, 2000);
    }
    return () => clearInterval(interval);
  }, [polling]);

  const fetchStatus = async () => {
    try {
      const data = await getPipelineStatus();
      setStatus(data);
      
      if (data.running) {
        setPolling(true);
      } else {
        setPolling(false);
      }
    } catch (error) {
      console.error('Error fetching pipeline status:', error);
    }
  };

  const handleStart = async () => {
    try {
      await runPipeline({
        use_existing_data: true,
        interactive_mode: false,
      });
      setPolling(true);
      fetchStatus();
    } catch (error) {
      console.error('Error starting pipeline:', error);
    }
  };

  const handleStop = async () => {
    try {
      await stopPipeline();
      fetchStatus();
    } catch (error) {
      console.error('Error stopping pipeline:', error);
    }
  };

  const handleClear = async () => {
    try {
      await clearPipelineState();
      fetchStatus();
    } catch (error) {
      console.error('Error clearing pipeline:', error);
    }
  };

  const getStatusColor = () => {
    if (!status) return 'bg-muted';
    switch (status.status) {
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      case 'processing':
      case 'initializing':
        return 'bg-blue-500';
      default:
        return 'bg-muted';
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Pipeline Monitor</span>
          {status?.running && (
            <span className="flex items-center text-sm font-normal text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              Running
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Status Bar */}
        {status && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Status:</span>
              <span className={`px-2 py-1 rounded text-xs ${getStatusColor()} text-white`}>
                {status.status}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Progress:</span>
              <span>{status.progress}%</span>
            </div>
            <div className="w-full bg-secondary rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all ${getStatusColor()}`}
                style={{ width: `${status.progress}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground">{status.message}</p>
          </div>
        )}

        {/* Logs */}
        {status && status.logs && status.logs.length > 0 && (
          <div>
            <p className="text-sm font-medium mb-2">Execution Logs</p>
            <ScrollArea className="h-48 w-full rounded-md border bg-muted/50 p-2">
              <div className="space-y-1">
                {status.logs.slice(-20).map((log, index) => (
                  <div key={index} className="text-xs font-mono">
                    {log}
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}

        {/* Results */}
        {status?.results && (
          <div className="grid grid-cols-2 gap-2">
            <div className="p-3 bg-muted rounded-md">
              <p className="text-xs text-muted-foreground">Documents</p>
              <p className="text-2xl font-bold">{status.results.documents_processed}</p>
            </div>
            <div className="p-3 bg-muted rounded-md">
              <p className="text-xs text-muted-foreground">Triples</p>
              <p className="text-2xl font-bold">
                {status.results.kg_stats?.total_triples || 0}
              </p>
            </div>
            <div className="p-3 bg-muted rounded-md">
              <p className="text-xs text-muted-foreground">Entities</p>
              <p className="text-2xl font-bold">
                {status.results.kg_stats?.entities || 0}
              </p>
            </div>
            <div className="p-3 bg-muted rounded-md">
              <p className="text-xs text-muted-foreground">Relations</p>
              <p className="text-2xl font-bold">
                {status.results.kg_stats?.relations || 0}
              </p>
            </div>
          </div>
        )}

        {/* Controls */}
        <div className="flex space-x-2">
          <Button
            onClick={handleStart}
            disabled={status?.running}
            className="flex-1"
          >
            <Play className="h-4 w-4 mr-2" />
            Start Pipeline
          </Button>
          <Button
            onClick={handleStop}
            disabled={!status?.running}
            variant="destructive"
          >
            <Square className="h-4 w-4" />
          </Button>
          <Button
            onClick={handleClear}
            disabled={status?.running}
            variant="outline"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default PipelineMonitor;
