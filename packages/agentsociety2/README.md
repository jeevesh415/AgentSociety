# AgentSociety 2

面向LLM原生的智能体模拟与实验平台

## 所使用LLM Agent社区最新成果

- LLM调用: litellm
- Memory: mem0

## 设计理念

- 简洁易用、灵活性高
  - LLM、Embedding全部调用外部平台，不在项目内部实现
  - 所有数据存储统一通过文件系统
  - 初始化系统面向写代码使用，而不是配置文件使用，通过AI Scientist Agent辅助初始化
- 低复杂度
  - 不再使用ray.io
- 强交互体验
  - 支持命令行Ctrl+C中断，支持终端交互式操作
  - 提供MCP接口