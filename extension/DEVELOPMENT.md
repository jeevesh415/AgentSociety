# AI Social Scientist Extension - Development Guide

## 目录

- [开发环境设置](#开发环境设置)
- [项目结构](#项目结构)
- [功能模块](#功能模块)
- [后端开发](#后端开发)
- [React Webview 开发](#react-webview-开发)
- [待实现功能](#待实现功能)
- [打包发布](#打包发布)
- [测试](#测试)
- [代码规范](#代码规范)

## 开发环境设置

### 前置要求

- Node.js (>= 16.x)
- npm 或 yarn
- Python 3.10+
- uv (Python包管理器)
- VSCode 或 Cursor (>= 1.80.0)

### 安装依赖

```bash
cd extension
npm install
```

### 编译项目

```bash
npm run compile          # 编译 TypeScript 扩展代码
npm run build-webview   # 构建 React webview
```

或者使用预发布命令（会自动执行两者）：
```bash
npm run vscode:prepublish
```

### 监听模式（开发时使用）

开发时需要同时运行两个 watch 模式：

**终端 1 - 编译扩展代码：**
```bash
npm run watch
```

**终端 2 - 构建 webview：**
```bash
npm run watch-webview
```

## 调试

1. 在 VSCode/Cursor 中打开 `extension` 文件夹
2. 按 `F5` 启动调试会话
3. 这将打开一个新的 Extension Development Host 窗口，插件已加载

## 项目结构

```
extension/
├── src/                          # 源代码目录
│   ├── extension.ts              # 主入口文件
│   ├── projectStructureProvider.ts  # 项目结构树视图提供者
│   ├── chatWebviewProvider.ts    # 聊天界面提供者
│   ├── simSettingsEditorProvider.ts  # SIM设置编辑器提供者
│   ├── prefillParamsViewProvider.ts  # Prefill参数视图提供者
│   ├── apiClient.ts              # API客户端
│   ├── paperWatcher.ts           # 论文文件监听器
│   ├── dragAndDropController.ts  # 拖放控制器
│   ├── i18n.ts                   # 国际化支持
│   └── webview/                  # React Webview 组件
│       ├── chat/                 # 聊天界面 React 组件
│       │   ├── index.tsx         # React 入口文件
│       │   ├── ChatApp.tsx       # 主应用组件（使用 Ant Design X）
│       │   ├── Header.tsx         # 头部组件
│       │   ├── types.ts          # TypeScript 类型定义
│       │   └── index.html        # HTML模板
│       ├── components/           # 共享组件
│       │   └── MarkdownRenderer.tsx
│       ├── prefillParams/        # Prefill参数界面
│       ├── simSettings/          # SIM设置界面
│       └── i18n/                 # 国际化资源
│           ├── index.ts
│           └── locales/
│               ├── en-US.json
│               └── zh-CN.json
├── out/                          # 编译输出目录（自动生成）
│   └── webview/                  # Webview 构建输出
│       └── chat.js               # 构建后的 React 应用
├── package.json                  # 插件配置文件
├── tsconfig.json                 # TypeScript配置
├── webpack.config.js            # Webpack 构建配置（用于 Webview）
└── README.md                     # 项目说明文档
```

## 功能模块

### 1. 项目结构视图 (Project Structure View)

- **文件**: `src/projectStructureProvider.ts`
- **功能**: 在左侧边栏显示研究项目的层次结构
  - 研究话题 (Topic)
  - 假设 (Hypotheses)
  - 实验 (Experiments)
  - 论文 (Papers)
- **特性**:
  - 支持拖放操作
  - 上下文菜单操作
  - 自动刷新

### 2. AI 聊天界面 (Chat Webview)

- **文件**: `src/chatWebviewProvider.ts` (Webview Provider)
- **React 组件**: `src/webview/chat/` (使用 React + Ant Design X V2)
- **功能**: 右侧边栏的 LLM Agent 对话交互入口
- **技术栈**:
  - React 18
  - Ant Design 6.x
  - Ant Design X V2 (AI 对话组件)
  - TypeScript
  - Webpack (构建工具)
- **特性**:
  - 美观的对话界面（使用 Ant Design X Chat 组件）
  - Markdown 消息渲染
  - 自动适配 VSCode 主题（亮色/暗色）
  - 工具调用和文件保存通知显示
  - 实时连接状态显示
  - 支持SSE流式响应

### 3. SIM 设置编辑器 (SIM Settings Editor)

- **文件**: `src/simSettingsEditorProvider.ts`
- **功能**: 自定义编辑器，用于编辑 `SIM_SETTINGS.json` 文件
- **特性**: 
  - 可视化选择 Agent Class
  - 可视化选择 Environment Module
  - JSON 配置编辑

### 4. API客户端 (API Client)

- **文件**: `src/apiClient.ts`
- **功能**: 处理与FastAPI后端的HTTP通信
- **特性**:
  - 支持SSE流式响应
  - 自动重连机制
  - 错误处理
  - 连接状态管理

## 后端开发

### 后端项目位置

后端代码位于 `packages/agentsociety2/agentsociety2/backend/`。

### 启动后端服务

```bash
cd packages/agentsociety2
uv run python -m agentsociety2.backend.run
```

### 后端环境变量配置

在 `packages/agentsociety2/.env` 文件中配置：

```env
# LLM配置（必需）
AGENTSOCIETY_LLM_API_KEY=your_api_key
AGENTSOCIETY_LLM_API_BASE=https://cloud.infini-ai.com/maas/v1
AGENTSOCIETY_LLM_MODEL=qwen2.5-14b-instruct

# 代码生成LLM配置（可选）
AGENTSOCIETY_CODER_LLM_API_KEY=your_coder_api_key
AGENTSOCIETY_CODER_LLM_API_BASE=https://cloud.infini-ai.com/maas/v1
AGENTSOCIETY_CODER_LLM_MODEL=qwen2.5-72b-instruct

# 高频操作LLM配置（可选）
AGENTSOCIETY_NANO_LLM_API_KEY=your_nano_api_key
AGENTSOCIETY_NANO_LLM_API_BASE=https://cloud.infini-ai.com/maas/v1
AGENTSOCIETY_NANO_LLM_MODEL=qwen2.5-7b-instruct

# Embedding模型配置（可选）
AGENTSOCIETY_EMBEDDING_API_KEY=your_embedding_api_key
AGENTSOCIETY_EMBEDDING_API_BASE=https://cloud.infini-ai.com/maas/v1
AGENTSOCIETY_EMBEDDING_MODEL=text-embedding-ada-002

# 后端服务配置
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8001
BACKEND_LOG_LEVEL=info

# 文献检索API（必需）
LITERATURE_SEARCH_API_URL=http://172.17.0.1:8002/api/v1/search
```

**重要提示**：
- `LITERATURE_SEARCH_API_URL` 必须指向文献检索服务的地址
- 默认值 `http://172.17.0.1:8002/api/v1/search` 适用于Docker环境
- 如果文献检索服务运行在本地，可以使用 `http://localhost:8002/api/v1/search`

### 后端API端点

- **GET `/health`** - 健康检查
- **GET `/docs`** - API文档（Swagger UI）
- **GET `/api/v1/agent-skills/list`** - 列出所有 Agent Skills
- **POST `/api/v1/agent-skills/enable`** - 启用 Skill
- **POST `/api/v1/agent-skills/disable`** - 禁用 Skill
- **POST `/api/v1/agent-skills/import`** - 导入 Skill
- **GET `/api/v1/modules/list`** - 列出可用模块
- **GET `/api/v1/prefill-params`** - 获取预填充参数

### Claude Code Skills

研究工作流通过 Claude Code Skills 实现：

- **agentsociety-literature-search** - 文献检索
- **agentsociety-hypothesis** - 假设管理
- **agentsociety-experiment-config** - 实验配置生成与验证
- **agentsociety-run-experiment** - 实验执行
- **agentsociety-analysis** - 数据分析
- **agentsociety-synthesize** - 结果综合
- **agentsociety-generate-paper** - 论文生成

## React Webview 开发

### 概述

本项目使用 React + Ant Design X V2 来构建 Webview 界面，提供了现代化的 AI 对话体验。

### 依赖说明

Webview 开发需要以下依赖：

- `react` 和 `react-dom` - React 框架
- `antd` - Ant Design 组件库 (v6.x)
- `@ant-design/x` - Ant Design X AI 组件库 (v2.0)
- `@ant-design/icons` - Ant Design 图标库
- `webpack` 和 `webpack-cli` - 构建工具
- `ts-loader` - TypeScript 加载器
- `css-loader` 和 `style-loader` - CSS 处理
- `less-loader` - Less 样式处理

### React 组件开发

#### 获取 VSCode API

在 React 组件中，通过 `acquireVsCodeApi()` 获取 VSCode API：

```tsx
import type { VSCodeAPI } from './types';

const vscode: VSCodeAPI = acquireVsCodeApi();
```

#### 与扩展通信

**发送消息到扩展：**
```tsx
vscode.postMessage({
  command: 'sendMessage',
  text: '用户输入的消息'
});
```

**接收扩展的消息：**
```tsx
React.useEffect(() => {
  const handleMessage = (event: MessageEvent<ExtensionMessage>) => {
    const message = event.data;
    switch (message.command) {
      case 'addMessage':
        // 处理消息
        break;
    }
  };
  
  window.addEventListener('message', handleMessage);
  return () => window.removeEventListener('message', handleMessage);
}, []);
```

#### 使用 VSCode 主题变量

React 组件中可以使用 VSCode 的 CSS 变量来适配主题：

```tsx
<div style={{
  backgroundColor: 'var(--vscode-editor-background)',
  color: 'var(--vscode-editor-foreground)',
}}>
  {/* 内容 */}
</div>
```

#### 使用 Ant Design X Chat 组件

```tsx
import { Chat } from '@ant-design/x';
import type { ChatMessage } from '@ant-design/x';

const [messages, setMessages] = React.useState<ChatMessage[]>([]);

<Chat
  messages={messages}
  onSend={handleSendMessage}
  loading={loading}
  placeholder="输入您的问题或请求..."
/>
```

### 工作原理

1. **构建过程**：
   - Webpack 将 React 组件（TSX）编译打包成 JavaScript
   - 输出到 `out/webview/chat.js`

2. **加载过程**：
   - `chatWebviewProvider.ts` 中的 `_getHtmlForWebview()` 方法生成 HTML
   - HTML 中包含 `<script src="chat.js">` 标签
   - Webview 加载并执行 React 应用

3. **通信机制**：
   - React 组件通过 `vscode.postMessage()` 发送消息
   - 扩展通过 `webview.postMessage()` 发送消息
   - React 组件通过 `window.addEventListener('message')` 接收消息

### 类型定义

项目在 `src/webview/chat/types.ts` 中定义了完整的类型：

- `VSCodeAPI` - VSCode Webview API 类型
- `ExtensionMessage` - 扩展发送到 Webview 的消息类型
- `WebviewMessage` - Webview 发送到扩展的消息类型

### 注意事项

1. **Webview 环境限制**：
   - Webview 运行在隔离的浏览器环境中
   - 不能直接访问 Node.js API
   - 不能直接访问 VSCode API（需要通过 `acquireVsCodeApi()`）

2. **资源加载**：
   - 所有资源（JS、CSS、图片等）需要通过 `webview.asWebviewUri()` 转换
   - 确保在 `localResourceRoots` 中配置了正确的路径

3. **性能优化**：
   - 生产构建使用 `webpack --mode production` 进行优化
   - 开发时使用 `--mode development` 保留 source map

4. **TypeScript 配置**：
   - Webview 使用独立的 `src/webview/tsconfig.json` 配置
   - 配置了正确的 JSX 和模块设置

## 待实现功能

根据项目需求，以下功能需要后续实现：

1. **文件操作工具**
   - `init_project_tool`: 初始化研究项目
   - `edit_file_tool`: 编辑文件
   - `read_file_tool`: 读取文件

2. **论文检索**
   - `search_paper_tool`: 搜索论文（已部分实现）
   - 论文下载和管理（已部分实现）

3. **假设生成**
   - `hypothesis` tool (with actions: init, add, get, list, delete): 管理研究假设
   - 假设文件夹结构创建

4. **实验初始化**
   - `try_init_agents`: 测试 Agent 初始化
   - `try_init_env_modules`: 测试环境模块初始化
   - 数据预处理和代码生成

5. **实验执行**
   - `steps.yaml` 生成
   - 实验进程监控
   - 结果数据库管理

6. **结果分析**
   - 数据可视化
   - 统计分析
   - 结论生成

## 打包发布

### 安装 vsce

```bash
npm install -g @vscode/vsce
```

### 打包插件

```bash
vsce package
```

这将生成一个 `.vsix` 文件，可以在 VSCode/Cursor 中安装。

## 测试

```bash
npm test
```

## 代码规范

项目使用 ESLint 进行代码检查：

```bash
npm run lint
```

## 参考资料

- [VSCode Extension API](https://code.visualstudio.com/api)
- [VSCode Extension Samples](https://github.com/Microsoft/vscode-extension-samples)
- [TypeScript Documentation](https://www.typescriptlang.org/docs/)
- [React Documentation](https://react.dev/)
- [Ant Design Documentation](https://ant.design/)
- [Ant Design X Documentation](https://x.ant.design/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
