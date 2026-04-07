/**
 * MinerU Parser - MinerU PDF 解析器（本地 CLI 调用）
 *
 * 本模块负责直接调用 MinerU CLI 进行 PDF 文档解析，不依赖后端 API。
 * 解析流程会将 PDF 转换为 Markdown 和 JSON 格式，并自动更新文献索引。
 *
 * 核心工作流程：
 *   1. 解析前检查 MinerU 环境是否就绪（CLI + 模型）
 *   2. 查找 MinerU CLI 可执行文件路径
 *   3. 确定输出目录（默认在 PDF 同级目录创建 mineru_output/）
 *   4. 执行 MinerU CLI 命令进行解析（自动检测 txt vs ocr 模式）
 *   5. 在输出目录中查找生成的 Markdown 和 JSON 文件
 *   6. 更新工作区的 literature_index.json 文献索引
 *
 * MinerU 输出目录结构：
 *   - pipeline 后端:         {outputDir}/auto/{fileName}.md
 *   - hybrid-auto-engine 后端: {outputDir}/{fileName}/hybrid_auto/{fileName}.md
 *
 * 关联文件：
 * - @extension/src/paperWatcher.ts - 文件监听器调用MinerU解析
 * - @extension/src/extension.ts - 主入口，创建MinerUParser实例
 * - @extension/src/dragAndDropController.ts - 拖拽上传后触发解析
 * - @extension/src/services/mineruInitializer.ts - 环境初始化状态检查
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { spawn, execFileSync } from 'child_process';
import * as os from 'os';
import type { MinerUInitializer } from './services/mineruInitializer';
import { localize } from './i18n';

/**
 * MinerU 解析选项
 *
 * @property filePath - 待解析的 PDF 文件绝对路径
 * @property workspacePath - 当前工作区根目录路径（用于定位文献索引）
 * @property outputPath - 可选的自定义输出目录，不指定则在 PDF 同级创建 mineru_output/
 */
export interface MinerUParseOptions {
  filePath: string;
  workspacePath: string;
  outputPath?: string;
}

/**
 * MinerU 解析结果
 *
 * @property success - 解析是否成功
 * @property message - 结果描述消息（成功时为文件名，失败时为错误原因）
 * @property parsedFilePath - 解析后的 Markdown 文件路径（成功时有值）
 * @property markdownFilePath - 同 parsedFilePath，解析后的 Markdown 文件路径
 * @property jsonFilePath - 解析后的 JSON 内容文件路径（如果存在）
 */
export interface MinerUParseResult {
  success: boolean;
  message: string;
  parsedFilePath?: string;
  markdownFilePath?: string;
  jsonFilePath?: string;
}

/**
 * MinerUParser - MinerU PDF 解析器
 *
 * 通过调用本地 MinerU CLI 将 PDF 文档解析为 Markdown 和 JSON 格式。
 * 支持与 MinerUInitializer 集成，在解析前自动检查环境是否就绪。
 *
 * 使用方式：
 *   const parser = new MinerUParser(initializer);  // initializer 可选
 *   const result = await parser.parse({ filePath, workspacePath });
 */
export class MinerUParser {
  /** 输出通道，用于在 VSCode "输出" 面板中展示解析日志 */
  private outputChannel: vscode.OutputChannel;

  /**
   * MinerU 环境初始化器实例（可选）
   *
   * 如果提供了初始化器，在解析前会自动检查：
   * - MinerU CLI 是否已安装
   * - 模型是否已下载
   * - 是否正在下载中
   * 未就绪时会弹窗提示用户，避免无意义的解析失败。
   * 如果未提供，则跳过检查（向后兼容旧版用法）。
   */
  private initializer: MinerUInitializer | null;

  constructor(initializer?: MinerUInitializer) {
    this.outputChannel = vscode.window.createOutputChannel('MinerU Parser');
    this.initializer = initializer ?? null;
  }

  private log(message: string): void {
    const timestamp = new Date().toISOString();
    this.outputChannel.appendLine(`[${timestamp}] ${message}`);
  }

  /**
   * 查找 MinerU CLI 可执行文件
   *
   * 查找策略（按优先级从高到低）：
   * 1. 从 .env 文件中配置的 PYTHON_PATH 推导 bin 目录，查找 mineru
   * 2. 在系统 PATH 和常见路径中查找（mineru、mineru_cli、~/.local/bin/mineru 等）
   *
   * 注意：此方法还会执行 --version 命令验证 CLI 是否真正可用。
   *
   * @returns MinerU CLI 路径字符串，未找到返回 null
   */
  private async findMinerUCLI(): Promise<string | null> {
    // First, try to get PYTHON_PATH from .env
    const { EnvManager } = await import('./envManager');
    const envManager = new EnvManager();
    const envConfig = envManager.readEnv();
    const configuredPythonPath = envConfig.pythonPath?.trim();

    this.log(`PYTHON_PATH from .env: ${configuredPythonPath || '(not set)'}`);

    // Check PYTHON_PATH/bin/mineru if configured
    if (configuredPythonPath) {
      const pythonBinDir = path.dirname(configuredPythonPath);
      const mineruPath = path.join(pythonBinDir, 'mineru');
      this.log(`Checking for mineru at: ${mineruPath}`);
      if (fs.existsSync(mineruPath)) {
        this.log(`Found MinerU at PYTHON_PATH/bin: ${mineruPath}`);
        return mineruPath;
      }
      this.log(`MinerU not found at: ${mineruPath}`);
    }

    // Fallback: check common paths
    const candidates = [
      'mineru',  // If in PATH
      'mineru_cli',
      path.join(os.homedir(), '.local', 'bin', 'mineru'),
      '/usr/local/bin/mineru',
    ];

    for (const candidate of candidates) {
      this.log(`Checking candidate: ${candidate}`);
      try {
        execFileSync(candidate, ['--version'], { stdio: 'ignore', timeout: 5000 });
        this.log(`Found MinerU CLI at: ${candidate}`);
        return candidate;
      } catch {
        // Continue to next candidate
      }
    }

    this.log(`MinerU CLI not found in any location`);
    return null;
  }

  /**
   * 检查 MinerU 初始化状态，未就绪时给出明确提示
   *
   * 在执行 PDF 解析前调用，根据 MinerUInitializer 的当前状态决定是否继续：
   * - models_ready:  环境就绪，继续解析（返回 true）
   * - not_installed: 弹出错误提示，引导用户查看安装指南（返回 false）
   * - cli_ready:     弹出警告提示，引导用户下载模型（返回 false 或等待下载完成）
   * - downloading:   提示用户等待下载完成（返回 false）
   * - checking:      提示用户等待检查完成（返回 false）
   * - error:         弹出错误提示，提供重试和查看日志选项（返回 false）
   *
   * @returns true 表示环境就绪可以继续解析，false 表示应中止解析
   */
  private async checkInitStatus(): Promise<boolean> {
    if (!this.initializer) {
      return true; // 没有初始化器，跳过检查（向后兼容）
    }

    const status = this.initializer.status;

    switch (status) {
      case 'models_ready':
        return true;

      case 'not_installed': {
        const installLabel = localize('mineruParser.showInstallGuide');
        const result = await vscode.window.showErrorMessage(
          localize('mineruParser.notInstalled'),
          installLabel
        );
        if (result === installLabel) {
          vscode.env.openExternal(vscode.Uri.parse('https://github.com/opendatalab/MinerU'));
        }
        return false;
      }

      case 'cli_ready': {
        const downloadLabel = localize('mineruParser.downloadModels');
        const result = await vscode.window.showWarningMessage(
          localize('mineruParser.noModels'),
          downloadLabel,
          localize('mineruParser.cancel')
        );
        if (result === downloadLabel) {
          const success = await this.initializer.downloadModels();
          return success;
        }
        return false;
      }

      case 'downloading':
        vscode.window.showInformationMessage(localize('mineruParser.downloading'));
        return false;

      case 'checking':
        vscode.window.showInformationMessage(localize('mineruParser.checking'));
        return false;

      case 'error': {
        const retryLabel = localize('mineruParser.retryCheck');
        const logsLabel = localize('mineruParser.showLogs');
        const result = await vscode.window.showErrorMessage(
          localize('mineruParser.initFailed'),
          retryLabel,
          logsLabel
        );
        if (result === retryLabel) {
          const newStatus = await this.initializer.checkAndInitialize();
          return newStatus === 'models_ready';
        } else if (result === logsLabel) {
          this.initializer.showLogs();
        }
        return false;
      }

      default:
        return true;
    }
  }

  /**
   * 执行 PDF 解析（主入口方法）
   *
   * 完整解析流程：
   * 1. 验证 PDF 文件是否存在
   * 2. 检查 MinerU 环境是否就绪（通过 initializer）
   * 3. 查找 MinerU CLI 可执行文件（优先使用 initializer 已找到的路径）
   * 4. 确定输出目录（默认: PDF同级目录/mineru_output/文件名/）
   * 5. 调用 MinerU CLI 执行解析（自动检测 txt vs ocr 模式）
   * 6. 在输出目录中查找生成的 Markdown 和 JSON 文件
   * 7. 更新工作区的 literature_index.json 文献索引
   *
   * @param options - 解析选项，包含文件路径和工作区路径
   * @returns 解析结果，包含成功状态、消息和输出文件路径
   */
  async parse(options: MinerUParseOptions): Promise<MinerUParseResult> {
    const { filePath, workspacePath, outputPath } = options;

    this.log(`Parsing PDF: ${filePath}`);

    // 验证 PDF 文件是否存在
    if (!fs.existsSync(filePath)) {
      return {
        success: false,
        message: `File not found: ${filePath}`,
      };
    }

    // 检查 MinerU 环境是否就绪（CLI 已安装 + 模型已下载）
    // 如果未就绪，会弹窗提示用户安装/下载，返回 false
    const initReady = await this.checkInitStatus();
    if (!initReady) {
      return {
        success: false,
        message: localize('mineruParser.envNotReady'),
      };
    }

    // 查找 MinerU CLI 路径
    // 优先使用初始化器已缓存的路径（避免重复查找），否则重新搜索
    const mineruCLI = this.initializer?.cliPath ?? await this.findMinerUCLI();
    if (!mineruCLI) {
      return {
        success: false,
        message: localize('mineruParser.cliNotFound'),
      };
    }

    // 确定输出目录
    // 默认输出到 PDF 文件同级目录下的 mineru_output/<文件名>/ 子目录
    // 此路径约定需要与 paperWatcher.checkParsedFileExists() 保持一致
    const pdfDir = path.dirname(filePath);
    const fileName = path.basename(filePath, path.extname(filePath));
    const defaultOutputDir = path.join(pdfDir, 'mineru_output', fileName);

    // 如果输出目录不存在则递归创建
    if (!fs.existsSync(defaultOutputDir)) {
      fs.mkdirSync(defaultOutputDir, { recursive: true });
    }

    // 运行 MinerU CLI 进行解析
    const outputDir = outputPath || defaultOutputDir;
    this.log(`Output directory: ${outputDir}`);

    try {
      const result = await this.runMinerUCLI(mineruCLI, filePath, outputDir);

      if (!result.success) {
        return result;
      }

      // ========== 在输出目录中查找解析结果文件 ==========
      // MinerU 根据后端类型会输出到不同的子目录：
      // - pipeline 后端:         {outputDir}/auto/{fileName}.md
      // - hybrid-auto-engine 后端: {outputDir}/{fileName}/hybrid_auto/{fileName}.md
      // 需要按优先级依次检查，找到第一个存在的文件

      // 优先检查 hybrid-auto-engine 后端的输出路径
      const hybridAutoDir = path.join(outputDir, fileName, 'hybrid_auto');
      const hybridMdFile = path.join(hybridAutoDir, `${fileName}.md`);
      const hybridJsonFile = path.join(hybridAutoDir, `${fileName}_content.json`);

      // 其次检查 pipeline 后端的输出路径
      const autoDir = path.join(outputDir, 'auto');
      const autoMdFile = path.join(autoDir, `${fileName}.md`);
      const autoJsonFile = path.join(autoDir, `${fileName}_content.json`);

      this.log(`Checking for output files...`);
      this.log(`Trying hybrid_auto: ${hybridMdFile}`);
      this.log(`Trying auto: ${autoMdFile}`);

      let mdFile = '';
      let jsonFile = '';

      if (fs.existsSync(hybridMdFile)) {
        mdFile = hybridMdFile;
        jsonFile = hybridJsonFile;
        this.log(`Found output in hybrid_auto directory`);
      } else if (fs.existsSync(autoMdFile)) {
        mdFile = autoMdFile;
        jsonFile = autoJsonFile;
        this.log(`Found output in auto directory`);
      } else {
        // 两个路径都未找到输出文件，记录输出目录内容以便调试
        this.log(`Output file not found in expected locations`);
        if (fs.existsSync(outputDir)) {
          const entries = fs.readdirSync(outputDir, { recursive: true });
          this.log(`Output directory contents: ${entries.join(', ')}`);
        }
        return {
          success: false,
          message: `MinerU completed but output file not found. Tried: ${hybridMdFile}, ${autoMdFile}`,
        };
      }

      this.log(`Found output file: ${mdFile}`);

      // ========== 更新文献索引 ==========
      // 将解析结果自动添加到工作区的 literature_index.json 中，
      // 以便文献管理功能（树视图、搜索等）能发现新解析的文献
      await this.updateLiteratureIndex(workspacePath, mdFile, jsonFile);

      return {
        success: true,
        message: `Successfully parsed: ${fileName}`,
        parsedFilePath: mdFile,
        markdownFilePath: mdFile,
        jsonFilePath: fs.existsSync(jsonFile) ? jsonFile : undefined,
      };
    } catch (error: any) {
      this.log(`Parse error: ${error.message || error}`);
      return {
        success: false,
        message: `Parse failed: ${error.message || error}`,
      };
    }
  }

  /**
   * 执行 MinerU CLI 命令
   *
   * 使用 `-m auto` 参数让 MinerU 自动检测解析方式：
   * - 对于文本型 PDF：使用文本提取模式（更快）
   * - 对于扫描件/图片型 PDF：使用 OCR 模式（更准确）
   *
   * 执行流程：
   * 1. 构建 CLI 命令参数
   * 2. 设置 MINERU_MODEL_SOURCE=modelscope 使用 ModelScope 作为模型源
   * 3. 在子进程中异步执行命令
   * 4. 实时收集 stdout 和 stderr 输出到日志
   * 5. 设置 5 分钟超时保护
   * 6. 根据退出码返回解析结果
   *
   * @param cliPath - MinerU CLI 可执行文件路径
   * @param inputPath - 待解析的 PDF 文件路径
   * @param outputDir - 输出目录路径
   * @returns 解析结果（成功/失败 + 消息）
   */
  private runMinerUCLI(
    cliPath: string,
    inputPath: string,
    outputDir: string
  ): Promise<MinerUParseResult> {
    return new Promise((resolve, reject) => {
      // 构建命令行参数：
      // -p: 输入 PDF 文件路径
      // -o: 输出目录路径
      // -m auto: 自动检测解析方式（文本提取 vs OCR）
      const args = ['-p', inputPath, '-o', outputDir, '-m', 'auto'];
      this.log(`Running: ${cliPath} ${args.join(' ')}`);

      // 设置 ModelScope 作为模型下载源
      // 使用 ModelScope 下载模型（国内直接访问，无需镜像）
      const spawnEnv = { ...process.env, MINERU_MODEL_SOURCE: 'modelscope' };

      const childProcess = spawn(cliPath, args, { env: spawnEnv });
      let stdout = '';
      let stderr = '';

      childProcess.stdout?.on('data', (data: Buffer) => {
        stdout += data.toString();
        this.log(`[STDOUT] ${data}`);
      });

      childProcess.stderr?.on('data', (data: Buffer) => {
        stderr += data.toString();
        this.log(`[STDERR] ${data}`);
      });

      // 设置 5 分钟超时保护，防止解析挂起（大型 PDF 可能需要较长时间）
      const timeout = setTimeout(() => {
        this.log('MinerU CLI timeout after 5 minutes, killing process');
        childProcess.kill();
        resolve({
          success: false,
          message: 'MinerU CLI timeout: parsing took longer than 5 minutes',
        });
      }, 5 * 60 * 1000);

      childProcess.on('close', (code: number | null) => {
        clearTimeout(timeout);
        this.log(`MinerU CLI exited with code: ${code}`);
        if (code === 0) {
          this.log('MinerU CLI completed successfully');
          resolve({
            success: true,
            message: 'Parse completed',
          });
        } else {
          this.log(`MinerU CLI failed with exit code ${code}`);
          // Show output channel for debugging
          this.outputChannel.show();
          resolve({
            success: false,
            message: `MinerU CLI failed with exit code ${code}. Check 'MinerU Parser' output for details.`,
          });
        }
      });

      childProcess.on('error', (error: Error) => {
        clearTimeout(timeout);
        this.log(`MinerU CLI error: ${error.message}`);
        this.outputChannel.show();
        reject(error);
      });
    });
  }

  /**
   * 更新文献索引文件 literature_index.json
   *
   * 解析完成后，将新文献条目添加到工作区的 papers/literature_index.json 中。
   * 索引结构示例：
   * {
   *   "entries": [
   *     { "title": "文件名", "file_path": "papers/xxx/xxx.md", "created_at": "..." }
   *   ],
   *   "updated_at": "..."
   * }
   *
   * 如果条目已存在（按 file_path 去重），则跳过添加。
   *
   * @param workspacePath - 工作区根目录路径
   * @param mdFilePath - 解析后的 Markdown 文件绝对路径
   * @param jsonFilePath - 解析后的 JSON 文件绝对路径（可选）
   */
  private async updateLiteratureIndex(
    workspacePath: string,
    mdFilePath: string,
    jsonFilePath?: string
  ): Promise<void> {
    const indexPath = path.join(workspacePath, 'papers', 'literature_index.json');

    let index: any = { entries: [] };

    // Load existing index
    if (fs.existsSync(indexPath)) {
      try {
        index = JSON.parse(fs.readFileSync(indexPath, 'utf-8'));
      } catch (error) {
        this.log(`Failed to parse existing index, creating new: ${error}`);
      }
    }

    // Add new entry
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      return;
    }

    const relativePath = path.relative(workspaceFolder.uri.fsPath, mdFilePath).replace(/\\/g, '/');
    const fileName = path.basename(mdFilePath, '.md');

    // Check if entry already exists
    const existingEntry = (index.entries || []).find((e: any) => e.file_path === relativePath);
    if (!existingEntry) {
      const newEntry = {
        title: fileName,
        file_path: relativePath,
        created_at: new Date().toISOString(),
      };

      index.entries = index.entries || [];
      index.entries.push(newEntry);
      index.updated_at = new Date().toISOString();

      // Save index
      fs.writeFileSync(indexPath, JSON.stringify(index, null, 2), 'utf-8');
      this.log(`Updated literature index with: ${fileName}`);
    }
  }

  /**
   * 释放资源
   *
   * 清理输出通道，防止内存泄漏。
   * 此方法会在扩展停用时由 VSCode 自动调用。
   */
  dispose(): void {
    this.outputChannel.dispose();
  }
}
