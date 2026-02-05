"""
分析模块通用工具函数
"""

from typing import Any, Dict, TypeVar, Type

import json_repair
from pydantic import BaseModel
from agentsociety2.config import extract_json


T = TypeVar('T', bound=BaseModel)


def parse_llm_json_response(content: str) -> Dict[str, Any]:
    """
    解析 LLM 返回的 JSON 响应。
    
    Args:
        content: LLM 原始响应文本
        
    Returns:
        解析后的字典，如果解析失败返回空字典
    """
    json_str = extract_json(content)
    if not json_str:
        return {}
    
    data = json_repair.loads(json_str)
    if not isinstance(data, dict):
        return {}
    
    return data


def parse_llm_json_to_model(content: str, model_class: Type[T]) -> T:
    """
    解析 LLM 返回的 JSON 响应并验证为 Pydantic 模型。
    
    Args:
        content: LLM 原始响应文本
        model_class: Pydantic 模型类
        
    Returns:
        验证后的模型实例
        
    Raises:
        ValidationError: 如果 JSON 不符合模型结构
        json.JSONDecodeError: 如果 JSON 解析失败
    """
    json_str = extract_json(content)
    if not json_str:
        json_str = content
    
    data = json_repair.loads(json_str)
    return model_class.model_validate(data)
