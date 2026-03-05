/**
 * 拖拽上传控制器 (Drag and Drop Controller)
 * 
 * 实现 TreeDragAndDropController 接口，处理文件拖拽到树视图节点的事件。
 * 支持将本地文件拖拽到"文献库"和"用户数据"节点进行上传。
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { ProjectItem, ProjectStructureProvider } from './projectStructureProvider';
import { localize } from './i18n';

/**
 * 文件处理信息
 */
interface FileToProcess {
  uri: vscode.Uri;
  fileName: string;
  targetUri: vscode.Uri;
  exists: boolean;
  size: number;
  relativePath?: string;  // 用于目录结构保留
}

/**
 * 覆盖策略类型
 */
type OverwriteStrategy = 'overwriteAll' | 'skipAll' | 'askEach' | 'cancel';

/**
 * 大文件阈值 (100 MB)
 */
const LARGE_FILE_THRESHOLD = 100 * 1024 * 1024;

/**
 * TreeDragAndDropController 实现
 * 
 * 处理拖拽事件：
 * - dragMimeTypes: 定义可以拖拽的数据类型（文件URI）
 * - dropMimeTypes: 定义可以接收的数据类型
 * - handleDrop: 处理拖拽放置事件，将文件复制到目标目录
 */
export class ProjectDragAndDropController implements vscode.TreeDragAndDropController<ProjectItem> {
  /**
   * 构造函数
   * @param provider - 项目结构提供者，用于刷新视图
   */
  constructor(private provider: ProjectStructureProvider) {
    // 创建输出通道用于调试日志
    this.outputChannel = vscode.window.createOutputChannel('AI Social Scientist - Drag & Drop');
  }

  private outputChannel: vscode.OutputChannel;

  /**
   * 日志记录方法
   */
  private log(message: string, ...args: any[]): void {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [DragAndDrop] ${message}`;
    console.log(logMessage, ...args);
    this.outputChannel.appendLine(logMessage + (args.length > 0 ? ` ${JSON.stringify(args)}` : ''));
  }

  /**
   * 支持的拖拽 MIME 类型
   * 'application/vnd.code.tree.projectStructureView' 是树视图内部拖拽
   * 'text/uri-list' 是文件系统文件拖拽（本地文件）
   */
  readonly dragMimeTypes = ['application/vnd.code.tree.projectStructureView', 'text/uri-list'];

  /**
   * 支持的接收 MIME 类型
   * 'text/uri-list' 表示可以接收文件URI列表
   */
  readonly dropMimeTypes = ['text/uri-list'];

  /**
   * 处理拖拽放置事件
   * 
   * @param target - 目标节点（文献库或用户数据节点）
   * @param dataTransfer - 拖拽的数据传输对象
   * @param token - 取消令牌
   */
  async handleDrop(
    target: ProjectItem | undefined,
    dataTransfer: vscode.DataTransfer,
    token: vscode.CancellationToken
  ): Promise<void> {
    this.log('handleDrop called', { target: target?.label, targetType: target?.type });

    try {
      // 检查目标节点是否有效
      if (!target) {
        this.log('No target node provided');
        vscode.window.showWarningMessage(localize('dragDrop.noTarget'));
        return;
      }

      this.log('Target node:', target.label, 'Type:', target.type);

      // 只支持拖拽到"文献库"（papers）或"用户数据"（userdata）节点
      if (target.type !== 'papers' && target.type !== 'userdata') {
        this.log('Invalid target type:', target.type);
        vscode.window.showWarningMessage(localize('dragDrop.invalidTarget', target.label));
        return;
      }

      // 获取拖拽的文件URI列表
      const transferItem = dataTransfer.get('text/uri-list');
      if (!transferItem) {
        this.log('No transfer item found in dataTransfer');
        // 检查是否有其他可用的MIME类型
        const availableTypes: string[] = [];
        for (const mimeType of ['text/uri-list', 'application/vnd.code.tree.projectStructureView']) {
          if (dataTransfer.get(mimeType)) {
            availableTypes.push(mimeType);
          }
        }
        this.log('Available MIME types:', availableTypes);
        vscode.window.showWarningMessage(localize('dragDrop.noFiles'));
        return;
      }

      this.log('Transfer item found, parsing URI list...');

      // 解析URI列表（可能包含多个文件，用换行符分隔）
      const uriListString = await transferItem.asString();
      this.log('URI list string:', uriListString.substring(0, 200)); // 只记录前200个字符

      const uris = uriListString
        .split('\n')
        .map(uri => uri.trim())
        .filter(uri => uri.length > 0)
        .map(uri => {
          try {
            const parsed = vscode.Uri.parse(uri);
            this.log('Parsed URI:', parsed.toString());
            return parsed;
          } catch (error: any) {
            this.log('Failed to parse URI:', uri, 'Error:', error.message);
            return null;
          }
        })
        .filter((uri): uri is vscode.Uri => uri !== null);

      this.log('Parsed URIs count:', uris.length);

      if (uris.length === 0) {
        this.log('No valid URIs found');
        vscode.window.showWarningMessage(localize('dragDrop.noValidUris'));
        return;
      }

      // 获取工作区路径
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      if (!workspaceFolder) {
        this.log('No workspace folder found');
        vscode.window.showErrorMessage(localize('dragDrop.noWorkspace'));
        return;
      }

      this.log('Workspace folder:', workspaceFolder.uri.toString());

      // 确定目标目录URI（使用URI而不是fsPath以支持远程）
      // 使用 path.join 构建路径，然后转换为 URI
      const targetDirPath = target.type === 'papers'
        ? path.join(workspaceFolder.uri.fsPath, 'papers')
        : path.join(workspaceFolder.uri.fsPath, 'user_data');
      const targetDirUri = vscode.Uri.file(targetDirPath);

      // 确保目标目录存在（使用VSCode文件系统API）
      try {
        this.log('Creating target directory:', targetDirUri.toString());
        await vscode.workspace.fs.createDirectory(targetDirUri);
        this.log('Target directory created or already exists');
      } catch (error: any) {
        // 目录可能已存在，记录但不中断
        this.log('Error creating directory (may already exist):', error.message);
      }

      // 复制文件
      let successCount = 0;
      let failCount = 0;
      let skipCount = 0;
      const errors: string[] = [];

      // 用于批量处理时的覆盖策略
      // undefined: 未决定，需要询问
      // true: 全部覆盖
      // false: 全部跳过
      let overwriteAll: boolean | undefined = undefined;

      // 先检查哪些文件已存在（使用VSCode文件系统API以支持远程）
      this.log('Starting to process files, count:', uris.length);
      const filesToProcess: Array<{ uri: vscode.Uri; fileName: string; targetUri: vscode.Uri; exists: boolean }> = [];
      for (const uri of uris) {
        if (token.isCancellationRequested) {
          this.log('Operation cancelled');
          break;
        }

        try {
          this.log('Processing URI:', uri.toString());
          // 使用VSCode文件系统API检查源文件
          let stat: vscode.FileStat;
          try {
            stat = await vscode.workspace.fs.stat(uri);
            this.log('File stat retrieved:', { type: stat.type, size: stat.size });
          } catch (error: any) {
            // 文件不存在或无法访问
            const fileName = path.basename(uri.fsPath) || path.basename(uri.path) || localize('dragDrop.fileNotAccessible', '');
            const errorMsg = localize('dragDrop.fileNotAccessible', `${fileName} (${error.message || error})`);
            this.log('Error accessing file:', errorMsg);
            errors.push(errorMsg);
            failCount++;
            continue;
          }

          // 检查是否为文件（不支持拖拽目录）
          if (stat.type === vscode.FileType.Directory) {
            const fileName = path.basename(uri.fsPath) || path.basename(uri.path) || '';
            errors.push(localize('dragDrop.unsupportedDirectory', fileName));
            failCount++;
            continue;
          }

          // 提取文件名（优先使用fsPath，如果不可用则使用path）
          const fileName = path.basename(uri.fsPath) || path.basename(uri.path) || '';
          const targetPath = path.join(targetDirPath, fileName);
          const targetUri = vscode.Uri.file(targetPath);

          // 检查目标文件是否存在
          let exists = false;
          try {
            await vscode.workspace.fs.stat(targetUri);
            exists = true;
          } catch {
            // 文件不存在，这是正常的
            exists = false;
          }

          filesToProcess.push({ uri, fileName, targetUri, exists });
          this.log('File added to process list:', fileName, 'exists:', exists);
        } catch (error: any) {
          const fileName = path.basename(uri.fsPath) || path.basename(uri.path) || '';
          const errorMsg = `${fileName}: ${error.message || error}`;
          this.log('Error processing file:', errorMsg);
          errors.push(errorMsg);
          failCount++;
        }
      }

      this.log('Files to process:', filesToProcess.length);

      // 如果有多个文件需要覆盖确认，先询问批量操作策略
      const existingFiles = filesToProcess.filter(f => f.exists);
      if (existingFiles.length > 0 && filesToProcess.length > 1) {
        const fileNames = existingFiles.slice(0, 3).map(f => f.fileName).join('、');
        const moreFiles = existingFiles.length > 3 ? localize('dragDrop.moreFiles', existingFiles.length) : '';
        const overwriteAllLabel = localize('dragDrop.overwriteAll');
        const skipAllLabel = localize('dragDrop.skipAll');
        const askEachLabel = localize('dragDrop.askEach');
        const response = await vscode.window.showWarningMessage(
          localize('dragDrop.fileExists', `${fileNames}${moreFiles}`),
          { modal: true },
          overwriteAllLabel,
          skipAllLabel,
          askEachLabel
        );

        if (response === overwriteAllLabel) {
          overwriteAll = true;
        } else if (response === skipAllLabel) {
          overwriteAll = false;
        }
        // 如果选择"逐个询问"或取消，overwriteAll 保持 undefined
      }

      // 处理文件复制（使用VSCode文件系统API以支持远程）
      this.log('Starting file copy process');
      for (const fileInfo of filesToProcess) {
        if (token.isCancellationRequested) {
          this.log('Operation cancelled during copy');
          break;
        }

        try {
          this.log('Copying file:', fileInfo.fileName);
          // 如果文件已存在，根据策略决定是否覆盖
          if (fileInfo.exists) {
            let shouldOverwrite = false;

            if (overwriteAll === true) {
              shouldOverwrite = true;
              this.log('Overwriting (all):', fileInfo.fileName);
            } else if (overwriteAll === false) {
              shouldOverwrite = false;
              this.log('Skipping (all):', fileInfo.fileName);
            } else {
              // 逐个询问
              this.log('Asking user for overwrite:', fileInfo.fileName);
              const overwriteLabel = localize('dragDrop.overwrite');
              const skipLabel = localize('dragDrop.skip');
              const overwrite = await vscode.window.showWarningMessage(
                localize('dragDrop.overwriteConfirm', fileInfo.fileName),
                { modal: true },
                overwriteLabel,
                skipLabel
              );
              shouldOverwrite = overwrite === overwriteLabel;
              this.log('User response:', overwrite, 'shouldOverwrite:', shouldOverwrite);
            }

            if (!shouldOverwrite) {
              skipCount++;
              this.log('Skipped file:', fileInfo.fileName);
              continue;
            }
          }

          // 使用VSCode文件系统API读取源文件并写入目标文件
          // 这样可以支持跨机器文件传输（本地文件拖拽到远程工作区）
          this.log('Reading source file:', fileInfo.uri.toString());
          const fileData = await vscode.workspace.fs.readFile(fileInfo.uri);
          this.log('File read, size:', fileData.length, 'bytes');

          this.log('Writing target file:', fileInfo.targetUri.toString());
          await vscode.workspace.fs.writeFile(fileInfo.targetUri, fileData);
          this.log('File copied successfully:', fileInfo.fileName);
          successCount++;
        } catch (error: any) {
          const errorMsg = `${fileInfo.fileName}: ${error.message || error}`;
          this.log('Error copying file:', errorMsg);
          errors.push(errorMsg);
          failCount++;
        }
      }

      this.log('File copy process completed', { successCount, failCount, skipCount });

      // 显示结果消息
      const targetName = target.type === 'papers' ? localize('dragDrop.literature') : localize('dragDrop.userData');
      this.log('Final results:', { successCount, failCount, skipCount, targetName });

      if (successCount > 0 && failCount === 0 && skipCount === 0) {
        vscode.window.showInformationMessage(
          localize('dragDrop.success', successCount, targetName)
        );
        // 刷新树视图以显示新上传的文件
        this.provider.refresh();
      } else if (successCount > 0) {
        const parts: string[] = [];
        if (successCount > 0) parts.push(localize('dragDrop.successCount', successCount));
        if (skipCount > 0) parts.push(localize('dragDrop.skipCount', skipCount));
        if (failCount > 0) parts.push(localize('dragDrop.failCount', failCount));

        const message = localize('dragDrop.partialSuccess', parts.join('，'));
        if (failCount > 0) {
          vscode.window.showWarningMessage(message);
        } else {
          vscode.window.showInformationMessage(message);
        }

        if (errors.length > 0) {
          this.log('Upload errors:', errors);
          // 显示详细错误信息
          this.outputChannel.show(true);
        }

        // 如果有成功上传的文件，刷新树视图
        if (successCount > 0) {
          this.provider.refresh();
        }
      } else if (skipCount > 0 && failCount === 0) {
        vscode.window.showInformationMessage(
          localize('dragDrop.allSkipped', skipCount)
        );
      } else if (failCount > 0) {
        const errorMessage = localize('dragDrop.allFailed', failCount);
        vscode.window.showErrorMessage(errorMessage);
        this.log('Upload failed:', errors);
        // 显示详细错误信息
        this.outputChannel.show(true);
      } else {
        // 所有文件都被跳过或没有文件处理
        this.log('No files were processed');
        vscode.window.showInformationMessage(localize('dragDrop.noFilesProcessed'));
      }
    } catch (error: any) {
      const errorMsg = localize('dragDrop.error', error.message || error);
      this.log('Unexpected error:', errorMsg, error);
      vscode.window.showErrorMessage(errorMsg);
      this.outputChannel.show(true);
    }
  }

  /**
   * 清理资源
   */
  dispose(): void {
    this.outputChannel.dispose();
  }
}

