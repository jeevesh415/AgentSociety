import * as vscode from 'vscode';
import * as path from 'path';
import { ProjectStructureProvider } from './projectStructureProvider';
import { ChatWebviewProvider } from './chatWebviewProvider';
import { SimSettingsEditorProvider } from './simSettingsEditorProvider';
import { PrefillParamsViewProvider } from './prefillParamsViewProvider';
import { ReplayWebviewProvider } from './replayWebviewProvider';
import { ConfigPageViewProvider } from './configPageViewProvider';
import { ApiClient } from './apiClient';
import { PaperWatcher } from './paperWatcher';
import { ProjectDragAndDropController } from './dragAndDropController';
import { localize } from './i18n';
import { BackendManager } from './services/backendManager';

// Global backend manager instance
let backendManager: BackendManager | null = null;

export function activate(context: vscode.ExtensionContext) {
  console.log(localize('extension.activate'));

  // Initialize backend manager
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
  const hasLlmApiKey = !!(config.get<string>('env.llmApiKey', '')?.trim());

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

  // Register project structure tree view with drag and drop support
  const projectStructureProvider = new ProjectStructureProvider(context, apiClient);
  const dragAndDropController = new ProjectDragAndDropController(projectStructureProvider);

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

  // Initialize paper watcher for MinerU parsing
  // PaperWatcher will register itself in its constructor
  new PaperWatcher(context, apiClient);

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

  const openChatCommand = vscode.commands.registerCommand(
    'aiSocialScientist.openChat',
    async () => {
      await ChatWebviewProvider.createOrShow(context);
    }
  );


  // 删除文献命令
  const deleteLiteratureCommand = vscode.commands.registerCommand(
    'aiSocialScientist.deleteLiterature',
    async (item: any) => {
      if (!item || !item.filePath) {
        vscode.window.showErrorMessage(localize('extension.deleteLiterature.noFile'));
        return;
      }

      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (!workspaceFolder) {
        vscode.window.showErrorMessage(localize('extension.deleteLiterature.noWorkspace'));
        return;
      }

      const fileName = item.label || item.filePath.split(/[/\\]/).pop();
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
        const relativePath = path.relative(workspaceFolder.uri.fsPath, item.filePath);
        // 统一使用正斜杠（后端期望的格式）
        const normalizedPath = relativePath.replace(/\\/g, '/');

        const response = await apiClient.deleteLiterature({
          file_path: normalizedPath,
          workspace_path: workspaceFolder.uri.fsPath,
        });

        if (response.success) {
          vscode.window.showInformationMessage(response.message);
          projectStructureProvider.refresh();
        } else {
          vscode.window.showErrorMessage(response.message);
        }
      } catch (error: any) {
        vscode.window.showErrorMessage(localize('extension.deleteLiterature.failed', error.message || error));
      }
    }
  );

  // 重命名文献命令
  const renameLiteratureCommand = vscode.commands.registerCommand(
    'aiSocialScientist.renameLiterature',
    async (item: any) => {
      if (!item || !item.filePath) {
        vscode.window.showErrorMessage(localize('extension.renameLiterature.noFile'));
        return;
      }

      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (!workspaceFolder) {
        vscode.window.showErrorMessage(localize('extension.renameLiterature.noWorkspace'));
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
        const relativePath = path.relative(workspaceFolder.uri.fsPath, item.filePath);
        // 统一使用正斜杠（后端期望的格式）
        const normalizedPath = relativePath.replace(/\\/g, '/');

        const response = await apiClient.renameLiterature({
          file_path: normalizedPath,
          new_name: newName,
          workspace_path: workspaceFolder.uri.fsPath,
        });

        if (response.success) {
          vscode.window.showInformationMessage(response.message);
          projectStructureProvider.refresh();
        } else {
          vscode.window.showErrorMessage(response.message);
        }
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

  // 使用MinerU解析PDF命令
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

      try {
        const relativePath = path.relative(workspaceFolder.uri.fsPath, filePath);
        // 统一使用正斜杠（后端期望的格式）
        const normalizedPath = relativePath.replace(/\\/g, '/');

        const fileName = item.label || path.basename(filePath);
        vscode.window.showInformationMessage(localize('extension.parseMinerU.parsing', fileName));

        const response = await apiClient.parseWithMinerU({
          file_path: normalizedPath,
          workspace_path: workspaceFolder.uri.fsPath,
        });

        if (response.success) {
          const openFileLabel = localize('extension.parseMinerU.openFile');
          vscode.window.showInformationMessage(
            localize('extension.parseMinerU.success', fileName),
            openFileLabel
          ).then(selection => {
            if (selection === openFileLabel && response.parsed_file_path) {
              // 解析后的文件路径可能是相对路径，需要转换为绝对路径
              const parsedFilePath = path.isAbsolute(response.parsed_file_path)
                ? response.parsed_file_path
                : path.join(workspaceFolder.uri.fsPath, response.parsed_file_path);
              vscode.window.showTextDocument(vscode.Uri.file(parsedFilePath));
            }
          });
          projectStructureProvider.refresh();
        } else {
          vscode.window.showErrorMessage(localize('extension.parseMinerU.failed', response.message));
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
      }
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
      }
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

  // Register all commands
  context.subscriptions.push(
    initProjectCommand,
    openChatCommand,
    deleteLiteratureCommand,
    renameLiteratureCommand,
    parseWithMinerUCommand,
    openMarkdownInEditorCommand,
    startBackendCommand,
    stopBackendCommand,
    restartBackendCommand,
    showBackendLogsCommand,
    showBackendStatusCommand,
    backendStatusMenuCommand,
    openConfigPageCommand
  );
}

export function deactivate() {
  // Stop backend service on deactivation
  if (backendManager) {
    backendManager.stop();
  }
}

