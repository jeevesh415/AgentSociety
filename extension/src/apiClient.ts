import * as vscode from 'vscode';

/**
 * API客户端 - 用于与FastAPI后端通信
 */
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
  data?: Record<string, any>; // Tool result data (e.g., literature search results)
}

/**
 * SSE事件类型
 */
export type SSEEventType = 'message' | 'tool' | 'complete' | 'heartbeat';

/**
 * SSE消息事件（MessageEvent）
 * 完全匹配后端 sse/models.py 中的 MessageEvent
 */
export interface MessageSSEEvent {
  type: 'message';
  content: string;
  is_thinking: boolean;
  is_error: boolean;
}

/**
 * SSE工具事件（ToolEvent）
 * 完全匹配后端 sse/models.py 中的 ToolEvent
 */
export interface ToolSSEEvent {
  type: 'tool';
  content: string;
  tool_name: string;
  tool_id: string;
  status: 'start' | 'progress' | 'success' | 'error';
}

/**
 * SSE完成事件（CompleteEvent）
 * 完全匹配后端 sse/models.py 中的 CompleteEvent
 */
export interface CompleteSSEEvent {
  type: 'complete';
  content: string;
}

/**
 * SSE心跳事件（HeartbeatEvent）
 * 完全匹配后端 sse/models.py 中的 HeartbeatEvent
 * 前端应该直接丢弃此事件，仅用于保持连接活跃
 */
export interface HeartbeatSSEEvent {
  type: 'heartbeat';
  content: string;
}

/**
 * SSE事件联合类型
 */
export type SSEEvent = MessageSSEEvent | ToolSSEEvent | CompleteSSEEvent | HeartbeatSSEEvent;

export interface CompletionRequest {
  messages: ChatMessage[];
  workspace_path: string;
}

export interface CompletionResponse {
  success: boolean;
  messages: ChatMessage[];
  final_answer?: string;
  tool_calls?: Array<{
    id: string;
    name: string;
    arguments: Record<string, any>;
  }>;
  is_complete: boolean;
  turn_count: number;
  message?: string;
}

export interface MinerUParseRequest {
  file_path: string;
  workspace_path: string;
}

export interface MinerUParseResponse {
  success: boolean;
  message: string;
  parsed_file_path?: string;
  content_preview?: string;
}

export interface LiteratureDeleteRequest {
  file_path: string;
  workspace_path: string;
}

export interface LiteratureDeleteResponse {
  success: boolean;
  message: string;
}

export interface LiteratureRenameRequest {
  file_path: string;
  new_name: string;
  workspace_path: string;
}

export interface LiteratureRenameResponse {
  success: boolean;
  message: string;
  new_file_path?: string;
}

export interface AgentInfo {
  type: string;
  class_name: string;
  description: string;
}

export interface EnvModuleInfo {
  type: string;
  class_name: string;
  description: string;
}

export interface AgentsListResponse {
  success: boolean;
  agents: Record<string, AgentInfo>;
  count: number;
}

export interface EnvModulesListResponse {
  success: boolean;
  modules: Record<string, EnvModuleInfo>;
  count: number;
}

export interface WorkspaceInitRequest {
  workspace_path: string;
  topic: string;
}

export interface WorkspaceInitResponse {
  success: boolean;
  message: string;
  data?: {
    workspace_path: string;
    files_created: string[];
  };
}

export interface PrefillParams {
  version?: string;
  env_modules: Record<string, Record<string, any>>;
  agents: Record<string, Record<string, any>>;
}

export interface PrefillParamsResponse {
  success: boolean;
  data: PrefillParams;
}

export interface ClassPrefillParamsResponse {
  success: boolean;
  class_kind: string;
  class_name: string;
  params: Record<string, any>;
}

export interface ClassInfo {
  type: string;
  class_name: string;
  description: string;
  has_prefill?: boolean;
}

export interface AvailableClassesResponse {
  success: boolean;
  env_modules: Record<string, ClassInfo>;
  agents: Record<string, ClassInfo>;
  env_module_count: number;
  agent_count: number;
}

export class ApiClient {
  private baseUrl: string;
  private outputChannel: vscode.OutputChannel;

  constructor(context: vscode.ExtensionContext) {
    // 从配置读取后端URL，默认为 http://localhost:8001
    const config = vscode.workspace.getConfiguration('aiSocialScientist');
    this.baseUrl = config.get<string>('backendUrl', 'http://localhost:8001');
    this.outputChannel = vscode.window.createOutputChannel('AI Social Scientist API');

    // 监听配置变化
    context.subscriptions.push(
      vscode.workspace.onDidChangeConfiguration(e => {
        if (e.affectsConfiguration('aiSocialScientist.backendUrl')) {
          this.baseUrl = config.get<string>('backendUrl', 'http://localhost:8001');
          this.log(`Backend URL updated to: ${this.baseUrl}`);
        }
      })
    );
  }

  private log(message: string): void {
    const timestamp = new Date().toISOString();
    this.outputChannel.appendLine(`[${timestamp}] ${message}`);
  }

  /**
   * 获取后端URL
   */
  getBaseUrl(): string {
    return this.baseUrl;
  }

  /**
   * 检查后端健康状态
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
   * 发送对话请求（支持流式和非流式）
   * 注意：后端现在只支持流式SSE响应，非流式请求已废弃
   */
  async chat(
    request: CompletionRequest,
    onStreamEvent: (event: SSEEvent) => void
  ): Promise<CompletionResponse | null> {
    try {
      const url = `${this.baseUrl}/api/v1/chat/completion`;
      this.log(`Sending chat request to ${url}`);

      // 流式请求
      this.log(`[SSE Client] 发送流式请求到 ${url}`);
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`[SSE Client] HTTP错误: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      this.log(`[SSE Client] 开始读取SSE流`);
      // 读取SSE流
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        this.log(`[SSE Client] 错误: Response body不可读`);
        throw new Error('Response body is not readable');
      }

      let buffer = '';
      let eventCount = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          this.log(`[SSE Client] SSE流读取完成，共处理${eventCount}个事件`);
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              this.log(`[SSE Client] 收到[DONE]标记，流式传输结束`);
              return null;
            }
            try {
              const event = JSON.parse(data) as SSEEvent;
              eventCount++;
              this.log(`[SSE Client] 解析事件 #${eventCount}: type=${event.type}`);
              if (onStreamEvent) {
                onStreamEvent(event);
              }
            } catch (e) {
              this.log(`[SSE Client] 解析SSE事件失败: ${data}, 错误: ${e}`);
            }
          }
        }
      }

      this.log(`[SSE Client] SSE流处理完成，返回null`);
      return null;
    } catch (error) {
      this.log(`Chat request failed: ${error}`);
      throw error;
    }
  }


  /**
   * 使用MinerU解析文档
   */
  async parseWithMinerU(request: MinerUParseRequest): Promise<MinerUParseResponse> {
    try {
      const url = `${this.baseUrl}/api/v1/mineru/parse`;
      this.log(`Sending MinerU parse request to ${url} for file: ${request.file_path}`);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`MinerU parse request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as MinerUParseResponse;
      this.log(`MinerU parse response: success=${data.success}, message=${data.message}`);
      return data;
    } catch (error) {
      this.log(`MinerU parse request failed: ${error}`);
      throw error;
    }
  }

  /**
   * 删除文献文件
   */
  async deleteLiterature(request: LiteratureDeleteRequest): Promise<LiteratureDeleteResponse> {
    try {
      const url = `${this.baseUrl}/api/v1/literature/delete`;
      this.log(`Sending delete literature request to ${url} for file: ${request.file_path}`);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Delete literature request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as LiteratureDeleteResponse;
      this.log(`Delete literature response: success=${data.success}, message=${data.message}`);
      return data;
    } catch (error) {
      this.log(`Delete literature request failed: ${error}`);
      throw error;
    }
  }

  /**
   * 重命名文献文件
   */
  async renameLiterature(request: LiteratureRenameRequest): Promise<LiteratureRenameResponse> {
    try {
      const url = `${this.baseUrl}/api/v1/literature/rename`;
      this.log(`Sending rename literature request to ${url} for file: ${request.file_path}`);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Rename literature request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as LiteratureRenameResponse;
      this.log(`Rename literature response: success=${data.success}, message=${data.message}`);
      return data;
    } catch (error) {
      this.log(`Rename literature request failed: ${error}`);
      throw error;
    }
  }

  /**
   * 获取所有可用的Agent类列表
   */
  async getAgentClasses(): Promise<AgentsListResponse> {
    try {
      const url = `${this.baseUrl}/api/v1/modules/agent_classes`;
      this.log(`Fetching agent classes from ${url}`);

      const response = await fetch(url);

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Get agent classes request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as AgentsListResponse;
      this.log(`Agent classes fetched: ${data.count} agents available`);
      return data;
    } catch (error) {
      this.log(`Get agent classes request failed: ${error}`);
      throw error;
    }
  }

  /**
   * 获取所有可用的Environment模块类列表
   */
  async getEnvModules(): Promise<EnvModulesListResponse> {
    try {
      const url = `${this.baseUrl}/api/v1/modules/env_module_classes`;
      this.log(`Fetching env module classes from ${url}`);

      const response = await fetch(url);

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Get env modules request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as EnvModulesListResponse;
      this.log(`Env modules fetched: ${data.count} modules available`);
      return data;
    } catch (error) {
      this.log(`Get env modules request failed: ${error}`);
      throw error;
    }
  }

  /**
   * 初始化工作区
   */
  async initWorkspace(request: WorkspaceInitRequest): Promise<WorkspaceInitResponse> {
    try {
      const url = `${this.baseUrl}/api/v1/workspace/init`;
      this.log(`Sending workspace init request to ${url} for path: ${request.workspace_path}`);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Workspace init request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as WorkspaceInitResponse;
      this.log(`Workspace init response: success=${data.success}, message=${data.message}`);
      return data;
    } catch (error) {
      this.log(`Workspace init request failed: ${error}`);
      throw error;
    }
  }

  /**
   * 获取全局预填充参数
   */
  async getPrefillParams(workspace_path: string): Promise<PrefillParamsResponse> {
    try {
      const url = `${this.baseUrl}/api/v1/prefill-params?workspace_path=${encodeURIComponent(workspace_path)}`;
      this.log(`Fetching prefill params from ${url}`);

      const response = await fetch(url);

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Get prefill params request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as PrefillParamsResponse;
      this.log(`Prefill params fetched successfully`);
      return data;
    } catch (error) {
      this.log(`Get prefill params request failed: ${error}`);
      throw error;
    }
  }

  /**
   * 获取特定类的预填充参数
   */
  async getClassPrefillParams(
    workspace_path: string,
    class_kind: 'env_module' | 'agent',
    class_name: string
  ): Promise<ClassPrefillParamsResponse> {
    try {
      const url = `${this.baseUrl}/api/v1/prefill-params/${class_kind}/${class_name}?workspace_path=${encodeURIComponent(workspace_path)}`;
      this.log(`Fetching class prefill params from ${url}`);

      const response = await fetch(url);

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Get class prefill params request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as ClassPrefillParamsResponse;
      this.log(`Class prefill params fetched successfully`);
      return data;
    } catch (error) {
      this.log(`Get class prefill params request failed: ${error}`);
      throw error;
    }
  }

  /**
   * 列出所有可用的类（Agent和Env Module）
   */
  async getAvailableClasses(workspace_path: string): Promise<AvailableClassesResponse> {
    try {
      const url = `${this.baseUrl}/api/v1/prefill-params/classes?workspace_path=${encodeURIComponent(workspace_path)}`;
      this.log(`Fetching available classes from ${url}`);

      const response = await fetch(url);

      if (!response.ok) {
        const errorText = await response.text();
        this.log(`Get available classes request failed: ${response.status}: ${errorText}`);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json() as AvailableClassesResponse;
      this.log(`Available classes fetched: ${data.env_module_count} env modules, ${data.agent_count} agents`);
      return data;
    } catch (error) {
      this.log(`Get available classes request failed: ${error}`);
      throw error;
    }
  }
}

