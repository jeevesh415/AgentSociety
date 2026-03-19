/**
 * Environment Manager - .env file operations
 *
 * Handles reading and writing .env files in the workspace root.
 * This provides a unified way to manage secrets and configuration
 * across backend, skills, and other components.
 *
 * 关联文件：
 * - @extension/src/configPageViewProvider.ts - 配置页面使用EnvManager读写.env
 * - @extension/src/services/backendManager.ts - 后端管理器使用EnvManager读取配置
 *
 * 相关环境变量（.env文件）：
 * - LLM配置: AGENTSOCIETY_LLM_API_KEY, AGENTSOCIETY_LLM_API_BASE, AGENTSOCIETY_LLM_MODEL
 * - 后端配置: BACKEND_HOST, BACKEND_PORT, BACKEND_LOG_LEVEL
 * - Python路径: PYTHON_PATH
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

export interface EnvConfig {
  // LLM Configuration
  llmApiKey?: string;
  llmApiBase?: string;
  llmModel?: string;

  // Coder LLM
  coderLlmApiKey?: string;
  coderLlmApiBase?: string;
  coderLlmModel?: string;

  // Nano LLM
  nanoLlmApiKey?: string;
  nanoLlmApiBase?: string;
  nanoLlmModel?: string;

  // Embedding
  embeddingApiKey?: string;
  embeddingApiBase?: string;
  embeddingModel?: string;
  embeddingDims?: number;

  // Backend
  backendHost?: string;
  backendPort?: number;
  backendPid?: number;
  backendLogLevel?: string;
  pythonPath?: string;

  // Web Search
  webSearchApiUrl?: string;
  webSearchApiToken?: string;

  // Miroflow
  miroflowDefaultLlm?: string;
  miroflowDefaultAgent?: string;

  // EasyPaper
  easypaperApiUrl?: string;
  easypaperLlmApiKey?: string;
  easypaperLlmModel?: string;
  easypaperVlmModel?: string;
  easypaperVlmApiKey?: string;

  // Literature Search
  literatureSearchApiUrl?: string;
}

/**
 * Map internal config keys to .env variable names
 */
const ENV_KEY_MAP: Record<keyof EnvConfig, string> = {
  llmApiKey: 'AGENTSOCIETY_LLM_API_KEY',
  llmApiBase: 'AGENTSOCIETY_LLM_API_BASE',
  llmModel: 'AGENTSOCIETY_LLM_MODEL',
  coderLlmApiKey: 'AGENTSOCIETY_CODER_LLM_API_KEY',
  coderLlmApiBase: 'AGENTSOCIETY_CODER_LLM_API_BASE',
  coderLlmModel: 'AGENTSOCIETY_CODER_LLM_MODEL',
  nanoLlmApiKey: 'AGENTSOCIETY_NANO_LLM_API_KEY',
  nanoLlmApiBase: 'AGENTSOCIETY_NANO_LLM_API_BASE',
  nanoLlmModel: 'AGENTSOCIETY_NANO_LLM_MODEL',
  embeddingApiKey: 'AGENTSOCIETY_EMBEDDING_API_KEY',
  embeddingApiBase: 'AGENTSOCIETY_EMBEDDING_API_BASE',
  embeddingModel: 'AGENTSOCIETY_EMBEDDING_MODEL',
  embeddingDims: 'AGENTSOCIETY_EMBEDDING_DIMS',
  backendHost: 'BACKEND_HOST',
  backendPort: 'BACKEND_PORT',
  backendPid: 'BACKEND_PID',
  backendLogLevel: 'BACKEND_LOG_LEVEL',
  pythonPath: 'PYTHON_PATH',
  webSearchApiUrl: 'WEB_SEARCH_API_URL',
  webSearchApiToken: 'WEB_SEARCH_API_TOKEN',
  miroflowDefaultLlm: 'MIROFLOW_DEFAULT_LLM',
  miroflowDefaultAgent: 'MIROFLOW_DEFAULT_AGENT',
  easypaperApiUrl: 'EASYPAPER_API_URL',
  easypaperLlmApiKey: 'EASYPAPER_LLM_API_KEY',
  easypaperLlmModel: 'EASYPAPER_LLM_MODEL',
  easypaperVlmModel: 'EASYPAPER_VLM_MODEL',
  easypaperVlmApiKey: 'EASYPAPER_VLM_API_KEY',
  literatureSearchApiUrl: 'LITERATURE_SEARCH_API_URL',
};

/**
 * Default values for configuration
 */
const DEFAULT_VALUES: Partial<EnvConfig> = {
  llmApiBase: 'https://cloud.infini-ai.com/maas/v1',
  llmModel: 'qwen3-next-80b-a3b-instruct',
  backendHost: '127.0.0.1',
  backendPort: 8001,
  backendLogLevel: 'info',
  coderLlmModel: 'glm-4.7',
  nanoLlmModel: 'qwen3-next-80b-a3b-instruct',
  embeddingModel: 'bge-m3',
  embeddingDims: 1024,
  miroflowDefaultLlm: 'qwen-3',
  miroflowDefaultAgent: 'mirothinker_v1.5_keep5_max200',
  easypaperLlmModel: 'qwen3-next-80b-a3b-instruct',
  easypaperVlmModel: 'qwen3-vl-235b-a22b-thinking',
  literatureSearchApiUrl: 'http://localhost:8002/api/v1/search',
};

export class EnvManager {
  private outputChannel: vscode.OutputChannel;

  constructor() {
    this.outputChannel = vscode.window.createOutputChannel('Env Manager');
  }

  private log(message: string): void {
    this.outputChannel.appendLine(`${new Date().toISOString()} ${message}`);
  }

  /**
   * Get workspace path
   */
  getWorkspacePath(): string | null {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    return workspaceFolder ? workspaceFolder.uri.fsPath : null;
  }

  /**
   * Get .env file path
   */
  getEnvPath(): string | null {
    const workspacePath = this.getWorkspacePath();
    return workspacePath ? path.join(workspacePath, '.env') : null;
  }

  /**
   * Check if .env file exists
   */
  envExists(): boolean {
    const envPath = this.getEnvPath();
    return envPath ? fs.existsSync(envPath) : false;
  }

  /**
   * Read .env file and parse into EnvConfig
   */
  readEnv(): EnvConfig {
    const envPath = this.getEnvPath();
    if (!envPath || !fs.existsSync(envPath)) {
      return { ...DEFAULT_VALUES };
    }

    const config: EnvConfig = { ...DEFAULT_VALUES };
    const content = fs.readFileSync(envPath, 'utf-8');
    const lines = content.split('\n');

    for (const line of lines) {
      const trimmed = line.trim();
      // Skip empty lines and comments
      if (!trimmed || trimmed.startsWith('#')) {
        continue;
      }

      // Parse KEY=VALUE
      const match = trimmed.match(/^([^=]+)=(.*)$/);
      if (!match) {
        continue;
      }

      const [, key, value] = match;
      const envVar = key.trim();

      // Find matching config key
      for (const [configKey, envName] of Object.entries(ENV_KEY_MAP)) {
        if (envName === envVar) {
          // Type conversion
          if (configKey === 'backendPort' || configKey === 'backendPid' || configKey === 'embeddingDims') {
            (config as any)[configKey] = parseInt(value, 10);
          } else {
            (config as any)[configKey] = value;
          }
          break;
        }
      }
    }

    return config;
  }

  /**
   * Write EnvConfig to .env file
   * Handles duplicate keys by keeping only the first occurrence
   */
  writeEnv(config: Partial<EnvConfig>): void {
    const envPath = this.getEnvPath();
    if (!envPath) {
      throw new Error('No workspace folder open');
    }

    // Read existing .env to preserve comments and unknown variables
    const existingLines: string[] = [];
    if (fs.existsSync(envPath)) {
      const content = fs.readFileSync(envPath, 'utf-8').trimEnd();
      existingLines.push(...content.split('\n'));
    }

    // Track which keys have been written (to handle duplicates)
    const writtenKeys = new Set<string>();
    const writtenEnvKeys = new Set<string>(); // Track env keys that have been written
    const newLines: string[] = [];

    // Process existing lines
    for (const line of existingLines) {
      const trimmed = line.trim();
      // Preserve comments and empty lines
      if (!trimmed || trimmed.startsWith('#')) {
        newLines.push(line);
        continue;
      }

      // Check if this is a known env variable
      const match = trimmed.match(/^([^=]+)=(.*)$/);
      if (match) {
        const key = match[1].trim();
        if (Object.values(ENV_KEY_MAP).includes(key)) {
          // Skip if this env key has already been written (handle duplicates)
          if (writtenEnvKeys.has(key)) {
            continue;
          }
          // Update value from config
          const configKey = this.getConfigKeyForEnv(key);
          if (configKey && config[configKey] !== undefined) {
            newLines.push(`${key}=${this.formatValue(config[configKey])}`);
            writtenKeys.add(configKey);
            writtenEnvKeys.add(key);
          } else {
            // Keep existing value if not in config
            newLines.push(line);
            writtenEnvKeys.add(key);
          }
        } else {
          // Preserve unknown variables
          newLines.push(line);
        }
      } else {
        newLines.push(line);
      }
    }

    // Add new values that weren't in the file
    for (const [configKey, envName] of Object.entries(ENV_KEY_MAP)) {
      if (!writtenKeys.has(configKey) && config[configKey as keyof EnvConfig] !== undefined) {
        newLines.push(`${envName}=${this.formatValue(config[configKey as keyof EnvConfig])}`);
      }
    }

    // Write to file
    fs.writeFileSync(envPath, newLines.join('\n') + '\n', 'utf-8');
    this.log(`Updated .env file: ${envPath}`);
  }

  /**
   * Get config key for environment variable name
   */
  private getConfigKeyForEnv(envName: string): keyof EnvConfig | undefined {
    for (const [configKey, name] of Object.entries(ENV_KEY_MAP)) {
      if (name === envName) {
        return configKey as keyof EnvConfig;
      }
    }
    return undefined;
  }

  /**
   * Format value for .env file
   */
  private formatValue(value: any): string {
    if (typeof value === 'string') {
      // Escape if contains special characters
      if (value.includes(' ') || value.includes('"') || value.includes("'") || value.includes('#')) {
        return `"${value.replace(/"/g, '\\"')}"`;
      }
      return value;
    }
    return String(value);
  }

  /**
   * Get .env.example content
   */
  static getExampleContent(): string {
    return `# AgentSociety Environment Configuration / AgentSociety 环境配置
# Copy this file to .env and fill in your API keys / 复制此文件为 .env 并填写您的 API 密钥

# ========== LLM Configuration / LLM 配置 ==========
# Default LLM for general operations / 默认 LLM，用于一般操作
# LLM API Key / LLM API 密钥
AGENTSOCIETY_LLM_API_KEY=your-api-key-here
# LLM API Base URL / LLM API 基础 URL
AGENTSOCIETY_LLM_API_BASE=https://cloud.infini-ai.com/maas/v1
# LLM Model Name / LLM 模型名称
AGENTSOCIETY_LLM_MODEL=qwen3-next-80b-a3b-instruct

# ========== Coder LLM / Coder LLM (代码生成) ==========
# Coder LLM for code generation / 用于代码生成的 LLM
AGENTSOCIETY_CODER_LLM_API_KEY=
AGENTSOCIETY_CODER_LLM_API_BASE=
AGENTSOCIETY_CODER_LLM_MODEL=glm-4.7

# ========== Nano LLM / Nano LLM (高频操作) ==========
# Nano LLM for high-frequency operations / 用于高频操作的轻量级 LLM
AGENTSOCIETY_NANO_LLM_API_KEY=
AGENTSOCIETY_NANO_LLM_API_BASE=
AGENTSOCIETY_NANO_LLM_MODEL=qwen3-next-80b-a3b-instruct

# ========== Embedding Model / 嵌入模型 ==========
# Embedding model for vector search / 用于向量搜索的嵌入模型
AGENTSOCIETY_EMBEDDING_API_KEY=
AGENTSOCIETY_EMBEDDING_API_BASE=
AGENTSOCIETY_EMBEDDING_MODEL=bge-m3
AGENTSOCIETY_EMBEDDING_DIMS=1024

# ========== Backend Configuration / 后端配置 ==========
# Backend host / 后端主机地址
BACKEND_HOST=127.0.0.1
# Backend port / 后端端口
BACKEND_PORT=8001
# Log level (debug, info, warning, error) / 日志级别
BACKEND_LOG_LEVEL=info
# Python executable path / Python 可执行文件路径
PYTHON_PATH=

# ========== Web Search / 网络搜索 ==========
# Web search API URL / 网络搜索 API 地址
WEB_SEARCH_API_URL=
# Web search API token / 网络搜索 API 令牌
WEB_SEARCH_API_TOKEN=

# ========== Miroflow / Miroflow 配置 ==========
# Default LLM for Miroflow / Miroflow 默认 LLM
MIROFLOW_DEFAULT_LLM=qwen-3
# Default agent for Miroflow / Miroflow 默认代理
MIROFLOW_DEFAULT_AGENT=mirothinker_v1.5_keep5_max200

# ========== EasyPaper / EasyPaper 配置 ==========
# EasyPaper API URL / EasyPaper API 地址
EASYPAPER_API_URL=
# EasyPaper LLM API Key / EasyPaper LLM API 密钥
EASYPAPER_LLM_API_KEY=
# EasyPaper LLM Model / EasyPaper LLM 模型
EASYPAPER_LLM_MODEL=qwen3-next-80b-a3b-instruct
# EasyPaper VLM Model / EasyPaper 视觉语言模型
EASYPAPER_VLM_MODEL=qwen3-vl-235b-a22b-thinking
# EasyPaper VLM API Key / EasyPaper VLM API 密钥
EASYPAPER_VLM_API_KEY=

# ========== Literature Search / 文献搜索 ==========
# Literature search API URL / 文献搜索 API 地址
LITERATURE_SEARCH_API_URL=http://localhost:8002/api/v1/search
`;
  }

  /**
   * Create .env file from example if it doesn't exist
   */
  createEnvFromExample(): boolean {
    const envPath = this.getEnvPath();
    if (!envPath) {
      return false;
    }

    if (fs.existsSync(envPath)) {
      return false; // Already exists
    }

    fs.writeFileSync(envPath, EnvManager.getExampleContent(), 'utf-8');
    this.log(`Created .env file from example: ${envPath}`);
    return true;
  }

  /**
   * Dispose
   */
  dispose(): void {
    this.outputChannel.dispose();
  }
}
