/**
 * PDF 解析模式管理器
 *
 * 管理 PDF 文件上传后的自动解析模式，提供状态栏按钮切换
 * - 自动模式：上传 PDF 后自动使用 MinerU 解析
 * - 手动模式：上传 PDF 后提示用户是否解析
 *
 * 关联文件：
 * - @extension/src/extension.ts - 主入口，创建ParseModeManager实例
 * - @extension/src/paperWatcher.ts - 文件监听器，根据解析模式处理PDF
 * - @extension/src/mineruParser.ts - MinerU本地解析器（备用）
 */

import * as vscode from 'vscode';
import { localize } from './i18n';

/**
 * 解析模式类型
 */
export type ParseMode = 'auto' | 'manual';

/**
 * 解析模式管理器
 */
export class ParseModeManager {
  private statusBarItem: vscode.StatusBarItem;
  private currentMode: ParseMode;
  private outputChannel: vscode.OutputChannel;
  private context: vscode.ExtensionContext;

  // 存储解析模式的 key
  private static readonly STORAGE_KEY = 'pdfParseMode';

  constructor(context: vscode.ExtensionContext) {
    this.context = context;
    this.outputChannel = vscode.window.createOutputChannel('PDF Parse Mode');

    // 从持久化存储读取模式，默认为 auto
    const savedMode = context.globalState.get<ParseMode>(ParseModeManager.STORAGE_KEY, 'auto');
    this.currentMode = savedMode;

    // 创建状态栏按钮
    this.statusBarItem = vscode.window.createStatusBarItem(
      'aiSocialScientist.parseMode',
      vscode.StatusBarAlignment.Right,
      100  // 优先级，与其他状态栏项目协调
    );

    this.updateStatusBarItem();
    this.statusBarItem.show();

    // 注册命令：切换解析模式
    const toggleCommand = vscode.commands.registerCommand(
      'aiSocialScientist.toggleParseMode',
      () => this.toggleMode()
    );
    context.subscriptions.push(toggleCommand);

    // 状态栏点击事件
    this.statusBarItem.command = 'aiSocialScientist.toggleParseMode';

    this.log(`ParseModeManager initialized with mode: ${this.currentMode}`);
  }

  /**
   * 获取当前解析模式
   */
  getMode(): ParseMode {
    return this.currentMode;
  }

  /**
   * 设置解析模式
   */
  async setMode(mode: ParseMode): Promise<void> {
    if (this.currentMode === mode) {
      return;
    }

    this.currentMode = mode;
    await this.context.globalState.update(ParseModeManager.STORAGE_KEY, mode);
    this.updateStatusBarItem();

    this.log(`Parse mode changed to: ${mode}`);
  }

  /**
   * 切换解析模式
   */
  async toggleMode(): Promise<void> {
    const newMode: ParseMode = this.currentMode === 'auto' ? 'manual' : 'auto';
    await this.setMode(newMode);
  }

  /**
   * 检查是否为自动模式
   */
  isAutoMode(): boolean {
    return this.currentMode === 'auto';
  }

  /**
   * 更新状态栏显示
   */
  private updateStatusBarItem(): void {
    if (this.currentMode === 'auto') {
      this.statusBarItem.text = 'PDF自动解析';
      this.statusBarItem.tooltip = localize('paperWatcher.parseMode');
      this.statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.prominentBackground');
    } else {
      this.statusBarItem.text = 'PDF手动解析';
      this.statusBarItem.tooltip = localize('paperWatcher.parseMode');
      this.statusBarItem.backgroundColor = undefined;
    }
  }

  /**
   * 日志记录
   */
  private log(message: string): void {
    const timestamp = new Date().toISOString();
    this.outputChannel.appendLine(`[${timestamp}] ${message}`);
  }

  /**
   * 清理资源
   */
  dispose(): void {
    this.statusBarItem.dispose();
    this.outputChannel.dispose();
  }
}
