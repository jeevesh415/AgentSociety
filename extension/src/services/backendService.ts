/**
 * BackendService - 后端通信服务
 *
 * 负责与 FastAPI 后端的所有 HTTP/SSE 通信。
 * 从 apiClient.ts 提取核心通信逻辑，提供更清晰的接口。
 */

import * as vscode from 'vscode';
import type { SSEEvent } from '../shared/messages';

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content?: string;
  tool_calls?: Array<{
    id: string;
    type: string;
    function: {
      name: string;
      arguments: string;
    };
  }>;
  tool_call_id?: string;
  name?: string;
  data?: Record<string, unknown>;
}

export interface CompletionRequest {
  messages: ChatMessage[];
  workspace_path: string;
}

export interface BackendStatus {
  connected: boolean;
  url: string;
  error?: string;
}

type SSEEventCallback = (event: SSEEvent) => void;

export class BackendService {
  private baseUrl: string;
  private outputChannel: vscode.OutputChannel;
  private disposables: vscode.Disposable[] = [];
  private abortController: AbortController | null = null;

  constructor(context: vscode.ExtensionContext) {
    const config = vscode.workspace.getConfiguration('aiSocialScientist');
    this.baseUrl = config.get<string>('backendUrl', 'http://localhost:8001');
    this.outputChannel = vscode.window.createOutputChannel('AI Social Scientist Backend');

    // Monitor configuration changes
    const configChangeDisposable = vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration('aiSocialScientist.backendUrl')) {
        this.baseUrl = config.get<string>('backendUrl', 'http://localhost:8001');
        this.log(`Backend URL updated to: ${this.baseUrl}`);
      }
    });
    this.disposables.push(configChangeDisposable);
    context.subscriptions.push(configChangeDisposable);
  }

  private log(message: string): void {
    const timestamp = new Date().toISOString();
    this.outputChannel.appendLine(`[${timestamp}] ${message}`);
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  /**
   * Check backend health status
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      return response.ok;
    } catch (error) {
      this.log(`Health check failed: ${error}`);
      return false;
    }
  }

  /**
   * Get backend status
   */
  async getStatus(): Promise<BackendStatus> {
    const connected = await this.healthCheck();
    return {
      connected,
      url: this.baseUrl,
    };
  }

  /**
   * Abort the current SSE stream
   */
  abortStream(): void {
    if (this.abortController) {
      this.log('[SSE] Aborting current stream');
      this.abortController.abort();
      this.abortController = null;
    }
  }

  /**
   * Send chat request with SSE streaming
   */
  async chat(request: CompletionRequest, onEvent: SSEEventCallback): Promise<void> {
    // Abort any existing stream
    this.abortStream();

    // Create new abort controller
    this.abortController = new AbortController();

    try {
      const url = `${this.baseUrl}/api/v1/chat/completion`;
      this.log(`[SSE] Sending streaming request to ${url}`);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`[SSE] HTTP error: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      this.log('[SSE] Starting to read SSE stream');

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        this.log('[SSE] Error: Response body is not readable');
        throw new Error('Response body is not readable');
      }

      let buffer = '';
      let eventCount = 0;

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            this.log(`[SSE] Stream reading complete, processed ${eventCount} events`);
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') {
                this.log('[SSE] Received [DONE] marker, stream ended');
                return;
              }
              try {
                const event = JSON.parse(data) as SSEEvent;
                eventCount++;
                this.log(`[SSE] Parsed event #${eventCount}: type=${event.type}`);
                onEvent(event);
              } catch (e) {
                this.log(`[SSE] Failed to parse SSE event: ${data}, error: ${e}`);
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    } catch (error: unknown) {
      if (error instanceof Error && error.name === 'AbortError') {
        this.log('[SSE] Stream was aborted');
        return;
      }
      this.log(`Chat request failed: ${error}`);
      throw error;
    } finally {
      this.abortController = null;
    }
  }

  dispose(): void {
    this.abortStream();
    this.disposables.forEach((d) => d.dispose());
    this.outputChannel.dispose();
  }
}
