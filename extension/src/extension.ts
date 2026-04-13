/**
 * VSCode插件主入口文件
 *
 * 负责插件的激活/停用、命令注册、各个组件的初始化。
 *
 * 关联文件：
 * - @extension/src/services/backendManager.ts - 后端服务进程管理
 * - @extension/src/configPageViewProvider.ts - 配置页面Webview
 * - @extension/src/prefillParamsViewProvider.ts - 预填充参数查看器
 * - @extension/src/replayWebviewProvider.ts - 回放可视化Webview
 * - @extension/src/projectStructureProvider.ts - 项目结构树视图
 * - @extension/src/simSettingsEditorProvider.ts - SIM_SETTINGS自定义编辑器
 * - @extension/src/apiClient.ts - 后端API通信客户端
 * - @extension/src/envManager.ts - 环境变量(.env)管理
 * - @extension/src/services/llmValidator.ts - LLM配置验证
 *
 * 后端API：
 * - @packages/agentsociety2/agentsociety2/backend/app.py - FastAPI应用主入口
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { ProjectStructureProvider } from './projectStructureProvider';
import { SimSettingsEditorProvider } from './simSettingsEditorProvider';
import { InitConfigEditorProvider } from './initConfigEditorProvider';
import { PrefillParamsViewProvider } from './prefillParamsViewProvider';
import { ReplayWebviewProvider } from './replayWebviewProvider';
import { ConfigPageViewProvider } from './configPageViewProvider';
import { ApiClient } from './apiClient';
import { PaperWatcher } from './paperWatcher';
import { ProjectDragAndDropController } from './dragAndDropController';
import { ParseModeManager } from './parseModeManager';
import { localize } from './i18n';
import { BackendManager } from './services/backendManager';
import { MinerUInitializer } from './services/mineruInitializer';
import { MinerUParser } from './mineruParser';
import { AIChatInvoker } from './aiChatInvoker';
import { LiteratureIndexViewer } from './literatureIndexViewer';
import { StepsViewer } from './stepsViewer';
import { ExperimentResultsViewer } from './experimentResultsViewer';
import { PidStatusViewer } from './pidStatusViewer';
import { hasConfiguredLlmApiKey, migrateLegacySettingsToEnv } from './runtimeConfig';

// 全局后端服务管理器实例（管理 FastAPI 后端进程的启动、停止、重启）
let backendManager: BackendManager | null = null;
// 全局 MinerU 初始化器实例（负责环境检查、模型下载、状态栏展示）
let mineruInitializer: MinerUInitializer | null = null;
// 全局 MinerU 解析器实例（负责调用 MinerU CLI 执行 PDF 解析）
let mineruParser: MinerUParser | null = null;

export function activate(context: vscode.ExtensionContext) {
  console.log(localize('extension.activate'));

  const migratedLegacyKeys = migrateLegacySettingsToEnv();
  if (migratedLegacyKeys.length > 0) {
    console.log(`Migrated legacy AI Social Scientist settings to .env: ${migratedLegacyKeys.join(', ')}`);
  }

  // ========== 初始化后端服务管理器 ==========
  // BackendManager 负责 FastAPI 后端进程的生命周期管理
  backendManager = new BackendManager(context);
  context.subscriptions.push({
    dispose: () => {
      if (backendManager) {
        backendManager.dispose();
        backendManager = null;
      }
    }
  });

  // 首次启动或配置未完成时，打开配置页；否则按设置决定是否自动启动后端
  const config = vscode.workspace.getConfiguration('aiSocialScientist');
  const autoStart = config.get<boolean>('backend.autoStart', true);
  const hasCompletedInitialSetup = context.globalState.get<boolean>('configPage.hasCompletedInitialSetup');
  const hasLlmApiKey = hasConfiguredLlmApiKey();

  if (!hasCompletedInitialSetup || !hasLlmApiKey) {
    // 首次启动或缺少必填配置时，打开配置页
    setTimeout(() => {
      ConfigPageViewProvider.createOrShow(context, vscode.ViewColumn.One);
    }, 500);
  } else if (autoStart) {
    // 配置已完成且启用自动启动，则启动后端
    backendManager.start().catch((error) => {
      console.error('Failed to auto-start backend:', error);
    });
  }

  // Initialize API client
  const apiClient = new ApiClient(context);

  // ========== 初始化 MinerU 环境检查器 ==========
  // MinerUInitializer 在后台检查 MinerU CLI 安装状态和模型下载状态，
  // 并在 VSCode 状态栏展示当前环境状态（Ready / Not Installed / No Models 等）
  mineruInitializer = new MinerUInitializer(context);
  context.subscriptions.push({
    dispose: () => {
      if (mineruInitializer) {
        mineruInitializer.dispose();
        mineruInitializer = null;
      }
    }
  });

  // ========== 初始化 MinerU PDF 解析器 ==========
  // MinerUParser 负责调用 MinerU CLI 执行 PDF 解析，
  // 传入 initializer 以便在解析前检查环境是否就绪
  mineruParser = new MinerUParser(mineruInitializer);
  context.subscriptions.push({
    dispose: () => {
      if (mineruParser) {
        mineruParser.dispose();
        mineruParser = null;
      }
    }
  });

  // Initialize AI Chat invoker
  const aiChatInvoker = new AIChatInvoker();
  context.subscriptions.push(aiChatInvoker);

  // ========== 后台执行 MinerU 环境检查 ==========
  // 异步执行环境检查，不阻塞扩展的激活流程。
  // 检查内容包括：查找 CLI、获取版本、检查模型下载状态。
  // 如果模型缺失，会自动弹窗提示用户下载。
  mineruInitializer.checkAndInitialize().catch((error) => {
    console.error('MinerU initialization check failed:', error);
  });

  // ========== 初始化解析模式管理器 ==========
  // ParseModeManager 管理 PDF 解析模式（本地 MinerU 解析 vs 后端 API 解析）
  const parseModeManager = new ParseModeManager(context);
  context.subscriptions.push(parseModeManager);

  // ========== 初始化论文文件监听器 ==========
  // PaperWatcher 监听 papers/ 目录下的新 PDF 文件，自动触发 MinerU 解析
  const paperWatcher = new PaperWatcher(context, mineruParser, parseModeManager);
  context.subscriptions.push(paperWatcher);

  // ========== 初始化项目结构树视图（支持拖拽） ==========
  // ProjectStructureProvider 提供左侧树视图，展示工作区文件结构
  const projectStructureProvider = new ProjectStructureProvider(context, apiClient);
  // 拖拽控制器：支持将 PDF 文件拖入 papers/ 目录并自动解析
  const dragAndDropController = new ProjectDragAndDropController(projectStructureProvider, parseModeManager, paperWatcher);

  // Use createTreeView instead of registerTreeDataProvider to support drag and drop
  const treeView = vscode.window.createTreeView('projectStructureView', {
    treeDataProvider: projectStructureProvider,
    dragAndDropController: dragAndDropController,
    showCollapseAll: true
  });

  // Register provider disposal on deactivation
  context.subscriptions.push({
    dispose: () => {
      projectStructureProvider.dispose();
      dragAndDropController.dispose();
    }
  });

  // Register tree view disposal
  context.subscriptions.push(treeView);

  // Register commands
  const initProjectCommand = vscode.commands.registerCommand(
    'aiSocialScientist.initProject',
    async () => {
      const topic = await vscode.window.showInputBox({
        prompt: localize('extension.initProject.prompt'),
        placeHolder: localize('extension.initProject.placeholder')
      });
      if (topic) {
        await projectStructureProvider.initProject(topic);
        vscode.window.showInformationMessage(localize('extension.initProject.success', topic));
      }
    }
  );

  // Configure environment command - open config page for .env setup
  const configureEnvCommand = vscode.commands.registerCommand(
    'aiSocialScientist.configureEnv',
    async () => {
      ConfigPageViewProvider.createOrShow(context, vscode.ViewColumn.One);
    }
  );

  // Fix workspace directory command
  const fixWorkspaceCommand = vscode.commands.registerCommand(
    'aiSocialScientist.fixWorkspace',
    async () => {
      await projectStructureProvider.fixWorkspace();
    }
  );

  // 删除文献命令 (使用本地文件操作)
  const deleteLiteratureCommand = vscode.commands.registerCommand(
    'aiSocialScientist.deleteLiterature',
    async (item: any) => {
      if (!item || !item.filePath) {
        vscode.window.showErrorMessage(localize('extension.deleteLiterature.noFile'));
        return;
      }

      const filePath = item.filePath;
      const fileName = item.label || filePath.split(/[/\\]/).pop();

      // 检查是否是目录
      const isDirectory = fs.existsSync(filePath) && fs.statSync(filePath).isDirectory();

      // 对于目录，不应该使用此命令删除（目录删除需要特殊处理）
      if (isDirectory) {
        vscode.window.showWarningMessage(
          `"${fileName}" 是一个目录，请使用专门的删除命令或手动删除。`
        );
        return;
      }

      const confirm = await vscode.window.showWarningMessage(
        localize('extension.deleteLiterature.confirm', fileName),
        { modal: true },
        localize('extension.deleteLiterature.confirmButton'),
        localize('extension.deleteLiterature.cancelButton')
      );

      if (confirm !== localize('extension.deleteLiterature.confirmButton')) {
        return;
      }

      try {
        // Delete the file
        fs.unlinkSync(filePath);
        vscode.window.showInformationMessage(`Deleted: ${fileName}`);

        // Update literature_index.json if it exists
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (workspaceFolder) {
          const indexPath = path.join(workspaceFolder.uri.fsPath, 'papers', 'literature_index.json');
          if (fs.existsSync(indexPath)) {
            try {
              const indexData = JSON.parse(fs.readFileSync(indexPath, 'utf-8'));
              const relativePath = path.relative(workspaceFolder.uri.fsPath, filePath).replace(/\\/g, '/');
              indexData.entries = (indexData.entries || []).filter((e: any) => e.file_path !== relativePath);
              indexData.updated_at = new Date().toISOString();
              fs.writeFileSync(indexPath, JSON.stringify(indexData, null, 2), 'utf-8');
            } catch (error) {
              console.error('Failed to update literature index:', error);
            }
          }
        }

        projectStructureProvider.refresh();
      } catch (error: any) {
        vscode.window.showErrorMessage(localize('extension.deleteLiterature.failed', error.message || error));
      }
    }
  );

  // 重命名文献命令 (使用本地文件操作)
  const renameLiteratureCommand = vscode.commands.registerCommand(
    'aiSocialScientist.renameLiterature',
    async (item: any) => {
      if (!item || !item.filePath) {
        vscode.window.showErrorMessage(localize('extension.renameLiterature.noFile'));
        return;
      }

      const currentName = item.label || item.filePath.split(/[/\\]/).pop();
      const newName = await vscode.window.showInputBox({
        prompt: localize('extension.renameLiterature.prompt'),
        value: currentName,
        validateInput: (value) => {
          if (!value || value.trim().length === 0) {
            return localize('extension.renameLiterature.emptyName');
          }
          if (value.includes('/') || value.includes('\\')) {
            return localize('extension.renameLiterature.invalidChars');
          }
          return null;
        },
      });

      if (!newName || newName === currentName) {
        return;
      }

      try {
        const dirPath = path.dirname(item.filePath);
        const newPath = path.join(dirPath, newName);

        // Rename the file
        fs.renameSync(item.filePath, newPath);
        vscode.window.showInformationMessage(`Renamed to: ${newName}`);

        // Update literature_index.json if it exists
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (workspaceFolder) {
          const indexPath = path.join(workspaceFolder.uri.fsPath, 'papers', 'literature_index.json');
          if (fs.existsSync(indexPath)) {
            try {
              const indexData = JSON.parse(fs.readFileSync(indexPath, 'utf-8'));
              const oldRelativePath = path.relative(workspaceFolder.uri.fsPath, item.filePath).replace(/\\/g, '/');
              const newRelativePath = path.join(path.dirname(oldRelativePath), newName).replace(/\\/g, '/');

              const entry = (indexData.entries || []).find((e: any) => e.file_path === oldRelativePath);
              if (entry) {
                entry.file_path = newRelativePath;
                entry.title = newName.replace(/\.(md|json)$/, '');
                indexData.updated_at = new Date().toISOString();
                fs.writeFileSync(indexPath, JSON.stringify(indexData, null, 2), 'utf-8');
              }
            } catch (error) {
              console.error('Failed to update literature index:', error);
            }
          }
        }

        projectStructureProvider.refresh();
      } catch (error: any) {
        vscode.window.showErrorMessage(localize('extension.renameLiterature.failed', error.message || error));
      }
    }
  );

  // 在编辑器中打开 Markdown 文件命令
  const openMarkdownInEditorCommand = vscode.commands.registerCommand(
    'aiSocialScientist.openMarkdownInEditor',
    async (item: any) => {
      if (!item || !item.filePath) {
        vscode.window.showErrorMessage(localize('extension.openMarkdown.noFile'));
        return;
      }

      const filePath = item.filePath;
      // 检查是否为 markdown 文件
      const isMarkdown = filePath.toLowerCase().endsWith('.md');
      if (!isMarkdown) {
        vscode.window.showWarningMessage(localize('extension.openMarkdown.warning'));
        return;
      }

      try {
        // 使用 vscode.open 命令在编辑器中打开文件
        const fileUri = vscode.Uri.file(filePath);
        await vscode.window.showTextDocument(fileUri);
      } catch (error: any) {
        vscode.window.showErrorMessage(localize('extension.openMarkdown.failed', error.message || error));
      }
    }
  );

  // Open AI Chat command
  const openChatCommand = vscode.commands.registerCommand(
    'aiSocialScientist.openChat',
    async () => {
      await aiChatInvoker.invokeChat();
    }
  );

  // 使用MinerU解析PDF命令 (本地调用MinerU CLI)
  const parseWithMinerUCommand = vscode.commands.registerCommand(
    'aiSocialScientist.parseWithMinerU',
    async (item: any) => {
      if (!item || !item.filePath) {
        vscode.window.showErrorMessage(localize('extension.parseMinerU.noFile'));
        return;
      }

      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (!workspaceFolder) {
        vscode.window.showErrorMessage(localize('extension.parseMinerU.noWorkspace'));
        return;
      }

      // 检查文件扩展名
      const filePath = item.filePath;
      const ext = filePath.split('.').pop()?.toLowerCase();
      if (ext !== 'pdf') {
        vscode.window.showWarningMessage(localize('extension.parseMinerU.unsupportedFormat'));
        return;
      }

      if (!mineruParser) {
        vscode.window.showErrorMessage('MinerU Parser not initialized');
        return;
      }

      const fileName = item.label || path.basename(filePath);
      vscode.window.showInformationMessage(localize('extension.parseMinerU.parsing', fileName));

      try {
        const result = await mineruParser.parse({
          filePath,
          workspacePath: workspaceFolder.uri.fsPath,
        });

        if (result.success) {
          const openFileLabel = localize('extension.parseMinerU.openFile');
          vscode.window.showInformationMessage(
            localize('extension.parseMinerU.success', fileName),
            openFileLabel
          ).then((selection) => {
            if (selection === openFileLabel && result.parsedFilePath) {
              vscode.window.showTextDocument(vscode.Uri.file(result.parsedFilePath));
            }
          });
          projectStructureProvider.refresh();
        } else {
          vscode.window.showErrorMessage(result.message);
        }
      } catch (error: any) {
        vscode.window.showErrorMessage(localize('extension.parseMinerU.failed', error.message || error));
      }
    }
  );

  // Register custom editor for SIM_SETTINGS.json
  context.subscriptions.push(
    vscode.window.registerCustomEditorProvider(
      'aiSocialScientist.simSettings',
      new SimSettingsEditorProvider(context),
      {
        webviewOptions: {
          retainContextWhenHidden: true
        },
        supportsMultipleEditorsPerDocument: false
      }
    )
  );

  // Register custom editor for init_config.json
  context.subscriptions.push(
    vscode.window.registerCustomEditorProvider(
      'aiSocialScientist.initConfig',
      new InitConfigEditorProvider(context),
      {
        webviewOptions: {
          retainContextWhenHidden: true
        },
        supportsMultipleEditorsPerDocument: false
      }
    )
  );

  // Register prefill parameters command
  const viewPrefillParamsCommand = vscode.commands.registerCommand(
    'agentsociety.viewPrefillParams',
    (kind?: 'env_module' | 'agent') => {
      PrefillParamsViewProvider.createOrShow(context, apiClient, kind);
    }
  );
  context.subscriptions.push(viewPrefillParamsCommand);

  // Register open replay command
  const openReplayCommand = vscode.commands.registerCommand(
    'aiSocialScientist.openReplay',
    async (item?: any) => {
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (!workspaceFolder) {
        vscode.window.showErrorMessage('No workspace folder open');
        return;
      }

      // Extract hypothesis_id and experiment_id from the item or prompt user
      let hypothesisId: string | undefined;
      let experimentId: string | undefined;

      if (item && item.hypothesisId && item.experimentId) {
        // Called from tree view with context
        hypothesisId = item.hypothesisId;
        experimentId = item.experimentId;
      } else if (item && item.filePath) {
        // Try to parse from file path (e.g., hypothesis_xxx/experiment_yyy/...)
        const relativePath = path.relative(workspaceFolder.uri.fsPath, item.filePath);
        const match = relativePath.match(/hypothesis_([^/\\]+)[/\\]experiment_([^/\\]+)/);
        if (match) {
          hypothesisId = match[1];
          experimentId = match[2];
        }
      }

      if (!hypothesisId || !experimentId) {
        // Prompt user to enter hypothesis_id and experiment_id manually
        hypothesisId = await vscode.window.showInputBox({
          prompt: 'Enter hypothesis ID (e.g., 1)',
          placeHolder: 'hypothesis_id'
        });
        if (!hypothesisId) {
          return;
        }

        experimentId = await vscode.window.showInputBox({
          prompt: 'Enter experiment ID (e.g., 1)',
          placeHolder: 'experiment_id'
        });
        if (!experimentId) {
          return;
        }
      }

      // Create replay webview
      ReplayWebviewProvider.create(
        context,
        workspaceFolder.uri.fsPath,
        hypothesisId,
        experimentId
      );
    }
  );
  context.subscriptions.push(openReplayCommand);

  // Register backend management commands
  const startBackendCommand = vscode.commands.registerCommand(
    'aiSocialScientist.startBackend',
    async () => {
      if (backendManager) {
        const started = await backendManager.start();
        if (started) {
          vscode.window.showInformationMessage('Backend service started successfully');
        } else {
          vscode.window.showErrorMessage('Failed to start backend service. Check the output panel for details.');
        }
        return started;
      }
      return false;
    }
  );

  const stopBackendCommand = vscode.commands.registerCommand(
    'aiSocialScientist.stopBackend',
    async () => {
      if (backendManager) {
        await backendManager.stop();
        vscode.window.showInformationMessage('Backend service stopped');
      }
    }
  );

  const restartBackendCommand = vscode.commands.registerCommand(
    'aiSocialScientist.restartBackend',
    async () => {
      if (backendManager) {
        const restarted = await backendManager.restart();
        if (restarted) {
          vscode.window.showInformationMessage('Backend service restarted successfully');
        } else {
          vscode.window.showErrorMessage('Failed to restart backend service. Check the output panel for details.');
        }
        return restarted;
      }
      return false;
    }
  );

  const showBackendLogsCommand = vscode.commands.registerCommand(
    'aiSocialScientist.showBackendLogs',
    () => {
      if (backendManager) {
        backendManager.showLogs();
      }
    }
  );

  const backendStatusMenuCommand = vscode.commands.registerCommand(
    'aiSocialScientist.backendStatusMenu',
    async () => {
      const items: vscode.QuickPickItem[] = [
        { label: `$(refresh) ${localize('backendManager.statusBar.restart')}`, detail: 'aiSocialScientist.restartBackend' },
        { label: `$(stop) ${localize('backendManager.statusBar.stop')}`, detail: 'aiSocialScientist.stopBackend' },
        { label: `$(play) ${localize('backendManager.statusBar.start')}`, detail: 'aiSocialScientist.startBackend' },
        { label: `$(output) ${localize('backendManager.statusBar.logs')}`, detail: 'aiSocialScientist.showBackendLogs' },
        { label: `$(info) ${localize('backendManager.statusBar.status')}`, detail: 'aiSocialScientist.showBackendStatus' },
        { label: `$(settings) ${localize('backendManager.statusBar.config')}`, detail: 'aiSocialScientist.openConfigPage' }
      ];
      const selected = await vscode.window.showQuickPick(items, {
        placeHolder: localize('backendManager.statusBar.placeholder'),
        matchOnDescription: true,
        matchOnDetail: true
      });
      if (selected?.detail) {
        await vscode.commands.executeCommand(selected.detail);
      }
    }
  );

  const showBackendStatusCommand = vscode.commands.registerCommand(
    'aiSocialScientist.showBackendStatus',
    async () => {
      if (backendManager) {
        const status = await backendManager.getStatus();
        const message = status.isRunning
          ? `Backend is running (PID: ${status.pid}, Port: ${status.port})`
          : 'Backend is not running';
        vscode.window.showInformationMessage(message);
      }
    }
  );

  const openConfigPageCommand = vscode.commands.registerCommand(
    'aiSocialScientist.openConfigPage',
    () => {
      ConfigPageViewProvider.createOrShow(context, vscode.ViewColumn.Beside);
    }
  );

  // ========== MinerU 环境管理命令 ==========
  // 以下命令用于在命令面板和状态栏菜单中管理 MinerU 环境

  /**
   * MinerU 状态菜单命令
   *
   * 点击状态栏的 MinerU 状态项时触发，弹出快速选择菜单。
   * 菜单内容根据当前环境状态动态生成：
   * - 始终显示：当前状态、重新检查环境、查看日志
   * - not_installed 时额外显示：安装指南链接
   * - cli_ready 时额外显示：下载模型按钮
   */
  const mineruStatusMenuCommand = vscode.commands.registerCommand(
    'aiSocialScientist.mineruStatusMenu',
    async () => {
      const items: vscode.QuickPickItem[] = [];

      if (mineruInitializer) {
        const status = mineruInitializer.status;
        items.push({
          label: `$(info) ${localize('extension.mineru.status', status)}`,
          detail: mineruInitializer.getStatusText(),
        });

        if (status === 'not_installed') {
          items.push({
            label: `$(link-external) ${localize('extension.mineru.installGuide')}`,
            detail: 'https://github.com/opendatalab/MinerU',
          });
        } else if (status === 'cli_ready') {
          items.push({
            label: `$(cloud-download) ${localize('extension.mineru.downloadModels')}`,
            detail: 'aiSocialScientist.mineruDownloadModels',
          });
        }

        items.push({
          label: `$(refresh) ${localize('extension.mineru.recheck')}`,
          detail: 'aiSocialScientist.mineruRecheck',
        });
        items.push({
          label: `$(output) ${localize('extension.mineru.showLogs')}`,
          detail: 'aiSocialScientist.showMinerULogs',
        });
      }

      if (items.length === 0) {
        items.push({ label: localize('extension.mineru.notAvailable') });
      }

      const selected = await vscode.window.showQuickPick(items, {
        placeHolder: localize('extension.mineru.envPlaceholder'),
        matchOnDescription: true,
        matchOnDetail: true,
      });

      if (selected?.detail) {
        if (selected.detail.startsWith('http')) {
          vscode.env.openExternal(vscode.Uri.parse(selected.detail));
        } else {
          await vscode.commands.executeCommand(selected.detail);
        }
      }
    }
  );

  /**
   * 重新检查 MinerU 环境命令
   *
   * 重新执行完整的环境检查流程（查找 CLI → 检查版本 → 检查模型）。
   * 适用场景：用户安装了 MinerU 或下载了模型后，手动刷新环境状态。
   */
  const mineruRecheckCommand = vscode.commands.registerCommand(
    'aiSocialScientist.mineruRecheck',
    async () => {
      if (mineruInitializer) {
        vscode.window.showInformationMessage(localize('extension.mineru.rechecking'));
        const status = await mineruInitializer.checkAndInitialize();
        vscode.window.showInformationMessage(localize('extension.mineru.recheckResult', status));
      }
    }
  );

  /**
   * 下载 MinerU 模型命令
   *
   * 手动触发模型下载流程。适用场景：
   * - 用户之前跳过了自动下载提示
   * - 模型下载失败后重试
   * - 模型文件被删除后重新下载
   */
  const mineruDownloadModelsCommand = vscode.commands.registerCommand(
    'aiSocialScientist.mineruDownloadModels',
    async () => {
      if (mineruInitializer) {
        await mineruInitializer.downloadModels();
      }
    }
  );

  /**
   * 显示 MinerU 日志命令
   *
   * 在 VSCode 输出面板中打开 "MinerU Initializer" 通道，
   * 展示详细的环境检查和模型下载日志。
   */
  const showMinerULogsCommand = vscode.commands.registerCommand(
    'aiSocialScientist.showMinerULogs',
    () => {
      if (mineruInitializer) {
        mineruInitializer.showLogs();
      }
    }
  );

  // ========== Custom Module Commands ==========

  const scanCustomModulesCommand = vscode.commands.registerCommand(
    'aiSocialScientist.scanCustomModules',
    async () => {
      await projectStructureProvider.scanCustomModules();
    }
  );

  const testCustomModulesCommand = vscode.commands.registerCommand(
    'aiSocialScientist.testCustomModules',
    async () => {
      await projectStructureProvider.testCustomModules();
    }
  );

  const listCustomModulesCommand = vscode.commands.registerCommand(
    'aiSocialScientist.listCustomModules',
    async () => {
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (!workspaceFolder) {
        vscode.window.showErrorMessage(localize('customModules.noWorkspace'));
        return;
      }

      try {
        const response = await apiClient.listCustomModules();

        if (response.success) {
          const items: string[] = [];
          if (response.total_agents > 0) {
            items.push(`Custom Agents (${response.total_agents}):`);
            response.agents.forEach(agent => {
              items.push(`  - ${agent.class_name}: ${agent.description}`);
            });
          }
          if (response.total_envs > 0) {
            items.push(`Custom Environments (${response.total_envs}):`);
            response.envs.forEach(env => {
              items.push(`  - ${env.class_name}: ${env.description}`);
            });
          }
          if (items.length === 0) {
            items.push(localize('customModules.noModules'));
          }

          const doc = await vscode.workspace.openTextDocument({
            content: items.join('\n'),
            language: 'text'
          });
          await vscode.window.showTextDocument(doc);
        } else {
          vscode.window.showErrorMessage(localize('customModules.listFailed'));
        }
      } catch (error: any) {
        vscode.window.showErrorMessage(localize('customModules.listFailed', error.message || error));
      }
    }
  );

  // ========== Agent Skills Commands ==========

  const scanAgentSkillsCommand = vscode.commands.registerCommand(
    'aiSocialScientist.scanAgentSkills',
    async () => {
      await projectStructureProvider.scanAgentSkills();
    }
  );

  const importAgentSkillCommand = vscode.commands.registerCommand(
    'aiSocialScientist.importAgentSkill',
    async () => {
      await projectStructureProvider.importAgentSkill();
    }
  );

  const toggleAgentSkillCommand = vscode.commands.registerCommand(
    'aiSocialScientist.toggleAgentSkill',
    async (item: any) => {
      await projectStructureProvider.toggleAgentSkill(item);
    }
  );

  const reloadAgentSkillCommand = vscode.commands.registerCommand(
    'aiSocialScientist.reloadAgentSkill',
    async (item: any) => {
      await projectStructureProvider.reloadAgentSkill(item);
    }
  );

  // 打开 Skill 文档命令
  const openAgentSkillDocCommand = vscode.commands.registerCommand(
    'aiSocialScientist.openAgentSkillDoc',
    async (skillName: string, skillPath: string, isBuiltin: boolean) => {
      await projectStructureProvider.openAgentSkillDoc(skillName, skillPath, isBuiltin);
    }
  );

  // 删除自定义 Skill 命令
  const removeAgentSkillCommand = vscode.commands.registerCommand(
    'aiSocialScientist.removeAgentSkill',
    async (item: any) => {
      if (!item) { return; }

      // 获取 skill 名称
      const skillName = item.skillName;
      if (!skillName) {
        vscode.window.showErrorMessage('无法获取 Skill 名称');
        return;
      }

      // 确认删除
      const confirm = await vscode.window.showWarningMessage(
        localize('projectStructure.skillRemoveConfirm', skillName),
        { modal: true },
        localize('extension.deleteLiterature.confirmButton'),
        localize('extension.deleteLiterature.cancelButton')
      );

      if (confirm !== localize('extension.deleteLiterature.confirmButton')) {
        return;
      }

      try {
        const response = await apiClient.removeAgentSkill(skillName);
        if (response.success) {
          vscode.window.showInformationMessage(response.message);
          await projectStructureProvider.refreshAgentSkillsCache();
          projectStructureProvider.refresh();
        }
      } catch (error: any) {
        vscode.window.showErrorMessage(`删除 Skill 失败: ${error.message || error}`);
      }
    }
  );

  const updateExtensionSkillsCommand = vscode.commands.registerCommand(
    'aiSocialScientist.updateExtensionSkills',
    async () => {
      await projectStructureProvider.updateExtensionSkills();
    }
  );

  // 打开 Skill 目录命令
  const openSkillFolderCommand = vscode.commands.registerCommand(
    'aiSocialScientist.openSkillFolder',
    async (item: any) => {
      if (!item) { return; }

      // 获取 skill 目录路径
      const skillDirPath = item.skillDirPath || item.filePath;
      if (!skillDirPath) {
        vscode.window.showErrorMessage('无法获取 Skill 目录路径');
        return;
      }

      // 在 VSCode 中打开文件夹
      const folderUri = vscode.Uri.file(skillDirPath);
      try {
        // 在新窗口中打开文件夹
        vscode.commands.executeCommand('revealFileInOS', folderUri);
      } catch (error: any) {
        vscode.window.showErrorMessage(`打开 Skill 目录失败: ${error.message || error}`);
      }
    }
  );

  // 格式化查看 JSON 文件命令
  const formatJsonCommand = vscode.commands.registerCommand(
    'aiSocialScientist.formatJsonFile',
    async (item: any) => {
      if (!item || !item.filePath) {
        vscode.window.showErrorMessage('无法获取文件路径');
        return;
      }

      const filePath = item.filePath;

      // 检查是否为 JSON 文件
      if (!filePath.toLowerCase().endsWith('.json')) {
        vscode.window.showWarningMessage('此命令仅适用于 JSON 文件');
        return;
      }

      try {
        // 打开文件
        const document = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
        const editor = await vscode.window.showTextDocument(document);

        // 格式化文档
        await vscode.commands.executeCommand('editor.action.formatDocument');

        // 可选：切换到更友好的视图（如果安装了 JSON tools 等扩展）
        vscode.window.showInformationMessage(`JSON 文件已格式化显示`);
      } catch (error: any) {
        vscode.window.showErrorMessage(`打开 JSON 文件失败: ${error.message || error}`);
      }
    }
  );

  // 文献索引预览命令
  const viewLiteratureIndexCommand = vscode.commands.registerCommand(
    'aiSocialScientist.viewLiteratureIndex',
    async (item: any) => {
      if (!item || !item.filePath) {
        vscode.window.showErrorMessage('无法获取文献索引文件路径');
        return;
      }

      const filePath = item.filePath;

      // 检查文件是否存在
      if (!fs.existsSync(filePath)) {
        vscode.window.showErrorMessage('文献索引文件不存在');
        return;
      }

      try {
        await LiteratureIndexViewer.show(context, filePath);
      } catch (error: any) {
        vscode.window.showErrorMessage(`打开文献索引预览失败: ${error.message || error}`);
      }
    }
  );

  // Steps YAML 预览命令
  const viewStepsYamlCommand = vscode.commands.registerCommand(
    'aiSocialScientist.viewStepsYaml',
    async (item: any) => {
      let filePath: string | undefined;

      if (item && item.filePath) {
        filePath = item.filePath;
      } else {
        // 如果没有传入文件路径，让用户选择
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
          vscode.window.showErrorMessage('请先打开工作区');
          return;
        }

        const files = await vscode.workspace.findFiles('**/init/steps.yaml');
        if (files.length === 0) {
          vscode.window.showErrorMessage('未找到 steps.yaml 文件');
          return;
        }

        if (files.length === 1) {
          filePath = files[0].fsPath;
        } else {
          const picks = files.map(f => ({
            label: vscode.workspace.asRelativePath(f),
            path: f.fsPath
          }));
          const selected = await vscode.window.showQuickPick(picks, {
            placeHolder: '选择要预览的 steps.yaml 文件'
          });
          if (!selected) {
            return;
          }
          filePath = selected.path;
        }
      }

      // 检查文件是否存在
      if (!filePath || !fs.existsSync(filePath)) {
        vscode.window.showErrorMessage('steps.yaml 文件不存在');
        return;
      }

      try {
        await StepsViewer.show(context, filePath);
      } catch (error: any) {
        vscode.window.showErrorMessage(`打开步骤预览失败: ${error.message || error}`);
      }
    }
  );

  // 实验结果可视化命令
  const viewExperimentResultsCommand = vscode.commands.registerCommand(
    'aiSocialScientist.viewExperimentResults',
    async (item: any) => {
      let filePath: string | undefined;

      if (item && item.filePath) {
        filePath = item.filePath;
      } else {
        // 如果没有传入文件路径，让用户选择
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
          vscode.window.showErrorMessage('请先打开工作区');
          return;
        }

        const files = await vscode.workspace.findFiles('**/run/experiment_results.json');
        if (files.length === 0) {
          vscode.window.showErrorMessage('未找到 experiment_results.json 文件');
          return;
        }

        if (files.length === 1) {
          filePath = files[0].fsPath;
        } else {
          const picks = files.map(f => ({
            label: vscode.workspace.asRelativePath(f),
            path: f.fsPath
          }));
          const selected = await vscode.window.showQuickPick(picks, {
            placeHolder: '选择要查看的实验结果文件'
          });
          if (!selected) {
            return;
          }
          filePath = selected.path;
        }
      }

      // 检查文件是否存在
      if (!filePath || !fs.existsSync(filePath)) {
        vscode.window.showErrorMessage('experiment_results.json 文件不存在');
        return;
      }

      try {
        await ExperimentResultsViewer.show(context, filePath);
      } catch (error: any) {
        vscode.window.showErrorMessage(`打开实验结果可视化失败: ${error.message || error}`);
      }
    }
  );

  // PID状态可视化命令
  const viewPidStatusCommand = vscode.commands.registerCommand(
    'aiSocialScientist.viewPidStatus',
    async (item: any) => {
      const filePath = item?.filePath;
      if (!filePath || !fs.existsSync(filePath)) {
        vscode.window.showErrorMessage('pid.json 文件不存在');
        return;
      }

      try {
        await PidStatusViewer.createOrShow(filePath);
      } catch (error: any) {
        vscode.window.showErrorMessage(`打开实验状态可视化失败: ${error.message || error}`);
      }
    }
  );

  // 复制文件路径命令
  const copyFilePathCommand = vscode.commands.registerCommand(
    'aiSocialScientist.copyFilePath',
    async (item: any) => {
      const filePath = item?.filePath;
      if (!filePath) {
        vscode.window.showErrorMessage('无法获取文件路径');
        return;
      }

      try {
        await vscode.env.clipboard.writeText(filePath);
        vscode.window.showInformationMessage(`已复制路径: ${filePath}`);
      } catch (error: any) {
        vscode.window.showErrorMessage(`复制失败: ${error.message || error}`);
      }
    }
  );

  // 复制 @引用 格式命令
  const copyAtReferenceCommand = vscode.commands.registerCommand(
    'aiSocialScientist.copyAtReference',
    async (item: any) => {
      const filePath = item?.filePath;
      if (!filePath) {
        vscode.window.showErrorMessage('无法获取文件路径');
        return;
      }

      try {
        const atReference = `@${filePath}`;
        await vscode.env.clipboard.writeText(atReference);
        vscode.window.showInformationMessage(`已复制引用: ${atReference}`);
      } catch (error: any) {
        vscode.window.showErrorMessage(`复制失败: ${error.message || error}`);
      }
    }
  );

  // Register all commands
  context.subscriptions.push(
    initProjectCommand,
    configureEnvCommand,
    fixWorkspaceCommand,
    deleteLiteratureCommand,
    renameLiteratureCommand,
    parseWithMinerUCommand,
    openMarkdownInEditorCommand,
    openChatCommand,
    startBackendCommand,
    stopBackendCommand,
    restartBackendCommand,
    showBackendLogsCommand,
    showBackendStatusCommand,
    backendStatusMenuCommand,
    openConfigPageCommand,
    scanCustomModulesCommand,
    testCustomModulesCommand,
    listCustomModulesCommand,
    scanAgentSkillsCommand,
    importAgentSkillCommand,
    toggleAgentSkillCommand,
    reloadAgentSkillCommand,
    openAgentSkillDocCommand,
    removeAgentSkillCommand,
    updateExtensionSkillsCommand,
    openSkillFolderCommand,
    formatJsonCommand,
    viewLiteratureIndexCommand,
    viewStepsYamlCommand,
    viewExperimentResultsCommand,
    viewPidStatusCommand,
    copyFilePathCommand,
    copyAtReferenceCommand,
    mineruStatusMenuCommand,
    mineruRecheckCommand,
    mineruDownloadModelsCommand,
    showMinerULogsCommand
  );
}

export function deactivate() {
  // 扩展停用时：停止后端服务并清理 MinerU 初始化器资源
  if (backendManager) {
    backendManager.stop();
  }
  if (mineruInitializer) {
    mineruInitializer.dispose();
  }
}
