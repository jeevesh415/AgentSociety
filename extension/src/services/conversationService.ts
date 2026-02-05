/**
 * ConversationService - 对话管理服务
 *
 * 负责对话状态管理、消息历史、SSE 事件处理。
 */

import * as vscode from 'vscode';
import type { SSEEvent, CompleteSSEEvent } from '../shared/messages';
import { BackendService, type ChatMessage, type CompletionRequest } from './backendService';
import { HistoryService, type SSEEventWithTimestamp } from './historyService';
import { localize } from '../i18n';

export interface ConversationState {
  messages: ChatMessage[];
  sseEventsHistory: Map<number, SSEEventWithTimestamp[]>;
  isProcessing: boolean;
}

type SSEEventHandler = (event: SSEEvent) => void;
type ErrorHandler = (error: Error) => void;
type CompleteHandler = (content: string | null) => void;

export class ConversationService {
  private messages: ChatMessage[] = [];
  private sseEventsHistory: Map<number, SSEEventWithTimestamp[]> = new Map();
  private isProcessing = false;

  constructor(
    private readonly backendService: BackendService,
    private readonly historyService: HistoryService
  ) {}

  /**
   * Get current conversation state
   */
  getState(): ConversationState {
    return {
      messages: [...this.messages],
      sseEventsHistory: new Map(this.sseEventsHistory),
      isProcessing: this.isProcessing,
    };
  }

  /**
   * Get conversation messages
   */
  getMessages(): ChatMessage[] {
    return [...this.messages];
  }

  /**
   * Get SSE events history
   */
  getSSEEventsHistory(): Map<number, SSEEventWithTimestamp[]> {
    return new Map(this.sseEventsHistory);
  }

  /**
   * Check if a conversation is currently being processed
   */
  isConversationProcessing(): boolean {
    return this.isProcessing;
  }

  /**
   * Clear conversation state
   */
  clear(): void {
    this.messages = [];
    this.sseEventsHistory.clear();
    this.isProcessing = false;
    this.historyService.resetCurrentFile();
  }

  /**
   * Load conversation from history
   */
  async loadFromHistory(fileName: string): Promise<void> {
    const historyData = await this.historyService.load(fileName);

    this.messages = historyData.messages;
    this.sseEventsHistory = this.historyService.arrayToMap(historyData.sseEvents);
  }

  /**
   * Send a message and handle the response
   */
  async sendMessage(
    text: string,
    onSSEEvent: SSEEventHandler,
    onError: ErrorHandler,
    onComplete: CompleteHandler
  ): Promise<void> {
    // Validate message
    if (!text.trim()) {
      return;
    }

    // Check if already processing
    if (this.isProcessing) {
      onError(new Error('A conversation is already in progress'));
      return;
    }

    this.isProcessing = true;

    try {
      // Create new history file if needed
      if (this.historyService.getCurrentFilePath() === null) {
        await this.historyService.createNewFile();
      }

      // Add user message to history
      const userMessage: ChatMessage = {
        role: 'user',
        content: text,
      };
      this.messages.push(userMessage);

      // Save history before API request
      await this.historyService.save(this.messages, this.sseEventsHistory);

      // Check backend health
      const isHealthy = await this.backendService.healthCheck();
      if (!isHealthy) {
        throw new Error(localize('chatWebview.noBackend', this.backendService.getBaseUrl()));
      }

      // Get workspace path
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (!workspaceFolder) {
        throw new Error(localize('chatWebview.noWorkspace'));
      }

      console.log('[Conversation] Starting streaming chat request');

      // Track complete event content
      let completeContent: string | null = null;

      // Get current user message index
      const currentUserMessageIndex = this.messages.length - 1;

      // Initialize SSE events array for current message
      if (!this.sseEventsHistory.has(currentUserMessageIndex)) {
        this.sseEventsHistory.set(currentUserMessageIndex, []);
      }

      const request: CompletionRequest = {
        messages: this.messages,
        workspace_path: workspaceFolder.uri.fsPath,
      };

      // Send request and handle SSE events
      await this.backendService.chat(request, (event: SSEEvent) => {
        // Discard heartbeat events
        if (event.type === 'heartbeat') {
          return;
        }

        console.log(`[Conversation] Received event: type=${event.type}`, event);

        // Save SSE event to history
        const events = this.sseEventsHistory.get(currentUserMessageIndex);
        if (events) {
          events.push({
            event,
            timestamp: Date.now(),
          });
        }

        // Check for complete event
        if (event.type === 'complete') {
          const completeEvent = event as CompleteSSEEvent;
          completeContent = completeEvent.content;
        }

        // Forward event to handler
        onSSEEvent(event);
      });

      console.log('[Conversation] Streaming complete');

      // Add assistant message if complete event was received
      if (completeContent !== null && completeContent !== undefined) {
        const content = completeContent as string;
        const assistantMessage: ChatMessage = {
          role: 'assistant',
          content,
        };
        this.messages.push(assistantMessage);

        const previewText =
          content.length > 50 ? content.substring(0, 50) + '...' : content;
        console.log(`[Conversation] Added complete event summary to history: ${previewText}`);

        // Save updated history
        await this.historyService.save(this.messages, this.sseEventsHistory);
      }

      onComplete(completeContent);
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`[Conversation] Error: ${errorMessage}`);
      onError(error instanceof Error ? error : new Error(errorMessage));
    } finally {
      this.isProcessing = false;
    }
  }

  /**
   * Interrupt the current conversation
   */
  interrupt(): void {
    if (this.isProcessing) {
      this.backendService.abortStream();
      this.isProcessing = false;
    }
  }

  /**
   * Restore state from loaded history
   */
  restoreState(messages: ChatMessage[], sseEventsHistory: Map<number, SSEEventWithTimestamp[]>): void {
    this.messages = messages;
    this.sseEventsHistory = sseEventsHistory;
  }
}
