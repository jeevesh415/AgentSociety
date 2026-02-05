"""文献管理API路由 - 提供删除、重命名等操作"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agentsociety2.backend.tools.literature_models import LiteratureIndex, LiteratureEntry
from agentsociety2.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/api/v1/literature", tags=["literature"])


class DeleteRequest(BaseModel):
    """删除文献请求"""
    file_path: str  # 相对于工作区的文件路径
    workspace_path: str


class DeleteResponse(BaseModel):
    """删除文献响应"""
    success: bool
    message: str


class RenameRequest(BaseModel):
    """重命名文献请求"""
    file_path: str  # 相对于工作区的旧文件路径
    new_name: str  # 新文件名（不含路径）
    workspace_path: str


class RenameResponse(BaseModel):
    """重命名文献响应"""
    success: bool
    message: str
    new_file_path: Optional[str] = None  # 新文件路径（相对于工作区）


def _get_literature_index_path(workspace_path: Path) -> Path:
    """获取文献索引JSON文件路径"""
    papers_dir = workspace_path / "papers"
    return papers_dir / "literature_index.json"


def _load_literature_index(workspace_path: Path) -> Optional[LiteratureIndex]:
    """加载文献索引"""
    index_path = _get_literature_index_path(workspace_path)
    if not index_path.exists():
        logger.info(f"Literature index file not found: {index_path}")
        return None
    
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return LiteratureIndex(**data)
    except Exception as e:
        logger.error(f"Failed to load literature index: {e}", exc_info=True)
        return None


def _save_literature_index(workspace_path: Path, index: LiteratureIndex) -> bool:
    """保存文献索引"""
    index_path = _get_literature_index_path(workspace_path)
    try:
        # 确保papers目录存在
        index_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 更新更新时间
        index.updated_at = datetime.now().isoformat()
        
        # 保存JSON文件
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index.model_dump(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved literature index with {len(index.entries)} entries")
        return True
    except Exception as e:
        logger.error(f"Failed to save literature index: {e}", exc_info=True)
        return False


def _normalize_file_path(file_path: str) -> str:
    """规范化文件路径（统一使用正斜杠）"""
    return file_path.replace("\\", "/")


@router.post("/delete", response_model=DeleteResponse)
async def delete_literature(request: DeleteRequest) -> DeleteResponse:
    """
    删除文献文件并更新索引
    
    1. 删除文件系统中的文件
    2. 从literature_index.json中移除对应条目
    3. 如果存在解析后的markdown文件，也一并删除
    """
    try:
        workspace_path = Path(request.workspace_path)
        if not workspace_path.exists() or not workspace_path.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"工作区路径不存在或不是目录: {request.workspace_path}"
            )

        # 解析文件路径
        file_path = Path(request.file_path)
        if not file_path.is_absolute():
            file_path = workspace_path / file_path
        
        # 规范化路径用于索引匹配
        normalized_path = _normalize_file_path(str(file_path.relative_to(workspace_path)))

        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"文件不存在: {file_path}"
            )

        # 删除文件
        try:
            if file_path.is_file():
                file_path.unlink()
                logger.info(f"Deleted file: {file_path}")
            elif file_path.is_dir():
                shutil.rmtree(file_path)
                logger.info(f"Deleted directory: {file_path}")
        except Exception as e:
            logger.error(f"Failed to delete file: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"删除文件失败: {e}"
            )

        # 删除解析后的markdown文件（如果存在）
        if file_path.suffix.lower() in [".pdf", ".docx", ".doc"]:
            parsed_file = file_path.parent / f"{file_path.stem}.parsed.md"
            if parsed_file.exists():
                try:
                    parsed_file.unlink()
                    logger.info(f"Deleted parsed markdown file: {parsed_file}")
                except Exception as e:
                    logger.warning(f"Failed to delete parsed markdown file: {e}")

        # 更新文献索引
        index = _load_literature_index(workspace_path)
        if index:
            # 移除匹配的条目
            original_count = len(index.entries)
            index.entries = [
                entry for entry in index.entries
                if _normalize_file_path(entry.file_path) != normalized_path
            ]
            
            # 如果条目数量减少，说明找到了匹配项，需要保存
            if len(index.entries) < original_count:
                if _save_literature_index(workspace_path, index):
                    logger.info(f"Removed entry from literature index: {normalized_path}")
                else:
                    logger.warning("Failed to save literature index after deletion")

        return DeleteResponse(
            success=True,
            message=f"成功删除文件: {file_path.name}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete literature: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"删除文献失败: {e}"
        )


@router.post("/rename", response_model=RenameResponse)
async def rename_literature(request: RenameRequest) -> RenameResponse:
    """
    重命名文献文件并更新索引
    
    1. 重命名文件系统中的文件
    2. 更新literature_index.json中对应条目的file_path
    3. 如果存在解析后的markdown文件，也一并重命名
    """
    try:
        workspace_path = Path(request.workspace_path)
        if not workspace_path.exists() or not workspace_path.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"工作区路径不存在或不是目录: {request.workspace_path}"
            )

        # 解析文件路径
        old_file_path = Path(request.file_path)
        if not old_file_path.is_absolute():
            old_file_path = workspace_path / old_file_path

        if not old_file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"文件不存在: {old_file_path}"
            )

        # 构建新文件路径
        new_file_path = old_file_path.parent / request.new_name
        
        # 检查新文件名是否已存在
        if new_file_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"目标文件已存在: {new_file_path}"
            )

        # 规范化路径用于索引匹配
        old_normalized_path = _normalize_file_path(str(old_file_path.relative_to(workspace_path)))
        new_normalized_path = _normalize_file_path(str(new_file_path.relative_to(workspace_path)))

        # 重命名文件
        try:
            old_file_path.rename(new_file_path)
            logger.info(f"Renamed file: {old_file_path} -> {new_file_path}")
        except Exception as e:
            logger.error(f"Failed to rename file: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"重命名文件失败: {e}"
            )

        # 重命名解析后的markdown文件（如果存在）
        if old_file_path.suffix.lower() in [".pdf", ".docx", ".doc"]:
            old_parsed_file = old_file_path.parent / f"{old_file_path.stem}.parsed.md"
            new_parsed_file = new_file_path.parent / f"{new_file_path.stem}.parsed.md"
            if old_parsed_file.exists():
                try:
                    old_parsed_file.rename(new_parsed_file)
                    logger.info(f"Renamed parsed markdown file: {old_parsed_file} -> {new_parsed_file}")
                except Exception as e:
                    logger.warning(f"Failed to rename parsed markdown file: {e}")

        # 更新文献索引
        index = _load_literature_index(workspace_path)
        if index:
            # 查找并更新匹配的条目
            updated = False
            for entry in index.entries:
                if _normalize_file_path(entry.file_path) == old_normalized_path:
                    entry.file_path = new_normalized_path
                    updated = True
                    logger.info(f"Updated entry in literature index: {old_normalized_path} -> {new_normalized_path}")
                    break
            
            # 如果找到匹配项，保存索引
            if updated:
                if _save_literature_index(workspace_path, index):
                    logger.info("Saved literature index after rename")
                else:
                    logger.warning("Failed to save literature index after rename")

        return RenameResponse(
            success=True,
            message=f"成功重命名文件: {old_file_path.name} -> {request.new_name}",
            new_file_path=new_normalized_path
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rename literature: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"重命名文献失败: {e}"
        )

