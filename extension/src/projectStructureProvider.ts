/**
 * 项目结构提供者 (Project Structure Provider)
 *
 * 这个文件实现了VSCode左侧边栏的树形视图，用于显示研究项目的层次结构。
 *
 * VSCode插件开发核心概念：
 * 1. TreeDataProvider: 实现这个接口可以创建自定义的树形视图
 * 2. TreeItem: 树形视图中的每个节点都是一个TreeItem
 * 3. FileSystemWatcher: 监听文件系统变化，实现实时更新
 * 4. EventEmitter: VSCode的事件系统，用于通知视图更新
 *
 * 关联文件：
 * - @extension/src/extension.ts - 主入口，注册TreeView和命令
 * - @extension/src/apiClient.ts - 调用后端API（初始化工作区、模块扫描等）
 * - @extension/src/workspaceManager.ts - 工作区状态管理
 *
 * 后端API：
 * - @packages/agentsociety2/agentsociety2/backend/routers/custom.py - /api/v1/custom/*
 * - @packages/agentsociety2/agentsociety2/backend/routers/modules.py - /api/v1/modules/*
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { localize } from './i18n';
import { ApiClient } from './apiClient';
import { WorkspaceManager } from './workspaceManager';

/**
 * ProjectItem - 项目树视图中的单个节点
 * 
 * 继承自 vscode.TreeItem，这是VSCode树形视图的基础类。
 * 每个节点可以显示标签、图标，并且可以展开/折叠。
 */
export class ProjectItem extends vscode.TreeItem {
  // Additional properties for experiment context
  public hypothesisId?: string;
  public experimentId?: string;
  // Custom module properties
  public isCustom?: boolean;
  public moduleType?: string;
  public className?: string;

  /**
   * 构造函数
   * @param label - 节点显示的文本标签
   * @param collapsibleState - 节点的折叠状态：
   *   - Collapsed: 可以展开（有子节点）
   *   - Expanded: 已展开
   *   - None: 没有子节点，不能展开
   * @param type - 节点类型，用于区分不同类型的项目项（用于上下文菜单等）
   * @param filePath - 可选的文件路径，如果提供，点击节点会打开该文件
   */
  constructor(
    public readonly label: string,
    public readonly collapsibleState: vscode.TreeItemCollapsibleState,
    public readonly type: 'initWorkspace' | 'configureEnv' | 'fixWorkspace' | 'aiChat' | 'topic' | 'hypothesis' | 'experiment' | 'paper' | 'file' | 'papers' | 'userdata' | 'prefillParams' | 'prefillParamsGroup' | 'prefillParamsEnv' | 'prefillParamsAgent' | 'settings' | 'syncResourcesGroup' | 'syncResourcesAction' | 'syncBuiltinSkillsGroup' | 'syncBuiltinSkillItem' | 'syncCustomSkillsGroup' | 'custom' | 'customScan' | 'customTest' | 'customClean' | 'customAgentItem' | 'customEnvItem' | 'customAgentsGroup' | 'customEnvsGroup' | 'customWorkspace' | 'presentation' | 'presentationHypothesis' | 'presentationExperiment' | 'synthesis' | 'reportHtml' | 'reportMd' | 'agentSkillsGroup' | 'agentSkillItem' | 'agentSkillScan' | 'agentSkillImport' | 'agentSkillBuiltinGroup' | 'agentSkillCustomGroup',
    public readonly filePath?: string
  ) {
    // 调用父类构造函数，初始化树节点
    super(label, collapsibleState);

    // tooltip: 鼠标悬停时显示的提示信息
    this.tooltip = filePath || label;

    // 获取文件扩展名（用于图标和命令设置）
    const ext = filePath ? filePath.toLowerCase().split('.').pop() : '';

    // 检查是否为 markdown 文件（用于后续的 contextValue 和命令设置）
    const isMarkdown = ext === 'md';

    // 检查是否为 JSON 文件
    const isJson = ext === 'json';

    // 检查是否为 Python 文件
    const isPython = ext === 'py';

    // 检查是否为 YAML 文件
    const isYaml = ext === 'yaml' || ext === 'yml';

    // contextValue: 用于上下文菜单的条件判断
    // 例如：当contextValue为'hypothesis'时，可以显示特定的右键菜单项
    // 对于 markdown 文件，添加 'markdown' 标识以便在右键菜单中显示特定选项
    // 对于 JSON 文件，添加 'json' 标识
    if (isMarkdown) {
      this.contextValue = `${type} markdown`;
    } else if (isJson) {
      this.contextValue = `${type} json`;
    } else {
      this.contextValue = type;
    }

    // 根据节点类型设置不同的图标
    // ThemeIcon是VSCode内置的图标系统，使用Codicons图标库
    const iconMap: { [key: string]: string } = {
      'initWorkspace': 'add',      // 加号图标，初始化工作区
      'configureEnv': 'gear',      // 齿轮图标，配置环境变量
      'fixWorkspace': 'tools',     // 工具图标，修复工作区
      'aiChat': 'comment-discussion',  // 聊天气泡图标，AI Chat
      'topic': 'book',           // 书籍图标，表示研究话题
      'hypothesis': 'lightbulb',  // 灯泡图标，表示假设
      'experiment': 'beaker',     // 烧杯图标，表示实验
      'papers': 'library',        // 图书馆图标，表示文献库
      'userdata': 'database',     // 数据库图标，表示用户数据
      'prefillParams': 'settings', // 设置图标，表示预填充参数
      'prefillParamsGroup': 'folder', // 文件夹图标，表示预填充参数组
      'prefillParamsEnv': 'symbol-namespace', // 命名空间图标，表示环境模块预置参数
      'prefillParamsAgent': 'symbol-interface', // 接口图标，表示智能体类预置参数
      'settings': 'settings-gear', // 齿轮设置图标，表示配置设置
      'syncResourcesGroup': 'cloud-download', // 同步 AI 助手资源图标
      'syncResourcesAction': 'sync', // 同步操作图标
      'syncBuiltinSkillsGroup': 'package', // 内置 Skills 分组图标
      'syncBuiltinSkillItem': 'puzzle', // 内置 Skill 项图标
      'syncCustomSkillsGroup': 'tools', // 自定义 Skills 分组图标
      'custom': 'workspace-trusted', // 自定义模块根图标
      'customScan': 'refresh', // 扫描图标
      'customTest': 'play', // 测试图标
      'customAgentItem': 'symbol-class', // 自定义Agent图标
      'customEnvItem': 'symbol-namespace', // 自定义环境模块图标
      'customAgentsGroup': 'folder', // Agents组图标
      'customEnvsGroup': 'folder', // Envs组图标
      'presentation': 'symbol-folder', // 分析报告根图标
      'presentationHypothesis': 'folder', // 假设文件夹
      'presentationExperiment': 'folder', // 实验文件夹
      'synthesis': 'symbol-misc', // 综合报告图标
      'reportHtml': 'browser', // HTML 报告图标
      'reportMd': 'file-code', // Markdown 报告图标
      'agentSkillsGroup': 'extensions', // Agent Skills 组图标
      'agentSkillItem': 'puzzle-piece', // 单个 Skill 图标
      'agentSkillScan': 'refresh', // 扫描 Skills 图标
      'agentSkillImport': 'cloud-download', // 导入 Skill 图标
      'agentSkillBuiltinGroup': 'package', // 内置 Skills 组图标
      'agentSkillCustomGroup': 'tools', // 自定义 Skills 组图标
    };

    // 对于 paper 和 file 类型，根据文件扩展名设置图标
    let iconId: string;
    if (type === 'paper' || type === 'file') {
      // 根据文件扩展名设置图标
      const fileIconMap: { [key: string]: string } = {
        'pdf': 'file-pdf',           // PDF 文件
        'md': 'file-text',           // Markdown 文件（比 file-code 更适合纯文本）
        'json': 'json',              // JSON 文件（VSCode 内置 json 图标）
        'py': 'file-code',           // Python 文件
        'yaml': 'file-code',         // YAML 文件
        'yml': 'file-code',          // YAML 文件
        'html': 'browser',           // HTML 文件
        'csv': 'table',              // CSV 文件
        'txt': 'file-text',          // 文本文件
        'db': 'database',            // 数据库文件
        'sqlite': 'database',        // SQLite 文件
        'png': 'file-media',         // 图片文件
        'jpg': 'file-media',         // 图片文件
        'jpeg': 'file-media',        // 图片文件
        'gif': 'file-media',         // 图片文件
      };
      iconId = (ext && fileIconMap[ext]) || 'file';
    } else {
      iconId = iconMap[type] || 'file';
    }

    // ThemeIcon的构造函数在类型定义中是私有的，但运行时可用
    // 使用类型断言绕过TypeScript的类型检查
    this.iconPath = new (vscode.ThemeIcon as any)(iconId);

    // 如果提供了文件路径，设置点击命令
    // 当用户点击这个节点时，会执行相应的命令打开文件
    if (filePath) {
      if (type === 'reportHtml' || (ext === 'html' && (type === 'presentationExperiment' || type === 'synthesis'))) {
        // HTML 报告文件使用 Live Preview 预览
        this.command = {
          command: 'livePreview.start.preview.atFile',
          title: 'Open with Live Preview',
          arguments: [vscode.Uri.file(filePath)]
        };
      } else if (type === 'reportMd' && isMarkdown) {
        // Markdown 报告默认以预览模式打开
        this.command = {
          command: 'markdown.showPreview',
          title: 'Open Preview',
          arguments: [vscode.Uri.file(filePath)]
        };
      } else if (isMarkdown) {
        // Markdown 文件默认以预览模式打开
        this.command = {
          command: 'markdown.showPreview',  // VSCode内置命令：预览 Markdown 文件
          title: 'Open Preview',
          arguments: [vscode.Uri.file(filePath)]  // 传递文件URI作为参数
        };
      } else if (isJson) {
        // JSON 文件：使用格式化方式打开，便于阅读
        this.command = {
          command: 'vscode.open',
          title: 'Open JSON File',
          arguments: [vscode.Uri.file(filePath)]
        };
      } else {
        // 其他文件使用默认打开方式
        this.command = {
          command: 'vscode.open',  // VSCode内置命令：打开文件
          title: 'Open File',
          arguments: [vscode.Uri.file(filePath)]  // 传递文件URI作为参数
        };
      }
    } else if (type === 'prefillParamsGroup') {
      // 环境与智能体节点：点击时打开统一的管理界面
      this.command = {
        command: 'agentsociety.viewPrefillParams',
        title: 'View Environment & Agents Management',
      };
    } else if (type === 'settings') {
      // 配置设置节点：点击时打开配置页（而非 VS Code 设置）
      this.command = {
        command: 'aiSocialScientist.openConfigPage',
        title: localize('projectStructure.settings')
      };
    }
  }
}

/**
 * ProjectStructureProvider - 项目结构数据提供者
 * 
 * 实现 TreeDataProvider<ProjectItem> 接口，这是VSCode树形视图的核心。
 * 
 * 主要职责：
 * 1. 提供树形视图的数据（通过getChildren方法）
 * 2. 响应文件系统变化，自动刷新视图
 * 3. 管理文件监听器和资源清理
 */
export class ProjectStructureProvider implements vscode.TreeDataProvider<ProjectItem> {
  /**
   * _onDidChangeTreeData - 事件发射器
   * 
   * EventEmitter是VSCode事件系统的核心。
   * 当数据发生变化时，通过fire()方法发射事件，视图会自动刷新。
   * 
   * 类型说明：
   * - ProjectItem | undefined | null: 可以传递特定的节点来刷新，或undefined/null刷新整个树
   */
  private _onDidChangeTreeData: vscode.EventEmitter<ProjectItem | undefined | null> = new vscode.EventEmitter<ProjectItem | undefined | null>();

  /**
   * onDidChangeTreeData - 公开的事件属性
   * 
   * VSCode通过这个属性订阅数据变化事件。
   * 当_onDidChangeTreeData.fire()被调用时，VSCode会自动调用getChildren()重新获取数据。
   */
  readonly onDidChangeTreeData: vscode.Event<ProjectItem | undefined | null> = this._onDidChangeTreeData.event;

  // 文件系统监听器 - 监听工作区文件的变化
  private watcher: vscode.FileSystemWatcher | undefined;

  // 当前工作区的路径
  private workspacePath: string = '';

  // 防抖定时器 - 用于限制刷新频率
  private refreshTimer: NodeJS.Timeout | undefined;

  // 防抖延迟时间（毫秒）- 200ms内多次刷新请求会被合并为一次
  private readonly DEBOUNCE_DELAY = 200;

  // 输出通道 - 用于显示调试日志
  // 用户可以在"输出"面板中查看这些日志
  private outputChannel: vscode.OutputChannel;

  // 自定义模块缓存 - 存储扫描结果
  private customModulesCache: {
    agents: Array<{ type: string; class_name: string; description: string; file_path: string }>;
    envs: Array<{ type: string; class_name: string; description: string; file_path: string }>;
  } = { agents: [], envs: [] };

  // Agent Skills 缓存
  private agentSkillsCache: Array<{
    name: string; priority: number; source: string; enabled: boolean; path: string; has_skill_md: boolean;
  }> = [];

  // Workspace Manager - 本地文件操作
  private workspaceManager: WorkspaceManager;

  /**
   * 构造函数
   * @param context - ExtensionContext，VSCode扩展的上下文对象
   * @param apiClient - ApiClient，与后端通信的客户端
   * 
   * ExtensionContext包含：
   * - subscriptions: 用于注册需要清理的资源（监听器、命令等）
   * - extensionPath: 扩展的安装路径
   * - workspaceState/globalState: 存储扩展的状态数据
   */
  constructor(private context: vscode.ExtensionContext, private apiClient: ApiClient) {
    // 创建输出通道，用于显示调试日志
    // 用户可以在VSCode的"输出"面板中选择"AI Social Scientist"查看日志
    this.outputChannel = vscode.window.createOutputChannel('AI Social Scientist');
    this.workspaceManager = new WorkspaceManager(context);
    this.log('ProjectStructureProvider initialized');

    // 设置文件系统监听器
    this.setupFileWatchers();

    // 监听工作区文件夹的变化
    // 当用户添加/删除工作区文件夹时，需要重新设置监听器
    vscode.workspace.onDidChangeWorkspaceFolders(() => {
      this.log('Workspace folders changed, reinitializing watchers');
      this.disposeWatcher();  // 清理旧的监听器
      this.setupFileWatchers();  // 重新设置监听器
      this.refresh();  // 刷新视图
    });
  }

  /**
   * 日志记录方法
   * 
   * 将日志同时输出到：
   * 1. 控制台（console.log）- 开发时在调试控制台查看
   * 2. 输出通道（OutputChannel）- 用户可以在VSCode的输出面板查看
   * 
   * @param message - 日志消息
   * @param args - 额外的参数（会被JSON序列化）
   */
  private log(message: string, ...args: any[]): void {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [ProjectStructureProvider] ${message}`;

    // 输出到控制台（开发调试用）
    console.log(logMessage, ...args);

    // 输出到VSCode的输出面板（用户可见）
    this.outputChannel.appendLine(logMessage + (args.length > 0 ? ` ${JSON.stringify(args)}` : ''));
  }

  /**
   * 设置文件系统监听器
   * 
   * FileSystemWatcher可以监听文件系统的变化：
   * - onDidChange: 文件被修改
   * - onDidCreate: 文件被创建
   * - onDidDelete: 文件被删除
   * 
   * 使用RelativePattern可以指定监听的范围
   * 监听模式使用双星号加斜杠加星号表示递归匹配所有文件
   */
  private setupFileWatchers(): void {
    // 获取当前打开的第一个工作区文件夹
    // workspaceFolders是一个数组，支持多根工作区
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      this.log('No workspace folder found, skipping file watcher setup');
      return;
    }

    // 保存工作区路径，后续会用到
    this.workspacePath = workspaceFolder.uri.fsPath;
    this.log(`Setting up file watcher for workspace: ${this.workspacePath}`);

    // 创建文件系统监听器
    // RelativePattern用于指定相对于工作区的文件模式
    // **/* 表示匹配所有文件和文件夹（递归）
    this.watcher = vscode.workspace.createFileSystemWatcher(
      new vscode.RelativePattern(workspaceFolder, '**/*')
    );

    // 监听文件修改事件
    // uri参数是文件的URI（统一资源标识符）
    this.watcher.onDidChange((uri) => {
      this.log(`File changed: ${uri.fsPath}`);
      this.refresh();  // 文件变化时刷新视图
    });

    // 监听文件创建事件
    this.watcher.onDidCreate((uri) => {
      this.log(`File created: ${uri.fsPath}`);
      this.refresh();
    });

    // 监听文件删除事件
    this.watcher.onDidDelete((uri) => {
      this.log(`File deleted: ${uri.fsPath}`);
      this.refresh();
    });

    // 将监听器添加到context.subscriptions
    // 这样当扩展停用时，VSCode会自动调用dispose()清理资源
    // 这是VSCode插件开发的最佳实践，避免内存泄漏
    this.context.subscriptions.push(this.watcher);
    this.log('File watcher setup completed');
  }

  /**
   * 清理文件监听器
   * 
   * 当工作区变化或扩展停用时调用，释放资源
   */
  private disposeWatcher(): void {
    if (this.watcher) {
      this.log('Disposing file watcher');
      this.watcher.dispose();  // 停止监听
      this.watcher = undefined;
    }
  }

  /**
   * 刷新树形视图
   * 
   * 使用防抖（debounce）机制：
   * - 如果200ms内多次调用refresh()，只会在最后一次调用后200ms执行刷新
   * - 这样可以避免频繁刷新，提升性能
   * 
   * 工作原理：
   * 1. 第一次调用：启动200ms定时器
   * 2. 200ms内再次调用：清除旧定时器，启动新定时器
   * 3. 200ms内没有新调用：执行刷新（调用fire()）
   */
  refresh(): void {
    // 如果已有待执行的定时器，先清除它
    if (this.refreshTimer) {
      this.log('Debouncing: clearing existing refresh timer');
      clearTimeout(this.refreshTimer);
    }

    // 设置新的定时器
    // setTimeout返回一个定时器ID，用于后续清除
    this.refreshTimer = setTimeout(() => {
      this.log('Executing debounced refresh');

      // fire()方法会触发onDidChangeTreeData事件
      // VSCode监听到这个事件后，会调用getChildren()重新获取数据
      // 传递undefined表示刷新整个树
      this._onDidChangeTreeData.fire(undefined);

      // 清除定时器引用
      this.refreshTimer = undefined;
    }, this.DEBOUNCE_DELAY);
  }

  /**
   * 清理资源
   * 
   * 当扩展停用时，VSCode会调用这个方法。
   * 需要清理所有资源，避免内存泄漏。
   */
  dispose(): void {
    this.log('Disposing ProjectStructureProvider');

    // 清除待执行的刷新定时器
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = undefined;
    }

    // 清理文件监听器
    this.disposeWatcher();

    // 清理输出通道
    this.outputChannel.dispose();

    // 清理 Workspace Manager
    this.workspaceManager.dispose();
  }

  /**
   * 获取树节点的显示信息
   * 
   * VSCode会为每个节点调用这个方法。
   * 由于ProjectItem本身就是TreeItem，直接返回即可。
   * 
   * @param element - 要显示的节点
   * @returns TreeItem对象，包含节点的显示信息
   */
  getTreeItem(element: ProjectItem): vscode.TreeItem {
    return element;
  }

  /**
   * 获取节点的子节点
   * 
   * 这是TreeDataProvider的核心方法。
   * VSCode会调用这个方法获取树形视图的数据：
   * - 当展开节点时，获取该节点的子节点
   * - 当首次加载视图时，element为undefined，返回根节点
   * 
   * 这个方法实现了递归的树形结构：
   * - 根节点（element为undefined）→ 显示"Research Topic"
   * - Topic节点 → 显示假设和论文
   * - Hypothesis节点 → 显示实验和SIM设置
   * - Experiment节点 → 显示初始化结果和运行结果
   * 
   * @param element - 当前节点，undefined表示根节点
   * @returns 子节点数组
   */
  async getChildren(element?: ProjectItem): Promise<ProjectItem[]> {
    // 获取工作区文件夹
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      return [];  // 没有工作区，返回空数组
    }

    const workspacePath = workspaceFolder.uri.fsPath;

    // 检查工作区状态
    const topicFile = path.join(workspacePath, 'TOPIC.md');
    const envFile = path.join(workspacePath, '.env');
    const hasEnv = fs.existsSync(envFile);
    const hasTopic = fs.existsSync(topicFile);

    // 检查.env是否已配置（有API key）
    const { EnvManager } = await import('./envManager');
    const envManager = new EnvManager();
    const envConfig = envManager.readEnv();
    const hasApiKey = !!(envConfig.llmApiKey?.trim());

    // 检查工作区目录结构是否完整
    const workspaceHealth = this.checkWorkspaceHealth(workspacePath);
    const needsFix = !workspaceHealth.isHealthy;

    // 根节点：显示研究话题
    // element为undefined表示这是根节点
    if (!element) {
      const items: ProjectItem[] = [];

      // 阶段1: 没有.env文件 -> 提示配置环境变量
      if (!hasEnv) {
        const settingsItem = new ProjectItem(
          localize('projectStructure.settings'),
          vscode.TreeItemCollapsibleState.None,
          'settings',
          undefined
        );
        items.push(settingsItem);
        return items;
      }

      // 阶段2: 有.env但没有配置API key -> 提示配置环境变量
      if (hasEnv && !hasApiKey) {
        const settingsItem = new ProjectItem(
          localize('projectStructure.settings'),
          vscode.TreeItemCollapsibleState.None,
          'settings',
          undefined
        );
        items.push(settingsItem);

        // 显示说明信息
        const infoItem = new ProjectItem(
          'API Key required / 需要配置 API 密钥',
          vscode.TreeItemCollapsibleState.None,
          'initWorkspace',
          undefined
        );
        items.push(infoItem);
        return items;
      }

      // 阶段3: 有.env且配置了API key，但没有TOPIC.md -> 提示初始化工作区
      if (hasEnv && hasApiKey && !hasTopic) {
        // 配置设置按钮始终在最上面
        const settingsItem = new ProjectItem(
          localize('projectStructure.settings'),
          vscode.TreeItemCollapsibleState.None,
          'settings',
          undefined
        );
        items.push(settingsItem);

        const initItem = new ProjectItem(
          localize('extension.initProject.button'),
          vscode.TreeItemCollapsibleState.None,
          'initWorkspace',
          undefined
        );
        initItem.command = {
          command: 'aiSocialScientist.initProject',
          title: 'Initialize Workspace'
        };
        items.push(initItem);

        return items;
      }

      // 已初始化：配置设置按钮始终在最上面
      const settingsItem = new ProjectItem(
        localize('projectStructure.settings'),
        vscode.TreeItemCollapsibleState.None,
        'settings',
        undefined
      );
      items.push(settingsItem);

      // 添加 AI Chat 入口
      const aiChatItem = new ProjectItem(
        localize('extension.aiChat.label'),
        vscode.TreeItemCollapsibleState.None,
        'aiChat',
        undefined
      );
      aiChatItem.command = {
        command: 'aiSocialScientist.openChat',
        title: 'Open AI Chat'
      };
      items.push(aiChatItem);

      // 如果工作区目录结构不完整，显示修复按钮
      if (needsFix) {
        const fixItem = new ProjectItem(
          localize('extension.fixWorkspace.button'),
          vscode.TreeItemCollapsibleState.None,
          'fixWorkspace',
          undefined
        );
        fixItem.command = {
          command: 'aiSocialScientist.fixWorkspace',
          title: 'Fix Workspace Directory'
        };
        items.push(fixItem);
      }

      // 添加同步 AI 助手资源节点（可展开，显示可用技能）
      items.push(new ProjectItem(
        localize('projectStructure.syncResources'),
        vscode.TreeItemCollapsibleState.Collapsed,
        'syncResourcesGroup',
        undefined
      ));

      // 添加 Agent Skills 管理节点
      items.push(new ProjectItem(
        localize('projectStructure.agentSkills') || 'Agent Skills',
        vscode.TreeItemCollapsibleState.Collapsed,
        'agentSkillsGroup',
        undefined
      ));

      // 添加环境与智能体组节点（直接点击打开管理页面）
      items.push(new ProjectItem(
        localize('prefillParams.groupTitle'),
        vscode.TreeItemCollapsibleState.None,
        'prefillParamsGroup',
        undefined
      ));

      // 添加 Research Topic 节点
      items.push(new ProjectItem(
        localize('projectStructure.researchTopic'),
        vscode.TreeItemCollapsibleState.Expanded,
        'topic',
        topicFile
      ));

      return items;
    }

    // 同步 AI 助手资源组的子节点
    if (element.type === 'syncResourcesGroup') {
      const items: ProjectItem[] = [];

      // 同步/更新按钮
      const syncActionItem = new ProjectItem(
        localize('projectStructure.syncResourcesAction') || '同步/更新 Skills',
        vscode.TreeItemCollapsibleState.None,
        'syncResourcesAction',
        undefined
      );
      syncActionItem.command = {
        command: 'aiSocialScientist.updateSkills',
        title: 'Sync Skills'
      };
      items.push(syncActionItem);

      // 导入自定义 Skill 按钮
      const importItem = new ProjectItem(
        localize('projectStructure.agentSkillsImport') || '导入 Skill',
        vscode.TreeItemCollapsibleState.None,
        'agentSkillImport',
        undefined
      );
      importItem.command = {
        command: 'aiSocialScientist.importAgentSkill',
        title: 'Import Agent Skill'
      };
      items.push(importItem);

      // 读取扩展中的 skills 目录
      const skillsDir = path.join(this.context.extensionPath, 'skills');
      if (fs.existsSync(skillsDir)) {
        const skillDirs = fs.readdirSync(skillsDir).filter(name => {
          const skillPath = path.join(skillsDir, name);
          const skillMdPath = path.join(skillPath, 'SKILL.md');
          return fs.statSync(skillPath).isDirectory() && fs.existsSync(skillMdPath);
        });

        if (skillDirs.length > 0) {
          // 内置 Skills 分组（可展开）
          const builtinGroup = new ProjectItem(
            `${localize('projectStructure.agentSkillsBuiltin') || '内置 Skills'} (${skillDirs.length})`,
            vscode.TreeItemCollapsibleState.Collapsed,
            'syncBuiltinSkillsGroup',
            undefined
          );
          items.push(builtinGroup);
        }
      }

      // 已安装的自定义 Skills（来自agentSkillsCache）
      const customSkills = this.agentSkillsCache.filter(s => s.source === 'custom');
      if (customSkills.length > 0) {
        const customGroup = new ProjectItem(
          `${localize('projectStructure.agentSkillsCustom') || '自定义 Skills'} (${customSkills.length})`,
          vscode.TreeItemCollapsibleState.Collapsed,
          'syncCustomSkillsGroup',
          undefined
        );
        items.push(customGroup);
      }

      return items;
    }

    // 内置 Skills 分组的子节点（来自扩展目录）
    if (element.type === 'syncBuiltinSkillsGroup') {
      const items: ProjectItem[] = [];
      const skillsDir = path.join(this.context.extensionPath, 'skills');
      if (fs.existsSync(skillsDir)) {
        const skillDirs = fs.readdirSync(skillsDir).filter(name => {
          const skillPath = path.join(skillsDir, name);
          const skillMdPath = path.join(skillPath, 'SKILL.md');
          return fs.statSync(skillPath).isDirectory() && fs.existsSync(skillMdPath);
        });

        for (const skillDir of skillDirs) {
          const skillPath = path.join(skillsDir, skillDir);
          const skillMdPath = path.join(skillPath, 'SKILL.md');
          try {
            const content = fs.readFileSync(skillMdPath, 'utf-8');
            const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---/);
            let skillName = skillDir;
            let skillDescription = '';

            if (frontmatterMatch) {
              const frontmatter = frontmatterMatch[1];
              const nameMatch = frontmatter.match(/^name:\s*(.+)$/m);
              const descMatch = frontmatter.match(/^description:\s*(.+)$/m);
              if (nameMatch) skillName = nameMatch[1].trim();
              if (descMatch) skillDescription = descMatch[1].trim();
            }

            const skillItem = new ProjectItem(
              skillName,
              vscode.TreeItemCollapsibleState.Collapsed,
              'syncBuiltinSkillItem',
              skillPath
            );
            skillItem.tooltip = skillDescription || skillName;
            skillItem.contextValue = 'syncBuiltinSkillItem';
            (skillItem as any).skillName = skillName;
            (skillItem as any).skillDescription = skillDescription;
            (skillItem as any).skillDirPath = skillPath;
            items.push(skillItem);
          } catch {
            items.push(new ProjectItem(skillDir, vscode.TreeItemCollapsibleState.Collapsed, 'syncBuiltinSkillItem', skillPath));
          }
        }
      }
      return items;
    }

    // 内置 Skill Item 展开时显示文件内容
    if (element.type === 'syncBuiltinSkillItem' && element.filePath) {
      const items: ProjectItem[] = [];
      const entries = fs.readdirSync(element.filePath);

      for (const entry of entries) {
        const fullPath = path.join(element.filePath, entry);
        const stat = fs.statSync(fullPath);

        if (stat.isFile()) {
          const fileItem = new ProjectItem(entry, vscode.TreeItemCollapsibleState.None, 'file', fullPath);
          if (entry.toLowerCase().endsWith('.md')) {
            fileItem.command = {
              command: 'markdown.showPreview',
              title: 'Open Preview',
              arguments: [vscode.Uri.file(fullPath)]
            };
          }
          items.push(fileItem);
        } else if (stat.isDirectory()) {
          items.push(new ProjectItem(entry, vscode.TreeItemCollapsibleState.Collapsed, 'file', fullPath));
        }
      }
      return items;
    }

    // 自定义 Skills 分组的子节点（来自工作区）
    if (element.type === 'syncCustomSkillsGroup') {
      const customSkills = this.agentSkillsCache.filter(s => s.source === 'custom');
      return this.createSkillItems(customSkills, false);
    }

    // Agent Skills 组的子节点
    if (element.type === 'agentSkillsGroup') {
      const items: ProjectItem[] = [];

      // 操作按钮组
      const scanItem = new ProjectItem(
        localize('projectStructure.agentSkillsScan') || '🔄 扫描 Skills',
        vscode.TreeItemCollapsibleState.None,
        'agentSkillScan',
        undefined
      );
      scanItem.command = {
        command: 'aiSocialScientist.scanAgentSkills',
        title: 'Scan Agent Skills'
      };
      items.push(scanItem);

      const importItem = new ProjectItem(
        localize('projectStructure.agentSkillsImport') || '📥 导入 Skill',
        vscode.TreeItemCollapsibleState.None,
        'agentSkillImport',
        undefined
      );
      importItem.command = {
        command: 'aiSocialScientist.importAgentSkill',
        title: 'Import Agent Skill'
      };
      items.push(importItem);

      // 分离 builtin 和 custom skills
      const builtinSkills = this.agentSkillsCache.filter(s => s.source === 'builtin');
      const customSkills = this.agentSkillsCache.filter(s => s.source === 'custom');

      // Builtin Skills 分组
      if (builtinSkills.length > 0) {
        const builtinGroup = new ProjectItem(
          `📦 ${localize('projectStructure.agentSkillsBuiltin') || '内置 Skills'} (${builtinSkills.length})`,
          vscode.TreeItemCollapsibleState.Collapsed,
          'agentSkillBuiltinGroup',
          undefined
        );
        items.push(builtinGroup);
      }

      // Custom Skills 分组
      if (customSkills.length > 0) {
        const customGroup = new ProjectItem(
          `🔧 ${localize('projectStructure.agentSkillsCustom') || '自定义 Skills'} (${customSkills.length})`,
          vscode.TreeItemCollapsibleState.Collapsed,
          'agentSkillCustomGroup',
          undefined
        );
        items.push(customGroup);
      }

      // 如果没有任何 skill，显示提示
      if (this.agentSkillsCache.length === 0) {
        const emptyItem = new ProjectItem(
          localize('projectStructure.agentSkillsEmpty') || '暂无 Skills，点击扫描或导入',
          vscode.TreeItemCollapsibleState.None,
          'agentSkillScan',
          undefined
        );
        emptyItem.command = {
          command: 'aiSocialScientist.scanAgentSkills',
          title: 'Scan Agent Skills'
        };
        items.push(emptyItem);
      }

      return items;
    }

    // Builtin Skills 分组的子节点
    if (element.type === 'agentSkillBuiltinGroup') {
      const builtinSkills = this.agentSkillsCache.filter(s => s.source === 'builtin');
      return this.createSkillItems(builtinSkills, true);
    }

    // Custom Skills 分组的子节点
    if (element.type === 'agentSkillCustomGroup') {
      const customSkills = this.agentSkillsCache.filter(s => s.source === 'custom');
      return this.createSkillItems(customSkills, false);
    }

    // Agent Skill Item 展开时显示目录内容
    if (element.type === 'agentSkillItem') {
      const skillDirPath = (element as any).skillDirPath || element.filePath;
      if (!skillDirPath || !fs.existsSync(skillDirPath) || !fs.statSync(skillDirPath).isDirectory()) {
        return [];
      }

      const items: ProjectItem[] = [];
      const entries = fs.readdirSync(skillDirPath);

      for (const entry of entries) {
        const fullPath = path.join(skillDirPath, entry);
        const stat = fs.statSync(fullPath);

        if (stat.isFile()) {
          // 文件节点
          const fileItem = new ProjectItem(
            entry,
            vscode.TreeItemCollapsibleState.None,
            'file',
            fullPath
          );

          // 如果是 Markdown 文件，设置预览命令
          if (entry.toLowerCase().endsWith('.md')) {
            fileItem.command = {
              command: 'markdown.showPreview',
              title: 'Open Preview',
              arguments: [vscode.Uri.file(fullPath)]
            };
          }

          items.push(fileItem);
        } else if (stat.isDirectory()) {
          // 目录节点
          items.push(new ProjectItem(
            entry,
            vscode.TreeItemCollapsibleState.Collapsed,
            'file',
            fullPath
          ));
        }
      }

      return items;
    }

    // 环境与智能体节点的子节点：已移空（测试功能移至webview内）
    if (element.type === 'prefillParamsGroup') {
      return [];
    }

    // 自定义模块节点的子节点：显示扫描结果（已废弃，保留兼容性）
    if (element.type === 'custom') {
      const items: ProjectItem[] = [];

      // 如果有扫描结果,显示分组
      if (this.customModulesCache.agents.length > 0) {
        items.push(new ProjectItem(
          `${localize('projectStructure.customAgents')} (${this.customModulesCache.agents.length})`,
          vscode.TreeItemCollapsibleState.Collapsed,
          'customAgentsGroup',
          undefined
        ));
      }

      if (this.customModulesCache.envs.length > 0) {
        items.push(new ProjectItem(
          `${localize('projectStructure.customEnvs')} (${this.customModulesCache.envs.length})`,
          vscode.TreeItemCollapsibleState.Collapsed,
          'customEnvsGroup',
          undefined
        ));
      }

      return items;
    }

    // 自定义Agents分组节点：显示所有Agent
    if (element.type === 'customAgentsGroup') {
      return this.customModulesCache.agents.map(agent => {
        const item = new ProjectItem(
          agent.class_name,
          vscode.TreeItemCollapsibleState.None,
          'customAgentItem',
          agent.file_path
        );
        item.tooltip = agent.description;
        item.isCustom = true;
        item.moduleType = 'agent';
        item.className = agent.class_name;
        return item;
      });
    }

    // 自定义Envs分组节点：显示所有环境模块
    if (element.type === 'customEnvsGroup') {
      return this.customModulesCache.envs.map(env => {
        const item = new ProjectItem(
          env.class_name,
          vscode.TreeItemCollapsibleState.None,
          'customEnvItem',
          env.file_path
        );
        item.tooltip = env.description;
        item.isCustom = true;
        item.moduleType = 'env';
        item.className = env.class_name;
        return item;
      });
    }

    // Topic节点的子节点：显示假设和论文
    if (element.type === 'topic') {
      const items: ProjectItem[] = [];

      // 查找所有假设目录（hypothesis_12345格式）
      // findDirectories方法会匹配符合正则表达式的目录名
      const hypothesisDirs = this.findDirectories(workspacePath, /^hypothesis_\d+$/);
      if (hypothesisDirs.length > 0) {
        for (const dir of hypothesisDirs) {
          const hypothesisFile = path.join(dir, 'HYPOTHESIS.md');
          const dirName = path.basename(dir);  // 如hypothesis_12345
          // 提取数字部分，转换为友好的显示名称（如"假设 12345"）
          const match = dirName.match(/^hypothesis_(\d+)$/);
          const displayName = match
            ? `${localize('projectStructure.hypothesis')} ${match[1]}`
            : dirName;  // 如果格式不匹配，使用原目录名
          items.push(new ProjectItem(
            displayName,  // 显示为"假设 12345"或"Hypothesis 12345"
            vscode.TreeItemCollapsibleState.Collapsed,  // 可展开
            'hypothesis',
            fs.existsSync(hypothesisFile) ? hypothesisFile : undefined  // 如果存在HYPOTHESIS.md，点击可打开
          ));
        }
      }

      // 查找papers目录，如果有论文文件，创建一个"文献库"节点
      const papersDir = path.join(workspacePath, 'papers');
      if (fs.existsSync(papersDir)) {
        // 创建一个"文献库"节点，可展开显示所有论文
        items.push(new ProjectItem(
          localize('projectStructure.literature'),  // 显示为"文献库"
          vscode.TreeItemCollapsibleState.Collapsed,  // 可展开
          'papers',  // 节点类型为papers
          undefined  // 文献库节点本身不关联文件
        ));
      }

      // 查找user_data目录，如果存在，创建一个"用户数据"节点
      const userDataDir = path.join(workspacePath, 'user_data');
      if (fs.existsSync(userDataDir)) {
        // 创建一个"用户数据"节点，可展开显示所有文件
        items.push(new ProjectItem(
          localize('projectStructure.userData'),  // 显示为"用户数据"
          vscode.TreeItemCollapsibleState.Collapsed,  // 可展开
          'userdata',  // 节点类型为userdata
          undefined  // 用户数据节点本身不关联文件
        ));
      }

      // 查找custom目录，如果存在，创建一个"自定义模块"节点
      const customDir = path.join(workspacePath, 'custom');
      if (fs.existsSync(customDir)) {
        // 创建一个"自定义模块"节点，可展开显示子目录
        items.push(new ProjectItem(
          localize('projectStructure.customModules'),
          vscode.TreeItemCollapsibleState.Collapsed,
          'customWorkspace',
          undefined
        ));
      }

      // 查找presentation目录（分析报告）
      const presentationDir = path.join(workspacePath, 'presentation');
      if (fs.existsSync(presentationDir)) {
        items.push(new ProjectItem(
          localize('projectStructure.presentation'),
          vscode.TreeItemCollapsibleState.Collapsed,
          'presentation',
          undefined
        ));
      }

      // 查找synthesis目录（综合报告）
      const synthesisDir = path.join(workspacePath, 'synthesis');
      if (fs.existsSync(synthesisDir)) {
        items.push(new ProjectItem(
          localize('projectStructure.synthesis'),
          vscode.TreeItemCollapsibleState.Collapsed,
          'synthesis',
          undefined
        ));
      }

      return items;
    }

    // Papers节点（文献库）的子节点：显示所有文件和子目录
    if (element.type === 'papers') {
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (!workspaceFolder) {
        return [];
      }
      const workspacePath = workspaceFolder.uri.fsPath;
      const papersDir = path.join(workspacePath, 'papers');
      const items: ProjectItem[] = [];

      if (fs.existsSync(papersDir)) {
        // 读取目录，忽略mineru_output文件夹
        const entries = fs.readdirSync(papersDir).filter(entry => entry !== 'mineru_output');

        for (const entry of entries) {
          const fullPath = path.join(papersDir, entry);
          const stat = fs.statSync(fullPath);

          if (stat.isFile()) {
            // 如果是文件，创建文件节点
            const fileItem = new ProjectItem(
              entry,  // 文件名作为标签
              vscode.TreeItemCollapsibleState.None,  // 文件没有子节点
              'paper',
              fullPath  // 完整文件路径
            );

            // 如果是 literature_index.json，设置特殊的 tooltip 和命令
            if (entry === 'literature_index.json') {
              try {
                const content = fs.readFileSync(fullPath, 'utf-8');
                const data = JSON.parse(content);
                const count = data.entries?.length || 0;
                fileItem.tooltip = `${localize('projectStructure.literatureIndex')} (${count} ${localize('projectStructure.articles')})`;
                fileItem.description = `(${count} ${localize('projectStructure.articles')})`;
                // 设置特殊的 contextValue 以便显示专用菜单
                fileItem.contextValue = 'paper json literatureIndex';
                // 设置点击命令为文献索引预览
                fileItem.command = {
                  command: 'aiSocialScientist.viewLiteratureIndex',
                  title: 'View Literature Index',
                  arguments: [{ filePath: fullPath }]
                };
              } catch {
                // 解析失败时使用默认 tooltip
              }
            }

            items.push(fileItem);
          } else if (stat.isDirectory()) {
            // 如果是目录，计算目录内的文件数量
            let fileCount = 0;
            try {
              const subEntries = fs.readdirSync(fullPath).filter((sub: string) => sub !== 'mineru_output');
              fileCount = subEntries.filter((sub: string) => {
                const subPath = path.join(fullPath, sub);
                return fs.statSync(subPath).isFile();
              }).length;
            } catch {
              // 忽略错误
            }

            // 创建可展开的目录节点，显示文件数量
            const dirItem = new ProjectItem(
              fileCount > 0 ? `${entry} (${fileCount})` : entry,
              vscode.TreeItemCollapsibleState.Collapsed,  // 可展开
              'paper',  // 使用paper类型表示文献库子项
              fullPath  // 存储目录路径，用于获取子节点
            );
            dirItem.tooltip = `${entry} - ${fileCount} ${localize('projectStructure.files')}`;
            items.push(dirItem);
          }
        }
      }

      return items;
    }

    // 处理paper类型节点：如果是目录，显示其子文件和子目录
    if (element.type === 'paper' && element.filePath) {
      const filePath = element.filePath;
      // 检查是否为目录
      if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
        const items: ProjectItem[] = [];
        // 读取目录内容，忽略mineru_output文件夹
        const entries = fs.readdirSync(filePath).filter(entry => entry !== 'mineru_output');

        for (const entry of entries) {
          const fullPath = path.join(filePath, entry);
          const stat = fs.statSync(fullPath);

          if (stat.isFile()) {
            // 如果是文件，创建文件节点
            items.push(new ProjectItem(
              entry,  // 文件名作为标签
              vscode.TreeItemCollapsibleState.None,  // 文件没有子节点
              'paper',
              fullPath  // 完整文件路径
            ));
          } else if (stat.isDirectory()) {
            // 如果是目录，创建可展开的目录节点
            items.push(new ProjectItem(
              entry,  // 目录名作为标签
              vscode.TreeItemCollapsibleState.Collapsed,  // 可展开
              'paper',  // 使用paper类型
              fullPath  // 存储目录路径，用于获取子节点
            ));
          }
        }

        return items;
      }
    }

    // UserData节点（用户数据）的子节点：显示所有文件
    if (element.type === 'userdata') {
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (!workspaceFolder) {
        return [];
      }
      const workspacePath = workspaceFolder.uri.fsPath;
      const userDataDir = path.join(workspacePath, 'user_data');
      const items: ProjectItem[] = [];

      if (fs.existsSync(userDataDir)) {
        // 读取目录下的所有文件和文件夹，忽略mineru_output文件夹
        const entries = fs.readdirSync(userDataDir).filter(entry => entry !== 'mineru_output');

        for (const entry of entries) {
          const fullPath = path.join(userDataDir, entry);
          const stat = fs.statSync(fullPath);

          if (stat.isFile()) {
            // 如果是文件，创建文件节点
            items.push(new ProjectItem(
              entry,  // 文件名作为标签
              vscode.TreeItemCollapsibleState.None,  // 文件没有子节点
              'file',
              fullPath  // 完整文件路径
            ));
          } else if (stat.isDirectory()) {
            // 如果是目录，创建可展开的目录节点
            // 将目录路径存储在filePath中，用于后续获取子节点
            items.push(new ProjectItem(
              entry,  // 目录名作为标签
              vscode.TreeItemCollapsibleState.Collapsed,  // 可展开
              'file',  // 使用file类型
              fullPath  // 存储目录路径，用于获取子节点
            ));
          }
        }
      }

      return items;
    }

    // 处理file类型节点：如果是目录，显示其子文件和子目录
    if (element.type === 'file' && element.filePath) {
      const filePath = element.filePath;
      // 检查是否为目录
      if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
        const items: ProjectItem[] = [];
        // 读取目录内容，忽略mineru_output文件夹
        const entries = fs.readdirSync(filePath).filter(entry => entry !== 'mineru_output');

        for (const entry of entries) {
          const fullPath = path.join(filePath, entry);
          const stat = fs.statSync(fullPath);

          if (stat.isFile()) {
            // 如果是文件，创建文件节点
            items.push(new ProjectItem(
              entry,  // 文件名作为标签
              vscode.TreeItemCollapsibleState.None,  // 文件没有子节点
              'file',
              fullPath  // 完整文件路径
            ));
          } else if (stat.isDirectory()) {
            // 如果是目录，创建可展开的目录节点
            items.push(new ProjectItem(
              entry,  // 目录名作为标签
              vscode.TreeItemCollapsibleState.Collapsed,  // 可展开
              'file',  // 使用file类型
              fullPath  // 存储目录路径，用于获取子节点
            ));
          }
        }

        return items;
      }
    }

    // Custom Workspace节点（custom/目录）的子节点：显示agents和envs
    if (element.type === 'customWorkspace') {
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (!workspaceFolder) {
        return [];
      }
      const workspacePath = workspaceFolder.uri.fsPath;
      const customDir = path.join(workspacePath, 'custom');
      const items: ProjectItem[] = [];

      if (fs.existsSync(customDir)) {
        const entries = fs.readdirSync(customDir);

        for (const entry of entries) {
          const fullPath = path.join(customDir, entry);
          const stat = fs.statSync(fullPath);

          if (stat.isDirectory()) {
            // 创建可展开的目录节点
            items.push(new ProjectItem(
              entry,
              vscode.TreeItemCollapsibleState.Collapsed,
              'file',  // 使用file类型来复用目录展开逻辑
              fullPath
            ));
          } else if (stat.isFile()) {
            // 创建文件节点
            items.push(new ProjectItem(
              entry,
              vscode.TreeItemCollapsibleState.None,
              'file',
              fullPath
            ));
          }
        }
      }

      return items;
    }

    // Hypothesis节点的子节点：显示实验和SIM设置
    if (element.type === 'hypothesis') {
      // 获取假设目录的路径
      // element.filePath是HYPOTHESIS.md的路径，dirname获取其所在目录
      const hypothesisDir = path.dirname(element.filePath || '');

      // 提取 hypothesis_id（从目录名 hypothesis_xxx 中提取）
      const hypothesisDirName = path.basename(hypothesisDir);
      const hypothesisMatch = hypothesisDirName.match(/^hypothesis_(\d+)$/);
      const hypothesisId = hypothesisMatch ? hypothesisMatch[1] : undefined;

      // 查找该假设下的所有实验目录（experiment_123格式）
      const experimentDirs = this.findDirectories(hypothesisDir, /^experiment_\d+$/);

      const items: ProjectItem[] = [];

      // 为每个实验目录创建节点
      for (const dir of experimentDirs) {
        const experimentFile = path.join(dir, 'EXPERIMENT.md');
        const dirName = path.basename(dir);  // 如experiment_123
        // 提取数字部分，转换为友好的显示名称（如"实验 123"）
        const match = dirName.match(/^experiment_(\d+)$/);
        const experimentId = match ? match[1] : undefined;
        const displayName = match
          ? `${localize('projectStructure.experiment')} ${match[1]}`
          : dirName;  // 如果格式不匹配，使用原目录名
        const item = new ProjectItem(
          displayName,  // 显示为"实验 123"或"Experiment 123"
          vscode.TreeItemCollapsibleState.Collapsed,  // 可展开
          'experiment',
          fs.existsSync(experimentFile) ? experimentFile : undefined
        );
        // Set hypothesis and experiment IDs for replay command
        item.hypothesisId = hypothesisId;
        item.experimentId = experimentId;
        items.push(item);
      }

      // 添加SIM_SETTINGS.json文件节点（如果存在）
      const simSettingsFile = path.join(hypothesisDir, 'SIM_SETTINGS.json');
      if (fs.existsSync(simSettingsFile)) {
        items.push(new ProjectItem(
          localize('projectStructure.simSettings'),  // 显示标签（国际化）
          vscode.TreeItemCollapsibleState.None,  // 文件没有子节点
          'file',
          simSettingsFile
        ));
      }

      return items;
    }

    // Experiment节点的子节点：显示初始化结果和运行结果
    if (element.type === 'experiment') {
      // 获取实验目录的路径
      const experimentDir = path.dirname(element.filePath || '');
      const items: ProjectItem[] = [];

      // 检查init目录（直接包含配置文件：config_params.py, init_config.json, steps.yaml）
      const initDir = path.join(experimentDir, 'init');
      if (fs.existsSync(initDir)) {
        // 读取init目录下的所有文件
        const initFiles = fs.readdirSync(initDir);
        for (const file of initFiles) {
          const filePath = path.join(initDir, file);
          const stat = fs.statSync(filePath);
          if (stat.isFile()) {
            items.push(new ProjectItem(
              `Init: ${file}`,  // 添加"Init:"前缀以便区分
              vscode.TreeItemCollapsibleState.None,
              'file',
              filePath
            ));
          }
        }
      }

      // 检查run目录下的sqlite.db文件
      const runDir = path.join(experimentDir, 'run');
      if (fs.existsSync(runDir)) {
        const dbFile = path.join(runDir, 'sqlite.db');
        if (fs.existsSync(dbFile)) {
          const item = new ProjectItem(
            localize('projectStructure.resultsDatabase'),  // 数据库文件的显示名称
            vscode.TreeItemCollapsibleState.None,
            'file',
            dbFile
          );

          // 如果父节点包含 hypothesisId 和 experimentId，设置打开回放的命令
          if (element.hypothesisId && element.experimentId) {
            item.command = {
              command: 'aiSocialScientist.openReplay',
              title: localize('projectStructure.openReplay'),
              arguments: [{
                hypothesisId: element.hypothesisId,
                experimentId: element.experimentId,
                filePath: dbFile
              }]
            };
            item.contextValue = 'replayableDatabase';
            // item.iconPath = new to.ThemeIcon('play-circle'); // Optional: change icon
          }

          items.push(item);
        }
      }

      return items;
    }

    // Presentation节点（分析报告）的子节点：显示所有假设目录
    if (element.type === 'presentation') {
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (!workspaceFolder) {
        return [];
      }
      const workspacePath = workspaceFolder.uri.fsPath;
      const presentationDir = path.join(workspacePath, 'presentation');
      const items: ProjectItem[] = [];

      if (fs.existsSync(presentationDir)) {
        // 读取目录，查找所有hypothesis_*目录
        const entries = fs.readdirSync(presentationDir);
        for (const entry of entries) {
          const fullPath = path.join(presentationDir, entry);
          const stat = fs.statSync(fullPath);

          if (stat.isDirectory() && entry.startsWith('hypothesis_')) {
            // 提取假设ID，转换为友好显示名称
            const match = entry.match(/^hypothesis_(\d+)$/);
            const displayName = match
              ? `${localize('projectStructure.hypothesis')} ${match[1]}`
              : entry;
            items.push(new ProjectItem(
              displayName,
              vscode.TreeItemCollapsibleState.Collapsed,
              'presentationHypothesis',
              fullPath
            ));
          }
        }
      }

      return items;
    }

    // PresentationHypothesis节点的子节点：显示所有实验目录
    if (element.type === 'presentationHypothesis' && element.filePath) {
      const items: ProjectItem[] = [];

      if (fs.existsSync(element.filePath) && fs.statSync(element.filePath).isDirectory()) {
        const entries = fs.readdirSync(element.filePath);
        for (const entry of entries) {
          const fullPath = path.join(element.filePath, entry);
          const stat = fs.statSync(fullPath);

          if (stat.isDirectory() && entry.startsWith('experiment_')) {
            // 提取实验ID，转换为友好显示名称
            const match = entry.match(/^experiment_(\d+)$/);
            const displayName = match
              ? `${localize('projectStructure.experiment')} ${match[1]}`
              : entry;
            items.push(new ProjectItem(
              displayName,
              vscode.TreeItemCollapsibleState.Collapsed,
              'presentationExperiment',
              fullPath
            ));
          }
        }
      }

      return items;
    }

    // PresentationExperiment节点的子节点：显示报告文件和数据目录
    if (element.type === 'presentationExperiment' && element.filePath) {
      const items: ProjectItem[] = [];

      if (fs.existsSync(element.filePath) && fs.statSync(element.filePath).isDirectory()) {
        const entries = fs.readdirSync(element.filePath);

        // 按优先级查找报告文件：语言特定版本优先于通用版本
        const reportFiles: { [key: string]: string } = {};
        for (const entry of entries) {
          const fullPath = path.join(element.filePath, entry);
          const stat = fs.statSync(fullPath);
          if (stat.isFile()) {
            reportFiles[entry] = fullPath;
          }
        }

        // 添加中文 HTML 报告
        if (reportFiles['report_zh.html']) {
          const item = new ProjectItem(
            localize('projectStructure.reportHtmlZh'),
            vscode.TreeItemCollapsibleState.None,
            'reportHtml',
            reportFiles['report_zh.html']
          );
          item.command = {
            command: 'livePreview.start.preview.atFile',
            title: 'Open with Live Preview',
            arguments: [vscode.Uri.file(reportFiles['report_zh.html'])]
          };
          items.push(item);
        }

        // 添加英文 HTML 报告
        if (reportFiles['report_en.html']) {
          const item = new ProjectItem(
            localize('projectStructure.reportHtmlEn'),
            vscode.TreeItemCollapsibleState.None,
            'reportHtml',
            reportFiles['report_en.html']
          );
          item.command = {
            command: 'livePreview.start.preview.atFile',
            title: 'Open with Live Preview',
            arguments: [vscode.Uri.file(reportFiles['report_en.html'])]
          };
          items.push(item);
        }

        // 如果没有语言特定版本，添加通用 HTML 报告
        if (!reportFiles['report_zh.html'] && !reportFiles['report_en.html'] && reportFiles['report.html']) {
          const item = new ProjectItem(
            localize('projectStructure.reportHtml'),
            vscode.TreeItemCollapsibleState.None,
            'reportHtml',
            reportFiles['report.html']
          );
          item.command = {
            command: 'livePreview.start.preview.atFile',
            title: 'Open with Live Preview',
            arguments: [vscode.Uri.file(reportFiles['report.html'])]
          };
          items.push(item);
        }

        // 添加中文 Markdown 报告
        if (reportFiles['report_zh.md']) {
          const item = new ProjectItem(
            localize('projectStructure.reportMdZh'),
            vscode.TreeItemCollapsibleState.None,
            'reportMd',
            reportFiles['report_zh.md']
          );
          item.command = {
            command: 'markdown.showPreview',
            title: 'Open Preview',
            arguments: [vscode.Uri.file(reportFiles['report_zh.md'])]
          };
          items.push(item);
        }

        // 添加英文 Markdown 报告
        if (reportFiles['report_en.md']) {
          const item = new ProjectItem(
            localize('projectStructure.reportMdEn'),
            vscode.TreeItemCollapsibleState.None,
            'reportMd',
            reportFiles['report_en.md']
          );
          item.command = {
            command: 'markdown.showPreview',
            title: 'Open Preview',
            arguments: [vscode.Uri.file(reportFiles['report_en.md'])]
          };
          items.push(item);
        }

        // 如果没有语言特定版本，添加通用 Markdown 报告
        if (!reportFiles['report_zh.md'] && !reportFiles['report_en.md'] && reportFiles['report.md']) {
          const item = new ProjectItem(
            localize('projectStructure.reportMd'),
            vscode.TreeItemCollapsibleState.None,
            'reportMd',
            reportFiles['report.md']
          );
          item.command = {
            command: 'markdown.showPreview',
            title: 'Open Preview',
            arguments: [vscode.Uri.file(reportFiles['report.md'])]
          };
          items.push(item);
        }

        // 添加 data 目录（分析数据）
        const dataDir = path.join(element.filePath, 'data');
        if (fs.existsSync(dataDir)) {
          items.push(new ProjectItem(
            localize('projectStructure.analysisData'),
            vscode.TreeItemCollapsibleState.Collapsed,
            'file',
            dataDir
          ));
        }

        // 添加 charts 目录（图表）
        const chartsDir = path.join(element.filePath, 'charts');
        if (fs.existsSync(chartsDir)) {
          items.push(new ProjectItem(
            localize('projectStructure.reportCharts'),
            vscode.TreeItemCollapsibleState.Collapsed,
            'file',
            chartsDir
          ));
        }

        // 添加 assets 目录（资源）
        const assetsDir = path.join(element.filePath, 'assets');
        if (fs.existsSync(assetsDir)) {
          items.push(new ProjectItem(
            localize('projectStructure.reportAssets'),
            vscode.TreeItemCollapsibleState.Collapsed,
            'file',
            assetsDir
          ));
        }
      }

      return items;
    }


    // Synthesis节点（综合报告）的子节点：显示所有综合报告文件
    if (element.type === 'synthesis') {
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (!workspaceFolder) {
        return [];
      }
      const workspacePath = workspaceFolder.uri.fsPath;
      const synthesisDir = path.join(workspacePath, 'synthesis');
      const items: ProjectItem[] = [];

      if (fs.existsSync(synthesisDir)) {
        const entries = fs.readdirSync(synthesisDir);
        
        // 分组报告：按基础名称和时间戳分组，支持双语版本
        const reportGroups: { [key: string]: { [lang: string]: string } } = {};
        
        for (const entry of entries) {
          const fullPath = path.join(synthesisDir, entry);
          const stat = fs.statSync(fullPath);
          
          if (stat.isFile() && entry.startsWith('synthesis_report_')) {
            // 匹配带语言后缀的文件: synthesis_report_YYYYMMDD_HHMMSS_(zh|en).(html|md)
            const langMatch = entry.match(/^synthesis_report_(\d+)_(zh|en)\.(html|md)$/);
            // 匹配通用文件: synthesis_report_YYYYMMDD_HHMMSS.(html|md)
            const genericMatch = entry.match(/^synthesis_report_(\d+)\.(html|md)$/);
            
            if (langMatch) {
              const timestamp = langMatch[1];
              const lang = langMatch[2];
              const ext = langMatch[3];
              const key = `${timestamp}_${ext}`;
              
              if (!reportGroups[key]) {
                reportGroups[key] = {};
              }
              reportGroups[key][lang] = fullPath;
            } else if (genericMatch) {
              const timestamp = genericMatch[1];
              const ext = genericMatch[2];
              const key = `${timestamp}_${ext}`;
              
              if (!reportGroups[key]) {
                reportGroups[key] = {};
              }
              reportGroups[key]['generic'] = fullPath;
            }
          }
        }
        
        // 生成显示项：优先显示语言特定版本，如果没有则显示通用版本
        for (const [key, paths] of Object.entries(reportGroups)) {
          const [timestamp, ext] = key.split('_');
          const isHtml = ext === 'html';
          
          if (isHtml) {
            // 中文 HTML
            if (paths.zh) {
              const item = new ProjectItem(
                `${localize('projectStructure.synthesis')} ${timestamp} (${localize('projectStructure.reportHtmlZh')})`,
                vscode.TreeItemCollapsibleState.None,
                'reportHtml',
                paths.zh
              );
              item.command = {
                command: 'livePreview.start.preview.atFile',
                title: 'Open with Live Preview',
                arguments: [vscode.Uri.file(paths.zh)]
              };
              items.push(item);
            }
            
            // 英文 HTML
            if (paths.en) {
              const item = new ProjectItem(
                `${localize('projectStructure.synthesis')} ${timestamp} (${localize('projectStructure.reportHtmlEn')})`,
                vscode.TreeItemCollapsibleState.None,
                'reportHtml',
                paths.en
              );
              item.command = {
                command: 'livePreview.start.preview.atFile',
                title: 'Open with Live Preview',
                arguments: [vscode.Uri.file(paths.en)]
              };
              items.push(item);
            }
            
            // 通用 HTML（仅当没有语言特定版本时）
            if (!paths.zh && !paths.en && paths.generic) {
              const item = new ProjectItem(
                `${localize('projectStructure.synthesis')} ${timestamp}`,
                vscode.TreeItemCollapsibleState.None,
                'reportHtml',
                paths.generic
              );
              item.command = {
                command: 'livePreview.start.preview.atFile',
                title: 'Open with Live Preview',
                arguments: [vscode.Uri.file(paths.generic)]
              };
              items.push(item);
            }
          } else {
            // Markdown
            // 中文 MD
            if (paths.zh) {
              const item = new ProjectItem(
                `${localize('projectStructure.synthesis')} ${timestamp} (${localize('projectStructure.reportMdZh')})`,
                vscode.TreeItemCollapsibleState.None,
                'reportMd',
                paths.zh
              );
              item.command = {
                command: 'markdown.showPreview',
                title: 'Open Preview',
                arguments: [vscode.Uri.file(paths.zh)]
              };
              items.push(item);
            }
            
            // 英文 MD
            if (paths.en) {
              const item = new ProjectItem(
                `${localize('projectStructure.synthesis')} ${timestamp} (${localize('projectStructure.reportMdEn')})`,
                vscode.TreeItemCollapsibleState.None,
                'reportMd',
                paths.en
              );
              item.command = {
                command: 'markdown.showPreview',
                title: 'Open Preview',
                arguments: [vscode.Uri.file(paths.en)]
              };
              items.push(item);
            }
            
            // 通用 MD（仅当没有语言特定版本时）
            if (!paths.zh && !paths.en && paths.generic) {
              const item = new ProjectItem(
                `${localize('projectStructure.synthesis')} ${timestamp} (${localize('projectStructure.reportMd')})`,
                vscode.TreeItemCollapsibleState.None,
                'reportMd',
                paths.generic
              );
              item.command = {
                command: 'markdown.showPreview',
                title: 'Open Preview',
                arguments: [vscode.Uri.file(paths.generic)]
              };
              items.push(item);
            }
          }
        }
      }

      return items;
    }

    // 其他类型的节点没有子节点
    return [];
  }

  /**
   * 查找符合模式的目录
   * 
   * 辅助方法，用于查找符合特定命名模式的目录。
   * 例如：查找所有hypothesis_12345格式的目录。
   * 
   * @param parentDir - 父目录路径
   * @param pattern - 正则表达式，用于匹配目录名
   * @returns 匹配的目录路径数组（已排序）
   */
  private findDirectories(parentDir: string, pattern: RegExp): string[] {
    // 如果父目录不存在，返回空数组
    if (!fs.existsSync(parentDir)) {
      return [];
    }

    // 读取目录内容，忽略mineru_output文件夹
    return fs.readdirSync(parentDir)
      .filter(name => {
        // 忽略mineru_output文件夹
        if (name === 'mineru_output') {
          return false;
        }
        const fullPath = path.join(parentDir, name);
        // 检查是否为目录且名称匹配正则表达式
        return fs.statSync(fullPath).isDirectory() && pattern.test(name);
      })
      .map(name => path.join(parentDir, name))  // 转换为完整路径
      .sort();  // 排序，确保顺序一致
  }

  /**
   * 初始化研究项目
   * 
   * 创建一个新的研究项目，包括：
   * 1. 创建TOPIC.md文件
   * 2. 创建papers目录
   * 
   * 这个方法通常由命令调用（如"Initialize Research Project"命令）。
   * 
   * @param topic - 研究话题的标题
   */
  async initProject(topic: string): Promise<void> {
    // 获取工作区文件夹
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      vscode.window.showErrorMessage(localize('projectStructure.noWorkspace'));
      return;
    }

    const workspacePath = workspaceFolder.uri.fsPath;

    // 检查 .agentsociety 文件夹是否存在
    const dotAgentSocietyPath = path.join(workspacePath, '.agentsociety');
    if (fs.existsSync(dotAgentSocietyPath)) {
      const confirm = await vscode.window.showWarningMessage(
        localize('projectStructure.initWorkspace.warnExists'),
        { modal: true },
        localize('projectStructure.initWorkspace.confirm'),
        localize('projectStructure.initWorkspace.cancel')
      );
      if (confirm !== localize('projectStructure.initWorkspace.confirm')) {
        return;
      }
    }

    try {
      // 使用进度提示显示初始化过程
      const result = await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: localize('workspaceInit.initializing'),
          cancellable: false,
        },
        async (progress) => {
          // 使用本地 WorkspaceManager 初始化，传递 progress 对象
          return await this.workspaceManager.init({ topic, progress });
        }
      );

      if (result.success) {
        vscode.window.showInformationMessage(localize('workspaceInit.success', topic));
      } else {
        // 失败时显示错误消息
        vscode.window.showErrorMessage(result.message);
      }
    } catch (error: any) {
      // 异常时也显示错误消息
      vscode.window.showErrorMessage(localize('projectStructure.initWorkspace.failed', error.message || error));
    }

    // 刷新视图，显示新创建的文件和目录
    this.refresh();
  }

  /**
   * 同步助手资源 - 复制最新技能和 CLAUDE.md 到工作区
   */
  async updateSkills(): Promise<void> {
    try {
      vscode.window.showInformationMessage(localize('customModules.syncAssistant.updating'));

      const result = await this.workspaceManager.copySkills();

      if (result.success) {
        const message = localize('customModules.syncAssistant.success', result.copied.length, result.message);
        if (result.claudeMdUpdated) {
          vscode.window.showInformationMessage(message + ' - ' + localize('customModules.syncAssistant.claudeMdUpdated'));
        } else {
          vscode.window.showInformationMessage(message);
        }
      } else {
        vscode.window.showErrorMessage(result.message);
      }
    } catch (error: any) {
      vscode.window.showErrorMessage(localize('customModules.syncAssistant.failed', error.message || error));
    }
  }

  /**
   * 获取 Skills 状态
   */
  getSkillsStatus(): { skillsDirExists: boolean; installedSkills: string[] } {
    return this.workspaceManager.getSkillsStatus();
  }

  /**
   * 扫描自定义模块
   */
  async scanCustomModules(): Promise<void> {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      vscode.window.showErrorMessage(localize('customModules.noWorkspace'));
      return;
    }

    const workspacePath = workspaceFolder.uri.fsPath;

    try {
      vscode.window.showInformationMessage(localize('customModules.scanning'));

      const response = await this.apiClient.scanCustomModules({
        workspace_path: workspacePath
      });

      if (response.success) {
        // 获取扫描后的模块列表
        const listResponse = await this.apiClient.listCustomModules();

        if (listResponse.success) {
          // 过滤出自定义模块（is_custom 为 true）
          this.customModulesCache.agents = listResponse.agents.filter(a => a.is_custom);
          this.customModulesCache.envs = listResponse.envs.filter(e => e.is_custom);

          this.log(`Custom modules scan completed: ${this.customModulesCache.agents.length} agents, ${this.customModulesCache.envs.length} envs`);

          vscode.window.showInformationMessage(
            localize('customModules.scanSuccess') +
            ` (${this.customModulesCache.agents.length} ${localize('projectStructure.customAgents')}, ` +
            `${this.customModulesCache.envs.length} ${localize('projectStructure.customEnvs')})`
          );

          // 刷新视图
          this.refresh();
        }
      } else {
        vscode.window.showErrorMessage(localize('customModules.scanFailed', response.message || 'Unknown error'));
      }
    } catch (error: any) {
      this.log(`Scan custom modules failed: ${error}`);
      vscode.window.showErrorMessage(localize('customModules.scanFailed', error.message || error));
    }
  }

  /**
   * 测试自定义模块
   */
  async testCustomModules(): Promise<void> {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      vscode.window.showErrorMessage(localize('customModules.noWorkspace'));
      return;
    }

    const workspacePath = workspaceFolder.uri.fsPath;

    try {
      vscode.window.showInformationMessage(localize('customModules.testing'));

      const response = await this.apiClient.testCustomModules({
        workspace_path: workspacePath
      });

      if (response.success) {
        vscode.window.showInformationMessage(
          localize('customModules.testSuccess')
        );

        // 如果有测试输出，显示在输出通道
        if (response.test_output) {
          this.outputChannel.show();
          this.outputChannel.appendLine('=== Custom Modules Test Output ===');
          this.outputChannel.appendLine(response.test_output);
        }
      } else {
        vscode.window.showErrorMessage(
          localize('customModules.testFailed', response.error || 'Unknown error')
        );
      }
    } catch (error: any) {
      this.log(`Test custom modules failed: ${error}`);
      vscode.window.showErrorMessage(localize('customModules.testFailed', error.message || error));
    }
  }

  /**
   * 检查工作区目录结构健康状态
   * @returns 工作区健康状态信息
   */
  checkWorkspaceHealth(workspacePath: string): {
    isHealthy: boolean;
    missingItems: string[];
    issues: string[];
  } {
    const missingItems: string[] = [];
    const issues: string[] = [];

    // 必需的目录
    const requiredDirs = [
      'papers',
      'user_data',
      'custom',
      'custom/agents',
      'custom/envs',
      '.agentsociety',
      '.claude',
      '.claude/skills'
    ];

    // 必需的文件
    const requiredFiles = [
      'TOPIC.md',
      'CLAUDE.md',
      'AGENTS.md',
      '.env',
      'papers/literature_index.json',
      '.agentsociety/prefill_params.json'
    ];

    // 检查目录
    for (const dir of requiredDirs) {
      const dirPath = path.join(workspacePath, dir);
      if (!fs.existsSync(dirPath)) {
        missingItems.push(`${dir}/`);
      }
    }

    // 检查文件
    for (const file of requiredFiles) {
      const filePath = path.join(workspacePath, file);
      if (!fs.existsSync(filePath)) {
        missingItems.push(file);
      }
    }

    // 检查custom目录中是否有示例文件（仅作为警告）
    const customAgentsDir = path.join(workspacePath, 'custom', 'agents');
    const customEnvsDir = path.join(workspacePath, 'custom', 'envs');
    if (fs.existsSync(customAgentsDir)) {
      const agents = fs.readdirSync(customAgentsDir);
      if (agents.length === 0 || agents.every(f => f.startsWith('__') || f === 'examples')) {
        issues.push('custom/agents/ 目录为空或只有示例文件');
      }
    }

    return {
      isHealthy: missingItems.length === 0,
      missingItems,
      issues
    };
  }

  /**
   * 修复工作区目录结构
   */
  async fixWorkspace(): Promise<void> {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      vscode.window.showErrorMessage(localize('customModules.noWorkspace'));
      return;
    }

    const workspacePath = workspaceFolder.uri.fsPath;
    const health = this.checkWorkspaceHealth(workspacePath);

    if (health.isHealthy) {
      vscode.window.showInformationMessage(localize('workspaceFix.healthy'));
      return;
    }

    // 显示问题并询问是否修复
    const missingList = health.missingItems.map(i => `  - ${i}`).join('\n');
    const message = localize('workspaceFix.confirm', health.missingItems.length, missingList);

    const confirm = await vscode.window.showWarningMessage(
      message,
      { modal: true },
      'Fix / 修复',
      'Cancel / 取消'
    );

    if (confirm !== 'Fix / 修复') {
      return;
    }

    try {
      // 使用 WorkspaceManager 来修复工作区
      const result = await this.workspaceManager.init({ topic: 'Fix Workspace' });

      if (result.success) {
        vscode.window.showInformationMessage(localize('workspaceFix.fixed', result.filesCreated?.length || 0));
        this.refresh();
      } else {
        vscode.window.showErrorMessage(localize('workspaceFix.failed', result.message));
      }
    } catch (error: any) {
      this.log(`Fix workspace failed: ${error}`);
      vscode.window.showErrorMessage(localize('workspaceFix.failed', error.message || error));
    }
  }

  // ========== Agent Skills 管理 ==========

  async scanAgentSkills(): Promise<void> {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    try {
      const response = await this.apiClient.scanAgentSkills(workspaceFolder?.uri.fsPath);
      if (response.success) {
        vscode.window.showInformationMessage(response.message);
        await this.refreshAgentSkillsCache();
        this.refresh();
      }
    } catch (error: any) {
      vscode.window.showErrorMessage(`扫描 Agent Skills 失败: ${error.message || error}`);
    }
  }

  async importAgentSkill(): Promise<void> {
    // 提供多种导入方式选择
    const importOptions = [
      { label: '$(folder) 从本地目录导入', description: localize('projectStructure.skillImportLocal') || '选择本地 Skill 目录', action: 'local' },
      { label: '$(globe) 从 URL 导入 (Git)', description: localize('projectStructure.skillImportUrl') || '从 Git 仓库 URL 克隆', action: 'url' },
    ];

    const selected = await vscode.window.showQuickPick(importOptions, {
      placeHolder: localize('projectStructure.skillImportPlaceholder') || '选择 Skill 导入方式',
    });

    if (!selected) { return; }

    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];

    if (selected.action === 'local') {
      // 从本地目录导入
      const uris = await vscode.window.showOpenDialog({
        canSelectFolders: true,
        canSelectFiles: false,
        canSelectMany: false,
        openLabel: localize('projectStructure.skillImportLocal') || 'Import Skill Directory',
      });
      if (!uris || uris.length === 0) { return; }

      try {
        const response = await this.apiClient.importAgentSkill(
          uris[0].fsPath,
          workspaceFolder?.uri.fsPath
        );
        if (response.success) {
          vscode.window.showInformationMessage(response.message);
          await this.refreshAgentSkillsCache();
          this.refresh();
        }
      } catch (error: any) {
        vscode.window.showErrorMessage(`导入 Agent Skill 失败: ${error.message || error}`);
      }
    } else if (selected.action === 'url') {
      // 从 URL 导入（通过 Git 克隆）
      const url = await vscode.window.showInputBox({
        prompt: localize('projectStructure.skillImportUrlPrompt') || '输入 Skill Git 仓库 URL',
        placeHolder: 'https://github.com/user/skill-name.git',
        validateInput: (value) => {
          if (!value || value.trim().length === 0) {
            return localize('projectStructure.skillImportUrlEmpty') || 'URL 不能为空';
          }
          if (!value.startsWith('http') && !value.startsWith('git@')) {
            return localize('projectStructure.skillImportUrlInvalid') || '请输入有效的 Git URL';
          }
          return null;
        },
      });

      if (!url) { return; }

      // 执行 Git 克隆
      const customSkillsDir = path.join(workspaceFolder?.uri.fsPath || '', 'custom', 'skills');
      const skillName = url.split('/').pop()?.replace('.git', '') || 'imported-skill';
      const targetDir = path.join(customSkillsDir, skillName);

      try {
        // 确保目录存在
        if (!fs.existsSync(customSkillsDir)) {
          fs.mkdirSync(customSkillsDir, { recursive: true });
        }

        // 检查是否已存在
        if (fs.existsSync(targetDir)) {
          const overwrite = await vscode.window.showWarningMessage(
            `Skill "${skillName}" 已存在，是否覆盖？`,
            { modal: true },
            '覆盖',
            '取消'
          );
          if (overwrite !== '覆盖') {
            return;
          }
          // 删除旧目录
          fs.rmSync(targetDir, { recursive: true, force: true });
        }

        // 显示进度
        await vscode.window.withProgress(
          {
            location: vscode.ProgressLocation.Notification,
            title: `正在克隆 Skill: ${skillName}`,
            cancellable: false,
          },
          async () => {
            const { execSync } = require('child_process');
            execSync(`git clone --depth 1 "${url}" "${targetDir}"`, { stdio: 'pipe' });
          }
        );

        // 删除 .git 目录（不需要版本控制）
        const gitDir = path.join(targetDir, '.git');
        if (fs.existsSync(gitDir)) {
          fs.rmSync(gitDir, { recursive: true, force: true });
        }

        vscode.window.showInformationMessage(`Skill "${skillName}" 导入成功`);

        // 扫描并刷新
        await this.apiClient.scanAgentSkills(workspaceFolder?.uri.fsPath);
        await this.refreshAgentSkillsCache();
        this.refresh();
      } catch (error: any) {
        vscode.window.showErrorMessage(`从 URL 导入 Skill 失败: ${error.message || error}`);
      }
    }
  }

  async toggleAgentSkill(item: ProjectItem): Promise<void> {
    if (!item || item.type !== 'agentSkillItem') { return; }

    // 从存储的 skillName 获取名称，或从 label 提取
    const name = (item as any).skillName || item.label?.toString().replace(/^[✓○]\s+/, '').split(' ')[0];
    if (!name) { return; }

    const isEnabled = item.contextValue?.includes('enabled');
    try {
      const response = isEnabled
        ? await this.apiClient.disableAgentSkill(name)
        : await this.apiClient.enableAgentSkill(name);
      if (response.success) {
        vscode.window.showInformationMessage(response.message);
        await this.refreshAgentSkillsCache();
        this.refresh();
      }
    } catch (error: any) {
      vscode.window.showErrorMessage(`切换 Skill 状态失败: ${error.message || error}`);
    }
  }

  /**
   * 创建 Skill 项列表
   * @param skills - skill 列表
   * @param isBuiltin - 是否为内置 skill
   * @returns ProjectItem 列表
   */
  private createSkillItems(
    skills: Array<{ name: string; priority: number; source: string; enabled: boolean; path: string; has_skill_md: boolean }>,
    isBuiltin: boolean
  ): ProjectItem[] {
    const items: ProjectItem[] = [];

    for (const skill of skills) {
      // 构建显示标签：启用状态 + 名称
      const statusIcon = skill.enabled ? '✓' : '○';
      const label = `${statusIcon} ${skill.name}`;

      // 检查是否有 SKILL.md
      const skillMdPath = skill.has_skill_md ? path.join(skill.path, 'SKILL.md') : undefined;

      // 判断是否可展开
      const isDir = fs.existsSync(skill.path) && fs.statSync(skill.path).isDirectory();
      const collapsibleState = isDir
        ? vscode.TreeItemCollapsibleState.Collapsed
        : vscode.TreeItemCollapsibleState.None;

      const item = new ProjectItem(
        label,
        collapsibleState,
        'agentSkillItem',
        skillMdPath  // 只传递 SKILL.md 路径，不传递目录路径
      );

      // 设置 tooltip：显示详细信息
      const statusText = skill.enabled
        ? (localize('projectStructure.skillEnabled') || '已启用')
        : (localize('projectStructure.skillDisabled') || '已禁用');
      item.tooltip = `${skill.name}\n${localize('projectStructure.skillPriority') || '优先级'}: ${skill.priority}\n${statusText}`;

      // 设置 contextValue：区分启用/禁用状态，以及 builtin/custom
      // 格式：agentSkillItem enabled builtin 或 agentSkillItem disabled custom
      const sourceTag = isBuiltin ? 'builtin' : 'custom';
      item.contextValue = skill.enabled
        ? `agentSkillItem enabled ${sourceTag}`
        : `agentSkillItem disabled ${sourceTag}`;

      // 存储额外信息
      (item as any).skillDirPath = skill.path;
      (item as any).skillName = skill.name;
      (item as any).isBuiltin = isBuiltin;
      (item as any).hasSkillMd = skill.has_skill_md;

      if (skill.has_skill_md) {
        item.command = {
          command: 'aiSocialScientist.openAgentSkillDoc',
          title: 'Open Skill Documentation',
          arguments: [skill.name, skill.path, isBuiltin]
        };
      }

      // 设置描述：显示优先级
      item.description = `P${skill.priority}`;

      items.push(item);
    }

    return items;
  }

  /**
   * 刷新 Agent Skills 缓存（公开方法）
   */
  async refreshAgentSkillsCache(): Promise<void> {
    try {
      const response = await this.apiClient.listAgentSkills();
      if (response.success) {
        this.agentSkillsCache = response.skills;
      }
    } catch {
      this.agentSkillsCache = [];
    }
  }

  /**
   * 打开 Skill 文档（SKILL.md）
   *
   * 对于内置 skill，文件路径可能在 Python 包内，前端无法直接访问，
   * 因此需要通过 API 获取内容并创建临时文件显示。
   * 对于自定义 skill，直接打开工作区中的文件。
   *
   * @param skillName - Skill 名称
   * @param skillPath - Skill 目录路径
   * @param isBuiltin - 是否为内置 skill
   */
  async openAgentSkillDoc(skillName: string, skillPath: string, isBuiltin: boolean): Promise<void> {
    const skillMdPath = path.join(skillPath, 'SKILL.md');

    // 对于自定义 skill，尝试直接打开文件
    if (!isBuiltin && fs.existsSync(skillMdPath)) {
      const uri = vscode.Uri.file(skillMdPath);
      await vscode.commands.executeCommand('markdown.showPreview', uri);
      return;
    }

    // 对于内置 skill 或文件不存在的情况，通过 API 获取内容
    try {
      const response = await this.apiClient.getAgentSkillInfo(skillName);
      if (response.success && response.skill_md) {
        // 创建临时文件显示内容
        const tempDir = path.join(this.context.globalStorageUri.fsPath, 'skill-docs');
        if (!fs.existsSync(tempDir)) {
          fs.mkdirSync(tempDir, { recursive: true });
        }

        const tempFilePath = path.join(tempDir, `${skillName}.md`);
        fs.writeFileSync(tempFilePath, response.skill_md, 'utf-8');

        const uri = vscode.Uri.file(tempFilePath);
        await vscode.commands.executeCommand('markdown.showPreview', uri);
      } else {
        vscode.window.showWarningMessage(`Skill "${skillName}" 没有可用的文档`);
      }
    } catch (error: any) {
      vscode.window.showErrorMessage(`无法打开 Skill 文档: ${error.message || error}`);
    }
  }
}
