/**
 * HistoryService - 历史记录管理服务
 *
 * 负责对话历史记录的文件读写、列表管理和格式化。
 */

import * as vscode from 'vscode';
import * as path from 'path';
import dayjs from 'dayjs';
import type { SSEEvent, HistoryItem } from '../shared/messages';
import type { ChatMessage } from './backendService';

export interface SSEEventWithTimestamp {
  event: SSEEvent;
  timestamp: number;
}

export interface HistoryData {
  startTime: string;
  lastUpdated?: string;
  messages: ChatMessage[];
  sseEvents: Array<{
    userMessageIndex: number;
    events: SSEEventWithTimestamp[];
  }>;
}

export interface HistoryFileInfo {
  fileName: string;
  startTime?: string;
  lastUserMessage?: string;
  modifiedTime: number;
  size: number;
}

const HISTORY_DIR_NAME = '.history';

export class HistoryService {
  private currentFilePath: string | null = null;

  /**
   * Get the history directory path
   */
  getHistoryDir(): string | null {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      return null;
    }
    return path.join(workspaceFolder.uri.fsPath, HISTORY_DIR_NAME);
  }

  /**
   * Get the current history file path
   */
  getCurrentFilePath(): string | null {
    return this.currentFilePath;
  }

  /**
   * Reset the current history file path
   */
  resetCurrentFile(): void {
    this.currentFilePath = null;
  }

  /**
   * Ensure the history directory exists
   */
  async ensureHistoryDir(): Promise<void> {
    const historyDir = this.getHistoryDir();
    if (!historyDir) {
      throw new Error('No workspace folder found');
    }

    try {
      const historyDirUri = vscode.Uri.file(historyDir);
      await vscode.workspace.fs.createDirectory(historyDirUri);
    } catch (error) {
      // Directory might already exist
      const stat = await vscode.workspace.fs.stat(vscode.Uri.file(historyDir));
      if (stat.type !== vscode.FileType.Directory) {
        throw new Error(`History directory exists but is not a directory: ${historyDir}`);
      }
    }
  }

  /**
   * Create a new history file
   */
  async createNewFile(): Promise<string> {
    await this.ensureHistoryDir();

    const historyDir = this.getHistoryDir();
    if (!historyDir) {
      throw new Error('No workspace folder found');
    }

    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');

    // Generate 6 random characters
    const randomChars = Math.random().toString(36).substring(2, 8).toUpperCase();

    const fileName = `chat_${year}${month}${day}_${hours}${minutes}${seconds}_${randomChars}.json`;
    this.currentFilePath = path.join(historyDir, fileName);

    const initialHistory: HistoryData = {
      startTime: now.toISOString(),
      messages: [],
      sseEvents: [],
    };

    const fileUri = vscode.Uri.file(this.currentFilePath);
    const content = JSON.stringify(initialHistory, null, 2);
    await vscode.workspace.fs.writeFile(fileUri, Buffer.from(content, 'utf8'));

    console.log(`[History] Created new history file: ${fileName}`);
    return this.currentFilePath;
  }

  /**
   * Save conversation history to current file
   */
  async save(
    messages: ChatMessage[],
    sseEventsMap: Map<number, SSEEventWithTimestamp[]>
  ): Promise<void> {
    if (this.currentFilePath === null) {
      return;
    }

    try {
      const historyDir = this.getHistoryDir();
      if (!historyDir) {
        console.warn('[History] Cannot save history: no workspace folder');
        return;
      }

      // Read existing file content to preserve metadata
      let historyData: HistoryData = {
        startTime: new Date().toISOString(),
        messages: [],
        sseEvents: [],
      };

      try {
        const fileUri = vscode.Uri.file(this.currentFilePath);
        const fileContent = await vscode.workspace.fs.readFile(fileUri);
        const existingData = JSON.parse(Buffer.from(fileContent).toString('utf8'));
        historyData = {
          ...existingData,
          messages,
          sseEvents: this.mapToArray(sseEventsMap),
          lastUpdated: new Date().toISOString(),
        };
      } catch {
        // File doesn't exist or read failed, use default structure
        historyData = {
          startTime: new Date().toISOString(),
          messages,
          sseEvents: this.mapToArray(sseEventsMap),
          lastUpdated: new Date().toISOString(),
        };
      }

      // Write to file
      const fileUri = vscode.Uri.file(this.currentFilePath);
      const content = JSON.stringify(historyData, null, 2);
      await vscode.workspace.fs.writeFile(fileUri, Buffer.from(content, 'utf8'));

      console.log(`[History] Saved history to: ${path.basename(this.currentFilePath)}`);
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`[History] Failed to save history: ${errorMessage}`);
    }
  }

  /**
   * Load history from a file
   */
  async load(fileName: string): Promise<HistoryData> {
    const historyDir = this.getHistoryDir();
    if (!historyDir) {
      throw new Error('No workspace folder found');
    }

    const filePath = path.join(historyDir, fileName);
    const fileUri = vscode.Uri.file(filePath);

    // Check if file exists
    try {
      await vscode.workspace.fs.stat(fileUri);
    } catch {
      throw new Error(`History file not found: ${fileName}`);
    }

    // Read file content
    const fileContent = await vscode.workspace.fs.readFile(fileUri);
    const historyData = JSON.parse(Buffer.from(fileContent).toString('utf8'));

    // Validate data structure
    if (!historyData.messages || !Array.isArray(historyData.messages)) {
      throw new Error('Invalid history file format');
    }

    // Update current file path
    this.currentFilePath = filePath;

    console.log(`[History] Loaded history: ${fileName} (${historyData.messages.length} messages)`);
    return historyData;
  }

  /**
   * List all history files
   */
  async list(): Promise<HistoryItem[]> {
    try {
      const historyDir = this.getHistoryDir();
      if (!historyDir) {
        return [];
      }

      // Ensure history directory exists
      try {
        await this.ensureHistoryDir();
      } catch {
        return [];
      }

      const historyDirUri = vscode.Uri.file(historyDir);

      // Read directory contents
      let files: [string, vscode.FileType][] = [];
      try {
        const entries = await vscode.workspace.fs.readDirectory(historyDirUri);
        files = entries.filter(
          ([name, type]) => type === vscode.FileType.File && name.endsWith('.json')
        );
      } catch {
        return [];
      }

      // Get detailed info for each file
      const histories = await Promise.all(
        files.map(async ([fileName]) => this.getFileInfo(historyDir, fileName))
      );

      // Sort by modified time (newest first)
      histories.sort((a, b) => b.modifiedTime - a.modifiedTime);

      // Convert to HistoryItem format
      return histories.map((h) => ({
        fileName: h.fileName,
        startTime: h.startTime,
        displayName: this.formatDisplayName(h.fileName, h.startTime, h.lastUserMessage),
      }));
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`[History] Failed to list histories: ${errorMessage}`);
      return [];
    }
  }

  /**
   * Get file info for a history file
   */
  private async getFileInfo(historyDir: string, fileName: string): Promise<HistoryFileInfo> {
    const filePath = path.join(historyDir, fileName);
    const fileUri = vscode.Uri.file(filePath);

    try {
      const stat = await vscode.workspace.fs.stat(fileUri);

      // Read file to get startTime and last user message
      let startTime: string | undefined;
      let lastUserMessage: string | undefined;
      try {
        const fileContent = await vscode.workspace.fs.readFile(fileUri);
        const historyData = JSON.parse(Buffer.from(fileContent).toString('utf8'));
        startTime = historyData.startTime;

        // Find last user message
        if (historyData.messages && Array.isArray(historyData.messages)) {
          for (let i = historyData.messages.length - 1; i >= 0; i--) {
            const msg = historyData.messages[i];
            if (msg.role === 'user' && msg.content) {
              lastUserMessage = msg.content;
              break;
            }
          }
        }
      } catch {
        // Ignore read errors
      }

      return {
        fileName,
        startTime: startTime || stat.mtime.toString(),
        lastUserMessage,
        modifiedTime: stat.mtime,
        size: stat.size,
      };
    } catch {
      return {
        fileName,
        startTime: undefined,
        lastUserMessage: undefined,
        modifiedTime: 0,
        size: 0,
      };
    }
  }

  /**
   * Format history display name
   */
  formatDisplayName(
    fileName: string,
    startTime?: string,
    lastUserMessage?: string
  ): string {
    // Prefer last user message as display name
    if (lastUserMessage && lastUserMessage.trim()) {
      const maxLength = 50;
      const truncated = lastUserMessage.trim();
      if (truncated.length > maxLength) {
        return truncated.substring(0, maxLength) + '...';
      }
      return truncated;
    }

    // Use timestamp if no user message
    if (startTime) {
      try {
        const date = dayjs(startTime);
        if (date.isValid()) {
          return date.format('YYYY-MM-DD HH:mm:ss');
        }
      } catch {
        // Fall through to file name parsing
      }
    }

    // Parse timestamp from file name (new format: chat_YYYYMMDD_HHMMSS_XXXXXX.json)
    const match = fileName.match(/chat_(\d{8})_(\d{6})_[A-Z0-9]{6}\.json/);
    if (match) {
      const dateStr = match[1];
      const timeStr = match[2];
      const date = dayjs(`${dateStr} ${timeStr}`, 'YYYYMMDD HHmmss');
      if (date.isValid()) {
        return date.format('YYYY-MM-DD HH:mm:ss');
      }
    }

    // Support old format (without random chars)
    const oldMatch = fileName.match(/chat_(\d{8})_(\d{6})\.json/);
    if (oldMatch) {
      const dateStr = oldMatch[1];
      const timeStr = oldMatch[2];
      const date = dayjs(`${dateStr} ${timeStr}`, 'YYYYMMDD HHmmss');
      if (date.isValid()) {
        return date.format('YYYY-MM-DD HH:mm:ss');
      }
    }

    return fileName;
  }

  /**
   * Convert SSE events Map to array format for storage
   */
  private mapToArray(
    sseEventsMap: Map<number, SSEEventWithTimestamp[]>
  ): HistoryData['sseEvents'] {
    return Array.from(sseEventsMap.entries()).map(([index, events]) => ({
      userMessageIndex: index,
      events,
    }));
  }

  /**
   * Convert SSE events array to Map format
   */
  arrayToMap(
    sseEvents: HistoryData['sseEvents']
  ): Map<number, SSEEventWithTimestamp[]> {
    const map = new Map<number, SSEEventWithTimestamp[]>();
    for (const item of sseEvents) {
      if (item.userMessageIndex !== undefined && item.events && Array.isArray(item.events)) {
        map.set(item.userMessageIndex, item.events);
      }
    }
    return map;
  }
}
