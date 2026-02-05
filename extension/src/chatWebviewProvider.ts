/**
 * ChatWebviewProvider - 聊天 Webview 提供者
 *
 * 职责：Webview 生命周期管理和消息路由。
 *
 * 服务依赖：
 * - BackendService: 后端通信
 * - ConversationService: 对话管理
 * - HistoryService: 历史记录管理
 */

import * as vscode from 'vscode';
import * as path from 'path';
import type { WebViewToExtensionMessage } from './shared/messages';
import { BackendService, ConversationService, HistoryService } from './services';
import { localize } from './i18n';

export class ChatWebviewProvider {
  public static currentPanel: ChatWebviewProvider | undefined;
  private static readonly viewType = 'aiSocialScientistChat';

  private readonly panel: vscode.WebviewPanel;
  private readonly extensionUri: vscode.Uri;
  private readonly backendService: BackendService;
  private readonly conversationService: ConversationService;
  private readonly historyService: HistoryService;
  private disposables: vscode.Disposable[] = [];

  /**
   * Create or show the chat panel (singleton pattern)
   */
  public static createOrShow(context: vscode.ExtensionContext) {
    if (ChatWebviewProvider.currentPanel) {
      ChatWebviewProvider.currentPanel.panel.reveal(vscode.ViewColumn.Beside);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      ChatWebviewProvider.viewType,
      'AI Social Scientist Chat',
      vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [context.extensionUri],
      }
    );

    ChatWebviewProvider.currentPanel = new ChatWebviewProvider(panel, context);
  }

  private constructor(panel: vscode.WebviewPanel, context: vscode.ExtensionContext) {
    this.panel = panel;
    this.extensionUri = context.extensionUri;

    // Initialize services
    this.backendService = new BackendService(context);
    this.historyService = new HistoryService();
    this.conversationService = new ConversationService(this.backendService, this.historyService);

    // Set webview content
    this.panel.webview.html = this.getHtmlForWebview();

    // Register event listeners
    this.panel.onDidDispose(() => this.dispose(), null, this.disposables);

    this.panel.webview.onDidReceiveMessage(
      (message: WebViewToExtensionMessage) => this.handleMessage(message),
      null,
      this.disposables
    );

    // Initialize
    this.checkBackendHealth();
    this.listHistories();
  }

  /**
   * Handle messages from webview
   */
  private async handleMessage(message: WebViewToExtensionMessage): Promise<void> {
    switch (message.command) {
      case 'sendMessage':
        await this.handleSendMessage(message.text);
        break;

      case 'clearChat':
        this.handleClearChat();
        break;

      case 'checkHealth':
        await this.checkBackendHealth();
        break;

      case 'openFile':
        this.handleOpenFile(message.filePath, message.line);
        break;

      case 'loadHistory':
        await this.handleLoadHistory(message.historyFileName);
        break;

      case 'listHistories':
        await this.listHistories();
        break;

      case 'interrupt':
        this.conversationService.interrupt();
        break;
    }
  }

  /**
   * Handle send message command
   */
  private async handleSendMessage(text: string): Promise<void> {
    await this.conversationService.sendMessage(
      text,
      // SSE event handler
      (event) => {
        this.postMessage({ command: 'sseEvent', event });
      },
      // Error handler
      (error) => {
        vscode.window.showErrorMessage(localize('chatWebview.chatFailed', error.message));
      },
      // Complete handler
      () => {
        // No additional action needed on complete
      }
    );
  }

  /**
   * Handle clear chat command
   */
  private handleClearChat(): void {
    this.conversationService.clear();
    this.postMessage({ command: 'clearMessages' });
  }

  /**
   * Handle open file command
   */
  private handleOpenFile(filePath: string, line?: number): void {
    if (filePath) {
      const fileUri = vscode.Uri.file(filePath);
      vscode.window.showTextDocument(fileUri, {
        selection: line ? new vscode.Range(line - 1, 0, line - 1, 0) : undefined,
      });
    }
  }

  /**
   * Handle load history command
   */
  private async handleLoadHistory(fileName: string): Promise<void> {
    try {
      await this.conversationService.loadFromHistory(fileName);

      const state = this.conversationService.getState();
      const messagesForWebview = state.messages.map((msg) => ({
        role: msg.role,
        content: msg.content || '',
      }));

      const sseEventsForWebview = Array.from(state.sseEventsHistory.entries()).map(
        ([index, events]) => ({
          userMessageIndex: index,
          events,
        })
      );

      this.postMessage({
        command: 'historyLoaded',
        messages: messagesForWebview,
        sseEvents: sseEventsForWebview,
      });
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      vscode.window.showErrorMessage(`Failed to load history: ${errorMessage}`);
      this.postMessage({
        command: 'historyLoadError',
        error: errorMessage,
      });
    }
  }

  /**
   * Check backend health status
   */
  private async checkBackendHealth(): Promise<void> {
    const status = await this.backendService.getStatus();
    this.postMessage({
      command: 'backendStatus',
      connected: status.connected,
      url: status.url,
    });
  }

  /**
   * List all history files
   */
  private async listHistories(): Promise<void> {
    const histories = await this.historyService.list();
    this.postMessage({
      command: 'historyList',
      histories,
    });
  }

  /**
   * Post message to webview
   */
  private postMessage(message: unknown): void {
    this.panel.webview.postMessage(message);
  }

  /**
   * Generate HTML for webview
   */
  private getHtmlForWebview(): string {
    const scriptUri = this.panel.webview.asWebviewUri(
      vscode.Uri.file(path.join(this.extensionUri.fsPath, 'out', 'webview', 'chat.js'))
    );

    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Social Scientist Chat</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            background-color: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
            height: 100vh;
            overflow: hidden;
        }

        #root {
            height: 100vh;
        }

        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes thinkingPulse {
            0%, 80%, 100% {
                opacity: 0.3;
                transform: scale(0.8);
            }
            40% {
                opacity: 1;
                transform: scale(1);
            }
        }
    </style>
</head>
<body>
    <div id="root"></div>
    <script src="${scriptUri}"></script>
</body>
</html>`;
  }

  /**
   * Dispose resources
   */
  public dispose(): void {
    ChatWebviewProvider.currentPanel = undefined;

    this.panel.dispose();
    this.backendService.dispose();

    while (this.disposables.length) {
      const disposable = this.disposables.pop();
      if (disposable) {
        disposable.dispose();
      }
    }
  }
}
