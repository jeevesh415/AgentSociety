/**
 * Papers目录文件监听器
 *
 * 监听papers目录下的文件变化，根据解析模式处理PDF文件：
 * - 自动模式：自动使用MinerU解析
 * - 手动模式：提示用户是否解析
 *
 * 关联文件：
 * - @extension/src/extension.ts - 主入口，创建PaperWatcher实例
 * - @extension/src/mineruParser.ts - MinerU本地解析器（直接调用CLI）
 * - @extension/src/parseModeManager.ts - 解析模式管理
 * - @extension/src/dragAndDropController.ts - 拖拽上传后触发解析
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { localize } from './i18n';
import { ParseModeManager } from './parseModeManager';
import { MinerUParser } from './mineruParser';

export class PaperWatcher {
  private watcher: vscode.FileSystemWatcher | undefined;
  private workspacePath: string = '';
  private outputChannel: vscode.OutputChannel;
  private mineruParser: MinerUParser;
  private context: vscode.ExtensionContext;
  private parseModeManager: ParseModeManager;

  // 已处理的文件集合（避免重复处理）
  private processedFiles: Set<string> = new Set();

  // 防抖定时器
  private debounceTimer: NodeJS.Timeout | undefined;
  private readonly DEBOUNCE_DELAY = 1000; // 1秒防抖

  // 支持的文件扩展名
  private readonly SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.doc'];

  constructor(context: vscode.ExtensionContext, mineruParser: MinerUParser, parseModeManager: ParseModeManager) {
    this.context = context;
    this.mineruParser = mineruParser;
    this.parseModeManager = parseModeManager;
    this.outputChannel = vscode.window.createOutputChannel('Paper Watcher');

    this.setupWatcher();

    // 注册清理函数
    context.subscriptions.push(this);
  }

  private log(message: string): void {
    const timestamp = new Date().toISOString();
    this.outputChannel.appendLine(`[${timestamp}] ${message}`);
  }

  /**
   * 设置文件系统监听器
   */
  private setupWatcher(): void {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      this.log('No workspace folder found, skipping paper watcher setup');
      return;
    }

    this.workspacePath = workspaceFolder.uri.fsPath;
    this.log(`Setting up paper watcher for workspace: ${this.workspacePath}`);

    // 创建papers目录的文件监听器
    const papersPattern = new vscode.RelativePattern(
      workspaceFolder,
      'papers/**/*'
    );

    this.watcher = vscode.workspace.createFileSystemWatcher(papersPattern);

    // 监听文件创建事件
    this.watcher.onDidCreate((uri) => {
      this.handleFileChange(uri, 'created');
    });

    // 监听文件修改事件（可能是文件被替换）
    this.watcher.onDidChange((uri) => {
      this.handleFileChange(uri, 'changed');
    });

    // 将监听器添加到context.subscriptions
    this.context.subscriptions.push(this.watcher);
    this.log('Paper watcher setup completed');

    // 初始化时扫描已存在的文件
    this.scanExistingFiles();
  }

  /**
   * 处理文件变化事件（带防抖）
   */
  private handleFileChange(uri: vscode.Uri, eventType: 'created' | 'changed'): void {
    const filePath = uri.fsPath;

    // 清除之前的定时器
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }

    // 设置新的防抖定时器
    this.debounceTimer = setTimeout(() => {
      this.processFileChange(filePath, eventType);
    }, this.DEBOUNCE_DELAY);
  }

  /**
   * 处理文件变化
   */
  private async processFileChange(filePath: string, eventType: 'created' | 'changed'): Promise<void> {
    try {
      // 忽略mineru_output文件夹中的文件变化
      if (filePath.includes('mineru_output')) {
        return;
      }

      // 检查文件扩展名
      const ext = path.extname(filePath).toLowerCase();
      if (!this.SUPPORTED_EXTENSIONS.includes(ext)) {
        return; // 不支持的文件格式，忽略
      }

      // 检查文件是否存在
      if (!fs.existsSync(filePath)) {
        return;
      }

      // 检查是否已经处理过
      if (this.processedFiles.has(filePath)) {
        return;
      }

      // 检查是否已有解析文件
      const hasParsedFile = this.checkParsedFileExists(filePath);
      if (hasParsedFile) {
        this.log(`File ${filePath} already has parsed markdown file, skipping`);
        this.processedFiles.add(filePath);
        return;
      }

      // 标记为已处理（避免重复处理）
      this.processedFiles.add(filePath);

      // 根据解析模式处理
      if (this.parseModeManager.isAutoMode()) {
        // 自动模式：直接解析
        this.log(`Auto-parse mode: automatically parsing ${filePath}`);
        await this.parseFile(filePath);
      } else {
        // 手动模式：提示用户
        await this.promptUserToParse(filePath);
      }

    } catch (error) {
      this.log(`Error processing file change: ${error}`);
    }
  }

  /**
   * 手动触发解析文件（用于拖拽上传后的自动解析）
   * @param filePath 文件路径
   * @param silent 是否静默解析（不显示通知）
   */
  async triggerParse(filePath: string, silent: boolean = false): Promise<boolean> {
    try {
      // 检查文件扩展名
      const ext = path.extname(filePath).toLowerCase();
      if (!this.SUPPORTED_EXTENSIONS.includes(ext)) {
        return false;
      }

      // 检查文件是否存在
      if (!fs.existsSync(filePath)) {
        return false;
      }

      // 检查是否已有解析文件
      if (this.checkParsedFileExists(filePath)) {
        this.log(`File ${filePath} already has parsed markdown file, skipping`);
        return false;
      }

      // 标记为已处理
      this.processedFiles.add(filePath);

      // 解析文件
      await this.parseFile(filePath, silent);
      return true;
    } catch (error) {
      this.log(`Error in triggerParse: ${error}`);
      return false;
    }
  }

  /**
   * 检查是否已存在解析文件
   */
  private checkParsedFileExists(filePath: string): boolean {
    const dir = path.dirname(filePath);
    const basename = path.basename(filePath, path.extname(filePath));

    // 检查两种可能的解析文件位置
    // 1. {原文件名}.parsed.md
    const parsedMdPath = path.join(dir, `${basename}.parsed.md`);
    if (fs.existsSync(parsedMdPath)) {
      return true;
    }

    // 2. mineru_output/{文件名}/auto/{文件名}.md
    const mineruOutputDir = path.join(dir, 'mineru_output');
    if (fs.existsSync(mineruOutputDir)) {
      // 查找所有可能的markdown文件
      try {
        const files = fs.readdirSync(mineruOutputDir, { recursive: true });
        for (const file of files) {
          if (typeof file === 'string' && file.endsWith('.md')) {
            return true;
          }
        }
      } catch (error) {
        // 忽略读取错误
      }
    }

    return false;
  }

  /**
   * 提示用户是否解析文件（手动模式）
   */
  private async promptUserToParse(filePath: string): Promise<void> {
    const fileName = path.basename(filePath);
    const relativePath = path.relative(this.workspacePath, filePath);

    const parseLabel = localize('paperWatcher.parse');
    const laterLabel = localize('paperWatcher.later');
    const dontAskLabel = localize('paperWatcher.dontAsk');

    const action = await vscode.window.showInformationMessage(
      `${localize('paperWatcher.newFile', fileName)}\n${localize('paperWatcher.parsePrompt')}`,
      { modal: false },
      parseLabel,
      laterLabel,
      dontAskLabel
    );

    if (action === parseLabel) {
      await this.parseFile(filePath);
    } else if (action === dontAskLabel) {
      // 将文件添加到已处理列表，不再提示
      this.processedFiles.add(filePath);
      vscode.window.showInformationMessage(
        localize('paperWatcher.skipped', fileName)
      );
    }
    // '稍后' 选项：不做任何操作，下次文件变化时还会提示
  }

  /**
   * 解析文件
   * @param filePath 文件路径
   * @param silent 是否静默解析（不显示进度通知）
   */
  private async parseFile(filePath: string, silent: boolean = false): Promise<void> {
    try {
      const fileName = path.basename(filePath);
      const relativePath = path.relative(this.workspacePath, filePath);

      this.log(`Starting MinerU parse for file: ${filePath}`);

      // 显示进度通知（非静默模式）
      if (!silent) {
        vscode.window.showInformationMessage(localize('paperWatcher.parsing', fileName));
      }

      // 使用本地 MinerU 解析器解析文件
      const result = await this.mineruParser.parse({
        filePath,
        workspacePath: this.workspacePath,
      });

      if (result.success) {
        const parsedFilePath = result.parsedFilePath || result.markdownFilePath;

        // 静默模式：仅在成功时显示简短通知
        if (silent) {
          this.log(`Successfully parsed file (silent): ${filePath}, result: ${parsedFilePath}`);
          // 静默模式可以选择不显示通知，或显示更简洁的通知
          vscode.window.showInformationMessage(
            `${localize('paperWatcher.success', fileName)}`,
            localize('extension.parseMinerU.openFile')
          ).then(selection => {
            if (selection === localize('extension.parseMinerU.openFile') && parsedFilePath) {
              vscode.window.showTextDocument(vscode.Uri.file(parsedFilePath));
            }
          });
        } else {
          const openFileLabel = localize('extension.parseMinerU.openFile');
          const relativeParsedPath = parsedFilePath ? path.relative(this.workspacePath, parsedFilePath) : 'N/A';
          const successMessage = `${localize('paperWatcher.success', fileName)}\n${localize('paperWatcher.parsedFile', relativeParsedPath)}`;
          vscode.window.showInformationMessage(
            successMessage,
            openFileLabel
          ).then(selection => {
            if (selection === openFileLabel && parsedFilePath) {
              vscode.window.showTextDocument(vscode.Uri.file(parsedFilePath));
            }
          });
        }
        this.log(`Successfully parsed file: ${filePath}, output: ${parsedFilePath}`);
      } else {
        vscode.window.showErrorMessage(
          localize('paperWatcher.failed', `${fileName}\n${result.message}`)
        );
        this.log(`Failed to parse file: ${filePath}, error: ${result.message}`);
      }
    } catch (error) {
      const fileName = path.basename(filePath);
      vscode.window.showErrorMessage(
        localize('paperWatcher.error', `${fileName}\n${error}`)
      );
      this.log(`Error parsing file: ${filePath}, error: ${error}`);
    }
  }

  /**
   * 扫描已存在的文件
   */
  private scanExistingFiles(): void {
    const papersDir = path.join(this.workspacePath, 'papers');
    if (!fs.existsSync(papersDir)) {
      this.log(`Papers directory not found: ${papersDir}`);
      return;
    }

    this.log(`Scanning existing files in ${papersDir}`);

    try {
      const files = this.getAllFiles(papersDir);
      for (const file of files) {
        const ext = path.extname(file).toLowerCase();
        if (this.SUPPORTED_EXTENSIONS.includes(ext)) {
          // 检查是否已有解析文件
          if (this.checkParsedFileExists(file)) {
            this.processedFiles.add(file);
          }
        }
      }
      this.log(`Scanned ${files.length} files, found ${this.processedFiles.size} files with parsed markdown`);
    } catch (error) {
      this.log(`Error scanning existing files: ${error}`);
    }
  }

  /**
   * 递归获取目录下所有文件
   */
  private getAllFiles(dir: string): string[] {
    const files: string[] = [];
    try {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);

        // 忽略mineru_output文件夹
        if (entry.isDirectory() && entry.name === 'mineru_output') {
          continue;
        }

        if (entry.isDirectory()) {
          files.push(...this.getAllFiles(fullPath));
        } else if (entry.isFile()) {
          files.push(fullPath);
        }
      }
    } catch (error) {
      // 忽略读取错误
    }
    return files;
  }

  /**
   * 清理资源
   */
  dispose(): void {
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }
    if (this.watcher) {
      this.watcher.dispose();
    }
    this.outputChannel.dispose();
    this.log('Paper watcher disposed');
  }
}
