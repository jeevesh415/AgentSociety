"""文献数据结构模型定义

使用Pydantic规范文献JSON条目的数据结构，提供类型验证和自动文档生成。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
from agentsociety2.logger import get_logger

logger = get_logger()


class LiteratureEntry(BaseModel):
    """文献条目数据模型
    
    用于规范文献索引JSON文件中的每个条目，确保数据结构的一致性和类型安全。
    """

    # 基本信息
    title: str = Field(..., description="文献标题")
    """文献标题，必填字段"""
    
    journal: Optional[str] = Field(None, description="期刊名称")
    """期刊或会议名称"""
    
    doi: Optional[str] = Field(None, description="DOI标识符")
    """数字对象标识符（Digital Object Identifier）"""
    
    abstract: Optional[str] = Field(None, description="摘要")
    """文献摘要"""
    
    # 文件信息
    file_path: str = Field(..., description="文件路径（相对于工作区根目录）")
    """文献文件的路径，相对于工作区根目录"""
    
    file_type: Literal["markdown", "pdf", "docx", "txt", "md"] = Field(
        ..., 
        description="文件类型"
    )
    """文件类型：markdown, pdf, docx, txt, md"""
    
    # 来源信息
    source: Literal["literature_search", "user_upload"] = Field(
        ..., 
        description="文献来源"
    )
    """文献来源：literature_search（文献调研工具生成）或 user_upload（用户上传）"""
    
    # 搜索相关（仅当source为literature_search时）
    query: Optional[str] = Field(None, description="搜索查询词")
    """用于检索此文献的查询词（仅当source为literature_search时）"""
    
    avg_similarity: Optional[float] = Field(
        None, 
        ge=0.0, 
        le=1.0, 
        description="平均相似度分数（0-1）"
    )
    """文献与查询的平均相似度分数，范围0-1"""
    
    # 时间信息
    saved_at: str = Field(..., description="保存时间（ISO格式）")
    """文献保存时间，ISO 8601格式字符串"""
    
    # 其他字段（允许扩展）
    extra_fields: Optional[Dict[str, Any]] = Field(
        None,
        description="其他扩展字段"
    )
    """其他扩展字段，用于存储额外的元数据"""
    
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "title": "Example Research Paper",
                "journal": "Journal of Example Studies",
                "doi": "10.1000/example",
                "abstract": "This is an example abstract...",
                "file_path": "papers/Example_Research_Paper_2024-01-01.md",
                "file_type": "markdown",
                "source": "literature_search",
                "query": "example research",
                "avg_similarity": 0.85,
                "saved_at": "2024-01-01T12:00:00",
            }
        }
    )
    
    @field_validator("saved_at")
    @classmethod
    def validate_saved_at(cls, v: str) -> str:
        """验证保存时间格式"""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"Invalid ISO format for saved_at: {v}")
        return v
    
    @field_validator("doi")
    @classmethod
    def validate_doi(cls, v: Optional[str]) -> Optional[str]:
        """验证DOI格式（基本检查）"""
        if v is None:
            return v
        # 基本DOI格式检查：10.xxxx/xxxx
        if not v.startswith("10."):
            logger.warning(f"DOI format may be invalid: {v}")
        return v
    


class LiteratureIndex(BaseModel):
    """文献索引数据模型
    
    用于规范整个文献索引JSON文件的结构。
    """
    
    entries: list[LiteratureEntry] = Field(
        default_factory=list,
        description="文献条目列表"
    )
    """所有文献条目的列表"""
    
    version: str = Field(
        default="1.0",
        description="索引文件版本"
    )
    """索引文件格式版本"""
    
    created_at: Optional[str] = Field(
        None,
        description="索引创建时间（ISO格式）"
    )
    """索引创建时间，ISO 8601格式字符串"""
    
    updated_at: Optional[str] = Field(
        None,
        description="索引最后更新时间（ISO格式）"
    )
    """索引最后更新时间，ISO 8601格式字符串"""
    
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "version": "1.0",
                "created_at": "2024-01-01T12:00:00",
                "updated_at": "2024-01-01T12:00:00",
                "entries": [
                    {
                        "title": "Example Research Paper",
                        "journal": "Journal of Example Studies",
                        "doi": "10.1000/example",
                        "abstract": "This is an example abstract...",
                        "file_path": "papers/Example_Research_Paper_2024-01-01.md",
                        "file_type": "markdown",
                        "source": "literature_search",
                        "query": "example research",
                        "avg_similarity": 0.85,
                        "saved_at": "2024-01-01T12:00:00",
                    }
                ]
            }
        }
    )
    



