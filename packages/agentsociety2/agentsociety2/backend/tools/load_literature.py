"""加载文献工具"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from agentsociety2.backend.tools.base import BaseTool, ToolResult
from agentsociety2.backend.tools.literature_models import (
    LiteratureEntry,
    LiteratureIndex,
)
from agentsociety2.backend.sse import ToolEvent
from agentsociety2.logger import get_logger

logger = get_logger()


class LoadLiteratureTool(BaseTool):
    """Tool for loading literature from JSON index and parsing various document formats"""

    def get_name(self) -> str:
        return "load_literature"

    def get_description(self) -> str:
        return (
            "Load literature from the workspace. "
            "This tool reads literature data from the JSON index file (created by literature search tool) "
            "and also scans the papers directory for additional documents (PDF, Word, TXT, Markdown) "
            "that are not in the JSON index. "
            "For PDF and Word documents, this tool will look for existing MinerU-parsed markdown files. "
            "If no parsed file exists, the document will be skipped. "
            "Use the MinerU parsing API to parse documents first if needed. "
            "Use this tool when you need to access previously saved literature or load user-uploaded documents."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory path to load literature from (optional, defaults to 'papers' directory in workspace)",
                },
                "include_json_index": {
                    "type": "boolean",
                    "description": "Whether to include literature from JSON index (optional, default true)",
                },
                "include_other_files": {
                    "type": "boolean",
                    "description": "Whether to scan and parse other files not in JSON index (optional, default true)",
                },
            },
            "required": [],
        }

    def _load_json_index(self, json_path: Path) -> List[LiteratureEntry]:
        """从JSON索引文件加载文献数据"""
        if not json_path.exists():
            logger.info(f"JSON index file not found: {json_path}")
            return []

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            index = LiteratureIndex(**data)
            return index.entries
        except Exception as e:
            logger.error(f"Failed to load JSON index: {e}", exc_info=True)
            return []

    def _load_parsed_content(self, file_path: Path) -> Optional[str]:
        """加载已存在的MinerU解析文件

        只检查 {原文件名}.parsed.md 文件（在文件旁边）。
        mineru_output 文件夹中的文件不会被检查，因为解析结果已经复制到 .parsed.md。

        如果解析文件不存在，返回None，表示文件尚未解析。
        """
        # 检查文件旁边的.parsed.md文件
        md_file_path = file_path.parent / f"{file_path.stem}.parsed.md"
        if md_file_path.exists() and md_file_path.is_file():
            try:
                with open(md_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if content and content.strip():
                    logger.info(
                        f"Found existing parsed markdown file: {md_file_path}"
                    )
                    return content
            except Exception as e:
                logger.warning(
                    f"Failed to read parsed markdown file {md_file_path}: {e}"
                )

        logger.info(
            f"No parsed markdown file found for {file_path}. "
            "Please use MinerU parsing API to parse this document first."
        )
        return None

    def _parse_txt(self, file_path: Path) -> Optional[str]:
        """解析TXT文件"""
        encodings = ["utf-8", "gbk", "gb2312", "latin-1"]
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                return content if content.strip() else None
            except UnicodeDecodeError:
                continue
        logger.warning(f"Failed to decode {file_path} with any encoding")
        return None

    def _parse_markdown(self, file_path: Path) -> Optional[str]:
        """解析Markdown文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return content if content.strip() else None
        except Exception as e:
            logger.error(
                f"Failed to parse Markdown file {file_path}: {e}", exc_info=True
            )
            return None

    def _parse_document(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """根据文件扩展名解析文档
        
        对于PDF和Word文档，只加载已存在的MinerU解析文件。
        如果解析文件不存在，返回None（跳过该文件）。
        """
        suffix = file_path.suffix.lower()

        content = None

        # 对于PDF和Word文档，只加载已存在的解析文件
        if suffix in [".pdf", ".docx", ".doc"]:
            if suffix == ".doc":
                logger.warning(
                    f"Old .doc format may not be fully supported: {file_path}"
                )
            content = self._load_parsed_content(file_path)
            # 如果解析文件不存在，跳过该文件
            if content is None:
                logger.info(
                    f"Skipping {file_path} - no parsed markdown file found. "
                    "Please use MinerU parsing API to parse this document first."
                )
                return None
        elif suffix == ".txt":
            content = self._parse_txt(file_path)
        elif suffix in [".md", ".markdown"]:
            content = self._parse_markdown(file_path)
        else:
            logger.debug(f"Unsupported file format: {suffix}, skipping {file_path}")
            return None

        if content is None:
            return None

        return {
            "title": file_path.stem,
            "file_path": str(file_path),
            "file_type": suffix[1:] if suffix.startswith(".") else suffix,
            "content": content,
            "source": "user_upload",
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行文献加载"""
        try:
            workspace_path = Path(self._workspace_path)

            # 确定目录路径
            directory = arguments.get("directory")
            if directory:
                papers_dir = workspace_path / directory
            else:
                papers_dir = workspace_path / "papers"

            if not papers_dir.exists():
                return ToolResult(
                    success=False,
                    content=f"Directory not found: {papers_dir}",
                    error="directory not found",
                )

            include_json_index = arguments.get("include_json_index", True)
            include_other_files = arguments.get("include_other_files", True)
            
            await self._send_progress(ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=f"Loading from {directory or 'papers'}",
            ))

            loaded_literature = []
            json_index_paths = set()

            # 1. 从JSON索引加载文献
            if include_json_index:
                json_index_path = papers_dir / "literature_index.json"
                json_entries = self._load_json_index(json_index_path)

                for entry in json_entries:
                    file_path = entry.file_path

                    # 转换为绝对路径
                    if Path(file_path).is_absolute():
                        full_path = Path(file_path)
                    else:
                        full_path = workspace_path / file_path

                    if full_path.exists():
                        json_index_paths.add(str(full_path))
                        loaded_literature.append(entry.model_dump())
                    else:
                        logger.warning(f"File not found in JSON index: {full_path}")

            # 2. 扫描并解析其他文件
            if include_other_files:
                supported_extensions = {".pdf", ".docx", ".txt", ".md", ".markdown"}

                for file_path in papers_dir.rglob("*"):
                    if not file_path.is_file():
                        continue

                    # 跳过JSON索引文件本身
                    if file_path.name == "literature_index.json":
                        continue

                    # 跳过已经在JSON索引中的文件
                    if str(file_path) in json_index_paths:
                        continue

                    # 只处理支持的格式
                    if file_path.suffix.lower() not in supported_extensions:
                        continue

                    parsed_doc = self._parse_document(file_path)
                    if parsed_doc:
                        # 转换为相对路径
                        try:
                            parsed_doc["file_path"] = str(
                                file_path.relative_to(workspace_path)
                            )
                        except ValueError:
                            parsed_doc["file_path"] = str(file_path)
                        loaded_literature.append(parsed_doc)

            # 格式化结果
            total = len(loaded_literature)

            # 按来源分类统计
            from_json = sum(
                1
                for item in loaded_literature
                if item.get("source") == "literature_search"
            )
            from_upload = sum(
                1 for item in loaded_literature if item.get("source") == "user_upload"
            )

            if total == 0:
                content = (
                    f"No literature found in {papers_dir}.\n\n"
                    "Suggestions:\n"
                    "1. Use the literature search tool to find and save articles\n"
                    "2. Upload PDF, Word, TXT, or Markdown files to the papers directory\n"
                    "3. Check that the directory path is correct"
                )
            else:
                content_parts = [
                    f"Loaded {total} literature item(s) from {papers_dir}:\n",
                ]

                content_parts.append(f"- From JSON index: {from_json}")
                content_parts.append(f"- From uploaded files: {from_upload}")
                content_parts.append("")

                # 显示前10个文献的标题
                content_parts.append("**Loaded Literature:**")
                for idx, item in enumerate(loaded_literature[:10], 1):
                    title = item.get("title", f"Document {idx}")
                    file_type = item.get("file_type", "unknown")
                    source = item.get("source", "unknown")
                    file_path = item.get("file_path", "")

                    content_parts.append(f"{idx}. **{title}**")
                    content_parts.append(f"   - Type: {file_type}")
                    content_parts.append(f"   - Source: {source}")
                    if file_path:
                        content_parts.append(f"   - Path: {file_path}")
                    content_parts.append("")

                if total > 10:
                    content_parts.append(f"... {total - 10} more item(s) not shown")

                content = "\n".join(content_parts)

            return ToolResult(
                success=True,
                content=content,
                data={
                    "literature": loaded_literature,
                    "total": total,
                    "directory": str(papers_dir),
                    "from_json_index": from_json,
                    "from_uploaded_files": from_upload,
                },
            )
        except Exception as e:
            logger.error(f"Load literature tool execution failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to load literature: {str(e)}",
                error=str(e),
            )


if __name__ == "__main__":
    """调试入口"""
    import asyncio
    import sys

    async def test_load_literature():
        """测试加载文献工具"""

        # 设置工作区路径（从命令行参数或使用默认值）
        if len(sys.argv) > 1:
            workspace_path = sys.argv[1]
        else:
            workspace_path = "."

        tool = LoadLiteratureTool(workspace_path=workspace_path)

        # 测试参数
        arguments = {
            "directory": None,  # 使用默认的papers目录
            "include_json_index": True,
            "include_other_files": True,
        }

        print(f"Testing LoadLiteratureTool with workspace: {workspace_path}")
        print("-" * 60)

        result = await tool.execute(arguments)

        print(f"Success: {result.success}")
        print(f"Content:\n{result.content}")
        print("-" * 60)
        if result.data:
            print(f"Total: {result.data.get('total', 0)}")
            print(f"From JSON index: {result.data.get('from_json_index', 0)}")
            print(f"From uploaded files: {result.data.get('from_uploaded_files', 0)}")

    # 运行测试
    asyncio.run(test_load_literature())
