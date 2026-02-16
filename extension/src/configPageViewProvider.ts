/**
 * 配置页视图提供者 (Config Page View Provider)
 *
 * 在首次启动时或用户手动打开时显示配置页，引导用户填写 LLM API 密钥等必要配置，
 * 避免让用户去 Settings 页面编写 JSON 配置。
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { localize } from './i18n';
import type { ConfigValues, WorkspaceInfo } from './webview/configPage/types';

export class ConfigPageViewProvider {
  public static currentPanel: ConfigPageViewProvider | undefined;
  private static readonly viewType = 'aiSocialScientistConfigPage';

  private readonly _panel: vscode.WebviewPanel;
  private readonly _extensionPath: string;
  private readonly _context: vscode.ExtensionContext;
  private _disposables: vscode.Disposable[] = [];

  public static createOrShow(
    context: vscode.ExtensionContext,
    viewColumn: vscode.ViewColumn = vscode.ViewColumn.One
  ): void {
    if (ConfigPageViewProvider.currentPanel) {
      ConfigPageViewProvider.currentPanel._panel.reveal(viewColumn);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      ConfigPageViewProvider.viewType,
      localize('configPage.title'),
      viewColumn,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [
          vscode.Uri.file(path.join(context.extensionPath, 'out', 'webview'))
        ]
      }
    );

    ConfigPageViewProvider.currentPanel = new ConfigPageViewProvider(panel, context);
  }

  private constructor(panel: vscode.WebviewPanel, context: vscode.ExtensionContext) {
    this._panel = panel;
    this._context = context;
    this._extensionPath = context.extensionPath;

    this._panel.webview.html = this._getHtmlForWebview(this._panel.webview);

    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

    this._panel.webview.onDidReceiveMessage(
      async (message: { command: string; config?: Partial<ConfigValues> }) => {
        switch (message.command) {
          case 'requestConfig':
            await this._sendInitialConfig();
            break;
          case 'saveConfig':
            await this._handleSaveConfig(message.config || {});
            break;
          case 'openVscodeSettings':
            await vscode.commands.executeCommand('workbench.action.openSettings', '@aiSocialScientist');
            break;
          case 'openFolder':
            await vscode.commands.executeCommand('workbench.action.files.openFolder');
            break;
        }
      },
      null,
      this._disposables
    );
  }

  private async _sendInitialConfig(): Promise<void> {
    const config = vscode.workspace.getConfiguration('aiSocialScientist');
    const backendConfig = config.get('backend', {}) as Record<string, unknown>;
    const envConfig = config.get('env', {}) as Record<string, unknown>;

    const configValues: Partial<ConfigValues> = {
      llmApiKey: (envConfig?.llmApiKey as string) || '',
      backendHost: (envConfig?.backendHost as string) || '127.0.0.1',
      backendPort: (envConfig?.backendPort as number) ?? 8001,
      pythonPath: (backendConfig?.pythonPath as string) || '',
      llmApiBase: (envConfig?.llmApiBase as string) || 'https://cloud.infini-ai.com/maas/v1',
      llmModel: (envConfig?.llmModel as string) || 'qwen3-next-80b-a3b-instruct',
      backendLogLevel: (envConfig?.backendLogLevel as string) || 'info',
      coderLlmApiKey: (envConfig?.coderLlmApiKey as string) || '',
      coderLlmApiBase: (envConfig?.coderLlmApiBase as string) || '',
      coderLlmModel: (envConfig?.coderLlmModel as string) || 'glm-4.7',
      nanoLlmApiKey: (envConfig?.nanoLlmApiKey as string) || '',
      nanoLlmApiBase: (envConfig?.nanoLlmApiBase as string) || '',
      nanoLlmModel: (envConfig?.nanoLlmModel as string) || 'qwen3-next-80b-a3b-instruct',
      embeddingApiKey: (envConfig?.embeddingApiKey as string) || '',
      embeddingApiBase: (envConfig?.embeddingApiBase as string) || '',
      embeddingModel: (envConfig?.embeddingModel as string) || 'bge-m3',
      embeddingDims: (envConfig?.embeddingDims as number) ?? 1024,
      miroflowMcpUrl: (envConfig?.miroflowMcpUrl as string) || '',
      miroflowMcpToken: (envConfig?.miroflowMcpToken as string) || '',
      miroflowDefaultLlm: (envConfig?.miroflowDefaultLlm as string) || 'qwen-3',
      miroflowDefaultAgent: (envConfig?.miroflowDefaultAgent as string) || 'mirothinker_v1.5_keep5_max200'
    };

    // 获取工作区信息
    const workspaceInfo: WorkspaceInfo = {
      hasWorkspace: !!(vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length > 0),
      workspacePath: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath
    };

    this._panel.webview.postMessage({
      command: 'initialConfig',
      config: configValues
    });

    this._panel.webview.postMessage({
      command: 'workspaceInfo',
      workspaceInfo: workspaceInfo
    });
  }

  private async _handleSaveConfig(config: Partial<ConfigValues>): Promise<void> {
    try {
      // 检查是否有工作区
      if (!vscode.workspace.workspaceFolders || vscode.workspace.workspaceFolders.length === 0) {
        this._panel.webview.postMessage({
          command: 'saveResult',
          success: false,
          error: localize('configPage.noWorkspace')
        });
        return;
      }
      const vscodeConfig = vscode.workspace.getConfiguration('aiSocialScientist');

      if (config.llmApiKey !== undefined) {
        await vscodeConfig.update('env.llmApiKey', config.llmApiKey, vscode.ConfigurationTarget.Workspace);
      }
      if (config.backendHost !== undefined) {
        await vscodeConfig.update('env.backendHost', config.backendHost, vscode.ConfigurationTarget.Workspace);
      }
      if (config.backendPort !== undefined) {
        await vscodeConfig.update('env.backendPort', config.backendPort, vscode.ConfigurationTarget.Workspace);
      }
      if (config.pythonPath !== undefined) {
        await vscodeConfig.update('backend.pythonPath', config.pythonPath, vscode.ConfigurationTarget.Workspace);
      }
      if (config.llmApiBase !== undefined) {
        await vscodeConfig.update('env.llmApiBase', config.llmApiBase, vscode.ConfigurationTarget.Workspace);
      }
      if (config.llmModel !== undefined) {
        await vscodeConfig.update('env.llmModel', config.llmModel, vscode.ConfigurationTarget.Workspace);
      }
      if (config.backendLogLevel !== undefined) {
        await vscodeConfig.update('env.backendLogLevel', config.backendLogLevel, vscode.ConfigurationTarget.Workspace);
      }
      if (config.coderLlmApiKey !== undefined) {
        await vscodeConfig.update('env.coderLlmApiKey', config.coderLlmApiKey, vscode.ConfigurationTarget.Workspace);
      }
      if (config.coderLlmApiBase !== undefined) {
        await vscodeConfig.update('env.coderLlmApiBase', config.coderLlmApiBase, vscode.ConfigurationTarget.Workspace);
      }
      if (config.coderLlmModel !== undefined) {
        await vscodeConfig.update('env.coderLlmModel', config.coderLlmModel, vscode.ConfigurationTarget.Workspace);
      }
      if (config.nanoLlmApiKey !== undefined) {
        await vscodeConfig.update('env.nanoLlmApiKey', config.nanoLlmApiKey, vscode.ConfigurationTarget.Workspace);
      }
      if (config.nanoLlmApiBase !== undefined) {
        await vscodeConfig.update('env.nanoLlmApiBase', config.nanoLlmApiBase, vscode.ConfigurationTarget.Workspace);
      }
      if (config.nanoLlmModel !== undefined) {
        await vscodeConfig.update('env.nanoLlmModel', config.nanoLlmModel, vscode.ConfigurationTarget.Workspace);
      }
      if (config.embeddingApiKey !== undefined) {
        await vscodeConfig.update('env.embeddingApiKey', config.embeddingApiKey, vscode.ConfigurationTarget.Workspace);
      }
      if (config.embeddingApiBase !== undefined) {
        await vscodeConfig.update('env.embeddingApiBase', config.embeddingApiBase, vscode.ConfigurationTarget.Workspace);
      }
      if (config.embeddingModel !== undefined) {
        await vscodeConfig.update('env.embeddingModel', config.embeddingModel, vscode.ConfigurationTarget.Workspace);
      }
      if (config.embeddingDims !== undefined) {
        await vscodeConfig.update('env.embeddingDims', config.embeddingDims, vscode.ConfigurationTarget.Workspace);
      }
      if (config.miroflowMcpUrl !== undefined) {
        await vscodeConfig.update('env.miroflowMcpUrl', config.miroflowMcpUrl, vscode.ConfigurationTarget.Workspace);
      }
      if (config.miroflowMcpToken !== undefined) {
        await vscodeConfig.update('env.miroflowMcpToken', config.miroflowMcpToken, vscode.ConfigurationTarget.Workspace);
      }
      if (config.miroflowDefaultLlm !== undefined) {
        await vscodeConfig.update('env.miroflowDefaultLlm', config.miroflowDefaultLlm, vscode.ConfigurationTarget.Workspace);
      }
      if (config.miroflowDefaultAgent !== undefined) {
        await vscodeConfig.update('env.miroflowDefaultAgent', config.miroflowDefaultAgent, vscode.ConfigurationTarget.Workspace);
      }

      // 标记已完成初始配置
      await this._context.globalState.update('configPage.hasCompletedInitialSetup', true);

      this._panel.webview.postMessage({ command: 'saveResult', success: true });

      // 启动后端服务
      await vscode.commands.executeCommand('aiSocialScientist.startBackend');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      this._panel.webview.postMessage({
        command: 'saveResult',
        success: false,
        error: message
      });
    }
  }

  private _getHtmlForWebview(webview: vscode.Webview): string {
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.file(path.join(this._extensionPath, 'out', 'webview', 'configPage.js'))
    );

    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src ${webview.cspSource} 'unsafe-eval' 'unsafe-inline';">
  <title>${localize('configPage.title')}</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--vscode-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
      background: var(--vscode-editor-background);
      color: var(--vscode-editor-foreground);
      height: 100vh;
      overflow: auto;
    }
    #root { min-height: 100vh; }
  </style>
</head>
<body>
  <div id="root"></div>
  <script src="${scriptUri}"></script>
</body>
</html>`;
  }

  public dispose(): void {
    ConfigPageViewProvider.currentPanel = undefined;
    while (this._disposables.length) {
      const d = this._disposables.pop();
      if (d) d.dispose();
    }
  }
}
