# API参考文档

## 基础信息

- **Base URL**: `http://localhost:8001` (默认)
- **API版本**: `v1`
- **Content-Type**: `application/json`
- **架构**: Function Calling (LLM自主选择工具)

## LLM对话API

### 1. 对话接口

**端点**: `POST /api/v1/chat/completion`

**请求体**:
```json
{
    "messages": [
        {
            "role": "user",
            "content": "我想研究社交媒体对政治观点的影响"
        }
    ],
    "enabled_tools": null,
    "max_turns": 10,
    "temperature": 0.7,
    "stream": false
}
```

**消息格式**:
- `role`: `"system" | "user" | "assistant" | "tool"`
- `content`: 消息内容（字符串）
- `tool_calls`: 工具调用列表（assistant角色）
- `tool_call_id`: 工具调用ID（tool角色）
- `name`: 工具名称（tool角色）

**响应**:
```json
{
    "success": true,
    "messages": [
        {
            "role": "user",
            "content": "我想研究社交媒体对政治观点的影响"
        },
        {
            "role": "assistant",
            "content": null,
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "search_literature",
                        "arguments": "{\"query\": \"social media influence on political opinions\"}"
                    }
                }
            ]
        },
        {
            "role": "tool",
            "content": "找到 5 篇相关文献...",
            "tool_call_id": "call_123",
            "name": "search_literature"
        },
        {
            "role": "assistant",
            "content": "根据搜索结果，我找到了以下相关文献..."
        }
    ],
    "final_answer": "根据搜索结果，我找到了以下相关文献...",
    "tool_calls": null,
    "is_complete": true,
    "turn_count": 2,
    "message": "对话完成"
}
```

### 2. 获取工具列表

**端点**: `GET /api/v1/chat/tools`

**查询参数**:
- `enabled` (可选): 逗号分隔的启用工具名称列表，例如: `"answer_directly,search_literature"`

**响应**:
```json
{
    "success": true,
    "tools": [
        {
            "name": "answer_directly",
            "description": "直接回答用户问题的工具...",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "对用户问题的直接回答"
                    }
                },
                "required": ["answer"]
            }
        },
        {
            "name": "search_literature",
            "description": "搜索与给定查询相关的学术文献...",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询词（支持中文，会自动翻译为英文）"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回的文献数量（可选，默认3）",
                        "minimum": 1,
                        "maximum": 20
                    },
                    "enable_multi_query": {
                        "type": "boolean",
                        "description": "是否启用多查询模式（可选，默认true）"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "design_top_level",
            "description": "生成或更新顶层实验设计...",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "实验话题（必需，除非提供current_design_json）"
                    },
                    "user_feedback": {
                        "type": "string",
                        "description": "用户反馈（可选，用于完善现有设计）"
                    },
                    "current_design_json": {
                        "type": "object",
                        "description": "当前设计JSON（可选）"
                    }
                },
                "required": []
            }
        }
    ],
    "enabled_tools": ["answer_directly", "search_literature", "design_top_level"]
}
```

## 工具说明

### answer_directly

直接回答用户问题的工具。当LLM能够直接回答用户的问题，或者用户的问题不需要文献检索或实验设计时，使用此工具。

**参数**:
- `answer` (必需): 对用户问题的直接回答

### search_literature

搜索与给定查询相关的学术文献。支持中文查询（会自动翻译为英文），支持多查询模式。

**参数**:
- `query` (必需): 搜索查询词
- `top_k` (可选): 返回的文献数量，默认3
- `enable_multi_query` (可选): 是否启用多查询模式，默认true

**返回内容**: 包含文献标题、期刊、摘要、DOI和相似度的格式化文本

### design_top_level

生成或更新顶层实验设计，包括研究话题、假设和实验计划框架。

**参数**:
- `topic` (可选): 实验话题（如果提供current_design_json则不需要）
- `user_feedback` (可选): 用户反馈，用于完善现有设计
- `current_design_json` (可选): 当前设计JSON，如果提供则基于此设计进行完善

**返回内容**: 包含设计JSON和格式化文本，设计会自动保存到文件

## 使用示例

### 示例1: 简单问答（LLM直接回答）

```python
import requests

response = requests.post(
    "http://localhost:8001/api/v1/chat/completion",
    json={
        "messages": [
            {"role": "user", "content": "什么是社会科学？"}
        ]
    }
)

result = response.json()
print(result['final_answer'])
# LLM会使用answer_directly工具直接回答
```

### 示例2: 文献搜索

```python
response = requests.post(
    "http://localhost:8001/api/v1/chat/completion",
    json={
        "messages": [
            {"role": "user", "content": "搜索关于社会规范的文献"}
        ]
    }
)

result = response.json()
# LLM会自动调用search_literature工具
# result['messages']包含完整的对话历史，包括工具调用和结果
```

### 示例3: 实验设计

```python
response = requests.post(
    "http://localhost:8001/api/v1/chat/completion",
    json={
        "messages": [
            {"role": "user", "content": "帮我设计一个关于社交媒体影响的实验"}
        ]
    }
)

result = response.json()
# LLM可能会先调用search_literature搜索相关文献
# 然后调用design_top_level生成实验设计
```

### 示例4: 多轮对话

```python
# 第一轮
response1 = requests.post(
    "http://localhost:8001/api/v1/chat/completion",
    json={
        "messages": [
            {"role": "user", "content": "搜索关于社会规范的文献"}
        ]
    }
)
result1 = response1.json()

# 第二轮：基于第一轮的结果继续
response2 = requests.post(
    "http://localhost:8001/api/v1/chat/completion",
    json={
        "messages": result1['messages'] + [
            {"role": "user", "content": "基于这些文献，帮我设计一个实验"}
        ]
    }
)
result2 = response2.json()
```

### 示例5: 只启用特定工具

```python
response = requests.post(
    "http://localhost:8001/api/v1/chat/completion",
    json={
        "messages": [
            {"role": "user", "content": "搜索文献"}
        ],
        "enabled_tools": ["search_literature"]  # 只启用文献搜索
    }
)
```

## 错误响应

所有API在出错时都会返回以下格式：

```json
{
    "success": false,
    "error": "Error message",
    "detail": "Detailed error information"
}
```

HTTP状态码：
- `200`: 成功
- `400`: 请求错误
- `500`: 服务器内部错误

## 注意事项

1. **消息历史**: 多轮对话需要传递完整的消息历史，包括工具调用和结果
2. **工具选择**: LLM会根据消息内容自主选择工具，无需手动指定
3. **对话轮数**: `max_turns` 控制最大对话轮数，防止无限循环
4. **工具参数**: LLM会自动构建工具参数，无需手动构造
5. **异步处理**: 所有API都是异步的，可能需要较长时间（特别是LLM调用）
