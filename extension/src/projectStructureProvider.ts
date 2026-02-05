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
    public readonly type: 'topic' | 'hypothesis' | 'experiment' | 'paper' | 'file' | 'papers' | 'userdata' | 'chat' | 'prefillParams' | 'prefillParamsGroup' | 'prefillParamsEnv' | 'prefillParamsAgent' | 'settings',
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
      'prefillParamsEnv': 'server-environment', // 服务器环境图标，表示环境模块预置参数
      'prefillParamsAgent': 'person', // 人员图标，表示智能体类预置参数
      'settings': 'settings-gear' // 齿轮设置图标，表示配置设置
    };
    const iconId = iconMap[type] || 'file';

    // ThemeIcon的构造函数在类型定义中是私有的，但运行时可用
    // 使用类型断言绕过TypeScript的类型检查
    this.iconPath = new (vscode.ThemeIcon as any)(iconId);

    // 如果提供了文件路径，设置点击命令
    // 当用户点击这个节点时，会执行相应的命令打开文件
    if (filePath) {
      if (isMarkdown) {
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
      // 配置设置节点：点击时打开 VS Code 设置页面并过滤到 aiSocialScientist 配置
      this.command = {
        command: 'workbench.action.openSettings',
        title: localize('projectStructure.settings'),
        arguments: ['@aiSocialScientist']
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

      return items;
    }

    // Papers节点（文献库）的子节点：显示所有论文文件
    if (element.type === 'papers') {
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (!workspaceFolder) {
        return [];
      }
      const workspacePath = workspaceFolder.uri.fsPath;
      const papersDir = path.join(workspacePath, 'papers');
      const items: ProjectItem[] = [];

      if (fs.existsSync(papersDir)) {
        // 读取目录，过滤出PDF、Markdown和文本文件，忽略mineru_output文件夹
        const papers = fs.readdirSync(papersDir).filter(f =>
          f !== 'mineru_output' && (f.endsWith('.pdf') || f.endsWith('.md') || f.endsWith('.txt'))
        );

        // 为每个论文文件创建节点
        for (const paper of papers) {
          items.push(new ProjectItem(
            paper,  // 文件名作为标签
            vscode.TreeItemCollapsibleState.None,  // 文件没有子节点
            'paper',
            path.join(papersDir, paper)  // 完整文件路径
          ));
        }
      }

      return items;
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
}
