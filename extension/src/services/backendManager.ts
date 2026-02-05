/**
 * BackendManager - 后端服务管理器
 *
 * 负责启动、停止和管理 FastAPI 后端服务进程。
 * 支持自动启动、健康检查、进程状态管理和日志输出。
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { spawn, ChildProcess, execSync } from 'child_process';
import { localize } from '../i18n';

export interface BackendStatus {
  isRunning: boolean;
  pid?: number;
  port?: number;
  error?: string;
}

export interface BackendConfig {
  pythonPath: string;
  workingDirectory: string;
  autoStart: boolean;
  env: Record<string, string>;
}

export class BackendManager {
  private process: ChildProcess | null = null;
  private outputChannel: vscode.OutputChannel;
  private statusBarItem: vscode.StatusBarItem;
  private config: BackendConfig;
  private context: vscode.ExtensionContext;
  private healthCheckInterval: NodeJS.Timeout | null = null;
  private isStarting = false;

  constructor(context: vscode.ExtensionContext) {
    this.context = context;
    this.outputChannel = vscode.window.createOutputChannel('AI Social Scientist Backend');
    this.statusBarItem = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Right,
      100
    );
    this.statusBarItem.command = 'aiSocialScientist.showBackendLogs';
    this.statusBarItem.tooltip = 'AI Social Scientist Backend Status';
    this.config = this.loadConfig();

    // 监听配置变化
    context.subscriptions.push(
      vscode.workspace.onDidChangeConfiguration((e) => {
        if (
          e.affectsConfiguration('aiSocialScientist.backend') ||
          e.affectsConfiguration('aiSocialScientist.env')
        ) {
          this.config = this.loadConfig();
          this.log('Configuration updated');
          // 如果服务正在运行，需要重启以应用新配置
          if (this.process) {
            this.log('Configuration changed, restarting backend...');
            this.restart();
          }
        }
      })
    );

    // 监听工作区文件夹变化（工作区切换时重新加载配置）
    context.subscriptions.push(
      vscode.workspace.onDidChangeWorkspaceFolders(() => {
        this.config = this.loadConfig();
        this.log('Workspace folders changed, configuration reloaded');
        // 如果服务正在运行，需要重启以应用新的工作目录
        if (this.process) {
          this.log('Workspace changed, restarting backend...');
          this.restart();
        }
      })
    );

    context.subscriptions.push(this.statusBarItem);
    this.updateStatusBar('stopped');
  }

  private log(message: string, level: 'info' | 'error' | 'warn' = 'info'): void {
    const timestamp = new Date().toISOString();
    const prefix = level === 'error' ? '[ERROR]' : level === 'warn' ? '[WARN]' : '[INFO]';
    this.outputChannel.appendLine(`[${timestamp}] ${prefix} ${message}`);
  }

  /**
   * 显示配置错误消息，并提供打开设置的选项
   */
  private async showConfigError(message: string): Promise<void> {
    const openSettingsLabel = localize('backendManager.openSettings');
    const result = await vscode.window.showErrorMessage(message, openSettingsLabel);
    if (result === openSettingsLabel) {
      // 打开设置页面并过滤到 aiSocialScientist 配置
      await vscode.commands.executeCommand('workbench.action.openSettings', '@aiSocialScientist');
    }
  }

  /**
   * 加载配置并映射为环境变量
   */
  private loadConfig(): BackendConfig {
    const config = vscode.workspace.getConfiguration('aiSocialScientist');
    const backendConfig = config.get('backend', {}) as any;
    const envConfig = config.get('env', {}) as any;

    // 检测 Python 路径
    let pythonPath = backendConfig?.pythonPath || '';
    if (!pythonPath) {
      // 尝试检测 python3 或 python
      pythonPath = this.detectPythonPath();
    }

    // 确定工作目录 - 始终使用工作区相对路径
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      throw new Error('No workspace folder found. Please open a workspace first.');
    }
    const workingDirectory = workspaceFolder.uri.fsPath;

    // 映射环境变量
    const env: Record<string, string> = {};

    // 后端服务配置
    if (envConfig?.backendHost) env.BACKEND_HOST = envConfig.backendHost;
    if (envConfig?.backendPort) env.BACKEND_PORT = String(envConfig.backendPort);
    if (envConfig?.backendLogLevel) env.BACKEND_LOG_LEVEL = envConfig.backendLogLevel;

    // 基础配置 - 始终使用工作区相对路径
    // AGENTSOCIETY_HOME_DIR 相对于工作区根目录
    env.AGENTSOCIETY_HOME_DIR = path.join(workspaceFolder.uri.fsPath, 'agentsociety_data');

    // LLM 配置
    if (envConfig?.llmApiKey) env.AGENTSOCIETY_LLM_API_KEY = envConfig.llmApiKey;
    if (envConfig?.llmApiBase) env.AGENTSOCIETY_LLM_API_BASE = envConfig.llmApiBase;
    if (envConfig?.llmModel) env.AGENTSOCIETY_LLM_MODEL = envConfig.llmModel;

    // Coder LLM 配置
    if (envConfig?.coderLlmApiKey) env.AGENTSOCIETY_CODER_LLM_API_KEY = envConfig.coderLlmApiKey;
    if (envConfig?.coderLlmApiBase) env.AGENTSOCIETY_CODER_LLM_API_BASE = envConfig.coderLlmApiBase;
    if (envConfig?.coderLlmModel) env.AGENTSOCIETY_CODER_LLM_MODEL = envConfig.coderLlmModel;

    // Nano LLM 配置
    if (envConfig?.nanoLlmApiKey) env.AGENTSOCIETY_NANO_LLM_API_KEY = envConfig.nanoLlmApiKey;
    if (envConfig?.nanoLlmApiBase) env.AGENTSOCIETY_NANO_LLM_API_BASE = envConfig.nanoLlmApiBase;
    if (envConfig?.nanoLlmModel) env.AGENTSOCIETY_NANO_LLM_MODEL = envConfig.nanoLlmModel;

    // Embedding 配置
    if (envConfig?.embeddingApiKey) env.AGENTSOCIETY_EMBEDDING_API_KEY = envConfig.embeddingApiKey;
    if (envConfig?.embeddingApiBase) env.AGENTSOCIETY_EMBEDDING_API_BASE = envConfig.embeddingApiBase;
    if (envConfig?.embeddingModel) env.AGENTSOCIETY_EMBEDDING_MODEL = envConfig.embeddingModel;
    if (envConfig?.embeddingDims) env.AGENTSOCIETY_EMBEDDING_DIMS = String(envConfig.embeddingDims);

    // MiroFlow MCP 配置
    if (envConfig?.miroflowMcpUrl) env.MIROFLOW_MCP_URL = envConfig.miroflowMcpUrl;
    if (envConfig?.miroflowMcpToken) env.MIROFLOW_MCP_TOKEN = envConfig.miroflowMcpToken;
    if (envConfig?.miroflowDefaultLlm) env.MIROFLOW_DEFAULT_LLM = envConfig.miroflowDefaultLlm;
    if (envConfig?.miroflowDefaultAgent) env.MIROFLOW_DEFAULT_AGENT = envConfig.miroflowDefaultAgent;

    return {
      pythonPath,
      workingDirectory,
      autoStart: backendConfig?.autoStart !== false,
      env,
    };
  }

  /**
   * 检测 Python 可执行文件路径
   */
  private detectPythonPath(): string {
    // 尝试常见的 Python 命令
    const candidates = ['python3', 'python', 'py'];
    for (const cmd of candidates) {
      try {
        // 使用 which/where 命令检测（Windows 使用 where，Unix 使用 which）
        const isWindows = process.platform === 'win32';
        const checkCommand = isWindows ? `where ${cmd}` : `which ${cmd}`;
        execSync(checkCommand, { stdio: 'ignore' });
        return cmd;
      } catch {
        // 继续尝试下一个
      }
    }
    // 如果都找不到，返回 python3 作为默认值
    return 'python3';
  }

  /**
   * 更新状态栏
   */
  private updateStatusBar(status: 'running' | 'stopped' | 'starting' | 'error'): void {
    switch (status) {
      case 'running':
        this.statusBarItem.text = '$(server) Backend: Running';
        this.statusBarItem.backgroundColor = undefined;
        this.statusBarItem.show();
        break;
      case 'starting':
        this.statusBarItem.text = '$(sync~spin) Backend: Starting...';
        this.statusBarItem.backgroundColor = undefined;
        this.statusBarItem.show();
        break;
      case 'error':
        this.statusBarItem.text = '$(error) Backend: Error';
        this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
        this.statusBarItem.show();
        break;
      case 'stopped':
        this.statusBarItem.text = '$(server) Backend: Stopped';
        this.statusBarItem.backgroundColor = undefined;
        this.statusBarItem.show();
        break;
    }
  }

  /**
   * 检查后端服务是否正在运行
   */
  async isRunning(): Promise<boolean> {
    if (!this.process || this.process.killed) {
      return false;
    }

    // 检查进程是否还在运行
    try {
      if (this.process.pid) {
        process.kill(this.process.pid, 0); // 发送信号 0 检查进程是否存在
      }
    } catch {
      return false;
    }

    // 进行健康检查
    return await this.healthCheck();
  }

  /**
   * 健康检查
   */
  async healthCheck(): Promise<boolean> {
    const config = vscode.workspace.getConfiguration('aiSocialScientist');
    const backendUrl = config.get<string>('backendUrl', 'http://localhost:8001');

    try {
      const response = await fetch(`${backendUrl}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(3000), // 3秒超时
      });
      return response.ok;
    } catch (error) {
      return false;
    }
  }

  /**
   * 启动后端服务
   */
  async start(): Promise<boolean> {
    if (this.isStarting) {
      this.log('Backend is already starting...', 'warn');
      return false;
    }

    if (await this.isRunning()) {
      this.log('Backend is already running', 'warn');
      return true;
    }

    this.isStarting = true;
    this.updateStatusBar('starting');

    try {
      // 验证 Python 路径
      if (!this.config.pythonPath) {
        const errorMessage = localize('backendManager.configInsufficient') + ': Python path not found. Please set aiSocialScientist.backend.pythonPath';
        this.log(errorMessage, 'error');
        this.isStarting = false;
        this.updateStatusBar('error');
        await this.showConfigError(errorMessage);
        return false;
      }

      // 验证工作目录
      if (!fs.existsSync(this.config.workingDirectory)) {
        const errorMessage = `Working directory does not exist: ${this.config.workingDirectory}`;
        this.log(errorMessage, 'error');
        this.isStarting = false;
        this.updateStatusBar('error');
        await this.showConfigError(errorMessage);
        return false;
      }

      // 验证必需的配置
      if (!this.config.env.AGENTSOCIETY_LLM_API_KEY) {
        const errorMessage = localize('backendManager.configInsufficient') + ': LLM API key is required. Please set aiSocialScientist.env.llmApiKey';
        this.log(errorMessage, 'error');
        this.isStarting = false;
        this.updateStatusBar('error');
        await this.showConfigError(errorMessage);
        return false;
      }

      this.log('Starting backend service...');
      this.log(`Python path: ${this.config.pythonPath}`);
      this.log(`Working directory: ${this.config.workingDirectory}`);

      // 合并环境变量
      const env = {
        ...process.env,
        ...this.config.env,
      };

      // 启动后端进程
      const args = ['-m', 'agentsociety2.backend.run'];
      this.process = spawn(this.config.pythonPath, args, {
        cwd: this.config.workingDirectory,
        env,
        stdio: ['ignore', 'pipe', 'pipe'],
      });

      // 处理 stdout
      this.process.stdout?.on('data', (data: Buffer) => {
        const message = data.toString();
        this.outputChannel.append(message);
        this.log(`[STDOUT] ${message.trim()}`, 'info');
      });

      // 处理 stderr
      this.process.stderr?.on('data', (data: Buffer) => {
        const message = data.toString();
        this.outputChannel.append(message);
        this.log(`[STDERR] ${message.trim()}`, 'warn');
      });

      // 处理进程退出
      this.process.on('exit', (code, signal) => {
        this.log(`Backend process exited with code ${code}, signal ${signal}`);
        this.process = null;
        this.isStarting = false;
        this.updateStatusBar('stopped');

        if (code !== 0 && code !== null) {
          this.updateStatusBar('error');
          vscode.window.showErrorMessage(
            `Backend service exited with code ${code}. Check the output panel for details.`
          );
        }
      });

      // 处理进程错误
      this.process.on('error', async (error) => {
        this.log(`Failed to start backend: ${error.message}`, 'error');
        this.process = null;
        this.isStarting = false;
        this.updateStatusBar('error');

        // 检查是否是配置相关的错误（如找不到 Python 可执行文件）
        const errorMessage = error.message || 'Unknown error';
        const isConfigError =
          errorMessage.includes('ENOENT') ||
          errorMessage.includes('spawn') ||
          errorMessage.includes('Python') ||
          errorMessage.includes('python');

        if (isConfigError) {
          await this.showConfigError(`Failed to start backend service: ${errorMessage}`);
        } else {
          vscode.window.showErrorMessage(
            `Failed to start backend service: ${errorMessage}`
          );
        }
      });

      // 等待服务启动（最多等待30秒）
      const maxWaitTime = 30000; // 30秒
      const checkInterval = 1000; // 每秒检查一次
      let elapsed = 0;

      while (elapsed < maxWaitTime) {
        await new Promise((resolve) => setTimeout(resolve, checkInterval));
        elapsed += checkInterval;

        if (await this.healthCheck()) {
          this.log('Backend service started successfully');
          this.isStarting = false;
          this.updateStatusBar('running');
          this.startHealthCheck();
          return true;
        }

        // 检查进程是否已经退出
        if (!this.process || this.process.killed) {
          throw new Error('Backend process exited unexpectedly');
        }
      }

      // 超时
      throw new Error('Backend service failed to start within 30 seconds');
    } catch (error: any) {
      this.log(`Failed to start backend: ${error.message}`, 'error');
      this.isStarting = false;
      this.updateStatusBar('error');

      // 检查是否是配置相关的错误
      const errorMessage = error.message || 'Unknown error';
      const isConfigError =
        errorMessage.includes('Python path') ||
        errorMessage.includes('LLM API key') ||
        errorMessage.includes('Working directory') ||
        errorMessage.includes('aiSocialScientist');

      if (isConfigError) {
        await this.showConfigError(`Failed to start backend service: ${errorMessage}`);
      } else {
        vscode.window.showErrorMessage(
          `Failed to start backend service: ${errorMessage}`
        );
      }

      // 清理进程
      if (this.process) {
        this.stop();
      }

      return false;
    }
  }

  /**
   * 停止后端服务
   */
  async stop(): Promise<void> {
    if (!this.process) {
      this.log('Backend is not running', 'warn');
      return;
    }

    this.log('Stopping backend service...');
    this.updateStatusBar('stopped');

    // 停止健康检查
    this.stopHealthCheck();

    // 终止进程
    if (this.process.pid) {
      try {
        // 尝试优雅关闭
        process.kill(this.process.pid, 'SIGTERM');

        // 等待最多5秒
        await new Promise<void>((resolve) => {
          const timeout = setTimeout(() => {
            // 强制终止
            if (this.process?.pid) {
              process.kill(this.process.pid, 'SIGKILL');
            }
            resolve();
          }, 5000);

          this.process?.on('exit', () => {
            clearTimeout(timeout);
            resolve();
          });
        });
      } catch (error: any) {
        this.log(`Error stopping backend: ${error.message}`, 'error');
        // 强制终止
        if (this.process?.pid) {
          try {
            process.kill(this.process.pid, 'SIGKILL');
          } catch {
            // 忽略错误
          }
        }
      }
    }

    this.process = null;
    this.log('Backend service stopped');
  }

  /**
   * 重启后端服务
   */
  async restart(): Promise<boolean> {
    this.log('Restarting backend service...');
    await this.stop();
    await new Promise((resolve) => setTimeout(resolve, 1000)); // 等待1秒
    return await this.start();
  }

  /**
   * 启动定期健康检查
   */
  private startHealthCheck(): void {
    this.stopHealthCheck(); // 确保没有重复的检查

    this.healthCheckInterval = setInterval(async () => {
      const isHealthy = await this.healthCheck();
      if (!isHealthy && this.process && !this.process.killed) {
        this.log('Health check failed, but process is still running', 'warn');
        // 可以选择重启或只是记录警告
      }
    }, 10000); // 每10秒检查一次
  }

  /**
   * 停止定期健康检查
   */
  private stopHealthCheck(): void {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
  }

  /**
   * 获取后端状态
   */
  async getStatus(): Promise<BackendStatus> {
    const isRunning = await this.isRunning();
    const config = vscode.workspace.getConfiguration('aiSocialScientist');
    const backendUrl = config.get<string>('backendUrl', 'http://localhost:8001');
    const portMatch = backendUrl.match(/:(\d+)/);
    const port = portMatch ? parseInt(portMatch[1], 10) : undefined;

    return {
      isRunning,
      pid: this.process?.pid,
      port,
    };
  }

  /**
   * 显示日志输出面板
   */
  showLogs(): void {
    this.outputChannel.show();
  }

  /**
   * 清理资源
   */
  dispose(): void {
    this.stopHealthCheck();
    this.stop();
    this.statusBarItem.dispose();
    this.outputChannel.dispose();
  }
}
