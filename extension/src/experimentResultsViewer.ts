/**
 * 实验结果可视化预览器 - 动态探测字段，通用可视化
 */

import * as vscode from 'vscode';
import * as fs from 'fs';

interface ExperimentResults {
  [key: string]: any;
}

export class ExperimentResultsViewer {
  private static currentPanel: vscode.WebviewPanel | undefined;

  public static async show(context: vscode.ExtensionContext, filePath: string): Promise<void> {
    let data: ExperimentResults;
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      data = JSON.parse(content);
    } catch (error: any) {
      vscode.window.showErrorMessage(`无法读取实验结果: ${error.message}`);
      return;
    }

    if (this.currentPanel) {
      this.currentPanel.reveal(vscode.ViewColumn.One);
      this.updateWebview(this.currentPanel, data, filePath);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      'experimentResultsViewer',
      '实验结果可视化',
      vscode.ViewColumn.One,
      { enableScripts: true, retainContextWhenHidden: true }
    );

    this.currentPanel = panel;
    panel.onDidDispose(() => { this.currentPanel = undefined; });
    this.updateWebview(panel, data, filePath);
  }

  private static updateWebview(
    panel: vscode.WebviewPanel,
    data: ExperimentResults,
    filePath: string
  ): void {
    const isChinese = vscode.env.language.startsWith('zh');

    panel.webview.html = this.getHtml(data, isChinese);
  }

  private static getHtml(data: ExperimentResults, isChinese: boolean): string {
    // 提取摘要字段
    const summaryFields: Array<{ key: string; value: any }> = [];
    Object.entries(data).forEach(([key, value]) => {
      const type = typeof value;
      if (type === 'number' || type === 'string' || type === 'boolean') {
        summaryFields.push({ key, value });
      }
    });

    // 查找数组类型的数据（轮次数据）
    const arrayFields: Array<{ key: string; data: any[] }> = [];
    Object.entries(data).forEach(([key, value]) => {
      if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object') {
        arrayFields.push({ key, data: value });
      }
    });

    return `<!DOCTYPE html>
<html lang="${isChinese ? 'zh-CN' : 'en'}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${isChinese ? '实验结果可视化' : 'Experiment Results'}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body {
      font-family: var(--vscode-font-family);
      background-color: var(--vscode-editor-background);
      color: var(--vscode-editor-foreground);
      padding: 24px;
      max-width: 1200px;
      margin: 0 auto;
    }
    .header { margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--vscode-panel-border); }
    .header h1 { margin: 0; font-size: 24px; }
    .summary-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }
    .summary-card { background-color: var(--vscode-editor-background); border: 1px solid var(--vscode-panel-border); border-radius: 8px; padding: 12px; }
    .summary-card h3 { margin: 0 0 6px 0; font-size: 11px; color: var(--vscode-descriptionForeground); text-transform: uppercase; }
    .summary-card .value { font-size: 18px; font-weight: 600; }
    .section { background-color: var(--vscode-editor-background); border: 1px solid var(--vscode-panel-border); border-radius: 8px; padding: 16px; margin-bottom: 20px; }
    .section h2 { margin: 0 0 12px 0; font-size: 15px; }
    .chart-container { height: 280px; margin-bottom: 12px; }
    .chart-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    @media (max-width: 800px) { .chart-grid { grid-template-columns: 1fr; } }
    .data-table { width: 100%; border-collapse: collapse; font-size: 11px; }
    .data-table th, .data-table td { padding: 6px 8px; text-align: left; border-bottom: 1px solid var(--vscode-panel-border); }
    .data-table th { background-color: var(--vscode-input-background); font-weight: 600; position: sticky; top: 0; }
    .data-table tr:hover { background-color: var(--vscode-list-hoverBackground); }
    .table-scroll { max-height: 350px; overflow: auto; }
    .tab-container { display: flex; gap: 6px; margin-bottom: 12px; border-bottom: 1px solid var(--vscode-panel-border); padding-bottom: 6px; flex-wrap: wrap; }
    .tab-btn { padding: 5px 12px; border: none; background: transparent; color: var(--vscode-descriptionForeground); cursor: pointer; font-size: 11px; border-radius: 4px; }
    .tab-btn:hover { background-color: var(--vscode-list-hoverBackground); }
    .tab-btn.active { background-color: var(--vscode-button-background); color: var(--vscode-button-foreground); }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .json-viewer { background-color: var(--vscode-input-background); border-radius: 6px; padding: 12px; font-family: var(--vscode-editor-font-family); font-size: 11px; max-height: 400px; overflow: auto; white-space: pre-wrap; word-break: break-all; }
  </style>
</head>
<body>
  <div class="header"><h1>📊 ${isChinese ? '实验结果可视化' : 'Experiment Results'}</h1></div>
  <div class="summary-cards" id="summaryCards"></div>
  <div class="section">
    <h2>📈 ${isChinese ? '数据可视化' : 'Data Visualization'}</h2>
    <div class="tab-container" id="tabContainer"></div>
    <div id="tabContents"></div>
  </div>
  <div class="section">
    <h2>📋 ${isChinese ? '原始数据' : 'Raw Data'}</h2>
    <div class="json-viewer" id="jsonViewer"></div>
  </div>

  <script>
    const data = ${JSON.stringify(data)};
    const summaryFields = ${JSON.stringify(summaryFields)};
    const arrayFields = ${JSON.stringify(arrayFields.map(f => ({ key: f.key, data: f.data })))};
    const isChinese = ${isChinese ? 'true' : 'false'};
    const colors = ['#1890ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb', '#a0d911'];

    // 渲染摘要
    function renderSummary() {
      const container = document.getElementById('summaryCards');
      container.innerHTML = summaryFields.slice(0, 8).map(f =>
        '<div class="summary-card"><h3>' + f.key + '</h3><div class="value">' + formatVal(f.value) + '</div></div>'
      ).join('');
    }

    function formatVal(v) {
      if (v === null || v === undefined) return '-';
      if (typeof v === 'object') return Array.isArray(v) ? '[' + v.length + ']' : '{...}';
      return String(v);
    }

    // 渲染标签页
    function renderTabs() {
      const tabContainer = document.getElementById('tabContainer');
      const contents = document.getElementById('tabContents');
      let tabHtml = '';
      let contentHtml = '';

      if (arrayFields.length > 0) {
        arrayFields.forEach((field, idx) => {
          const isActive = idx === 0;
          const tabId = 'tab_' + field.key;
          tabHtml += '<button class="tab-btn ' + (isActive ? 'active' : '') + '" onclick="showTab(\\'' + tabId + '\\')">' + field.key + '</button>';
          contentHtml += '<div id="' + tabId + '" class="tab-content ' + (isActive ? 'active' : '') + '">';
          contentHtml += generateTable(field.data);
          contentHtml += '<div class="chart-grid" id="charts_' + field.key + '"></div>';
          contentHtml += '</div>';
        });
      } else {
        tabHtml = '<button class="tab-btn active" onclick="showTab(\\'tab_overview\\')">Overview</button>';
        contentHtml = '<div id="tab_overview" class="tab-content active"><p>No array data to visualize</p></div>';
      }

      tabContainer.innerHTML = tabHtml;
      contents.innerHTML = contentHtml;

      // 渲染图表
      arrayFields.forEach(field => renderCharts(field.key, field.data));
    }

    function generateTable(arr) {
      if (!arr || arr.length === 0) return '<p>Empty</p>';
      const firstItem = arr[0];
      const columns = Object.keys(firstItem);

      // 检查嵌套对象
      const flatCols = [];
      const nestedCols = {};
      columns.forEach(col => {
        const val = firstItem[col];
        if (val && typeof val === 'object' && !Array.isArray(val)) {
          nestedCols[col] = Object.keys(val);
        } else {
          flatCols.push(col);
        }
      });

      let html = '<div class="table-scroll"><table class="data-table"><thead><tr><th>#</th>';
      flatCols.forEach(c => { html += '<th>' + c + '</th>'; });
      Object.keys(nestedCols).forEach(parent => {
        nestedCols[parent].forEach(sub => { html += '<th>' + parent + '.' + sub + '</th>'; });
      });
      html += '</tr></thead><tbody>';

      arr.forEach((item, i) => {
        html += '<tr><td>' + (i + 1) + '</td>';
        flatCols.forEach(c => { html += '<td>' + formatVal(item[c]) + '</td>'; });
        Object.keys(nestedCols).forEach(parent => {
          nestedCols[parent].forEach(sub => { html += '<td>' + formatVal(item[parent] && item[parent][sub]) + '</td>'; });
        });
        html += '</tr>';
      });

      html += '</tbody></table></div>';
      return html;
    }

    function renderCharts(key, arr) {
      const container = document.getElementById('charts_' + key);
      if (!container || !arr || arr.length === 0) return;

      const firstItem = arr[0];
      Object.keys(firstItem).forEach(col => {
        const val = firstItem[col];
        if (val && typeof val === 'object' && !Array.isArray(val)) {
          // 字典类型的数值（如 trustor_investments）
          createMultiLineChart(container, arr, col, val);
        } else if (typeof val === 'number') {
          // 单个数值
          createSingleLineChart(container, arr, col);
        }
      });
    }

    function createMultiLineChart(container, arr, col, firstVal) {
      const subKeys = Object.keys(firstVal);
      const labels = arr.map((item, i) => item.round || i + 1);

      const datasets = subKeys.map((k, i) => ({
        label: k,
        data: arr.map(item => (item[col] && item[col][k]) || 0),
        borderColor: colors[i % colors.length],
        backgroundColor: colors[i % colors.length] + '22',
        fill: false,
        tension: 0.3
      }));

      const wrapper = document.createElement('div');
      wrapper.style.height = '260px';
      wrapper.style.marginBottom = '12px';
      const canvas = document.createElement('canvas');
      wrapper.appendChild(canvas);
      container.appendChild(wrapper);

      new Chart(canvas, {
        type: 'line',
        data: { labels: labels, datasets: datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'top' }, title: { display: true, text: col } },
          scales: { y: { beginAtZero: true } }
        }
      });
    }

    function createSingleLineChart(container, arr, col) {
      const labels = arr.map((item, i) => item.round || i + 1);
      const values = arr.map(item => item[col] || 0);

      const wrapper = document.createElement('div');
      wrapper.style.height = '200px';
      wrapper.style.marginBottom = '12px';
      const canvas = document.createElement('canvas');
      wrapper.appendChild(canvas);
      container.appendChild(wrapper);

      new Chart(canvas, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [{ label: col, data: values, borderColor: '#1890ff', backgroundColor: '#1890ff22', fill: true, tension: 0.3 }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { title: { display: true, text: col } },
          scales: { y: { beginAtZero: true } }
        }
      });
    }

    function showTab(tabId) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      document.querySelector('[onclick*="' + tabId + '"]').classList.add('active');
      document.getElementById(tabId).classList.add('active');
    }

    // 渲染 JSON
    document.getElementById('jsonViewer').textContent = JSON.stringify(data, null, 2);

    // 初始化
    renderSummary();
    renderTabs();
  </script>
</body>
</html>`;
  }
}
