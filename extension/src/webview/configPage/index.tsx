import * as React from 'react';
import * as ReactDOM from 'react-dom/client';
import { ConfigPageApp } from './ConfigPageApp';
import type { VSCodeAPI } from './types';
import 'antd/dist/reset.css';

declare function acquireVsCodeApi(): VSCodeAPI;

const vscode: VSCodeAPI = acquireVsCodeApi();

const rootElement = document.getElementById('root');
if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(<ConfigPageApp vscode={vscode} />);
} else {
  console.error('Root element not found');
}
