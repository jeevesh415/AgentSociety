# Extension TODO

## 已完成

- [x] 将MinerU解析文件视为一个独立的操作，不在load_literature工具中进行解析
  - VSCode文件系统监听发现papers目录下的文件变化
  - 支持自动/手动两种解析模式（parseModeManager.ts）
  - 自动检测已解析文件，避免重复处理
  - 详见：paperWatcher.ts, mineruParser.ts
- [x] 实现参数预填充功能，解决部分模块需要一些无法由LLM生成的参数的问题
- [x] 假设和配置生成完成后能通过 experiment_runner 启动实验
- [x] 迁移到 Claude Code Skills 架构（移除旧的 chat completion API）
