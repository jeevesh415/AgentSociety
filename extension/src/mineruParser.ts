/**
 * MinerU Parser - Local MinerU CLI invocation
 *
 * 直接调用 MinerU CLI 进行 PDF 解析，不依赖后端 API。
 *
 * 关联文件：
 * - @extension/src/paperWatcher.ts - 文件监听器调用MinerU解析
 * - @extension/src/extension.ts - 主入口，创建MinerUParser实例
 * - @extension/src/dragAndDropController.ts - 拖拽上传后触发解析
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { spawn } from 'child_process';
import * as os from 'os';

export interface MinerUParseOptions {
  filePath: string;
  workspacePath: string;
  outputPath?: string;
}

export interface MinerUParseResult {
  success: boolean;
  message: string;
  parsedFilePath?: string;
  markdownFilePath?: string;
  jsonFilePath?: string;
}

export class MinerUParser {
  private outputChannel: vscode.OutputChannel;

  constructor() {
    this.outputChannel = vscode.window.createOutputChannel('MinerU Parser');
  }

  private log(message: string): void {
    const timestamp = new Date().toISOString();
    this.outputChannel.appendLine(`[${timestamp}] ${message}`);
  }

  /**
   * Find MinerU CLI executable
   * Uses PYTHON_PATH from .env if configured, otherwise falls back to system PATH
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
        const result = spawnSync(candidate, ['--version'], { stdio: 'ignore' });
        if (result.status === 0 || result.error === undefined) {
          this.log(`Found MinerU CLI at: ${candidate}`);
          return candidate;
        }
      } catch {
        // Continue to next candidate
      }
    }

    this.log(`MinerU CLI not found in any location`);
    return null;
  }

  /**
   * Parse PDF with MinerU CLI
   */
  async parse(options: MinerUParseOptions): Promise<MinerUParseResult> {
    const { filePath, workspacePath, outputPath } = options;

    this.log(`Parsing PDF: ${filePath}`);

    // Verify file exists
    if (!fs.existsSync(filePath)) {
      return {
        success: false,
        message: `File not found: ${filePath}`,
      };
    }

    // Find MinerU CLI
    const mineruCLI = await this.findMinerUCLI();
    if (!mineruCLI) {
      return {
        success: false,
        message: 'MinerU CLI not found. Please install MinerU and add it to your PATH.',
      };
    }

    // Determine output directory
    // Output to mineru_output subdirectory next to the PDF file
    // This matches what paperWatcher.checkParsedFileExists() expects
    const pdfDir = path.dirname(filePath);
    const fileName = path.basename(filePath, path.extname(filePath));
    const defaultOutputDir = path.join(pdfDir, 'mineru_output', fileName);

    // Create output directory if needed
    if (!fs.existsSync(defaultOutputDir)) {
      fs.mkdirSync(defaultOutputDir, { recursive: true });
    }

    // Run MinerU CLI
    const outputDir = outputPath || defaultOutputDir;
    this.log(`Output directory: ${outputDir}`);

    try {
      const result = await this.runMinerUCLI(mineruCLI, filePath, outputDir);

      if (!result.success) {
        return result;
      }

      // Find generated files
      // MinerU can output to different directories depending on backend:
      // - pipeline backend: {outputDir}/auto/{fileName}.md
      // - hybrid-auto-engine backend: {outputDir}/{fileName}/hybrid_auto/{fileName}.md

      // First, try hybrid_auto directory (hybrid-auto-engine backend)
      const hybridAutoDir = path.join(outputDir, fileName, 'hybrid_auto');
      const hybridMdFile = path.join(hybridAutoDir, `${fileName}.md`);
      const hybridJsonFile = path.join(hybridAutoDir, `${fileName}_content.json`);

      // Second, try auto directory (pipeline backend)
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
        // Not found in either location, list what was created
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

      // Update literature_index.json
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
   * Run MinerU CLI
   * Uses -m auto for automatic method selection (txt vs ocr)
   */
  private runMinerUCLI(
    cliPath: string,
    inputPath: string,
    outputDir: string
  ): Promise<MinerUParseResult> {
    return new Promise((resolve, reject) => {
      // Use -m auto for automatic method detection
      const args = ['-p', inputPath, '-o', outputDir, '-m', 'auto'];
      this.log(`Running: ${cliPath} ${args.join(' ')}`);

      // Set HF_ENDPOINT to use mirror if HuggingFace is unreachable
      const spawnEnv = { ...process.env, HF_ENDPOINT: 'https://hf-mirror.com' };

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

      // Set a timeout to avoid hanging (5 minutes)
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
   * Update literature_index.json
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
   * Dispose
   */
  dispose(): void {
    this.outputChannel.dispose();
  }
}

// Helper for spawnSync
function spawnSync(command: string, args: string[], p0: { stdio: string; }): any {
  const { spawnSync } = require('child_process');
  return spawnSync(command, args);
}
