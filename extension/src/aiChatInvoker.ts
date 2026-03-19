/**
 * AI Chat Invoker - Simple invocation for Claude Code and Cursor
 */

import * as vscode from 'vscode';

export type AIChatType = 'claude-code' | 'cursor' | 'none';

export class AIChatInvoker {
  private outputChannel: vscode.OutputChannel;

  constructor() {
    this.outputChannel = vscode.window.createOutputChannel('AI Chat Invoker');
  }

  private log(message: string): void {
    this.outputChannel.appendLine(`${new Date().toISOString()} ${message}`);
  }

  /**
   * Get the preferred AI Chat type
   * Priority: Claude Code > Cursor
   */
  getPreferredChat(): AIChatType {
    // Check Claude Code extension by exact ID
    if (vscode.extensions.getExtension('anthropic.claude-code')) {
      return 'claude-code';
    }
    return 'cursor'; // Cursor is always available when this extension runs in it
  }

  /**
   * Invoke AI Chat - directly opens the chat window
   */
  async invokeChat(): Promise<boolean> {
    const chatType = this.getPreferredChat();
    const command = chatType === 'claude-code'
      ? 'claude-vscode.editor.open'
      : 'cursor.chat';

    this.log(`Invoking ${chatType}...`);
    const success = await vscode.commands.executeCommand(command).then(
      () => true,
      (err) => {
        this.log(`Failed: ${err}`);
        return false;
      }
    );

    if (!success) {
      vscode.window.showInformationMessage('Install Claude Code: https://claude.ai/code');
    }
    return success;
  }

  dispose(): void {
    this.outputChannel.dispose();
  }
}
