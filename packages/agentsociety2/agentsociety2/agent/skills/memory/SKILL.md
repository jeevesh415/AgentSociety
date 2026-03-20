---
name: memory
description: Step finalize - flush cognition memory to long-term storage and optional intention query.
priority: 90
auto_load: finalize
requires:
  - observation
provides:
  - memory_persistence
  - long_term_memory
---

# Memory (Finalize)

Pipeline 收尾阶段——将当前 step 中 cognition skill 产生的内部状态
（需求变化、情感、思考）批量持久化到长期记忆。

## 为什么是 finalize

`cognition` skill（dynamic, priority=40）在执行过程中会向
`agent._cognition_memory` 写入多条记录。memory 必须在所有 dynamic
skills 执行完毕后才能 flush，否则会丢失数据。

## What It Does

1. **Flush cognition memory** — 将 `_cognition_memory` 中按 type 分组的条目批量写入长期记忆（纯内存操作，0 LLM 调用）。
2. **Intention query**（可选）— 每隔 2 步查询一次当前意图（1 LLM 调用），仅在 cognition skill 已运行时触发。

## Key Methods on Agent

| Method | Purpose |
|--------|---------|
| `_flush_cognition_memory_to_memory()` | Batch-commit cognition scratchpad to long-term |
| `_query_current_intention()` | LLM 查询当前意图（可选） |
