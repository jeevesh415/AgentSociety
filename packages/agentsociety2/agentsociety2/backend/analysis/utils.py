"""分析模块通用工具函数。约定：LLM 按要求只返回 JSON 或 ```json ... ``` 包裹的一段。"""

from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar, Type

AnalysisProgressCallback = Optional[Callable[[str], Awaitable[None]]]

import json_repair
from pydantic import BaseModel

_SKILLS_PATH = Path(__file__).resolve().parent / "analysis_skills.md"
T = TypeVar("T", bound=BaseModel)


def get_analysis_skills() -> str:
    """供分析 Agent 使用的 skill 指导；注入到各步 LLM 的 system 或 prompt 中。"""
    if _SKILLS_PATH.exists():
        return _SKILLS_PATH.read_text(encoding="utf-8").strip()
    return ""


def _take_json_string(content: str) -> str:
    """从约定格式中取出 JSON 字符串：整段即 JSON，或 ```json ... ``` 中唯一一段。"""
    raw = (content or "").strip()
    if not raw:
        return ""
    if raw.startswith("```"):
        parts = raw.split("```")
        for i, p in enumerate(parts):
            s = p.strip()
            if i == 0:
                s = s.lstrip("json").strip()
            if s and (s.startswith("{") or s.startswith("[")):
                return s
        return ""
    return raw


def parse_llm_json_response(content: str) -> Dict[str, Any]:
    """解析 LLM 返回的 JSON，约定为单段 JSON 或 ```json ... ```。返回 dict，失败返回 {}。"""
    json_str = _take_json_string(content)
    if not json_str:
        return {}
    data = json_repair.loads(json_str)
    return data if isinstance(data, dict) else {}


def parse_llm_json_to_model(content: str, model_class: Type[T]) -> T:
    """解析 LLM 返回的 JSON 并验证为 Pydantic 模型。约定同上。"""
    json_str = _take_json_string(content)
    if not json_str:
        json_str = (content or "").strip()
    data = json_repair.loads(json_str)
    return model_class.model_validate(data)
