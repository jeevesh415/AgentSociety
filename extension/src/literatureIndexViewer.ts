/**
 * 文献索引预览器 - 以友好方式显示 literature_index.json
 *
 * 关联文件：
 * - @extension/src/extension.ts - 注册命令
 * - @extension/src/projectStructureProvider.ts - 文献索引节点
 */

import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

interface LiteratureEntry {
  title?: string;
  file_path?: string;
  authors?: string[];
  year?: number;
  abstract?: string;
  keywords?: string[];
  doi?: string;
  url?: string;
  [key: string]: any;
}

interface LiteratureIndex {
  version?: string;
  created_at?: string;
  updated_at?: string;
  entries?: LiteratureEntry[];
}

export class LiteratureIndexViewer {
  private static currentPanel: vscode.WebviewPanel | undefined;

  public static async show(context: vscode.ExtensionContext, filePath: string): Promise<void> {
    // 读取 JSON 文件
    let data: LiteratureIndex;
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      data = JSON.parse(content);
    } catch (error: any) {
      vscode.window.showErrorMessage(`无法读取文献索引: ${error.message}`);
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
      'literatureIndexViewer',
      '文献索引预览',
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
    data: LiteratureIndex,
    filePath: string
  ): void {
    const entries = data.entries || [];
    const total = entries.length;
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];

    // 获取当前语言
    const isChinese = vscode.env.language.startsWith('zh');

    panel.webview.html = `
<!DOCTYPE html>
<html lang="${isChinese ? 'zh-CN' : 'en'}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${isChinese ? '文献索引预览' : 'Literature Index Viewer'}</title>
  <style>
    body {
      font-family: var(--vscode-font-family);
      background-color: var(--vscode-editor-background);
      color: var(--vscode-editor-foreground);
      padding: 20px;
      max-width: 1200px;
      margin: 0 auto;
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      padding-bottom: 15px;
      border-bottom: 1px solid var(--vscode-panel-border);
    }

    .header h1 {
      margin: 0;
      font-size: 24px;
    }

    .stats {
      color: var(--vscode-descriptionForeground);
      font-size: 14px;
    }

    .search-box {
      margin-bottom: 20px;
    }

    .search-box input {
      width: 100%;
      padding: 10px 15px;
      font-size: 14px;
      border: 1px solid var(--vscode-input-border);
      background-color: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border-radius: 4px;
      outline: none;
    }

    .search-box input:focus {
      border-color: var(--vscode-focusBorder);
    }

    .entry {
      background-color: var(--vscode-editor-background);
      border: 1px solid var(--vscode-panel-border);
      border-radius: 8px;
      padding: 15px;
      margin-bottom: 15px;
      transition: box-shadow 0.2s;
    }

    .entry:hover {
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }

    .entry-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 10px;
    }

    .entry-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--vscode-textLink-foreground);
      cursor: pointer;
      flex: 1;
    }

    .entry-title:hover {
      text-decoration: underline;
    }

    .entry-year {
      background-color: var(--vscode-badge-background);
      color: var(--vscode-badge-foreground);
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 12px;
      margin-left: 10px;
    }

    .entry-authors {
      color: var(--vscode-descriptionForeground);
      font-size: 13px;
      margin-bottom: 8px;
    }

    .entry-abstract {
      font-size: 13px;
      line-height: 1.5;
      color: var(--vscode-editor-foreground);
      margin-bottom: 10px;
    }

    .entry-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      font-size: 12px;
    }

    .keyword {
      background-color: var(--vscode-input-background);
      color: var(--vscode-descriptionForeground);
      padding: 2px 8px;
      border-radius: 4px;
      border: 1px solid var(--vscode-input-border);
    }

    .file-path {
      color: var(--vscode-textLink-foreground);
      font-size: 12px;
      margin-top: 8px;
      font-family: var(--vscode-editor-font-family);
    }

    .empty-state {
      text-align: center;
      padding: 40px;
      color: var(--vscode-descriptionForeground);
    }

    .filter-group {
      display: flex;
      gap: 10px;
      margin-bottom: 15px;
    }

    .filter-btn {
      padding: 6px 12px;
      border: 1px solid var(--vscode-button-border);
      background-color: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
    }

    .filter-btn:hover {
      background-color: var(--vscode-button-secondaryHoverBackground);
    }

    .filter-btn.active {
      background-color: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
    }

    .sort-select {
      padding: 6px 12px;
      border: 1px solid var(--vscode-input-border);
      background-color: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border-radius: 4px;
      font-size: 12px;
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>${isChinese ? '📚 文献索引' : '📚 Literature Index'}</h1>
    <div class="stats">
      ${isChinese ? `共 ${total} 篇文献` : `${total} articles`}
      ${data.updated_at ? `<br>${isChinese ? '更新于' : 'Updated'}: ${new Date(data.updated_at).toLocaleString()}` : ''}
    </div>
  </div>

  <div class="search-box">
    <input type="text" id="searchInput" placeholder="${isChinese ? '搜索标题、作者或关键词...' : 'Search title, authors, or keywords...'}" />
  </div>

  <div class="filter-group">
    <select id="sortSelect" class="sort-select">
      <option value="default">${isChinese ? '默认排序' : 'Default Order'}</option>
      <option value="year-desc">${isChinese ? '年份 (新→旧)' : 'Year (New→Old)'}</option>
      <option value="year-asc">${isChinese ? '年份 (旧→新)' : 'Year (Old→New)'}</option>
      <option value="title">${isChinese ? '标题 A-Z' : 'Title A-Z'}</option>
    </select>
  </div>

  <div id="entries"></div>

  <script>
    const entries = ${JSON.stringify(entries)};
    const workspacePath = ${workspaceFolder ? `"${workspaceFolder.uri.fsPath}"` : 'null'};
    const isChinese = ${isChinese ? 'true' : 'false'};

    function renderEntries(filteredEntries) {
      const container = document.getElementById('entries');
      container.innerHTML = '';

      if (filteredEntries.length === 0) {
        container.innerHTML = '<div class="empty-state">' + (isChinese ? '没有找到匹配的文献' : 'No matching articles found') + '</div>';
        return;
      }

      filteredEntries.forEach((entry, index) => {
        const div = document.createElement('div');
        div.className = 'entry';
        div.dataset.index = index;

        const title = entry.title || (isChinese ? '未命名文献' : 'Untitled');
        const year = entry.year || '';
        const authors = entry.authors || [];
        const abstract = entry.abstract || '';
        const keywords = entry.keywords || [];
        const filePath = entry.file_path || '';

        div.innerHTML = \`
          <div class="entry-header">
            <div class="entry-title" onclick="openFile('\${filePath}')">\${title}</div>
            \${year ? \`<span class="entry-year">\${year}</span>\` : ''}
          </div>
          \${authors.length > 0 ? \`<div class="entry-authors">\${authors.join(', ')}</div>\` : ''}
          \${abstract ? \`<div class="entry-abstract">\${abstract.substring(0, 300)}\${abstract.length > 300 ? '...' : ''}</div>\` : ''}
          <div class="entry-meta">
            \${keywords.slice(0, 5).map(k => \`<span class="keyword">\${k}</span>\`).join('')}
          </div>
          \${filePath ? \`<div class="file-path">📄 \${filePath}</div>\` : ''}
        \`;

        container.appendChild(div);
      });
    }

    function openFile(filePath) {
      if (filePath && workspacePath) {
        const vscode = acquireVsCodeApi();
        vscode.postMessage({
          command: 'openFile',
          filePath: filePath
        });
      }
    }

    // 搜索功能
    document.getElementById('searchInput').addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase();
      const filtered = entries.filter(entry => {
        const title = (entry.title || '').toLowerCase();
        const authors = (entry.authors || []).join(' ').toLowerCase();
        const keywords = (entry.keywords || []).join(' ').toLowerCase();
        const abstract = (entry.abstract || '').toLowerCase();
        return title.includes(query) || authors.includes(query) || keywords.includes(query) || abstract.includes(query);
      });
      applySort(filtered);
    });

    // 排序功能
    function applySort(entriesToSort) {
      const sortValue = document.getElementById('sortSelect').value;
      let sorted = [...entriesToSort];

      if (sortValue === 'year-desc') {
        sorted.sort((a, b) => (b.year || 0) - (a.year || 0));
      } else if (sortValue === 'year-asc') {
        sorted.sort((a, b) => (a.year || 0) - (b.year || 0));
      } else if (sortValue === 'title') {
        sorted.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
      }

      renderEntries(sorted);
    }

    document.getElementById('sortSelect').addEventListener('change', () => {
      const query = document.getElementById('searchInput').value.toLowerCase();
      const filtered = entries.filter(entry => {
        const title = (entry.title || '').toLowerCase();
        const authors = (entry.authors || []).join(' ').toLowerCase();
        const keywords = (entry.keywords || []).join(' ').toLowerCase();
        return title.includes(query) || authors.includes(query) || keywords.includes(query);
      });
      applySort(filtered);
    });

    // 初始渲染
    renderEntries(entries);
  </script>
</body>
</html>`;
  }
}
