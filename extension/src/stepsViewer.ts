/**
 * Steps YAML 预览器 - 以时间线方式显示 steps.yaml
 *
 * 关联文件：
 * - @extension/src/extension.ts - 注册命令
 * - @extension/src/projectStructureProvider.ts - steps.yaml 节点
 */

import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';

interface RunStep {
  type: 'run';
  num_steps?: number;
  tick?: number;
}

interface AskStep {
  type: 'ask';
  question?: string;
}

interface InterveneStep {
  type: 'intervene';
  target?: string;
  action?: string;
  params?: Record<string, any>;
}

type Step = RunStep | AskStep | InterveneStep;

interface StepsConfig {
  start_t?: string;
  steps?: Step[];
}

export class StepsViewer {
  private static currentPanel: vscode.WebviewPanel | undefined;

  public static async show(context: vscode.ExtensionContext, filePath: string): Promise<void> {
    // 读取 YAML 文件
    let data: StepsConfig;
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      data = yaml.load(content) as StepsConfig;
    } catch (error: any) {
      vscode.window.showErrorMessage(`无法读取 steps.yaml: ${error.message}`);
      return;
    }

    // 如果已有面板，复用它
    if (this.currentPanel) {
      this.currentPanel.reveal(vscode.ViewColumn.One);
      this.updateWebview(this.currentPanel, data, filePath);
      return;
    }

    // 创建新的 webview 面板
    const panel = vscode.window.createWebviewPanel(
      'stepsViewer',
      '实验步骤预览',
      vscode.ViewColumn.One,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
      }
    );

    this.currentPanel = panel;

    // 处理面板关闭
    panel.onDidDispose(() => {
      this.currentPanel = undefined;
    });

    // 更新内容
    this.updateWebview(panel, data, filePath);
  }

  private static updateWebview(
    panel: vscode.WebviewPanel,
    data: StepsConfig,
    filePath: string
  ): void {
    const steps = data.steps || [];
    const isChinese = vscode.env.language.startsWith('zh');

    // 统计各类型步骤数量
    const runCount = steps.filter(s => s.type === 'run').length;
    const askCount = steps.filter(s => s.type === 'ask').length;
    const interveneCount = steps.filter(s => s.type === 'intervene').length;

    panel.webview.html = `
<!DOCTYPE html>
<html lang="${isChinese ? 'zh-CN' : 'en'}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${isChinese ? '实验步骤预览' : 'Steps Preview'}</title>
  <style>
    body {
      font-family: var(--vscode-font-family);
      background-color: var(--vscode-editor-background);
      color: var(--vscode-editor-foreground);
      padding: 24px;
      max-width: 1000px;
      margin: 0 auto;
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--vscode-panel-border);
    }

    .header h1 {
      margin: 0;
      font-size: 24px;
    }

    .stats {
      display: flex;
      gap: 16px;
    }

    .stat-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 4px 12px;
      border-radius: 16px;
      font-size: 13px;
    }

    .stat-badge.run {
      background-color: rgba(82, 196, 26, 0.15);
      color: #52c41a;
    }

    .stat-badge.ask {
      background-color: rgba(24, 144, 255, 0.15);
      color: #1890ff;
    }

    .stat-badge.intervene {
      background-color: rgba(250, 173, 20, 0.15);
      color: #faad14;
    }

    .start-time {
      background-color: var(--vscode-input-background);
      padding: 12px 16px;
      border-radius: 8px;
      margin-bottom: 24px;
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .start-time-label {
      color: var(--vscode-descriptionForeground);
      font-size: 13px;
    }

    .start-time-value {
      font-weight: 600;
      font-size: 15px;
    }

    .timeline {
      position: relative;
      padding-left: 32px;
    }

    .timeline::before {
      content: '';
      position: absolute;
      left: 12px;
      top: 0;
      bottom: 0;
      width: 2px;
      background-color: var(--vscode-panel-border);
    }

    .step {
      position: relative;
      margin-bottom: 20px;
      padding: 16px;
      background-color: var(--vscode-editor-background);
      border: 1px solid var(--vscode-panel-border);
      border-radius: 8px;
      transition: box-shadow 0.2s;
    }

    .step:hover {
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }

    .step::before {
      content: '';
      position: absolute;
      left: -26px;
      top: 20px;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      border: 2px solid var(--vscode-panel-border);
      background-color: var(--vscode-editor-background);
    }

    .step.run::before {
      background-color: #52c41a;
      border-color: #52c41a;
    }

    .step.ask::before {
      background-color: #1890ff;
      border-color: #1890ff;
    }

    .step.intervene::before {
      background-color: #faad14;
      border-color: #faad14;
    }

    .step-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }

    .step-type {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .step-icon {
      font-size: 18px;
    }

    .step-label {
      font-weight: 600;
      font-size: 14px;
      text-transform: uppercase;
    }

    .step-label.run { color: #52c41a; }
    .step-label.ask { color: #1890ff; }
    .step-label.intervene { color: #faad14; }

    .step-number {
      background-color: var(--vscode-badge-background);
      color: var(--vscode-badge-foreground);
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 12px;
    }

    .step-content {
      font-size: 13px;
      line-height: 1.6;
    }

    .step-params {
      margin-top: 12px;
      padding: 12px;
      background-color: var(--vscode-input-background);
      border-radius: 6px;
      font-family: var(--vscode-editor-font-family);
      font-size: 12px;
    }

    .param-row {
      display: flex;
      gap: 8px;
      margin-bottom: 4px;
    }

    .param-row:last-child {
      margin-bottom: 0;
    }

    .param-key {
      color: var(--vscode-textPreformat-foreground);
      min-width: 80px;
    }

    .param-value {
      color: var(--vscode-editor-foreground);
    }

    .question-box {
      margin-top: 12px;
      padding: 12px 16px;
      background-color: rgba(24, 144, 255, 0.08);
      border-left: 3px solid #1890ff;
      border-radius: 0 6px 6px 0;
      font-size: 13px;
      line-height: 1.6;
    }

    .empty-state {
      text-align: center;
      padding: 48px;
      color: var(--vscode-descriptionForeground);
    }
    .copy-btn {
      padding: 6px 12px;
      background-color: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
    }
    .copy-btn:hover {
      background-color: var(--vscode-button-hoverBackground);
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>📋 ${isChinese ? '实验步骤预览' : 'Steps Preview'}</h1>
    <div style="display: flex; align-items: center; gap: 16px;">
      <button class="copy-btn" id="copyBtn">📋 ${isChinese ? '复制配置' : 'Copy Config'}</button>
      <div class="stats">
      <span class="stat-badge run">▶ Run × ${runCount}</span>
      <span class="stat-badge ask">❓ Ask × ${askCount}</span>
      <span class="stat-badge intervene">✋ Intervene × ${interveneCount}</span>
      </div>
    </div>
  </div>

  ${data.start_t ? `
    <div class="start-time">
      <span class="start-time-label">${isChinese ? '📅 开始时间' : '📅 Start Time'}:</span>
      <span class="start-time-value">${data.start_t}</span>
    </div>
  ` : ''}

  <div class="timeline" id="timeline"></div>

  <script>
    const steps = ${JSON.stringify(steps)};
    const isChinese = ${isChinese ? 'true' : 'false'};

    function renderSteps() {
      const container = document.getElementById('timeline');

      if (steps.length === 0) {
        container.innerHTML = '<div class="empty-state">' + (isChinese ? '暂无步骤配置' : 'No steps configured') + '</div>';
        return;
      }

      const icons = {
        run: '▶️',
        ask: '❓',
        intervene: '✋'
      };

      const labels = {
        run: isChinese ? '运行模拟' : 'Run Simulation',
        ask: isChinese ? '提问观察' : 'Ask Question',
        intervene: isChinese ? '干预操作' : 'Intervene'
      };

      steps.forEach((step, index) => {
        const div = document.createElement('div');
        div.className = 'step ' + step.type;

        let content = '';

        if (step.type === 'run') {
          content = \`
            <div class="step-params">
              <div class="param-row">
                <span class="param-key">num_steps:</span>
                <span class="param-value">\${step.num_steps || 1}</span>
              </div>
              <div class="param-row">
                <span class="param-key">tick:</span>
                <span class="param-value">\${step.tick || 60}s</span>
              </div>
            </div>
          \`;
        } else if (step.type === 'ask') {
          content = \`
            <div class="question-box">\${step.question || (isChinese ? '(无问题)' : '(No question)')}</div>
          \`;
        } else if (step.type === 'intervene') {
          const params = Object.entries(step.params || {}).map(([k, v]) => \`<div class="param-row"><span class="param-key">\${k}:</span><span class="param-value">\${JSON.stringify(v)}</span></div>\`).join('');
          content = \`
            <div class="step-params">
              <div class="param-row">
                <span class="param-key">target:</span>
                <span class="param-value">\${step.target || '-'}</span>
              </div>
              <div class="param-row">
                <span class="param-key">action:</span>
                <span class="param-value">\${step.action || '-'}</span>
              </div>
              \${params}
            </div>
          \`;
        }

        div.innerHTML = \`
          <div class="step-header">
            <div class="step-type">
              <span class="step-icon">\${icons[step.type]}</span>
              <span class="step-label \${step.type}">\${labels[step.type]}</span>
            </div>
            <span class="step-number">#\${index + 1}</span>
          </div>
          <div class="step-content">
            \${content}
          </div>
        \`;

        container.appendChild(div);
      });
    }

    // 复制步骤配置
    document.getElementById('copyBtn').addEventListener('click', function() {
      const yamlLines = ['start_t: ' + (data.start_t || ''), 'steps:'];
      steps.forEach(function(s) {
        if (s.type === 'run') {
          yamlLines.push('  - type: run');
          yamlLines.push('    num_steps: ' + (s.num_steps || 1));
          yamlLines.push('    tick: ' + (s.tick || 60));
        } else if (s.type === 'ask') {
          yamlLines.push('  - type: ask');
          yamlLines.push('    question: "' + (s.question || '') + '"');
        } else if (s.type === 'intervene') {
          yamlLines.push('  - type: intervene');
          yamlLines.push('    target: ' + (s.target || ''));
          yamlLines.push('    action: ' + (s.action || ''));
        }
      });
      const yamlContent = yamlLines.join('\\n');
      navigator.clipboard.writeText(yamlContent).then(function() {
        const btn = document.getElementById('copyBtn');
        const originalText = btn.textContent;
        btn.textContent = '✓ ' + (isChinese ? '已复制' : 'Copied');
        setTimeout(function() { btn.textContent = originalText; }, 2000);
      }).catch(function() {
        alert(isChinese ? '复制失败' : 'Copy failed');
      });
    });

    renderSteps();
  </script>
</body>
</html>`;
  }
}
