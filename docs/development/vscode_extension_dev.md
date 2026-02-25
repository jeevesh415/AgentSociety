# AI Social Scientist VSCode Extension Development Guide

This guide explains how to develop and extend the AI Social Scientist VSCode extension.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Development Environment Setup](#development-environment-setup)
3. [Project Structure](#project-structure)
4. [Extension Points](#extension-points)
5. [Adding New Tools](#adding-new-tools)
6. [Backend Development](#backend-development)
7. [Webview Development](#webview-development)
8. [Testing and Debugging](#testing-and-debugging)
9. [Packaging and Publishing](#packaging-and-publishing)

## Architecture Overview

The AI Social Scientist extension consists of three main components:

```
┌─────────────────────────────────────────────────────────────────┐
│                    VSCode Extension                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Extension Host (TypeScript)                  │  │
│  │  - Command Registration                                   │  │
│  │  - Tree Views (Project Structure)                         │  │
│  │  - Webview Providers (Chat, Settings)                     │  │
│  │  - API Client (HTTP/SSE)                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                 │
│                              │ HTTP/WebSockets                │
│                              ▼                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              FastAPI Backend (Python)                     │  │
│  │  - Tool Registry                                          │  │
│  │  - LLM Router (litellm)                                   │  │
│  │  - AgentSociety 2 Integration                             │  │
│  │  - SSE Streaming                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Development Environment Setup

### Prerequisites

- Node.js >= 16.x
- Python >= 3.11
- uv (Python package manager)
- VSCode or Cursor >= 1.80.0

### Installation

```bash
# Clone the repository
git clone https://github.com/tsinghua-fib-lab/agentsociety.git
cd agentsociety/extension

# Install npm dependencies
npm install

# Install Python dependencies
cd ../packages/agentsociety2
uv sync
```

### Build Commands

```bash
# In extension/ directory
npm run compile          # Compile TypeScript
npm run build-webview   # Build React webview
npm run watch          # Watch mode for TypeScript
npm run watch-webview  # Watch mode for React
```

## Project Structure

```
extension/
├── src/
│   ├── extension.ts              # Main entry point
│   ├── projectStructureProvider.ts  # Project tree view
│   ├── chatWebviewProvider.ts    # Chat interface
│   ├── apiClient.ts              # Backend API client
│   └── webview/
│       ├── chat/                 # React chat components
│       │   ├── ChatApp.tsx       # Main chat component
│       │   ├── types.ts          # Type definitions
│       │   └── index.html        # HTML template
│       └── components/           # Shared components
├── package.json
├── tsconfig.json
└── webpack.config.js

packages/agentsociety2/agentsociety2/backend/
├── run.py                        # FastAPI app entry
├── routers/                      # API endpoints
├── tools/                        # LLM tools
│   ├── base.py                   # Base tool class
│   └── registry.py               # Tool registry
└── tasks/                        # Background tasks
```

## Extension Points

### 1. Commands

Register new commands in `extension.ts`:

```typescript
import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
    // Register a new command
    const disposable = vscode.commands.registerCommand(
        'aiSocialScientist.myCommand',
        async () => {
            // Command implementation
            vscode.window.showInformationMessage('Hello from my command!');
        }
    );

    context.subscriptions.push(disposable);
}
```

Add to `package.json`:

```json
{
    "contributes": {
        "commands": [
            {
                "command": "aiSocialScientist.myCommand",
                "title": "My Custom Command"
            }
        ]
    }
}
```

### 2. Tree Views

Add a new tree view provider in `projectStructureProvider.ts`:

```typescript
export class MyTreeProvider implements vscode.TreeDataProvider<MyTreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<MyTreeItem | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    constructor(private workspaceRoot: string) {}

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: MyTreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: MyTreeItem): Thenable<MyTreeItem[]> {
        // Return children items
    }
}

class MyTreeItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super(label, collapsibleState);
    }
}
```

Register in `extension.ts`:

```typescript
const myTreeProvider = new MyTreeProvider(workspaceRoot);
vscode.window.createTreeView('aiSocialScientist.myTreeView', {
    treeDataProvider: myTreeProvider
});
```

### 3. Webview Providers

Create a new webview provider:

```typescript
export class MyWebviewProvider {
    public static readonly viewType = 'aiSocialScientist.myWebview';

    private _view?: vscode.WebviewView;
    private _panel?: vscode.WebviewPanel;

    constructor(
        private _extensionUri: vscode.Uri,
        private _context: vscode.ExtensionContext
    ) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView
    ) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [vscode.Uri.joinPath(this._extensionUri, 'out')]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        // Handle messages from webview
        webviewView.webview.onDidReceiveMessage(
            message => {
                switch (message.command) {
                    case 'alert':
                        vscode.window.showInformationMessage(message.text);
                        return;
                }
            }
        );
    }

    private _getHtmlForWebview(webview: vscode.Webview) {
        // Return HTML content
    }
}
```

## Adding New Tools

Tools are the primary way to extend the extension's capabilities. They are
Python classes that the LLM can call during conversations.

### Create a New Tool

1. Create a new file in `packages/agentsociety2/agentsociety2/backend/tools/`:

```python
from typing import Any, Dict
from .base import BaseTool

class MyCustomTool(BaseTool):
    """A custom tool for doing X."""

    @staticmethod
    def get_name() -> str:
        return "my_custom_tool"

    @staticmethod
    def get_description() -> str:
        return """A description of what this tool does.
        Use it when you need to accomplish X."""

    @staticmethod
    def get_parameters_schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "Description of param1"
                },
                "param2": {
                    "type": "integer",
                    "description": "Description of param2"
                }
            },
            "required": ["param1"]
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool logic."""
        param1 = kwargs.get("param1")
        param2 = kwargs.get("param2", 0)

        try:
            # Your tool logic here
            result = f"Processed {param1} with {param2}"

            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
```

2. Register the tool in `tools/registry.py`:

```python
from .my_custom_tool import MyCustomTool

def get_registry() -> ToolRegistry:
    registry = ToolRegistry()

    # Register your tool
    registry.register(MyCustomTool())

    return registry
```

3. The tool is now available to the LLM!

### Tool Best Practices

1. **Clear descriptions**: Help the LLM understand when to use the tool
2. **Validation**: Validate all input parameters
3. **Error handling**: Return structured error responses
4. **Idempotency**: Tools should be safe to call multiple times
5. **Logging**: Log important operations for debugging

## Backend Development

### API Endpoints

Add new endpoints in `packages/agentsociety2/agentsociety2/backend/routers/`:

```python
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

router = APIRouter(prefix="/api/v1/custom", tags=["custom"])

@router.post("/endpoint")
async def custom_endpoint(data: Dict[str, Any]) -> Dict[str, Any]:
    """Custom endpoint description."""
    try:
        # Your logic here
        result = {"status": "success", "data": data}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

Register in `backend/app.py`:

```python
from .routers import custom_router

app.include_router(custom_router.router)
```

### SSE Streaming

For real-time streaming responses:

```python
from fastapi import Response
from fastapi.responses import StreamingResponse
import asyncio
import json

async def stream_generator(data: str):
    """Generator for SSE streaming."""
    chunks = [data[i:i+10] for i in range(0, len(data), 10)]
    for chunk in chunks:
        yield f"data: {json.dumps({'content': chunk})}\n\n"
        await asyncio.sleep(0.1)

@router.get("/stream")
async def stream_endpoint():
    """Stream response endpoint."""
    return StreamingResponse(
        stream_generator("Hello, World!"),
        media_type="text/event-stream"
    )
```

## Webview Development

### React Components

Webview components use React with Ant Design:

```tsx
import React, { useState, useEffect } from 'react';
import { Button, Input } from 'antd';
import type { VSCodeAPI } from '../types';

const vscode = acquireVsCodeApi();

export const MyComponent: React.FC = () => {
    const [data, setData] = useState<string>('');

    useEffect(() => {
        // Listen for messages from extension
        const handleMessage = (event: MessageEvent) => {
            const message = event.data;
            switch (message.command) {
                case 'updateData':
                    setData(message.data);
                    break;
            }
        };

        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, []);

    const handleClick = () => {
        // Send message to extension
        vscode.postMessage({
            command: 'myCommand',
            data: data
        });
    };

    return (
        <div style={{ padding: '20px' }}>
            <Input
                value={data}
                onChange={(e) => setData(e.target.value)}
                placeholder="Enter data"
            />
            <Button onClick={handleClick}>Send</Button>
        </div>
    );
};
```

### Theme Integration

Use VSCode theme variables:

```tsx
const themedStyle = {
    backgroundColor: 'var(--vscode-editor-background)',
    color: 'var(--vscode-editor-foreground)',
    border: '1px solid var(--vscode-panel-border)'
};
```

## Testing and Debugging

### Debugging the Extension

1. Open `extension/` in VSCode
2. Press F5 to launch Extension Development Host
3. In the new window, open Command Palette and run your command

### Debugging the Backend

```bash
cd packages/agentsociety2
uv run python -m agentsociety2.backend.run
```

With debugger:

```bash
uv run python -m debugpy --listen 5678 -m agentsociety2.backend.run
```

Then attach in VSCode using Python debugger.

### Running Tests

```bash
# Frontend tests
cd extension
npm test

# Backend tests
cd packages/agentsociety2
pytest
```

## Packaging and Publishing

### Build for Production

```bash
cd extension
npm run vscode:prepublish  # Build everything
vsce package              # Create .vsix file
```

### Publishing to Marketplace

```bash
vsce publish
```

Ensure you have a `publisher` configured in `package.json` and a
Personal Access Token from `https://dev.azure.com/`.

## Extension Settings

Add configuration settings in `package.json`:

```json
{
    "configuration": {
        "title": "AI Social Scientist",
        "properties": {
            "aiSocialScientist.backendUrl": {
                "type": "string",
                "default": "http://localhost:8001",
                "description": "Backend service URL"
            },
            "aiSocialScientist.enableDebug": {
                "type": "boolean",
                "default": false,
                "description": "Enable debug logging"
            }
        }
    }
}
```

Access in extension code:

```typescript
const config = vscode.workspace.getConfiguration('aiSocialScientist');
const backendUrl = config.get('backendUrl', 'http://localhost:8001');
```

## Useful Resources

- [VSCode Extension API](https://code.visualstudio.com/api)
- [VSCode Extension Samples](https://github.com/Microsoft/vscode-extension-samples)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Ant Design Documentation](https://ant.design/)

## Contributing

When contributing to the extension:

1. Follow the existing code style
2. Add tests for new features
3. Update documentation
4. Test on both Windows and macOS/Linux
5. Ensure accessibility standards are met

## Troubleshooting

### Common Issues

1. **Webview not loading**: Check webview.asWebviewUri() paths
2. **Backend connection refused**: Verify backend is running and CORS settings
3. **Tools not available**: Check tool registration in registry.py
4. **Messages not received**: Verify message event listeners

### Debug Mode

Enable debug logging in settings:

```json
{
    "aiSocialScientist.enableDebug": true
}
```

Then check the "Output" panel in VSCode for "AI Social Scientist" channel.
