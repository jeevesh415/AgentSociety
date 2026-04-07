/**
 * MinerUInitializer - MinerU 环境检查与模型初始化服务
 *
 * 本模块负责在 VSCode 扩展激活时，后台自动检查 MinerU CLI 是否已安装、
 * 模型是否已下载，并在需要时引导用户完成初始化流程。
 *
 * 核心工作流程：
 *   1. 在扩展激活时调用 checkAndInitialize()，后台执行环境检查
 *   2. 查找 MinerU CLI 可执行文件（优先从 .env 配置的 PYTHON_PATH 中查找）
 *   3. 检查 MinerU 版本信息
 *   4. 检查模型是否已下载到本地（支持多种模型存储路径）
 *   5. 若模型缺失，弹窗提示用户下载（使用国内 HuggingFace 镜像加速）
 *   6. 在 VSCode 状态栏实时展示 MinerU 环境状态
 *
 * 状态机：
 *   checking → not_installed / cli_ready → models_ready
 *                      ↓                      ↑
 *                  downloading ────────────────┘
 *                      ↓
 *                    error
 *
 * 关联文件：
 * - @extension/src/extension.ts - 主入口，激活时调用初始化检查
 * - @extension/src/mineruParser.ts - 解析前检查初始化状态
 * - @extension/src/envManager.ts - 读取 PYTHON_PATH 等配置
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';
import { spawn, execFileSync } from 'child_process';
import { localize } from '../i18n';

/**
 * MinerU 环境状态枚举
 *
 * 定义了 MinerU 初始化过程中可能出现的所有状态，
 * 状态栏和解析器根据此状态决定下一步行为。
 *
 * - not_installed:  MinerU CLI 未找到（用户可能未安装 MinerU）
 * - cli_ready:      CLI 可用但模型未下载（需要执行 mineru-models-download）
 * - models_ready:   一切就绪，可以进行 PDF 解析
 * - downloading:    模型正在下载中（后台进程运行中）
 * - checking:       正在执行环境检查（扩展刚激活时的初始状态）
 * - error:          检查或下载过程中发生错误
 */
export type MinerUStatus =
  | 'not_installed'   // CLI 未找到
  | 'cli_ready'       // CLI 可用，模型未下载
  | 'models_ready'    // 一切就绪
  | 'downloading'     // 模型下载中
  | 'checking'        // 正在检查环境
  | 'error';          // 检查或下载出错

/**
 * MinerUInitializer - MinerU 环境初始化管理器
 *
 * 职责：
 * 1. 管理 MinerU CLI 的查找与版本检测
 * 2. 检查模型文件的下载状态（支持多种存储路径）
 * 3. 提供模型下载功能（使用国内 HuggingFace 镜像）
 * 4. 在 VSCode 状态栏实时展示环境状态
 * 5. 通过输出通道记录详细的初始化日志
 *
 * 生命周期：
 * - 创建于扩展激活时（extension.ts activate()）
 * - 随扩展停用而销毁（dispose()）
 */
export class MinerUInitializer {
  /** 输出通道，用于在 VSCode "输出" 面板中展示 MinerU 初始化日志 */
  private outputChannel: vscode.OutputChannel;

  /** 状态栏项，在 VSCode 底部状态栏右侧显示 MinerU 当前状态 */
  private statusBarItem: vscode.StatusBarItem;

  /** 当前 MinerU 环境状态，默认为 checking（检查中） */
  private _status: MinerUStatus = 'checking';

  /** 已找到的 MinerU CLI 可执行文件路径，若未找到则为 null */
  private _cliPath: string | null = null;

  /** MinerU CLI 的版本号字符串，若获取失败则为 null */
  private _version: string | null = null;

  /** VSCode 扩展上下文，用于管理资源生命周期（subscriptions） */
  private context: vscode.ExtensionContext;

  /**
   * 构造函数
   *
   * @param context - VSCode 扩展上下文，用于注册可释放资源
   *
   * 初始化流程：
   * 1. 创建 MinerU Initializer 输出通道（用于日志展示）
   * 2. 创建状态栏项（右侧，优先级 99，略低于 Backend 的 100）
   * 3. 绑定状态栏点击命令（点击后弹出状态菜单）
   * 4. 注册到扩展订阅列表（随扩展停用自动清理）
   * 5. 初始化状态栏显示为 "Checking..."
   */
  constructor(context: vscode.ExtensionContext) {
    this.context = context;
    // 创建专用的输出通道，用户可在输出面板中选择 "MinerU Initializer" 查看日志
    this.outputChannel = vscode.window.createOutputChannel('MinerU Initializer');
    // 创建状态栏项，优先级 99（数字越大越靠左，Backend 为 100）
    this.statusBarItem = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Right,
      99  // 略低于 Backend 的 100
    );
    // 点击状态栏时触发状态菜单命令
    this.statusBarItem.command = 'aiSocialScientist.mineruStatusMenu';
    // 注册到扩展的 subscriptions 中，确保扩展停用时自动清理
    context.subscriptions.push(this.statusBarItem);
    // 根据当前状态（checking）更新状态栏显示
    this.updateStatusBar();
  }

  /** 获取当前 MinerU 环境状态（只读属性） */
  get status(): MinerUStatus {
    return this._status;
  }

  /** 获取已找到的 MinerU CLI 路径（只读属性） */
  get cliPath(): string | null {
    return this._cliPath;
  }

  /** 获取 MinerU 版本号（只读属性） */
  get version(): string | null {
    return this._version;
  }

  /**
   * 写入日志到输出通道
   *
   * @param message - 日志消息内容
   * @param level - 日志级别：info（默认）、warn（警告）、error（错误）
   *
   * 日志格式为：[ISO时间戳] [级别] 消息内容
   * 用户可在 VSCode 输出面板中选择 "MinerU Initializer" 查看所有日志。
   */
  private log(message: string, level: 'info' | 'warn' | 'error' = 'info'): void {
    const timestamp = new Date().toISOString();
    const prefix = level === 'error' ? '[ERROR]' : level === 'warn' ? '[WARN]' : '[INFO]';
    this.outputChannel.appendLine(`[${timestamp}] ${prefix} ${message}`);
  }

  /**
   * 更新状态栏显示
   *
   * 根据当前 _status 值更新状态栏的文本、提示信息、背景色。
   * 状态栏显示规则：
   * - models_ready:  ✓ 绿色勾号 + "Ready"（无特殊背景色）
   * - not_installed: ✗ 红色叉号 + "Not Installed"（红色错误背景）
   * - cli_ready:     ⚠ 黄色警告 + "No Models"（黄色警告背景）
   * - downloading:   ⟳ 旋转图标 + "Downloading..."（无特殊背景色）
   * - checking:      ⟳ 旋转图标 + "Checking..."（无特殊背景色）
   * - error:         ✗ 红色叉号 + "Error"（红色错误背景）
   */
  private updateStatusBar(): void {
    switch (this._status) {
      case 'models_ready':
        // 一切就绪：显示绿色勾号
        this.statusBarItem.text = '$(check) MinerU: Ready';
        this.statusBarItem.tooltip = 'MinerU is ready for PDF parsing';
        this.statusBarItem.backgroundColor = undefined;
        this.statusBarItem.show();
        break;
      case 'not_installed':
        // CLI 未安装：显示红色叉号和错误背景色
        this.statusBarItem.text = '$(error) MinerU: Not Installed';
        this.statusBarItem.tooltip = 'MinerU CLI not found. Click for help.';
        this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
        this.statusBarItem.show();
        break;
      case 'cli_ready':
        // CLI 已安装但模型未下载：显示黄色警告和警告背景色
        this.statusBarItem.text = '$(warning) MinerU: No Models';
        this.statusBarItem.tooltip = 'MinerU CLI found but models not downloaded. Click to download.';
        this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        this.statusBarItem.show();
        break;
      case 'downloading':
        // 模型下载中：显示旋转动画图标
        this.statusBarItem.text = '$(sync~spin) MinerU: Downloading...';
        this.statusBarItem.tooltip = 'MinerU models are being downloaded';
        this.statusBarItem.backgroundColor = undefined;
        this.statusBarItem.show();
        break;
      case 'checking':
        // 正在检查环境：显示旋转动画图标
        this.statusBarItem.text = '$(sync~spin) MinerU: Checking...';
        this.statusBarItem.tooltip = 'Checking MinerU environment';
        this.statusBarItem.backgroundColor = undefined;
        this.statusBarItem.show();
        break;
      case 'error':
        // 发生错误：显示红色叉号和错误背景色
        this.statusBarItem.text = '$(error) MinerU: Error';
        this.statusBarItem.tooltip = 'MinerU initialization error. Click for details.';
        this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
        this.statusBarItem.show();
        break;
    }
  }

  /**
   * 设置状态并更新状态栏
   *
   * @param status - 新的 MinerU 环境状态
   *
   * 同时更新内部状态变量和状态栏显示。
   */
  private setStatus(status: MinerUStatus): void {
    this._status = status;
    this.updateStatusBar();
  }

  /**
   * 查找 MinerU CLI 可执行文件
   *
   * 查找策略（按优先级从高到低）：
   * 1. 从 .env 文件中配置的 PYTHON_PATH 推导 bin 目录，查找 mineru 可执行文件
   * 2. 在系统 PATH 中查找 mineru 命令
   * 3. 检查常见安装路径（~/.local/bin/mineru、/usr/local/bin/mineru）
   *
   * @returns MinerU CLI 路径字符串，未找到则返回 null
   */
  async findMinerUCLI(): Promise<string | null> {
    // ========== 策略 1：从 .env 配置的 PYTHON_PATH 查找 ==========
    // 读取工作区 .env 文件中配置的 PYTHON_PATH
    const { EnvManager } = await import('../envManager');
    const envManager = new EnvManager();
    const envConfig = envManager.readEnv();
    const configuredPythonPath = envConfig.pythonPath?.trim();

    if (configuredPythonPath) {
      // PYTHON_PATH 通常指向 python 可执行文件，mineru 应在其同级目录
      // 例如：PYTHON_PATH=/path/to/venv/bin/python → 查找 /path/to/venv/bin/mineru
      const pythonBinDir = path.dirname(configuredPythonPath);
      const candidates = [
        path.join(pythonBinDir, 'mineru'),
      ];
      for (const candidate of candidates) {
        this.log(`Checking: ${candidate}`);
        if (fs.existsSync(candidate)) {
          this.log(`Found MinerU CLI: ${candidate}`);
          return candidate;
        }
      }
    }

    // ========== 策略 2：在系统 PATH 和常见路径中查找 ==========
    // 如果 .env 中没有配置 PYTHON_PATH，则在系统级路径中查找
    const systemCandidates = [
      'mineru',                                              // 系统 PATH 中的 mineru
      path.join(os.homedir(), '.local', 'bin', 'mineru'),    // 用户级安装路径
      '/usr/local/bin/mineru',                                // 系统级安装路径
    ];

    for (const candidate of systemCandidates) {
      this.log(`Checking candidate: ${candidate}`);
      try {
        // 使用 which（Linux/macOS）或 where（Windows）检查命令是否可用
        const isWindows = process.platform === 'win32';
        const checkCmd = isWindows ? 'where' : 'which';
        // execFileSync 同步执行命令，若命令不存在会抛出异常
        execFileSync(checkCmd, [candidate], { stdio: 'ignore', timeout: 5000 });
        this.log(`Found MinerU CLI in PATH: ${candidate}`);
        return candidate;
      } catch {
        // 候选路径不存在，继续尝试下一个
      }
    }

    this.log('MinerU CLI not found');
    return null;
  }

  /**
   * 检查 MinerU CLI 版本号
   *
   * 执行 `mineru --version` 命令获取版本信息。
   * 版本获取失败不会阻断流程——CLI 仍然可能正常工作。
   *
   * @param cliPath - MinerU CLI 可执行文件路径
   * @returns 版本号字符串，获取失败返回 null
   */
  async checkMinerUVersion(cliPath: string): Promise<string | null> {
    try {
      // 同步执行 --version 命令，10 秒超时
      const result = execFileSync(cliPath, ['--version'], {
        encoding: 'utf-8',
        timeout: 10000,
      }).trim();
      this.log(`MinerU version: ${result}`);
      return result;
    } catch (error: any) {
      this.log(`Failed to get MinerU version: ${error.message}`, 'warn');
      // --version 可能失败但 CLI 仍然可用，不阻断流程
      return null;
    }
  }

  /**
   * 查找 mineru-models-download 命令
   *
   * 该命令用于下载 MinerU 所需的 AI 模型文件。
   * 查找策略与 findMinerUCLI() 一致：
   * 1. 优先从 PYTHON_PATH/bin 目录查找
   * 2. 然后在系统 PATH 中查找
   *
   * @returns 命令路径字符串，未找到返回 null
   */
  async findModelsDownloadCLI(): Promise<string | null> {
    // ========== 策略 1：从 PYTHON_PATH/bin 查找 ==========
    const { EnvManager } = await import('../envManager');
    const envManager = new EnvManager();
    const envConfig = envManager.readEnv();
    const configuredPythonPath = envConfig.pythonPath?.trim();

    if (configuredPythonPath) {
      const pythonBinDir = path.dirname(configuredPythonPath);
      const candidates = [
        path.join(pythonBinDir, 'mineru-models-download'),
      ];
      for (const candidate of candidates) {
        if (fs.existsSync(candidate)) {
          this.log(`Found models-download CLI: ${candidate}`);
          return candidate;
        }
      }
    }

    // ========== 策略 2：系统路径 ==========
    const systemCandidates = [
      'mineru-models-download',
    ];
    for (const candidate of systemCandidates) {
      try {
        const isWindows = process.platform === 'win32';
        const checkCmd = isWindows ? 'where' : 'which';
        execFileSync(checkCmd, [candidate], { stdio: 'ignore', timeout: 5000 });
        this.log(`Found models-download CLI in PATH: ${candidate}`);
        return candidate;
      } catch {
        // continue
      }
    }

    return null;
  }

  /**
   * 检查 MinerU 模型是否已下载到本地
   *
   * MinerU 依赖多个 AI 模型（布局检测、公式识别等）进行 PDF 解析。
   * 本方法按优先级检查以下位置：
   *
   * 1. 默认模型目录 ~/.mineru/models/（MinerU 官方默认路径）
   * 2. mineru.json 配置文件中指定的模型路径（支持多种配置键名）
   * 3. HuggingFace 缓存目录 ~/.cache/huggingface/hub/（模型可能由 HF 自动下载）
   *
   * 只要在任一位置找到模型文件（目录非空），即认为模型已就绪。
   *
   * @returns true 表示模型已下载，false 表示未找到模型文件
   */
  checkModelsDownloaded(): boolean {
    // ========== 检查 1：默认模型目录 ~/.mineru/models/ ==========
    // 这是 MinerU 安装后默认的模型存储路径
    const defaultModelDir = path.join(os.homedir(), '.mineru', 'models');
    if (fs.existsSync(defaultModelDir)) {
      try {
        const entries = fs.readdirSync(defaultModelDir);
        // 目录存在且非空，说明模型已下载
        if (entries.length > 0) {
          this.log(`Models found in ${defaultModelDir}: ${entries.join(', ')}`);
          return true;
        }
      } catch {
        // 读取目录失败，忽略并继续检查其他位置
      }
    }

    // ========== 检查 2：mineru.json 配置文件中的自定义模型路径 ==========
    // 用户可能在配置文件中指定了不同的模型存储目录
    const configPaths = [
      path.join(os.homedir(), '.mineru', 'mineru.json'),  // ~/.mineru/mineru.json
      path.join(os.homedir(), 'mineru.json'),              // ~/mineru.json
    ];

    for (const configPath of configPaths) {
      if (fs.existsSync(configPath)) {
        try {
          const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
          // 支持多种可能的配置键名（不同版本的 MinerU 可能使用不同的键名）
          const modelDir = config['models-dir'] || config['models_dir'] || config['modelDir'];
          if (modelDir && fs.existsSync(modelDir)) {
            const entries = fs.readdirSync(modelDir);
            if (entries.length > 0) {
              this.log(`Models found via config: ${modelDir}`);
              return true;
            }
          }
        } catch {
          // JSON 解析失败或目录读取失败，忽略
        }
      }
    }

    // ========== 检查 3：HuggingFace 缓存中的 PDF-Extract-Kit 模型 ==========
    // MinerU 使用的模型基于 PDF-Extract-Kit 项目，可能通过 HuggingFace 自动下载
    // HuggingFace 默认将模型缓存到 ~/.cache/huggingface/hub/ 目录
    const hfCacheDir = path.join(os.homedir(), '.cache', 'huggingface', 'hub');
    if (fs.existsSync(hfCacheDir)) {
      try {
        const entries = fs.readdirSync(hfCacheDir);
        // 查找与 MinerU 相关的模型目录（PDF-Extract-Kit 及其子模型）
        const modelEntries = entries.filter(e =>
          e.toLowerCase().includes('pdf-extract-kit') ||  // 主模型
          e.toLowerCase().includes('layoutdet') ||         // 布局检测模型
          e.toLowerCase().includes('mfd') ||               // 数学公式检测模型
          e.toLowerCase().includes('mfr')                  // 数学公式识别模型
        );
        if (modelEntries.length > 0) {
          this.log(`Models found in HuggingFace cache: ${modelEntries.join(', ')}`);
          return true;
        }
      } catch {
        // 读取 HuggingFace 缓存目录失败，忽略
      }
    }

    this.log('No downloaded models found');
    return false;
  }

  /**
   * 执行完整的环境检查流程
   *
   * 这是初始化检查的主入口方法，在扩展激活时被调用。
   * 完整流程：
   *   Step 1: 查找 MinerU CLI 可执行文件
   *   Step 2: 获取 CLI 版本信息
   *   Step 3: 检查模型下载状态
   *   Step 4: 若模型缺失，自动提示用户下载
   *
   * 状态转换：
   *   checking → not_installed（CLI 未找到）
   *   checking → cli_ready（CLI 找到但模型缺失，触发下载提示）
   *   checking → models_ready（CLI 和模型均就绪）
   *
   * @returns 最终的 MinerU 环境状态
   */
  async checkAndInitialize(): Promise<MinerUStatus> {
    // 设置状态为 "检查中"
    this.setStatus('checking');
    this.log('Starting MinerU environment check...');

    // Step 1: 查找 MinerU CLI 可执行文件
    this._cliPath = await this.findMinerUCLI();
    if (!this._cliPath) {
      // CLI 未找到，设置为 not_installed 状态
      this.log('MinerU CLI not found', 'warn');
      this.setStatus('not_installed');
      return this._status;
    }

    // Step 2: 检查 CLI 版本（非必须，仅用于日志记录和状态展示）
    this._version = await this.checkMinerUVersion(this._cliPath);
    this.log(`MinerU CLI found: ${this._cliPath}, version: ${this._version || 'unknown'}`);

    // Step 3: 检查模型下载状态
    const hasModels = this.checkModelsDownloaded();
    if (hasModels) {
      // 模型已就绪，设置为 models_ready 状态
      this.log('MinerU environment is ready');
      this.setStatus('models_ready');
    } else {
      // CLI 可用但模型缺失，设置为 cli_ready 状态
      this.log('MinerU CLI found but models not downloaded', 'warn');
      this.setStatus('cli_ready');

      // 自动弹出提示，引导用户下载模型
      this.promptDownloadModels();
    }

    return this._status;
  }

  /**
   * 提示用户下载 MinerU 模型
   *
   * 当检测到 CLI 已安装但模型未下载时，弹出 VSCode 信息提示框。
   * 用户可以选择：
   * - "Download Models"：立即开始下载模型
   * - "Not Now"：暂时跳过，后续可通过命令面板手动触发下载
   *
   * 注意：此方法不会阻塞调用者，下载在后台异步进行。
   */
  private async promptDownloadModels(): Promise<void> {
    const downloadLabel = localize('mineruInitializer.promptDownload.download');
    const dismissLabel = localize('mineruInitializer.promptDownload.dismiss');

    // 弹出信息提示框，等待用户选择
    const result = await vscode.window.showInformationMessage(
      localize('mineruInitializer.promptDownload.message'),
      downloadLabel,
      dismissLabel
    );

    if (result === downloadLabel) {
      // 用户选择下载，调用下载方法
      await this.downloadModels();
    }
    // 用户选择 "Not Now" 或关闭提示框，不做任何操作
  }

  /**
   * 下载 MinerU 模型
   *
   * 执行 `mineru-models-download` 命令下载 MinerU 所需的 AI 模型。
   *
   * 下载流程：
   * 1. 查找 mineru-models-download 命令路径
   * 2. 使用 -s modelscope -m all 参数跳过交互式提示
   * 3. 在后台子进程中执行下载命令
   * 4. 实时将 stdout/stderr 输出到日志通道
   * 5. 设置 10 分钟超时保护，防止下载挂起
   * 6. 根据退出码判断下载成功或失败
   *
   * @returns true 表示下载成功，false 表示下载失败或被中断
   */
  async downloadModels(): Promise<boolean> {
    // 查找模型下载命令
    const downloadCLI = await this.findModelsDownloadCLI();
    if (!downloadCLI) {
      vscode.window.showErrorMessage(
        localize('mineruInitializer.download.notFound')
      );
      return false;
    }

    // 更新状态为 "下载中"
    this.setStatus('downloading');
    this.log(`Starting model download: ${downloadCLI}`);

    // 使用 withProgress 在 VSCode 右下角显示带进度信息的浮窗通知
    return vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: localize('mineruInitializer.download.title'),
        cancellable: true,
      },
      async (progress, token) => {
        // 用户点击取消时终止下载进程
        let childProcess: ReturnType<typeof spawn> | null = null;
        token.onCancellationRequested(() => {
          this.log('User cancelled model download');
          childProcess?.kill();
        });

        return new Promise<boolean>((resolve) => {
          // 传入 -s modelscope -m all 参数，跳过交互式提示
          childProcess = spawn(downloadCLI, ['-s', 'modelscope', '-m', 'all']);

          // 用于累积最近一行输出，作为浮窗进度消息展示
          let lastLine = '';

          // 监听标准输出，实时记录到日志并更新浮窗消息
          childProcess!.stdout?.on('data', (data: Buffer) => {
            const message = data.toString();
            this.log(`[STDOUT] ${message.trim()}`);
            lastLine = message.trim().split('\n').pop() || lastLine;
            if (lastLine) {
              progress.report({ message: lastLine });
            }
          });

          // 监听标准错误输出，实时记录到日志并更新浮窗消息
          childProcess!.stderr?.on('data', (data: Buffer) => {
            const message = data.toString();
            this.log(`[STDERR] ${message.trim()}`);
            lastLine = message.trim().split('\n').pop() || lastLine;
            if (lastLine) {
              progress.report({ message: lastLine });
            }
          });

          // 设置 10 分钟超时保护
          const timeout = setTimeout(() => {
            this.log('Model download timeout after 10 minutes', 'error');
            childProcess?.kill();
            this.setStatus('error');
            vscode.window.showErrorMessage(localize('mineruInitializer.download.timeout'));
            resolve(false);
          }, 10 * 60 * 1000);

          // 监听子进程退出事件
          childProcess!.on('close', (code) => {
            clearTimeout(timeout);
            if (code === 0) {
              this.log('Model download completed successfully');
              this.setStatus('models_ready');
              vscode.window.showInformationMessage(localize('mineruInitializer.download.success'));
              resolve(true);
            } else if (code !== null) {
              // 非 0 退出码（被 kill 时 code 为 null，由取消处理）
              this.log(`Model download failed with exit code: ${code}`, 'error');
              this.setStatus('error');
              vscode.window.showErrorMessage(
                localize('mineruInitializer.download.failed', String(code))
              );
              resolve(false);
            } else {
              // 被 kill（用户取消或超时），状态已由调用方设置
              resolve(false);
            }
          });

          // 监听子进程错误事件
          childProcess!.on('error', (error) => {
            clearTimeout(timeout);
            this.log(`Model download error: ${error.message}`, 'error');
            this.setStatus('error');
            vscode.window.showErrorMessage(localize('mineruInitializer.download.error', error.message));
            resolve(false);
          });
        });
      }
    );
  }

  /**
   * 显示 MinerU 初始化日志
   *
   * 在 VSCode 输出面板中打开 "MinerU Initializer" 通道，
   * 方便用户查看详细的环境检查和下载日志。
   */
  showLogs(): void {
    this.outputChannel.show();
  }

  /**
   * 获取当前状态的可读文本描述
   *
   * 用于在状态菜单中展示详细的 MinerU 环境信息，
   * 包括版本号、CLI 路径和下一步操作建议。
   *
   * @returns 状态描述字符串
   */
  getStatusText(): string {
    switch (this._status) {
      case 'models_ready':
        // 就绪状态：显示版本号和 CLI 路径
        return `MinerU Ready (v${this._version || 'unknown'}, CLI: ${this._cliPath})`;
      case 'not_installed':
        // 未安装：给出安装命令提示
        return 'MinerU CLI not found. Please install MinerU: pip install mineru[all]';
      case 'cli_ready':
        // CLI 可用但缺模型：给出下载命令提示
        return `MinerU CLI found (${this._cliPath}) but models not downloaded. Run: mineru-models-download`;
      case 'downloading':
        // 下载中：提示等待
        return 'MinerU models are being downloaded...';
      case 'checking':
        // 检查中：提示等待
        return 'Checking MinerU environment...';
      case 'error':
        // 错误状态：建议查看日志
        return 'MinerU initialization error. Check output for details.';
    }
  }

  /**
   * 释放资源
   *
   * 清理状态栏项和输出通道，防止内存泄漏。
   * 此方法会在扩展停用时由 VSCode 自动调用。
   */
  dispose(): void {
    this.statusBarItem.dispose();
    this.outputChannel.dispose();
  }
}
