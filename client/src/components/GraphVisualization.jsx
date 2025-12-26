import React, { useState, useCallback, useEffect } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { RefreshCw, Loader2, AlertCircle } from 'lucide-react';
import { getGraphData } from '../lib/api';

// Custom tooltip component
const NodeTooltip = ({ node, position }) => {
  if (!node) return null;
  
  return (
    <div
      style={{
        position: 'absolute',
        left: position.x + 50,
        top: position.y - 20,
        background: '#18181b',
        border: '1px solid #27272a',
        borderRadius: '6px',
        padding: '8px 12px',
        color: '#fafafa',
        fontSize: '12px',
        zIndex: 1000,
        pointerEvents: 'none',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
        maxWidth: '250px',
        whiteSpace: 'normal',
      }}
    >
      <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
        {node.data.fullLabel}
      </div>
      {node.data.type && (
        <div style={{ fontSize: '10px', color: '#a1a1aa' }}>
          Type: {node.data.type}
        </div>
      )}
    </div>
  );
};

// Neo4j-inspired color palette for different entity types
const NEO4J_COLORS = [
  { bg: '#68BC00', border: '#5CA300', text: '#FFFFFF' }, // Green
  { bg: '#FB8500', border: '#E07700', text: '#FFFFFF' }, // Orange
  { bg: '#DA3B83', border: '#C33575', text: '#FFFFFF' }, // Pink
  { bg: '#604A7B', border: '#53426A', text: '#FFFFFF' }, // Purple
  { bg: '#4C8EDA', border: '#437FC7', text: '#FFFFFF' }, // Blue
  { bg: '#AA2344', border: '#991F3D', text: '#FFFFFF' }, // Red
  { bg: '#FFC454', border: '#E6B04C', text: '#333333' }, // Yellow
  { bg: '#57C7E3', border: '#4DB3CE', text: '#FFFFFF' }, // Cyan
  { bg: '#F25A29', border: '#DA5125', text: '#FFFFFF' }, // Coral
  { bg: '#9B59B6', border: '#8E44AD', text: '#FFFFFF' }, // Violet
];

// Edge colors for Neo4j style
const EDGE_COLORS = [
  '#68BC00', // Green
  '#FB8500', // Orange
  '#DA3B83', // Pink
  '#604A7B', // Purple
  '#4C8EDA', // Blue
  '#AA2344', // Red
];

const GraphVisualization = ({ graphData: propGraphData, skipAutoFetch = false }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });
  const [graphData, setGraphData] = useState(propGraphData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const hoverTimeoutRef = React.useRef(null);

  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  // Helper function to get entity type or hash string for consistent coloring
  const getEntityColor = (entity, index) => {
    // Try to use entity type if available
    const entityType = entity.type || entity.label || entity.text || '';
    
    // Create a simple hash from the entity type for consistent colors
    let hash = 0;
    for (let i = 0; i < entityType.length; i++) {
      hash = entityType.charCodeAt(i) + ((hash << 5) - hash);
    }
    
    const colorIndex = Math.abs(hash) % NEO4J_COLORS.length;
    return NEO4J_COLORS[colorIndex];
  };

  // Helper function to get edge color based on relation type
  const getEdgeColor = (relation) => {
    const relationType = relation.type || relation.relation || '';
    
    let hash = 0;
    for (let i = 0; i < relationType.length; i++) {
      hash = relationType.charCodeAt(i) + ((hash << 5) - hash);
    }
    
    const colorIndex = Math.abs(hash) % EDGE_COLORS.length;
    return EDGE_COLORS[colorIndex];
  };

  // Fetch graph data from Neo4j
  const fetchGraphData = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const data = await getGraphData(300);
      setGraphData(data);
    } catch (err) {
      console.error('Failed to fetch graph data:', err);
      setError('Failed to load graph data. Neo4j might not be available.');
      // Use prop data as fallback if available
      if (propGraphData) {
        setGraphData(propGraphData);
      }
    } finally {
      setLoading(false);
    }
  }, [propGraphData]);

  // Fetch data on mount (only if not skipping auto-fetch)
  useEffect(() => {
    if (skipAutoFetch) {
      // In chat mode, use prop data only
      if (propGraphData) {
        setGraphData(propGraphData);
      }
    } else if (!propGraphData) {
      // In graph mode, fetch from Neo4j
      fetchGraphData();
    } else {
      setGraphData(propGraphData);
    }
  }, [propGraphData, fetchGraphData, skipAutoFetch]);

  // Generate nodes and edges from graph data
  React.useEffect(() => {
    if (graphData && graphData.entities) {
      // Limit to 300 nodes for better performance and visualization
      const limitedEntities = graphData.entities.slice(0, 300);
      const entityIds = new Set(limitedEntities.map((e, i) => e.id || `node-${i}`));
      
      const newNodes = limitedEntities.map((entity, index) => {
        const color = getEntityColor(entity, index);
        const entityLabel = entity.label || entity.text || 'Unknown';
        const entityType = entity.type || '';
        
        // Create short label (first letter or first few chars)
        const shortLabel = entityLabel.length > 2 
          ? entityLabel.substring(0, 2).toUpperCase() 
          : entityLabel.charAt(0).toUpperCase();
        
        return {
          id: entity.id || `node-${index}`,
          type: 'default',
          data: {
            label: shortLabel,
            // Store full info for tooltip
            fullLabel: entityLabel,
            type: entityType,
          },
          position: {
            x: Math.random() * 1500,
            y: Math.random() * 1000,
          },
          style: {
            background: `${color.bg}40`, // 40 in hex = 25% opacity (translucent)
            color: color.text,
            border: `2px solid ${color.border}`,
            borderRadius: '50%',
            padding: '0',
            fontSize: '10px',
            fontWeight: '600',
            width: '40px',
            height: '40px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            transformOrigin: 'center',
          },
        };
      });

      // Filter edges to only include those connecting visible nodes
      const newEdges = graphData.relations
        ? graphData.relations
            .filter((relation) => {
              return entityIds.has(relation.source) && entityIds.has(relation.target);
            })
            .map((relation, index) => {
              const edgeColor = getEdgeColor(relation);
              
              return {
                id: `edge-${index}`,
                source: relation.source,
                target: relation.target,
                label: relation.type || relation.relation,
                type: 'smoothstep',
                animated: true,
                style: { 
                  stroke: edgeColor,
                  strokeWidth: 2,
                },
                markerEnd: {
                  type: MarkerType.ArrowClosed,
                  color: edgeColor,
                  width: 20,
                  height: 20,
                },
                labelStyle: {
                  fill: '#fafafa',
                  fontSize: 11,
                  fontWeight: '500',
                },
                labelBgStyle: {
                  fill: '#09090b',
                  fillOpacity: 0.8,
                },
                labelBgPadding: [4, 8],
                labelBgBorderRadius: 4,
              };
            })
        : [];

      setNodes(newNodes);
      setEdges(newEdges);
    }
  }, [graphData, setNodes, setEdges]);

  // Handle node hover with debouncing
  const onNodeMouseEnter = useCallback((event, node) => {
    // Clear any pending timeout
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }
    
    // Debounce the hover state update
    hoverTimeoutRef.current = setTimeout(() => {
      setHoveredNode(node);
      
      // Get the React Flow container position for relative tooltip positioning
      const flowElement = event.target.closest('.react-flow');
      if (flowElement) {
        const rect = flowElement.getBoundingClientRect();
        setTooltipPosition({ 
          x: event.clientX - rect.left, 
          y: event.clientY - rect.top 
        });
      } else {
        setTooltipPosition({ x: event.clientX, y: event.clientY });
      }
      
      // Update node style on hover
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id === node.id) {
            return {
              ...n,
              style: {
                ...n.style,
                transform: 'scale(1.5)',
                transformOrigin: 'center',
                zIndex: 1000,
                boxShadow: '0 0 20px rgba(255, 255, 255, 0.5)',
                background: n.style.background.replace('40', 'CC'), // Make more opaque on hover
              },
            };
          }
          return n;
        })
      );
    }, 50); // 50ms debounce
  }, [setNodes]);

  const onNodeMouseLeave = useCallback((event, node) => {
    // Clear any pending timeout
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }
    
    setHoveredNode(null);
    
    // Reset node style
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id === node.id) {
          const color = getEntityColor(n.data, 0);
          return {
            ...n,
            style: {
              ...n.style,
              transformOrigin: 'center',
              transform: 'scale(1)',
              zIndex: 1,
              boxShadow: 'none',
              background: `${color.bg}40`,
            },
          };
        }
        return n;
      })
    );
  }, [setNodes]);

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Knowledge Graph Visualization</span>
          <div className="flex items-center gap-3">
            <span className="text-sm font-normal text-muted-foreground">
              {nodes.length} nodes, {edges.length} edges
            </span>
            {!skipAutoFetch && (
              <Button
                variant="outline"
                size="sm"
                onClick={fetchGraphData}
                disabled={loading}
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
              </Button>
            )}
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div style={{ height: '600px', position: 'relative' }}>
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-50">
              <div className="flex flex-col items-center gap-2">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">Loading graph data...</p>
              </div>
            </div>
          )}
          {error && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50">
              <div className="flex items-center gap-2 bg-destructive/10 border border-destructive text-destructive px-4 py-2 rounded-md">
                <AlertCircle className="h-4 w-4" />
                <span className="text-sm">{error}</span>
              </div>
            </div>
          )}
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeMouseEnter={onNodeMouseEnter}
            onNodeMouseLeave={onNodeMouseLeave}
            fitView
            attributionPosition="bottom-left"
            style={{
              background: 'linear-gradient(to bottom, #0a0a0a, #1a1a1a)',
            }}
          >
            <Controls
              style={{
                button: {
                  backgroundColor: '#18181b',
                  color: '#fafafa',
                  borderBottom: '1px solid #27272a',
                },
              }}
            />
                {/* <MiniMap
                style={{
                    backgroundColor: '#18181b',
                    border: '1px solid #27272a',
                }}
                nodeStrokeWidth={2}
                maskColor="rgba(0, 0, 0, 0.6)"
                /> */}
            <Background
              variant="dots"
              gap={16}
              size={1}
              color="#27272a"
            />
          </ReactFlow>
          {hoveredNode && <NodeTooltip node={hoveredNode} position={tooltipPosition} />}
        </div>
        <div className="px-4 py-3 border-t border-border bg-muted/30">
          <p className="text-xs text-muted-foreground text-center">
            <span className="font-semibold">Note:</span> Graph is limited to 300 nodes for optimal performance and clarity.
            {graphData?.entities?.length > 300 && (
              <span> Showing {nodes.length} of {graphData.entities.length} total entities.</span>
            )}
            {' '}Hover over nodes to view full details.
          </p>
        </div>
      </CardContent>
    </Card>
  );
};

export default GraphVisualization;
