/**
 * AI Social Scientist - 协议常量和工具函数
 */

/** 协议版本 */
export const PROTOCOL_VERSION = '1.0.0';

/** 消息命令常量 */
export const Commands = {
  // WebView → Extension
  SEND_MESSAGE: 'sendMessage',
  CLEAR_CHAT: 'clearChat',
  CHECK_HEALTH: 'checkHealth',
  OPEN_FILE: 'openFile',
  LOAD_HISTORY: 'loadHistory',
  LIST_HISTORIES: 'listHistories',
  TOOL_PERMISSION_RESPONSE: 'toolPermissionResponse',
  INTERRUPT: 'interrupt',

  // Extension → WebView
  SSE_EVENT: 'sseEvent',
  CLEAR_MESSAGES: 'clearMessages',
  BACKEND_STATUS: 'backendStatus',
  HISTORY_LOADED: 'historyLoaded',
  HISTORY_LIST: 'historyList',
  HISTORY_LOAD_ERROR: 'historyLoadError',
  TOOL_PERMISSION_REQUEST: 'toolPermissionRequest',
  EXPERIMENT_STATUS: 'experimentStatus',
} as const;

/** 工具风险等级 */
export const RiskLevel = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
} as const;

/** 实验状态 */
export const ExperimentStatus = {
  PENDING: 'pending',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
} as const;

/** SSE 事件类型 */
export const SSEEventTypes = {
  MESSAGE: 'message',
  TOOL: 'tool',
  COMPLETE: 'complete',
  HEARTBEAT: 'heartbeat',
} as const;

/** 工具执行状态 */
export const ToolStatus = {
  START: 'start',
  PROGRESS: 'progress',
  SUCCESS: 'success',
  ERROR: 'error',
} as const;
