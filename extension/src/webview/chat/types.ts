/**
 * VSCode Webview API 类型定义
 */
export interface VSCodeAPI {
  postMessage(message: any): void;
  getState(): any;
  setState(state: any): void;
}

// 从共享模块重新导出类型
export type {
  SSEEventType,
  SSEEvent,
  MessageSSEEvent,
  ToolSSEEvent,
  CompleteSSEEvent,
  HeartbeatSSEEvent,
  ChatMessage,
  ConversationProcess,
  HistoryItem,
  BackendStatus,
  WebViewToExtensionMessage,
  ExtensionToWebViewMessage,
} from '../../shared/messages';

// 为了向后兼容，保留旧的类型别名
export type { ExtensionToWebViewMessage as ExtensionMessage } from '../../shared/messages';
export type { WebViewToExtensionMessage as WebviewMessage } from '../../shared/messages';

