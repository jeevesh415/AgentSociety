# AI Social Scientist

AI Social Scientist是LLM驱动的智能自主社会科学研究智能体，其具备以下可自主执行的专业能力：

+ 社会科学文献检索
+ 基于AgentSociety2所提供的Agent和Environment Module，构建检验研究想法的社会科学模拟实验
    - 选定Agent和Environment Module
    - 处理数据、生成代码以初始化Agent Class
    - 处理数据、生成代码以初始化Environment Module
    - 设计实验过程中外部与虚拟世界的交互，从而干预虚拟世界以达成某种实验目的
+ 开展模拟实验的执行，形成：
    - 实验过程可视化数据（存储在Sqlite数据库中）
    - 实验Log（文本文件，用于debug）
    - 实验模块提供的统计结果（结构化文本，如JSON，用于数据分析）
+ 数据总结与分析
    - LLM编写代码处理数据
    - LLM绘图
    - 形成总结结论，返回给实验

## 系统架构

AI Social Scientist采用VSCode插件 + Claude Code Skills的架构：

1. **VSCode插件** - 提供用户界面和文件系统管理
   - 左侧边栏：项目结构视图
   - Agent Skills 管理面板
   - 参数预填充功能

2. **Claude Code Skills** - 提供完整的研究工作流能力
   - 文献检索、假设管理、实验配置、实验执行、数据分析、论文生成

## 快速开始

### 前置要求

- Node.js (>= 16.x)
- Python 3.10+
- uv (Python包管理器)
- VSCode 或 Cursor (>= 1.80.0)

### 1. 安装插件依赖

```bash
cd extension
npm install
```

### 2. 编译插件

```bash
npm run build        # 生产构建（打包扩展和 webview）
npm run compile      # 开发构建
```

或者使用预发布命令：
```bash
npm run vscode:prepublish
```

### 3. 配置后端

#### 3.1 创建环境变量文件

在 `packages/agentsociety2` 目录下创建 `.env` 文件：

```bash
cd packages/agentsociety2
touch .env
```

#### 3.2 配置环境变量

编辑 `.env` 文件，添加以下配置：

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
- 默认支持多数据源搜索：local（本地知识库）、arxiv、crossref、openalex

### 4. 启动后端服务

```bash
cd packages/agentsociety2
uv run python -m agentsociety2.backend.run
```

服务启动后，您将看到：
```
启动 AI Social Scientist Backend API 服务...
服务地址: http://0.0.0.0:8001
API文档: http://0.0.0.0:8001/docs
健康检查: http://0.0.0.0:8001/health
日志等级: info
```

### 5. 配置插件

在VSCode设置中配置后端服务URL：

1. 打开设置（`Ctrl+,` 或 `Cmd+,`）
2. 搜索 `AI Social Scientist`
3. 设置 `Backend Url` 为您的FastAPI后端地址（默认：`http://localhost:8001`）

或者直接在 `settings.json` 中添加：

```json
{
  "aiSocialScientist.backendUrl": "http://localhost:8001"
}
```

### 6. 调试插件

1. 在 VSCode/Cursor 中打开 `extension` 文件夹
2. 按 `F5` 启动调试
3. 新的 Extension Development Host 窗口将打开，插件已加载

### 7. 使用插件

在 Extension Development Host 窗口中：

- **左侧边栏**: 点击 "AI Social Scientist" 图标查看项目结构视图
- **右侧边栏**: 自动打开 AI Chat 面板，可以开始对话
- **命令面板**: 按 `Ctrl+Shift+P` (或 `Cmd+Shift+P`)，输入 "AI Social Scientist" 查看所有可用命令

## 功能特性

### 1. 项目结构管理

插件会在工作区创建以下结构：

```
workspace/
├── TOPIC.md                    # 研究话题描述
├── papers/                     # 论文目录
│   ├── literature_index.json   # 文献索引（可视化查看）
│   ├── pdf/                    # PDF 文献
│   ├── md/                     # Markdown 笔记
│   └── json/                   # JSON 文件
├── hypothesis_12345/           # 假设目录
│   ├── HYPOTHESIS.md          # 假设描述
│   ├── SIM_SETTINGS.json      # 模拟设置（可用自定义编辑器打开）
│   └── experiment_123/        # 实验目录
│       ├── EXPERIMENT.md      # 实验描述
│       ├── init/              # 初始化结果
│       │   └── results/
│       └── run/               # 运行结果
│           ├── pid.json       # 实验状态（可视化查看）
│           ├── steps.yaml     # 实验步骤（可视化查看）
│           └── sqlite.db      # 结果数据库
```

### 2. 可视化文件查看器

插件提供多种文件的可视化查看功能：

| 文件类型 | 功能 |
|---------|------|
| **JSON 文件** | 语法高亮、折叠展开、搜索、复制内容/路径 |
| **YAML 文件** | 语法高亮、复制内容、转换为 JSON |
| **steps.yaml** | 时间线视图、编辑保存 |
| **pid.json** | 实验状态监控（运行/完成/失败）、自动刷新 |
| **literature_index.json** | 文献列表、搜索、批量操作、复制 @引用 |

点击树视图中的文件即可自动使用对应的可视化查看器打开。

### 3. 右键菜单功能

在项目结构视图中，右键点击文件可使用：

**通用操作**：
- 复制文件路径
- 复制文件名
- 在文件管理器中打开

**文献操作**：
- 复制 @引用（如 `@papers/example.pdf`）
- 删除文献
- 重命名文献

**JSON/YAML 文件**：
- 可视化查看
- 格式化

**Markdown 文件**：
- 预览
- 在编辑器中打开

### 4. Agent Skills 管理

通过左侧边栏的 Skills 面板：
- 查看可用的 Agent Skills
- 导入自定义 Skills
- 启用/禁用 Skills
- 查看 Skill 详情

### 5. 参数预填充

解决部分模块需要非LLM生成参数的问题，通过预填充参数配置简化实验配置流程。

### 6. 实验状态监控

- 项目根节点显示实验概览（运行中/完成数/文献数）
- 假设节点显示实验统计
- pid.json 文件实时显示实验状态（✅完成/🔄运行中/❌失败/⏸️暂停）

## 开发模式

开发时运行 watch 模式：

```bash
npm run watch
```

## 项目结构

```
extension/
├── src/                          # 源代码目录
│   ├── extension.ts              # 主入口文件
│   ├── projectStructureProvider.ts  # 项目结构树视图
│   ├── apiClient.ts              # API客户端
│   ├── services/                 # 服务模块
│   └── webview/                  # React Webview 组件
│       ├── components/           # 共享组件
│       ├── configPage/           # 配置页面
│       ├── replay/               # 实验回放
│       ├── simSettings/          # SIM设置编辑器
│       └── ...
├── skills/                       # Agent Skills
├── package.json                  # 插件配置文件
├── tsconfig.json                 # TypeScript配置
├── webpack.config.js             # Webpack 构建配置
└── README.md                     # 项目说明文档
```

## 故障排除

### 后端连接问题

如果看到"未连接"状态：

1. 检查后端服务是否正在运行（`cd packages/agentsociety2 && uv run python -m agentsociety2.backend.run`）
2. 检查后端URL配置是否正确（VSCode设置中的 `aiSocialScientist.backendUrl`）
3. 检查防火墙/网络设置
4. 查看VSCode输出面板中的"AI Social Scientist API"日志

### 文献检索失败

如果文献检索失败：

1. 检查 `.env` 文件中的 `LITERATURE_SEARCH_API_URL` 是否正确配置
2. 确保文献检索服务正在运行
3. 检查网络连接（特别是Docker环境中的网络配置）

### 编译错误

如果遇到编译错误：

1. 确保已安装所有依赖：`npm install`
2. 检查Node.js版本：`node --version`（需要 >= 16.x）
3. 清理并重新编译：`rm -rf out node_modules && npm install && npm run compile`

## 下一步

查看 [DEVELOPMENT.md](./DEVELOPMENT.md) 了解详细的开发指南和待实现功能。

## 参考资料

- [AgentSociety V2技术方案](https://tsinghuafiblab.yuque.com/hhbywg/wg833b/ux6id6186lv3ae8p#ZJerZ)
- [实验设计-实验配置-实验执行 自动化](https://tsinghuafiblab.yuque.com/hhbywg/wg833b/gw8fv1hhsakau1rw)
