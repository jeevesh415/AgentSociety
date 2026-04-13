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
npm run build        # 生产构建（打包扩展和 webview）
npm run compile      # 开发构建
```

或者使用预发布命令：
```bash
npm run vscode:prepublish
```

### 监听模式（开发时使用）

```bash
npm run watch        # 监听模式构建
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
│   ├── apiClient.ts              # API客户端
│   ├── i18n.ts                   # 国际化字符串
│   ├── jsonViewer.ts             # JSON 可视化查看器
│   ├── yamlViewer.ts             # YAML 可视化查看器
│   ├── stepsViewer.ts            # 步骤时间线查看器
│   ├── pidStatusViewer.ts        # 实验状态监控查看器
│   ├── literatureIndexViewer.ts  # 文献索引查看器
│   ├── experimentResultsViewer.ts # 实验结果查看器
│   ├── services/                 # 服务模块
│   │   ├── backendManager.ts     # 后端管理
│   │   ├── backendService.ts     # 后端服务
│   │   └── ...
│   └── webview/                  # React Webview 组件
│       ├── components/           # 共享组件
│       ├── configPage/           # 配置页面
│       ├── initConfig/           # 初始化配置
│       ├── prefillParams/        # 预填充参数界面
│       ├── replay/               # 实验回放界面
│       ├── simSettings/          # SIM设置界面
│       └── i18n/                 # 国际化资源
├── skills/                       # Agent Skills
├── out/                          # 编译输出目录（自动生成）
├── package.json                  # 插件配置文件
├── tsconfig.json                 # TypeScript配置
├── webpack.config.js             # Webpack 构建配置
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
  - 实验状态概览显示

### 2. 可视化文件查看器

插件提供多种文件类型的可视化查看功能：

#### JSON Viewer (`src/jsonViewer.ts`)
- 语法高亮显示
- 折叠/展开对象和数组
- 搜索功能
- 复制内容、复制路径

#### YAML Viewer (`src/yamlViewer.ts`)
- 语法高亮显示
- 复制内容
- 转换为 JSON

#### Steps Viewer (`src/stepsViewer.ts`)
- 时间线视图显示实验步骤
- 编辑和保存功能
- 状态指示器

#### PID Status Viewer (`src/pidStatusViewer.ts`)
- 实验运行状态监控
- 自动刷新（运行中的实验）
- 状态图标（完成/运行/失败/暂停）
- 详细信息展示

#### Literature Index Viewer (`src/literatureIndexViewer.ts`)
- 文献列表展示
- 搜索和过滤
- 批量操作
- 复制 @引用格式
- 键盘快捷键支持

### 3. AI 聊天界面 (Chat Webview)

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
# 默认 LLM 配置（必需）
AGENTSOCIETY_LLM_API_KEY=your_api_key
AGENTSOCIETY_LLM_API_BASE=https://cloud.infini-ai.com/maas/v1
AGENTSOCIETY_LLM_MODEL=qwen3-next-80b-a3b-instruct

# 代码生成 LLM 配置（可选，未设置时回退到 AGENTSOCIETY_LLM_*）
AGENTSOCIETY_CODER_LLM_API_KEY=your_coder_api_key
AGENTSOCIETY_CODER_LLM_API_BASE=https://cloud.infini-ai.com/maas/v1
AGENTSOCIETY_CODER_LLM_MODEL=glm-5

# 高频操作 LLM 配置（可选）
AGENTSOCIETY_NANO_LLM_API_KEY=your_nano_api_key
AGENTSOCIETY_NANO_LLM_API_BASE=https://cloud.infini-ai.com/maas/v1
AGENTSOCIETY_NANO_LLM_MODEL=qwen3-next-80b-a3b-instruct

# 数据分析 LLM 配置（可选，用于数据分析、洞察生成、报告撰写）
AGENTSOCIETY_ANALYSIS_LLM_API_KEY=your_analysis_api_key
AGENTSOCIETY_ANALYSIS_LLM_API_BASE=https://cloud.infini-ai.com/maas/v1
AGENTSOCIETY_ANALYSIS_LLM_MODEL=glm-5

# Embedding 模型配置（可选）
AGENTSOCIETY_EMBEDDING_API_KEY=your_embedding_api_key
AGENTSOCIETY_EMBEDDING_API_BASE=https://cloud.infini-ai.com/maas/v1
AGENTSOCIETY_EMBEDDING_MODEL=bge-m3

# 后端服务配置
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8001

# 文献检索 API（统一学术文献检索服务）
LITERATURE_SEARCH_API_URL=http://localhost:8008/api/search
LITERATURE_SEARCH_API_KEY=lit-your-api-key-here
```

**重要提示**：
- `LITERATURE_SEARCH_API_URL` 必须指向文献检索服务的地址
- `LITERATURE_SEARCH_API_KEY` 用于认证，请替换为实际的 API Key

### 后端API端点

#### 基础接口
- **GET `/health`** - 健康检查
- **GET `/docs`** - API文档（Swagger UI）

#### Agent Skills 接口 (`/api/v1/agent-skills`)
- **GET `/list`** - 列出所有 Agent Skills
- **POST `/enable`** - 启用 Skill
- **POST `/disable`** - 禁用 Skill
- **POST `/scan`** - 扫描自定义 Skill
- **POST `/import`** - 从路径导入 Skill
- **POST `/create`** - 创建新 Skill
- **POST `/upload`** - 上传 zip 包导入 Skill
- **POST `/reload`** - 热重载 Skill
- **POST `/remove`** - 移除自定义 Skill
- **GET `/{name}/info`** - 获取 Skill 详情

#### 模块接口 (`/api/v1/modules`)
- **GET `/agent_classes`** - 获取所有 Agent 类
- **GET `/env_module_classes`** - 获取所有环境模块类
- **GET `/all`** - 获取所有模块（一次性返回）

#### 预填充参数接口 (`/api/v1/prefill-params`)
- **GET `/`** - 获取全局预填充参数
- **GET `/{class_kind}/{class_name}`** - 获取特定类的预填充参数

#### 实验数据接口 (`/api/v1/experiments`)
- **GET `/{hypothesis_id}/{experiment_id}/info`** - 获取实验信息
- **GET `/{hypothesis_id}/{experiment_id}/artifacts`** - 获取产出文件列表
- **GET `/{hypothesis_id}/{experiment_id}/artifacts/{artifact_name}`** - 获取产出文件内容

#### 回放数据接口 (`/api/v1/replay`)
- **GET `/{hypothesis_id}/{experiment_id}/info`** - 获取实验基本信息
- **GET `/{hypothesis_id}/{experiment_id}/timeline`** - 获取时间线数据
- **GET `/{hypothesis_id}/{experiment_id}/agents`** - 获取所有 Agent 列表
- **GET `/{hypothesis_id}/{experiment_id}/agent/{agent_id}`** - 获取 Agent 详情

#### 自定义模块接口 (`/api/v1/custom`)
- **POST `/scan`** - 扫描自定义模块
- **POST `/clean`** - 清理自定义模块配置
- **POST `/test`** - 测试自定义模块
- **GET `/list`** - 列出已注册的自定义模块
- **GET `/status`** - 获取自定义模块状态

### Claude Code Skills

研究工作流通过 Claude Code Skills 实现：

- **agentsociety-literature-search** - 文献检索
- **agentsociety-hypothesis** - 假设管理
- **agentsociety-experiment-config** - 实验配置生成与验证
- **agentsociety-run-experiment** - 实验执行
- **agentsociety-analysis** - 数据分析
- **agentsociety-synthesize** - 结果综合
- **agentsociety-generate-paper** - 论文生成
- **agentsociety-scan-modules** - 扫描模块
- **agentsociety-create-env-module** - 创建环境模块
- **agentsociety-create-dataset** - 创建数据集
- **agentsociety-use-dataset** - 使用数据集
- **agentsociety-web-research** - 网络研究

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
