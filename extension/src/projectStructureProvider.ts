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
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { localize } from './i18n';
import { ApiClient } from './apiClient';

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
    public readonly type: 'topic' | 'hypothesis' | 'experiment' | 'paper' | 'file' | 'papers' | 'userdata' | 'chat' | 'prefillParams' | 'prefillParamsGroup' | 'prefillParamsEnv' | 'prefillParamsAgent' | 'settings' | 'custom' | 'customScan' | 'customTest' | 'customClean' | 'customAgentItem' | 'customEnvItem' | 'customAgentsGroup' | 'customEnvsGroup' | 'presentation' | 'presentationHypothesis' | 'presentationExperiment' | 'synthesis' | 'reportHtml' | 'reportMd',
    public readonly filePath?: string
  ) {
    // 调用父类构造函数，初始化树节点
    super(label, collapsibleState);

    // tooltip: 鼠标悬停时显示的提示信息
    this.tooltip = filePath || label;

    // 检查是否为 markdown 文件（用于后续的 contextValue 和命令设置）
    const isMarkdown = filePath && filePath.toLowerCase().endsWith('.md');

    // contextValue: 用于上下文菜单的条件判断
    // 例如：当contextValue为'hypothesis'时，可以显示特定的右键菜单项
    // 对于 markdown 文件，添加 'markdown' 标识以便在右键菜单中显示特定选项
    this.contextValue = isMarkdown ? `${type} markdown` : type;

    // 根据节点类型设置不同的图标
    // ThemeIcon是VSCode内置的图标系统，使用Codicons图标库
    const iconMap: { [key: string]: string } = {
      'topic': 'book',           // 书籍图标，表示研究话题
      'hypothesis': 'lightbulb',  // 灯泡图标，表示假设
      'experiment': 'beaker',     // 烧杯图标，表示实验
      'paper': 'file-pdf',        // PDF文件图标
      'papers': 'library',        // 图书馆图标，表示文献库
      'userdata': 'database',     // 数据库图标，表示用户数据
      'file': 'file',             // 普通文件图标
      'chat': 'comment-discussion', // 对话图标，表示AI Chat
      'prefillParams': 'settings', // 设置图标，表示预填充参数
      'prefillParamsGroup': 'folder', // 文件夹图标，表示预填充参数组
      'prefillParamsEnv': 'symbol-namespace', // 命名空间图标，表示环境模块预置参数
      'prefillParamsAgent': 'symbol-interface', // 接口图标，表示智能体类预置参数
      'settings': 'settings-gear', // 齿轮设置图标，表示配置设置
      'custom': 'workspace-trusted', // 自定义模块根图标
      'customScan': 'refresh', // 扫描图标
      'customTest': 'play', // 测试图标
      'customClean': 'trash', // 清空图标
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
    };
    const iconId = iconMap[type] || 'file';

    // ThemeIcon的构造函数在类型定义中是私有的，但运行时可用
    // 使用类型断言绕过TypeScript的类型检查
    this.iconPath = new (vscode.ThemeIcon as any)(iconId);

    // 如果提供了文件路径，设置点击命令
    // 当用户点击这个节点时，会执行相应的命令打开文件
    if (filePath) {
      if (type === 'reportHtml' || (filePath.toLowerCase().endsWith('.html') && (type === 'presentationExperiment' || type === 'synthesis'))) {
        // HTML 报告文件使用 live-server 预览（如果有安装）
        this.command = {
          command: 'liveServer.preview.open',
          title: 'Open with Live Server',
          arguments: [vscode.Uri.file(filePath)]
        };
      } else if (type === 'reportMd' && filePath.toLowerCase().endsWith('.md')) {
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
      } else {
        // 其他文件使用默认打开方式
        this.command = {
          command: 'vscode.open',  // VSCode内置命令：打开文件
          title: 'Open File',
          arguments: [vscode.Uri.file(filePath)]  // 传递文件URI作为参数
        };
      }
    } else if (type === 'chat') {
      // AI Chat节点：点击时打开AI Chat界面
      this.command = {
        command: 'aiSocialScientist.openChat',  // 打开AI Chat的命令
        title: localize('projectStructure.openAiChat')
      };
    } else if (type === 'prefillParamsEnv') {
      // 环境模块预置参数节点：点击时打开预填充参数界面（显示环境模块）
      this.command = {
        command: 'agentsociety.viewPrefillParams',
        title: 'View Environment Module Prefill Parameters',
        arguments: ['env_module']
      };
    } else if (type === 'prefillParamsAgent') {
      // 智能体类预置参数节点：点击时打开预填充参数界面（显示Agent）
      this.command = {
        command: 'agentsociety.viewPrefillParams',
        title: 'View Agent Prefill Parameters',
        arguments: ['agent']
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

    // 根节点：显示研究话题和AI Chat
    // element为undefined表示这是根节点
    if (!element) {
      const items: ProjectItem[] = [];

      // 添加AI Chat节点（始终显示）
      items.push(new ProjectItem(
        localize('projectStructure.aiChat'),  // 显示标签（国际化）
        vscode.TreeItemCollapsibleState.None,  // 没有子节点
        'chat',  // 节点类型
        undefined  // 不关联文件，点击时执行命令
      ));

      // 添加配置设置节点（始终显示，在AI Chat下方）
      items.push(new ProjectItem(
        localize('projectStructure.settings'),  // 显示标签（国际化）：配置设置
        vscode.TreeItemCollapsibleState.None,  // 没有子节点
        'settings',  // 节点类型
        undefined  // 不关联文件，点击时执行命令
      ));

      // 添加预填充参数组节点（始终显示，在配置设置下方）
      items.push(new ProjectItem(
        localize('prefillParams.groupTitle'),  // 显示标签（国际化）：环境与智能体
        vscode.TreeItemCollapsibleState.Collapsed,  // 可展开
        'prefillParamsGroup',  // 节点类型
        undefined  // 不关联文件
      ));

      // 添加自定义模块组节点（始终显示，在预填充参数下方）
      items.push(new ProjectItem(
        localize('projectStructure.customModules'),  // 显示标签（国际化）：自定义模块
        vscode.TreeItemCollapsibleState.Collapsed,  // 可展开
        'custom',  // 节点类型
        undefined  // 不关联文件
      ));

      // 如果存在TOPIC.md文件，添加Research Topic节点
      const topicFile = path.join(workspacePath, 'TOPIC.md');
      if (fs.existsSync(topicFile)) {
        items.push(new ProjectItem(
          localize('projectStructure.researchTopic'),  // 显示标签（国际化）
          vscode.TreeItemCollapsibleState.Expanded,  // 初始状态为展开
          'topic',  // 节点类型
          topicFile  // 文件路径，点击可打开
        ));
      }

      return items;
    }

    // 预填充参数组节点的子节点：显示环境模块预置参数和智能体类预置参数
    if (element.type === 'prefillParamsGroup') {
      const items: ProjectItem[] = [];

      // 添加环境模块预置参数节点
      items.push(new ProjectItem(
        localize('prefillParams.envModuleTitle'),  // 环境模块预置参数
        vscode.TreeItemCollapsibleState.None,  // 没有子节点
        'prefillParamsEnv',  // 节点类型
        undefined  // 不关联文件，点击时执行命令
      ));

      // 添加智能体类预置参数节点
      items.push(new ProjectItem(
        localize('prefillParams.agentTitle'),  // 智能体类预置参数
        vscode.TreeItemCollapsibleState.None,  // 没有子节点
        'prefillParamsAgent',  // 节点类型
        undefined  // 不关联文件，点击时执行命令
      ));

      return items;
    }

    // 自定义模块节点的子节点：显示操作按钮和扫描结果
    if (element.type === 'custom') {
      const items: ProjectItem[] = [];

      // 添加扫描按钮
      const scanItem = new ProjectItem(
        localize('projectStructure.customScan'),
        vscode.TreeItemCollapsibleState.None,
        'customScan',
        undefined
      );
      scanItem.command = {
        command: 'aiSocialScientist.scanCustomModules',
        title: localize('projectStructure.customScan')
      };
      items.push(scanItem);

      // 添加测试按钮
      const testItem = new ProjectItem(
        localize('projectStructure.customTest'),
        vscode.TreeItemCollapsibleState.None,
        'customTest',
        undefined
      );
      testItem.command = {
        command: 'aiSocialScientist.testCustomModules',
        title: localize('projectStructure.customTest')
      };
      items.push(testItem);

      // 添加清空按钮
      const cleanItem = new ProjectItem(
        localize('projectStructure.customClean'),
        vscode.TreeItemCollapsibleState.None,
        'customClean',
        undefined
      );
      cleanItem.command = {
        command: 'aiSocialScientist.cleanCustomModules',
        title: localize('projectStructure.customClean')
      };
      items.push(cleanItem);

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
              'paper',  // 使用paper类型表示文献库子项
              fullPath  // 存储目录路径，用于获取子节点
            ));
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

      // 检查init/results目录
      const initDir = path.join(experimentDir, 'init');
      if (fs.existsSync(initDir)) {
        const resultsDir = path.join(initDir, 'results');
        if (fs.existsSync(resultsDir)) {
          // 读取results目录下的所有文件
          const resultFiles = fs.readdirSync(resultsDir);
          for (const file of resultFiles) {
            items.push(new ProjectItem(
              localize('projectStructure.init', file),  // 添加"Init:"前缀以便区分
              vscode.TreeItemCollapsibleState.None,
              'file',
              path.join(resultsDir, file)
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
            command: 'liveServer.preview.open',
            title: 'Open with Live Server',
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
            command: 'liveServer.preview.open',
            title: 'Open with Live Server',
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
            command: 'liveServer.preview.open',
            title: 'Open with Live Server',
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
        const reportGroups: { [key: string]: { zh?: string; en?: string; generic?: string } } = {};
        
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
                command: 'liveServer.preview.open',
                title: 'Open with Live Server',
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
                command: 'liveServer.preview.open',
                title: 'Open with Live Server',
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
                command: 'liveServer.preview.open',
                title: 'Open with Live Server',
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
      // 调用后端初始化能力
      const response = await this.apiClient.initWorkspace({
        workspace_path: workspacePath,
        topic: topic
      });

      if (response.success) {
        vscode.window.showInformationMessage(response.message);
      } else {
        vscode.window.showErrorMessage(response.message);
      }
    } catch (error: any) {
      vscode.window.showErrorMessage(localize('projectStructure.initWorkspace.failed', error.message || error));
    }

    // 刷新视图，显示新创建的文件和目录
    this.refresh();
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
          localize('customModules.testSuccess') +
          (response.test_file ? `\n${response.test_file}` : '')
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
   * 清空自定义模块配置
   */
  async cleanCustomModules(): Promise<void> {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      vscode.window.showErrorMessage(localize('customModules.noWorkspace'));
      return;
    }

    const workspacePath = workspaceFolder.uri.fsPath;

    // 确认对话框
    const confirm = await vscode.window.showWarningMessage(
      localize('customModules.cleanConfirm'),
      { modal: true },
      localize('customModules.cleanConfirmButton'),
      localize('projectStructure.initWorkspace.cancel')
    );

    if (confirm !== localize('customModules.cleanConfirmButton')) {
      return;
    }

    try {
      const response = await this.apiClient.cleanCustomModules({
        workspace_path: workspacePath
      });

      if (response.success) {
        // 清空缓存
        this.customModulesCache = { agents: [], envs: [] };

        vscode.window.showInformationMessage(
          localize('customModules.cleanSuccess') +
          ` (${response.removed_count} ${localize('projectStructure.customModules')} removed)`
        );

        // 刷新视图
        this.refresh();
      } else {
        vscode.window.showErrorMessage(localize('customModules.cleanFailed', response.message));
      }
    } catch (error: any) {
      this.log(`Clean custom modules failed: ${error}`);
      vscode.window.showErrorMessage(localize('customModules.cleanFailed', error.message || error));
    }
  }
}
