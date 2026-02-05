"""MinerU文档解析API路由"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agentsociety2.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/api/v1/mineru", tags=["mineru"])

# 创建线程池执行器用于执行同步的MinerU命令
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mineru")


class ParseRequest(BaseModel):
    """MinerU解析请求"""
    file_path: str
    workspace_path: str


class ParseResponse(BaseModel):
    """MinerU解析响应"""
    success: bool
    message: str
    parsed_file_path: Optional[str] = None
    content_preview: Optional[str] = None


def _parse_with_mineru(file_path: Path, workspace_path: Path) -> Optional[str]:
    """使用MinerU解析文档（支持PDF、Word等多种格式），输出Markdown格式

    如果已存在对应的markdown文件，直接读取，避免重复解析。
    生成的文件名固定为 {原文件名}.parsed.md
    MinerU的输出先放在临时文件夹，然后移动到工作区。
    使用命令行工具调用MinerU，设置模型源为modelscope（中国大陆环境）。
    参考: https://opendatalab.github.io/MinerU/zh/usage/quick_usage/
    """
    # 固定生成的markdown文件名（在工作区内）
    md_file_path = file_path.parent / f"{file_path.stem}.parsed.md"

    # 检查是否已存在解析后的markdown文件
    if md_file_path.exists() and md_file_path.is_file():
        try:
            with open(md_file_path, "r", encoding="utf-8") as f:
                content = f.read()
            if content and content.strip():
                logger.info(
                    f"Found existing markdown file for {file_path}, skipping MinerU parsing"
                )
                return content
        except Exception as e:
            logger.warning(
                f"Failed to read existing markdown file {md_file_path}: {e}"
            )

    # 使用MinerU命令行工具解析
    try:
        # 使用工作区目录作为MinerU输出目录
        # MinerU的输出结构：mineru_output/{文件名}/auto/{文件名}.md
        tmp_output_dir = file_path.parent / "mineru_output"
        tmp_output_dir.mkdir(parents=True, exist_ok=True)

        # 使用当前Python虚拟环境调用MinerU
        # mineru是当前虚拟环境下的一个二进制入口
        # 参考官方文档: mineru -p <input_path> -o <output_path>
        # 设置环境变量确保使用modelscope模型源（中国大陆环境）
        env = os.environ.copy()
        env["MINERU_MODEL_SOURCE"] = "modelscope"

        # 查找当前虚拟环境中的mineru命令
        # 优先查找与sys.executable同目录下的mineru（虚拟环境的bin目录）
        mineru_cmd = None

        # 尝试在虚拟环境的bin目录中查找
        venv_bin_dir = Path(sys.executable).parent
        venv_mineru = venv_bin_dir / "mineru"
        if venv_mineru.exists() and venv_mineru.is_file():
            mineru_cmd = str(venv_mineru)
            logger.info(f"Found mineru in virtual environment: {mineru_cmd}")
        else:
            # 如果虚拟环境目录中找不到，使用which查找（会在PATH中查找，包括当前虚拟环境）
            mineru_cmd = shutil.which("mineru")
            if mineru_cmd:
                logger.info(f"Found mineru in PATH: {mineru_cmd}")
            else:
                logger.error(
                    "MinerU command not found. Please ensure MinerU is installed in the current virtual environment"
                )
                return None

        cmd = [
            mineru_cmd,
            "-p",
            str(file_path),
            "-o",
            str(tmp_output_dir),
            "--source",
            "modelscope",
        ]

        logger.info(f"Running MinerU command: {' '.join(cmd)}")
        logger.info(f"Using Python interpreter: {sys.executable}")
        logger.info(f"Using MinerU command: {mineru_cmd}")

        # 执行MinerU命令
        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=600  # 10分钟超时
        )

        if result.returncode != 0:
            logger.error(
                f"MinerU command failed with return code {result.returncode}"
            )
            if result.stderr:
                logger.error(f"stderr: {result.stderr}")
            if result.stdout:
                logger.error(f"stdout: {result.stdout}")
            return None

        # 查找MinerU生成的markdown文件
        # MinerU的输出结构：mineru_output/{文件名}/auto/{文件名}.md
        # 例如：mineru_output/GCMC/auto/GCMC.md
        md_files = list(tmp_output_dir.rglob("*.md"))
        if not md_files:
            logger.warning(
                f"MinerU processed {file_path} but no markdown file found in {tmp_output_dir}"
            )
            return None

        # 找到最近生成的markdown文件（通常是主输出文件）
        generated_md = max(md_files, key=lambda p: p.stat().st_mtime)

        # 读取markdown内容
        with open(generated_md, "r", encoding="utf-8") as f:
            content = f.read()

        if not content or not content.strip():
            logger.warning(f"MinerU processed {file_path} but content is empty")
            return None

        # 将markdown文件复制到文件旁边，命名为 {原文件名}.parsed.md
        # 保留mineru_output文件夹中的原始文件
        try:
            # 复制文件而不是移动，保留mineru_output中的原始输出
            shutil.copy2(str(generated_md), str(md_file_path))
            logger.info(
                f"Successfully parsed {file_path} with MinerU, copied to {md_file_path}"
            )
        except Exception as e:
            logger.error(
                f"Failed to copy markdown file to {md_file_path}: {e}"
            )
            # 如果复制失败，返回None
            return None

        return content

    except subprocess.TimeoutExpired:
        logger.error(f"MinerU command timed out after 10 minutes for {file_path}")
        return None
    except FileNotFoundError:
        logger.error(
            "MinerU command not found. Please ensure MinerU is installed and available in PATH"
        )
        return None
    except Exception as e:
        logger.error(f"MinerU failed to parse {file_path}: {e}", exc_info=True)
        return None


@router.post("/parse", response_model=ParseResponse)
async def parse_document(request: ParseRequest) -> ParseResponse:
    """
    使用MinerU解析文档（PDF、Word等格式）为Markdown

    支持的格式：
    - PDF (.pdf)
    - Word文档 (.docx, .doc)
    
    解析后的Markdown文件会保存在文件旁边，命名为 {原文件名}.parsed.md
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

        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"文件不存在: {file_path}"
            )

        if not file_path.is_file():
            raise HTTPException(
                status_code=400,
                detail=f"路径不是文件: {file_path}"
            )

        # 检查文件格式
        suffix = file_path.suffix.lower()
        if suffix not in [".pdf", ".docx", ".doc"]:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式: {suffix}。支持的格式: .pdf, .docx, .doc"
            )

        # 在线程池中异步执行MinerU解析，避免阻塞事件循环
        # 使用 run_in_executor 将同步的 subprocess 调用放到线程池执行
        # 这样不会阻塞 FastAPI 的事件循环，其他 HTTP 请求可以正常处理
        loop = asyncio.get_running_loop()
        content = await loop.run_in_executor(
            _executor, _parse_with_mineru, file_path, workspace_path
        )

        if content is None:
            return ParseResponse(
                success=False,
                message=f"MinerU解析失败: {file_path}",
            )

        # 确定解析后的文件路径（应该是.parsed.md文件）
        parsed_file_path = file_path.parent / f"{file_path.stem}.parsed.md"
        if not parsed_file_path.exists():
            # 如果复制失败，返回错误
            return ParseResponse(
                success=False,
                message=f"MinerU解析完成，但无法创建解析文件: {parsed_file_path}",
            )

        # 生成内容预览（前500字符）
        content_preview = content[:500] + "..." if len(content) > 500 else content

        # 转换为相对路径用于返回
        try:
            parsed_file_path_rel = str(parsed_file_path.relative_to(workspace_path))
        except ValueError:
            parsed_file_path_rel = str(parsed_file_path)

        return ParseResponse(
            success=True,
            message=f"成功解析文件: {file_path.name}",
            parsed_file_path=parsed_file_path_rel,
            content_preview=content_preview,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MinerU解析API错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"解析失败: {str(e)}"
        )

