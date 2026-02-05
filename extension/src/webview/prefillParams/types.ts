/**
 * 预填充参数Webview的类型定义
 */

export interface VSCodeAPI {
  postMessage(message: any): void;
  getState(): any;
  setState(state: any): void;
}

export interface ClassInfo {
  type: string;
  class_name: string;
  description: string;
  has_prefill?: boolean;
}

export interface AvailableClasses {
  success: boolean;
  env_modules: Record<string, ClassInfo>;
  agents: Record<string, ClassInfo>;
  env_module_count: number;
  agent_count: number;
}

export interface PrefillParams {
  version?: string;
  env_modules: Record<string, Record<string, any>>;
  agents: Record<string, Record<string, any>>;
}
