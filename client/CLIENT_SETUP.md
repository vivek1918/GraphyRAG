# Knowledge Graph RAG - React Frontend

A modern, monotone-themed React frontend for the Knowledge Graph RAG system with graph visualization, chat interface, file upload, and pipeline monitoring.

## Features

- **Chat Interface**: Interactive RAG-powered chat with message history
- **Graph Visualization**: Real-time knowledge graph visualization using React Flow
- **Multi-modal File Upload**: Support for PDF, audio, image, video, and text files
- **Pipeline Monitoring**: Real-time pipeline execution tracking with logs
- **Monotone Design**: Clean, professional dark theme with zinc/gray palette
- **shadcn UI**: Modern component library with Radix UI primitives

## Tech Stack

- **React** 19.2.3 - UI framework
- **React Flow** 11.10.4 - Graph visualization
- **shadcn/ui** - Component library
- **Tailwind CSS** 3.4.0 - Styling
- **Axios** 1.6.2 - HTTP client
- **Lucide React** - Icon library

## Prerequisites

- Node.js 16+ and npm
- FastAPI backend running on `http://localhost:8000`

## Installation

1. Install dependencies:
```bash
cd client
npm install
```

2. Configure environment (optional):
```bash
# Edit .env if needed
REACT_APP_API_URL=http://localhost:8000
```

## Running the Application

### Development Mode

```bash
npm start
```

Opens [http://localhost:3000](http://localhost:3000) in your browser.

### Production Build

```bash
npm run build
```

Builds the app for production to the `build/` folder.

## Project Structure

```
client/
├── public/              # Static assets
├── src/
│   ├── components/
│   │   ├── ui/          # shadcn UI components
│   │   │   ├── button.jsx
│   │   │   ├── card.jsx
│   │   │   ├── input.jsx
│   │   │   ├── scroll-area.jsx
│   │   │   └── tabs.jsx
│   │   ├── ChatInterface.jsx       # Chat UI with message history
│   │   ├── GraphVisualization.jsx  # React Flow graph component
│   │   ├── FileUpload.jsx          # Multi-modal file upload
│   │   └── PipelineMonitor.jsx     # Pipeline execution monitor
│   ├── lib/
│   │   ├── api.js       # API client (Axios wrapper)
│   │   └── utils.js     # Utility functions
│   ├── App.js           # Main application component
│   ├── App.css          # Global styles + CSS variables
│   ├── index.js         # Entry point
│   └── index.css        # Tailwind directives
├── tailwind.config.js   # Tailwind configuration
├── postcss.config.js    # PostCSS configuration
└── package.json         # Dependencies
```

## Components

### ChatInterface
- Send messages to RAG system
- View conversation history
- Display relevant documents
- Update graph visualization on response

### GraphVisualization
- React Flow-based knowledge graph
- Entity nodes and relation edges
- Interactive controls (zoom, pan)
- Minimap and background grid
- Monotone styling

### FileUpload
- Multi-modal file support (PDF, audio, image, video, text)
- Drag-and-drop interface
- File list with size display
- Upload progress feedback

### PipelineMonitor
- Start/stop/clear pipeline execution
- Real-time status updates
- Progress bar (0-100%)
- Log viewer (last 20 entries)
- Results display (documents, triples, entities, relations)

## API Integration

The frontend connects to the FastAPI backend via Axios client (`src/lib/api.js`):

```javascript
import { sendChatMessage, uploadFiles, runPipeline } from './lib/api';

// Chat
const response = await sendChatMessage({ query: "What is X?" });

// Upload files
await uploadFiles(files, 'pdf');

// Run pipeline
await runPipeline();
```

## Styling

The app uses a monotone color scheme defined in [tailwind.config.js](tailwind.config.js):

- **Background**: #09090b (zinc-950)
- **Card/Surface**: #18181b (zinc-900)
- **Border**: #27272a (zinc-800)
- **Text**: #fafafa (zinc-50)
- **Muted**: #71717a (zinc-500)

CSS variables are defined in [App.css](src/App.css) for both light and dark modes.

## Environment Variables

- `REACT_APP_API_URL`: FastAPI backend URL (default: `http://localhost:8000`)

## Available Scripts

- `npm start` - Run development server
- `npm run build` - Build for production
- `npm test` - Run tests
- `npm run eject` - Eject from Create React App (irreversible)

## Troubleshooting

### Backend Connection Issues

1. Ensure FastAPI server is running:
```bash
cd ..
uvicorn api:app --reload
```

2. Check CORS settings in `api.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    ...
)
```

### Build Errors

1. Clear node modules and reinstall:
```bash
rm -rf node_modules package-lock.json
npm install
```

2. Clear Create React App cache:
```bash
rm -rf node_modules/.cache
```

### Graph Not Rendering

1. Check React Flow installation:
```bash
npm list reactflow
```

2. Verify graph data structure in console:
```javascript
console.log(graphData);
```

## Development Tips

1. **Hot Reload**: Changes to React components trigger automatic reload
2. **API Debugging**: Check Network tab in browser DevTools
3. **Console Logging**: Use `console.log()` to debug state changes
4. **React DevTools**: Install browser extension for component inspection

## Production Deployment

1. Build the application:
```bash
npm run build
```

2. Serve with static server:
```bash
npx serve -s build -p 3000
```

3. Or use Nginx/Apache to serve the `build/` directory

## License

MIT

## Support

For issues or questions, refer to the main project documentation or API reference:
- [API_DOCUMENTATION.md](../API_DOCUMENTATION.md)
- [API_QUICK_REFERENCE.md](../API_QUICK_REFERENCE.md)
