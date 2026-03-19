/**
 * ReplayWebviewProvider - Simulation Replay Webview Provider
 *
 * Provides a webview for replaying and visualizing simulation data.
 *
 * 关联文件：
 * - @extension/src/extension.ts - 主入口，注册命令 'aiSocialScientist.openReplay'
 * - @extension/src/webview/replay/ - 前端React组件 (编译后为replay.js)
 *
 * 后端API：
 * - @packages/agentsociety2/agentsociety2/backend/routers/replay.py - /api/v1/replay/*
 * - @packages/agentsociety2/agentsociety2/backend/routers/experiments.py - /api/v1/experiments/*
 */

import * as vscode from 'vscode';
import * as path from 'path';
import type { WebviewMessage, ExtensionMessage, InitData } from './webview/replay/types';

export class ReplayWebviewProvider {
  private readonly panel: vscode.WebviewPanel;
  private readonly extensionUri: vscode.Uri;
  private readonly backendUrl: string;
  private readonly workspacePath: string;
  private readonly hypothesisId: string;
  private readonly experimentId: string;
  private disposables: vscode.Disposable[] = [];

  /**
   * Create and show a new replay webview panel
   */
  public static create(
    context: vscode.ExtensionContext,
    workspacePath: string,
    hypothesisId: string,
    experimentId: string
  ): ReplayWebviewProvider {
    const panel = vscode.window.createWebviewPanel(
      'aiSocialScientistReplay',
      `Replay: ${experimentId}`,
      vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [context.extensionUri],
      }
    );

    return new ReplayWebviewProvider(
      panel,
      context,
      workspacePath,
      hypothesisId,
      experimentId
    );
  }

  private constructor(
    panel: vscode.WebviewPanel,
    context: vscode.ExtensionContext,
    workspacePath: string,
    hypothesisId: string,
    experimentId: string
  ) {
    this.panel = panel;
    this.extensionUri = context.extensionUri;
    this.workspacePath = workspacePath;
    this.hypothesisId = hypothesisId;
    this.experimentId = experimentId;

    // Get backend URL from configuration
    const config = vscode.workspace.getConfiguration('aiSocialScientist');
    this.backendUrl = config.get('backendUrl', 'http://localhost:8001');

    // Set webview content
    this.panel.webview.html = this.getHtmlForWebview();

    // Register event listeners
    this.panel.onDidDispose(() => this.dispose(), null, this.disposables);

    this.panel.webview.onDidReceiveMessage(
      (message: WebviewMessage) => this.handleMessage(message),
      null,
      this.disposables
    );
  }

  /**
   * Handle messages from webview
   */
  private async handleMessage(message: WebviewMessage): Promise<void> {
    switch (message.command) {
      case 'ready':
        this.sendInitData();
        break;

      case 'fetchExperimentInfo':
        await this.fetchExperimentInfo();
        break;

      case 'fetchTimeline':
        await this.fetchTimeline();
        break;

      case 'fetchAgentProfiles':
        await this.fetchAgentProfiles();
        break;

      case 'fetchAgentStatuses':
        await this.fetchAgentStatuses(message.step);
        break;

      case 'fetchAgentStatusHistory':
        await this.fetchAgentStatusHistory(message.agentId);
        break;

      case 'fetchAgentDialogs':
        await this.fetchAgentDialogs(message.agentId, message.dialogType);
        break;

      case 'fetchSocialProfile':
        await this.fetchSocialProfile(message.agentId);
        break;

      case 'fetchSocialPosts':
        await this.fetchSocialPosts(message.agentId);
        break;

      case 'fetchSocialDirectMessages':
        await this.fetchSocialDirectMessages(message.agentId, message.step);
        break;

      case 'fetchSocialGroupMessages':
        await this.fetchSocialGroupMessages(message.agentId, message.step);
        break;

      case 'fetchSocialNetwork':
        await this.fetchSocialNetwork();
        break;

      case 'fetchSocialActivity':
        await this.fetchSocialActivity(message.step);
        break;

      case 'fetchAllPosts':
        await this.fetchAllPosts(message.step);
        break;

      case 'fetchPostComments':
        await this.fetchPostComments(message.postId);
        break;

      case 'fetchTrajectory':
        await this.fetchTrajectory(message.agentId, message.startStep, message.endStep);
        break;

      case 'fetchDbTables':
        await this.fetchDbTables();
        break;

      case 'fetchDbTableContent':
        await this.fetchDbTableContent(message.tableName, message.page, message.pageSize);
        break;

      case 'error':
        vscode.window.showErrorMessage(`Replay error: ${message.message}`);
        break;
    }
  }

  /**
   * Send initialization data to webview
   */
  private sendInitData(): void {
    const initData: InitData = {
      workspacePath: this.workspacePath,
      hypothesisId: this.hypothesisId,
      experimentId: this.experimentId,
      backendUrl: this.backendUrl,
    };

    this.postMessage({ type: 'init', data: initData });
  }

  /**
   * Fetch experiment info from backend
   */
  private async fetchExperimentInfo(): Promise<void> {
    try {
      const url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/info?workspace_path=${encodeURIComponent(this.workspacePath)}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'experimentInfo', data });
    } catch (error) {
      this.handleFetchError('experiment info', error);
    }
  }

  /**
   * Fetch timeline from backend
   */
  private async fetchTimeline(): Promise<void> {
    try {
      const url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/timeline?workspace_path=${encodeURIComponent(this.workspacePath)}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'timeline', data });
    } catch (error) {
      this.handleFetchError('timeline', error);
    }
  }

  /**
   * Fetch agent profiles from backend
   */
  private async fetchAgentProfiles(): Promise<void> {
    try {
      const url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/agents/profiles?workspace_path=${encodeURIComponent(this.workspacePath)}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'agentProfiles', data });
    } catch (error) {
      this.handleFetchError('agent profiles', error);
    }
  }

  /**
   * Fetch agent statuses at a specific step
   */
  private async fetchAgentStatuses(step?: number): Promise<void> {
    try {
      let url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/agents/status?workspace_path=${encodeURIComponent(this.workspacePath)}`;
      if (step !== undefined) {
        url += `&step=${step}`;
      }

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'agentStatuses', data });
    } catch (error) {
      this.handleFetchError('agent statuses', error);
    }
  }

  /**
   * Fetch full status history for one agent (all steps)
   */
  private async fetchAgentStatusHistory(agentId: number): Promise<void> {
    try {
      const url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/agents/${agentId}/status?workspace_path=${encodeURIComponent(this.workspacePath)}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'agentStatusHistory', data });
    } catch (error) {
      this.handleFetchError('agent status history', error);
    }
  }

  /**
   * Fetch agent dialogs
   */
  private async fetchAgentDialogs(agentId: number, dialogType?: number): Promise<void> {
    try {
      let url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/agents/${agentId}/dialog?workspace_path=${encodeURIComponent(this.workspacePath)}`;
      if (dialogType !== undefined) {
        url += `&dialog_type=${dialogType}`;
      }

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'agentDialogs', data });
    } catch (error) {
      this.handleFetchError('agent dialogs', error);
    }
  }

  /**
   * Fetch social media profile
   */
  private async fetchSocialProfile(agentId: number): Promise<void> {
    try {
      const url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/social/users/${agentId}?workspace_path=${encodeURIComponent(this.workspacePath)}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'socialProfile', data });
    } catch (error) {
      this.handleFetchError('social profile', error);
    }
  }

  /**
   * Fetch social media posts
   */
  private async fetchSocialPosts(agentId: number): Promise<void> {
    try {
      const url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/social/users/${agentId}/posts?workspace_path=${encodeURIComponent(this.workspacePath)}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'socialPosts', data });
    } catch (error) {
      this.handleFetchError('social posts', error);
    }
  }

  /**
   * Fetch social media direct messages (optionally up to a given step for timeline)
   */
  private async fetchSocialDirectMessages(agentId: number, step?: number): Promise<void> {
    try {
      let url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/social/users/${agentId}/direct_messages?workspace_path=${encodeURIComponent(this.workspacePath)}`;
      if (step !== undefined && step !== null) {
        url += `&max_step=${step}`;
      }
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'socialDirectMessages', data });
    } catch (error) {
      this.handleFetchError('social direct messages', error);
    }
  }

  /**
   * Fetch social media group messages (optionally up to a given step for timeline)
   */
  private async fetchSocialGroupMessages(agentId: number, step?: number): Promise<void> {
    try {
      let url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/social/users/${agentId}/group_messages?workspace_path=${encodeURIComponent(this.workspacePath)}`;
      if (step !== undefined && step !== null) {
        url += `&max_step=${step}`;
      }
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'socialGroupMessages', data });
    } catch (error) {
      this.handleFetchError('social group messages', error);
    }
  }

  /**
   * Fetch per-step social activity (who received/sent DMs, sent group messages)
   */
  private async fetchSocialActivity(step: number): Promise<void> {
    try {
      const url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/social/activity?workspace_path=${encodeURIComponent(this.workspacePath)}&step=${step}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const raw = await response.json();
      const data = {
        step: raw.step,
        receivedDmAgentIds: raw.received_dm_agent_ids ?? [],
        sentDmAgentIds: raw.sent_dm_agent_ids ?? [],
        sentGroupMessageAgentIds: raw.sent_group_message_agent_ids ?? [],
      };
      this.postMessage({ type: 'socialActivity', data });
    } catch (error) {
      this.handleFetchError('social activity', error);
    }
  }

  /**
   * Fetch social network graph
   */
  private async fetchSocialNetwork(): Promise<void> {
    try {
      const url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/social/network?workspace_path=${encodeURIComponent(this.workspacePath)}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'socialNetwork', data });
    } catch (error) {
      this.handleFetchError('social network', error);
    }
  }

  /**
   * Fetch all posts (optionally up to step for timeline)
   */
  private async fetchAllPosts(step?: number): Promise<void> {
    try {
      let url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/social/posts?workspace_path=${encodeURIComponent(this.workspacePath)}`;
      if (step !== undefined && step !== null) {
        url += `&max_step=${step}`;
      }
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'allPosts', data });
    } catch (error) {
      this.handleFetchError('all posts', error);
    }
  }

  /**
   * Fetch comments for a post
   */
  private async fetchPostComments(postId: number): Promise<void> {
    try {
      const url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/social/posts/${postId}/comments?workspace_path=${encodeURIComponent(this.workspacePath)}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'postComments', data, postId });
    } catch (error) {
      this.handleFetchError('post comments', error);
    }
  }

  /**
   * Fetch database tables
   */
  private async fetchDbTables(): Promise<void> {
    try {
      const url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/tables?workspace_path=${encodeURIComponent(this.workspacePath)}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'dbTables', data });
    } catch (error) {
      this.handleFetchError('db tables', error);
    }
  }

  /**
   * Fetch database table content
   */
  private async fetchDbTableContent(tableName: string, page: number = 1, pageSize: number = 50): Promise<void> {
    try {
      const url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/tables/${tableName}?workspace_path=${encodeURIComponent(this.workspacePath)}&page=${page}&page_size=${pageSize}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'dbTableContent', data, tableName });
    } catch (error) {
      this.handleFetchError('db table content', error);
    }
  }

  /**
   * Fetch agent trajectory
   */
  private async fetchTrajectory(
    agentId: number,
    startStep?: number,
    endStep?: number
  ): Promise<void> {
    try {
      let url = `${this.backendUrl}/api/v1/replay/${this.hypothesisId}/${this.experimentId}/agents/${agentId}/trajectory?workspace_path=${encodeURIComponent(this.workspacePath)}`;
      if (startStep !== undefined) {
        url += `&start_step=${startStep}`;
      }
      if (endStep !== undefined) {
        url += `&end_step=${endStep}`;
      }

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.postMessage({ type: 'trajectory', data });
    } catch (error) {
      this.handleFetchError('trajectory', error);
    }
  }

  /**
   * Handle fetch errors
   */
  private handleFetchError(resource: string, error: unknown): void {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`Failed to fetch ${resource}:`, error);
    this.postMessage({ type: 'error', message: `Failed to fetch ${resource}: ${message}` });
  }

  /**
   * Post message to webview
   */
  private postMessage(message: ExtensionMessage): void {
    this.panel.webview.postMessage(message);
  }

  /**
   * Generate HTML for webview
   */
  private getHtmlForWebview(): string {
    const scriptUri = this.panel.webview.asWebviewUri(
      vscode.Uri.file(path.join(this.extensionUri.fsPath, 'out', 'webview', 'replay.js'))
    );

    // Generate icon URIs for agent avatars
    const iconNames = ['agent', 'boy1', 'boy2', 'boy3', 'girl1', 'girl2', 'girl3'];
    const iconUris: Record<string, string> = {};
    for (const name of iconNames) {
      iconUris[name] = this.panel.webview.asWebviewUri(
        vscode.Uri.file(path.join(this.extensionUri.fsPath, 'media', 'icons', `${name}.png`))
      ).toString();
    }
    const csp = [
      "default-src 'none'",
      `img-src ${this.panel.webview.cspSource} https://*.mapbox.com https://*.tiles.mapbox.com data: blob:`,
      `style-src ${this.panel.webview.cspSource} 'unsafe-inline' https://api.mapbox.com`,
      `script-src ${this.panel.webview.cspSource}`,
      `connect-src ${this.panel.webview.cspSource} https://*.mapbox.com https://*.tiles.mapbox.com ${this.backendUrl} data: blob:`,
      `worker-src ${this.panel.webview.cspSource} blob:`,
      `font-src ${this.panel.webview.cspSource} https://api.mapbox.com https://*.mapbox.com data:`,
    ].join('; ');

    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="${csp}">
    <title>Simulation Replay</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        html,
        body {
            height: 100%;
            width: 100%;
        }

        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            background-color: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
            height: 100vh;
            overflow: hidden;
        }

        #root {
            height: 100%;
            width: 100%;
            display: flex;
            flex-direction: column;
        }

        /* Loading state */
        .loading-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100vh;
            gap: 16px;
        }

        .loading-spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--vscode-editor-foreground);
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to {
                transform: rotate(360deg);
            }
        }

        /* Main layout */
        .replay-container {
            position: relative;
            height: 100%;
            width: 100%;
        }

        :root {
            --replay-header: 0px;
            --replay-top: 20px;
            --panel-width: clamp(260px, 21vw, 360px);
            --timeline-width: clamp(360px, 52vw, 860px);
        }

        .deck {
            position: absolute;
            top: var(--replay-header);
            left: 0;
            width: 100%;
            height: calc(100% - var(--replay-header));
            z-index: 0;
        }

        .deck > div,
        .deck canvas,
        .deck .mapboxgl-canvas,
        .deck .mapboxgl-map {
            width: 100% !important;
            height: 100% !important;
        }

        .agentsociety-left {
            position: absolute;
            top: calc(var(--replay-header) + var(--replay-top));
            left: 0;
            z-index: 1;
        }

        .agentsociety-right {
            position: absolute;
            top: calc(var(--replay-header) + var(--replay-top));
            right: 0;
            z-index: 1;
            overflow: hidden;
            width: var(--panel-width);
        }

        .left-inner {
            background: rgba(255, 255, 255, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0px 4px 4px rgba(0, 0, 0, 0.2);
            border-radius: 0 8px 8px 0;
            margin: 8px 0;
            padding: 12px 16px;
            width: var(--panel-width);
            height: calc(100vh - var(--replay-header) - 60px);
            overflow: auto;
            backdrop-filter: blur(40px);
            transition: transform 0.3s ease-in-out;
        }

        .left-inner.collapsed {
            transform: translateX(-100%);
        }

        .left-title {
            display: flex;
            align-items: center;
            gap: 6px;
            font-weight: 600;
            margin: 8px 0 12px;
        }

        .left-title-icon {
            font-size: 16px;
        }

        .left-section-title {
            font-weight: 600;
            margin: 12px 0 6px;
        }

        .left-info-block,
        .left-info-block-status {
            min-width: 47%;
            margin: 4px 0;
            padding: 8px;
            border-radius: 4px;
            align-items: center;
            background: rgba(22, 119, 255, 0.06);
            display: flex;
            justify-content: space-between;
        }

        .left-info-block-status {
            line-height: 1.4;
            display: block;
        }

        .left-info-block:hover,
        .left-info-block-status:hover {
            background: rgba(22, 119, 255, 0.12);
            cursor: pointer;
            transition: background 0.3s;
        }

        .left-info-history-card {
            border-radius: 8px;
            background-color: rgba(192, 192, 192, 0.1);
            margin: 8px 0;
            width: 100%;
        }

        .left-info-history-inner {
            padding: 8px;
        }

        .left-info-empty {
            padding: 12px 8px;
            color: #5a5a5a;
        }

        .left-label {
            color: #4a4a4a;
            margin-right: 4px;
        }

        .left-value {
            color: #1f1f1f;
        }

        .right-inner {
            background: rgba(255, 255, 255, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0px 4px 4px rgba(0, 0, 0, 0.2);
            border-radius: 8px 0 0 8px;
            margin: 8px 0;
            width: var(--panel-width);
            height: calc(100vh - var(--replay-header) - 60px);
            display: flex;
            flex-direction: column;
            backdrop-filter: blur(40px);
            transition: transform 0.3s ease-in-out;
        }

        .right-inner.collapsed {
            transform: translateX(100%);
        }

        .tabs {
            display: flex;
            gap: 6px;
            padding: 12px 8px 8px;
            flex-wrap: wrap;
        }

        .tab-item {
            border: none;
            padding: 6px 10px;
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.6);
            cursor: pointer;
            font-size: 12px;
        }

        .tab-item.active {
            background: rgba(22, 119, 255, 0.2);
            color: #1677FF;
            font-weight: 600;
        }

        .right-content {
            flex: 1;
            overflow: auto;
            padding: 0 12px 12px;
        }

        .right-section-title {
            font-weight: 600;
            margin: 12px 0 6px;
        }

        .right-card,
        .right-info-card {
            background: rgba(255, 255, 255, 0.7);
            border-radius: 8px;
            padding: 8px 10px;
            margin-bottom: 8px;
            line-height: 1.4;
        }

        .right-card-meta {
            font-size: 11px;
            color: #5a5a5a;
            margin-bottom: 4px;
        }

        .right-card-content {
            font-size: 13px;
        }

        .right-empty {
            color: #5a5a5a;
            padding: 8px 0;
        }

        .network-graph {
            width: 100%;
            margin-bottom: 8px;
        }

        .control-progress {
            position: absolute;
            background: rgba(255, 255, 255, 1);
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0px 4px 4px rgba(0, 0, 0, 0.2);
            border-radius: 28px;
            bottom: 32px;
            left: calc(50% - (var(--timeline-width) * 0.5));
            width: var(--timeline-width);
            height: 56px;
            z-index: 10;
            display: flex;
            align-items: center;
            padding: 0 12px;
            gap: 12px;
        }

        /* Dialog list */
        .dialog-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .dialog-item {
            padding: 8px 12px;
            border-radius: 6px;
            background: var(--vscode-editor-inactiveSelectionBackground);
        }

        .dialog-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 4px;
            font-size: 11px;
            color: var(--vscode-descriptionForeground);
        }

        .dialog-content {
            font-size: 13px;
            line-height: 1.4;
        }

        /* V2 only uses 反思 (thought/reflection) */
        .dialog-type-thought {
            border-left: 3px solid #9b59b6;
        }

        /* Timeline player */
        .timeline-player {
            display: flex;
            align-items: center;
            gap: 12px;
            width: 100%;
        }

        .status {
            border-radius: 16px;
            background: rgba(192, 192, 192, 0.2);
            height: 32px;
            padding: 0 12px;
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 12px;
            white-space: nowrap;
        }

        .player {
            border-radius: 16px;
            background: rgba(192, 192, 192, 0.2);
            height: 32px;
            padding: 0 12px;
            display: flex;
            align-items: center;
            gap: 8px;
            flex: 1;
        }

        .player-controls {
            display: flex;
            align-items: center;
            gap: 8px;
            flex: 1;
        }

        .timeline-btn {
            width: 28px;
            height: 28px;
            border: none;
            border-radius: 6px;
            background: rgba(255, 255, 255, 0.6);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
        }

        .timeline-btn:hover {
            background: rgba(22, 119, 255, 0.2);
        }

        .timeline-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .timeline-slider {
            flex: 1;
            height: 4px;
            -webkit-appearance: none;
            background: rgba(22, 119, 255, 0.3);
            border-radius: 2px;
            outline: none;
        }

        .timeline-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #1677FF;
            cursor: pointer;
        }

        .speed-selector {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 11px;
            white-space: nowrap;
        }

        .speed-selector select {
            background: rgba(255, 255, 255, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.6);
            border-radius: 16px;
            padding: 2px 8px;
            font-size: 11px;
        }

        .circle-wrap select {
            border-radius: 16px;
        }

        /* Map placeholder */
        .map-placeholder {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: var(--vscode-descriptionForeground);
            gap: 8px;
        }

        .map-placeholder-icon {
            font-size: 48px;
            opacity: 0.5;
        }

        /* Ant Design Tabs overrides - Two row aligned layout */
        .right-inner .ant-tabs {
            width: 100% !important;
        }

        .right-inner .ant-tabs-nav {
            margin: 0 !important;
            padding: 8px 8px 4px !important;
        }

        .right-inner .ant-tabs-nav-list {
            display: grid !important;
            grid-template-columns: repeat(3, 1fr) !important;
            gap: 6px !important;
            width: 100% !important;
            flex-wrap: wrap !important;
        }

        .right-inner .ant-tabs-nav-wrap {
            overflow: visible !important;
            flex: 1 !important;
        }

        .right-inner .ant-tabs-ink-bar {
            display: none !important;
        }

        .right-inner .ant-tabs-content {
            padding: 0 8px 8px;
            overflow: auto;
            height: calc(100vh - var(--replay-header) - 140px);
        }

        .right-inner .ant-tabs-tab {
            padding: 6px 4px !important;
            margin: 0 !important;
            border-radius: 14px !important;
            background: rgba(0, 0, 0, 0.04) !important;
            font-size: 12px !important;
            border: none !important;
            transition: all 0.2s;
            justify-content: center !important;
            text-align: center !important;
        }

        .right-inner .ant-tabs-tab:hover {
            background: rgba(22, 119, 255, 0.1) !important;
        }

        .right-inner .ant-tabs-tab-active {
            background: rgba(22, 119, 255, 0.15) !important;
        }

        .right-inner .ant-tabs-tab-active .ant-tabs-tab-btn {
            color: #1677FF !important;
        }

        /* Bubble list styles */
        .bubble-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
            padding: 8px;
            overflow: auto;
            height: calc(100vh - var(--replay-header) - 180px);
        }

        .bubble-item {
            display: flex;
            gap: 8px;
            align-items: flex-start;
        }

        .bubble-item.bubble-left {
            flex-direction: row;
        }

        .bubble-item.bubble-right {
            flex-direction: row-reverse;
        }

        .bubble-content {
            max-width: 80%;
            background: rgba(255, 255, 255, 0.9);
            border-radius: 8px;
            padding: 8px 12px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
        }

        .bubble-header {
            font-size: 11px;
            color: #888;
            margin-bottom: 4px;
        }

        .bubble-text {
            font-size: 13px;
            line-height: 1.4;
            color: #333;
            word-wrap: break-word;
        }
    </style>
</head>
<body>
    <div id="root"></div>
    <script>
        window.__AGENT_ICON_URIS__ = ${JSON.stringify(iconUris)};
    </script>
    <script src="${scriptUri}"></script>
</body>
</html>`;
  }

  /**
   * Dispose the webview panel and resources
   */
  public dispose(): void {
    this.disposables.forEach((d) => d.dispose());
    this.disposables = [];
  }
}
