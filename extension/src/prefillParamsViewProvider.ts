/**
 * 预填充参数视图提供者 (Prefill Parameters View Provider)
 * 
 * 这个类负责创建和管理VSCode中的预填充参数查看窗口（只读）。
 * 使用WebviewPanel模式，类似ChatWebviewProvider，作为项目结构视图中的一个入口。
 * 
 * 功能：
 * 1. 显示所有可用的Agent类和Env Module类
 * 2. 显示每个类的预填充参数（只读）
 * 3. 支持搜索和筛选
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { ApiClient } from './apiClient';
import { localize } from './i18n';

export class PrefillParamsViewProvider {
  /**
   * 当前活动的预填充参数面板实例（单例模式）
   */
  public static currentPanel: PrefillParamsViewProvider | undefined;

  /**
   * Webview视图类型标识符
   */
  private static readonly viewType = 'prefillParamsView';

  /**
   * Webview面板实例
   */
  private readonly _panel: vscode.WebviewPanel;

  /**
   * 扩展的URI
   */
  private readonly _extensionUri: vscode.Uri;

  /**
   * 扩展路径
   */
  private readonly _extensionPath: string;

  /**
   * API客户端实例
   */
  private readonly _apiClient: ApiClient;

  /**
   * 过滤类型（可选）
   */
  private readonly _filterKind?: 'env_module' | 'agent';

  /**
   * 可清理资源列表
   */
  private _disposables: vscode.Disposable[] = [];

  /**
   * 创建或显示预填充参数面板（静态工厂方法）
   */
  public static createOrShow(
    context: vscode.ExtensionContext,
    apiClient: ApiClient,
    kind?: 'env_module' | 'agent'
  ) {
    // 如果已经有一个面板打开，直接显示它（单例模式）
    if (PrefillParamsViewProvider.currentPanel) {
      PrefillParamsViewProvider.currentPanel._panel.reveal(vscode.ViewColumn.Beside);
      // 如果指定了kind，更新当前面板的过滤
      if (kind) {
        PrefillParamsViewProvider.currentPanel._panel.webview.postMessage({
          command: 'setFilterKind',
          kind: kind,
        });
      }
      return;
    }

    // 创建新的WebviewPanel
    const title = kind === 'env_module'
      ? localize('prefillParams.envModuleTitle')
      : kind === 'agent'
        ? localize('prefillParams.agentTitle')
        : localize('prefillParams.title');

    const panel = vscode.window.createWebviewPanel(
      PrefillParamsViewProvider.viewType,
      title,
      vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [
          vscode.Uri.file(path.join(context.extensionPath, 'out', 'webview'))
        ]
      }
    );

    // 创建PrefillParamsViewProvider实例并保存为当前面板
    PrefillParamsViewProvider.currentPanel = new PrefillParamsViewProvider(panel, context, apiClient, kind);
  }

  /**
   * 构造函数（私有，只能通过createOrShow调用）
   */
  private constructor(
    panel: vscode.WebviewPanel,
    context: vscode.ExtensionContext,
    apiClient: ApiClient,
    filterKind?: 'env_module' | 'agent'
  ) {
    this._panel = panel;
    this._extensionUri = context.extensionUri;
    this._extensionPath = context.extensionPath;
    this._apiClient = apiClient;
    this._filterKind = filterKind;

    // 设置Webview的HTML内容
    this._panel.webview.html = this._getHtmlForWebview(this._panel.webview);

    // 监听面板销毁事件
    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

    // 处理来自Webview的消息
    this._panel.webview.onDidReceiveMessage(
      async (message) => {
        switch (message.command) {
          case 'requestData':
            await this._handleRequestData();
            break;
          case 'refresh':
            await this._handleRequestData();
            break;
          case 'setFilterKind':
            // 更新过滤类型（用于单例模式下的切换）
            (this as any)._filterKind = message.kind;
            await this._handleRequestData();
            break;
        }
      },
      null,
      this._disposables
    );

    // 初始加载数据
    this._handleRequestData();
  }

  private async _handleRequestData() {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      this._panel.webview.postMessage({
        command: 'error',
        error: localize('prefillParamsViewProvider.noWorkspace'),
      });
      return;
    }

    try {
      // 获取可用的类列表
      const classesResponse = await this._apiClient.getAvailableClasses(workspaceFolder.uri.fsPath);

      // 获取所有预填充参数
      const prefillResponse = await this._apiClient.getPrefillParams(workspaceFolder.uri.fsPath);

      this._panel.webview.postMessage({
        command: 'initialData',
        classes: classesResponse,
        prefillParams: prefillResponse.data,
        filterKind: this._filterKind, // 传递过滤类型
      });
    } catch (error: any) {
      this._panel.webview.postMessage({
        command: 'error',
        error: error.message || localize('prefillParams.errorMessages.loadFailed'),
      });
    }
  }

  public dispose() {
    PrefillParamsViewProvider.currentPanel = undefined;

    // 清理资源
    while (this._disposables.length) {
      const x = this._disposables.pop();
      if (x) {
        x.dispose();
      }
    }
  }

  private _getHtmlForWebview(webview: vscode.Webview): string {
    // 获取webview资源的URI
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.file(path.join(this._extensionPath, 'out', 'webview', 'prefillParams.js'))
    );

    // 使用非空断言，因为我们知道这些文件会被webpack生成
    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src ${webview.cspSource} 'unsafe-eval' 'unsafe-inline';">
    <title>Prefill Parameters</title>
    <style>
      * {
        box-sizing: border-box;
        margin: 0;
        padding: 0;
      }
      body {
        height: 100vh;
        overflow: hidden;
      }
      #root {
        height: 100vh;
      }
    </style>
</head>
<body>
    <div id="root"></div>
    <script src="${scriptUri}"></script>
</body>
</html>`;
  }
}
