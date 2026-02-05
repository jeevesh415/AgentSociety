"""文件系统工具集 - 参考 Gemini CLI 设计"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import fnmatch

from agentsociety2.backend.tools.base import BaseTool, ToolResult
from agentsociety2.backend.sse import ToolEvent
from agentsociety2.logger import get_logger

logger = get_logger()


class ListDirectoryTool(BaseTool):
    """列出目录内容的工具 (ReadFolder)"""

    def get_name(self) -> str:
        return "list_directory"

    def get_description(self) -> str:
        return (
            "List the names of files and subdirectories within a specified directory path. "
            "Can optionally ignore entries matching provided glob patterns. "
            "Returns a sorted list with directories first, then files alphabetically."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the directory to list (relative to workspace root)",
                },
                "ignore": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of glob patterns to exclude from listing (e.g., ['*.log', '.git'])",
                },
            },
            "required": ["path"],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行目录列表操作"""
        try:
            rel_path = arguments.get("path", "").strip()
            ignore_patterns = arguments.get("ignore", [])
            
            await self._send_progress(ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=f"Listing {rel_path}",
            ))

            # 解析路径
            target_dir = Path(self._workspace_path) / rel_path
            target_dir = target_dir.resolve()

            # 安全检查：确保在工作区内
            workspace = Path(self._workspace_path).resolve()
            try:
                target_dir.relative_to(workspace)
            except ValueError:
                return ToolResult(
                    success=False,
                    content=f"Path is outside workspace: {target_dir}",
                    error="path_outside_workspace",
                )

            if not target_dir.exists():
                return ToolResult(
                    success=False,
                    content=f"Directory not found: {target_dir}",
                    error="directory_not_found",
                )

            if not target_dir.is_dir():
                return ToolResult(
                    success=False,
                    content=f"Path is not a directory: {target_dir}",
                    error="not_a_directory",
                )

            # 读取目录内容
            entries = []
            for entry in target_dir.iterdir():
                # 检查是否应该忽略
                should_ignore = False
                for pattern in ignore_patterns:
                    if fnmatch.fnmatch(entry.name, pattern):
                        should_ignore = True
                        break

                if should_ignore:
                    continue

                # 忽略隐藏文件（以.开头）
                if entry.name.startswith("."):
                    continue

                is_dir = entry.is_dir()
                entries.append({"name": entry.name, "is_dir": is_dir})

            # 排序：目录在前，然后按字母顺序
            entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

            # 构建输出
            content_lines = [f"Directory listing for {target_dir}:"]
            for entry in entries:
                prefix = "[DIR] " if entry["is_dir"] else ""
                content_lines.append(f"{prefix}{entry['name']}")

            return ToolResult(
                success=True,
                content="\n".join(content_lines),
                data={
                    "path": str(target_dir),
                    "entries": entries,
                    "total_count": len(entries),
                },
            )

        except Exception as e:
            logger.error(f"List directory failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to list directory: {str(e)}",
                error=str(e),
            )


class ReadFileTool(BaseTool):
    """读取文件内容的工具 (ReadFile)"""

    def get_name(self) -> str:
        return "read_file"

    def get_description(self) -> str:
        return (
            "Read and return the content of text files. "
            "Can read specific line ranges using offset and limit parameters."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to read (relative to workspace root)",
                },
                "offset": {
                    "type": "integer",
                    "description": "For text files, the 0-based line number to start reading from",
                },
                "limit": {
                    "type": "integer",
                    "description": "For text files, the maximum number of lines to read",
                },
            },
            "required": ["path"],
        }

    def _read_text_file(
        self, file_path: Path, offset: Optional[int] = None, limit: Optional[int] = None
    ) -> Tuple[str, bool, int]:
        """
        读取文本文件
        
        Returns:
            (content, is_truncated, total_lines)
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            # 尝试其他编码
            with open(file_path, "r", encoding="latin-1") as f:
                lines = f.readlines()

        total_lines = len(lines)
        is_truncated = False

        # 应用offset和limit
        if offset is not None and limit is not None:
            start = offset
            end = offset + limit
            lines = lines[start:end]
            is_truncated = end < total_lines
        elif limit is not None:
            lines = lines[:limit]
            is_truncated = limit < total_lines
        elif total_lines > 2000:
            # 默认最大2000行
            lines = lines[:2000]
            is_truncated = True

        content = "".join(lines)
        return content, is_truncated, total_lines

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行文件读取操作"""
        try:
            rel_path = arguments.get("path", "").strip()
            offset = arguments.get("offset")
            limit = arguments.get("limit")
            
            # 构建进度消息
            if offset is not None and limit is not None:
                progress_msg = f"Reading {rel_path} L{offset+1}-{offset+limit}"
            else:
                progress_msg = f"Reading {rel_path}"
            
            await self._send_progress(ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=progress_msg,
            ))

            # 解析路径
            file_path = Path(self._workspace_path) / rel_path
            file_path = file_path.resolve()

            # 安全检查
            workspace = Path(self._workspace_path).resolve()
            try:
                file_path.relative_to(workspace)
            except ValueError:
                return ToolResult(
                    success=False,
                    content=f"Path is outside workspace: {file_path}",
                    error="path_outside_workspace",
                )

            if not file_path.exists():
                return ToolResult(
                    success=False,
                    content=f"File not found: {file_path}",
                    error="file_not_found",
                )

            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    content=f"Path is not a file: {file_path}",
                    error="not_a_file",
                )

            # 读取文本文件
            content, is_truncated, total_lines = self._read_text_file(file_path, offset, limit)

            # 构建输出
            content_parts = []
            if is_truncated:
                if offset is not None and limit is not None:
                    content_parts.append(
                        f"[File content truncated: showing lines {offset+1}-{offset+limit} of {total_lines} total lines]"
                    )
                else:
                    displayed = len(content.splitlines())
                    content_parts.append(
                        f"[File content truncated: showing lines 1-{displayed} of {total_lines} total lines]"
                    )
            content_parts.append(content)

            return ToolResult(
                success=True,
                content="\n".join(content_parts),
                data={
                    "path": str(file_path),
                    "total_lines": total_lines,
                    "is_truncated": is_truncated,
                },
            )

        except Exception as e:
            logger.error(f"Read file failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to read file: {str(e)}",
                error=str(e),
            )


class WriteFileTool(BaseTool):
    """写入文件的工具 (WriteFile)"""

    def get_name(self) -> str:
        return "write_file"

    def get_description(self) -> str:
        return (
            "Write content to a specified file. "
            "If the file exists, it will be overwritten. "
            "If the file doesn't exist, it (and any necessary parent directories) will be created."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the file to write to (relative to workspace root)",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write into the file",
                },
            },
            "required": ["file_path", "content"],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行文件写入操作"""
        try:
            rel_path = arguments.get("file_path", "").strip()
            content = arguments.get("content", "")
            
            await self._send_progress(ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=f"Writing {rel_path}",
            ))

            if not rel_path:
                return ToolResult(
                    success=False,
                    content="file_path is required",
                    error="missing_file_path",
                )

            # 解析路径
            file_path = Path(self._workspace_path) / rel_path
            file_path = file_path.resolve()

            # 安全检查
            workspace = Path(self._workspace_path).resolve()
            try:
                file_path.relative_to(workspace)
            except ValueError:
                return ToolResult(
                    success=False,
                    content=f"Path is outside workspace: {file_path}",
                    error="path_outside_workspace",
                )

            # 检查文件是否已存在
            file_exists = file_path.exists()

            # 创建父目录
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入文件
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # 构建结果消息
            if file_exists:
                message = f"Successfully overwrote file: {file_path}"
            else:
                message = f"Successfully created and wrote to new file: {file_path}"

            return ToolResult(
                success=True,
                content=message,
                data={
                    "path": str(file_path),
                    "size": len(content),
                    "was_overwrite": file_exists,
                },
            )

        except Exception as e:
            logger.error(f"Write file failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to write file: {str(e)}",
                error=str(e),
            )


class GlobTool(BaseTool):
    """使用glob模式查找文件的工具 (FindFiles)"""

    def get_name(self) -> str:
        return "glob"

    def get_description(self) -> str:
        return (
            "Find files matching specific glob patterns (e.g., 'src/**/*.ts', '*.md'). "
            "Returns absolute paths sorted by modification time (newest first)."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The glob pattern to match against (e.g., '*.py', 'src/**/*.js')",
                },
                "path": {
                    "type": "string",
                    "description": "The directory to search within (relative to workspace root). If omitted, searches workspace root",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Whether the search should be case-sensitive. Defaults to false",
                    "default": False,
                },
            },
            "required": ["pattern"],
        }

    def _should_ignore(self, path: Path) -> bool:
        """检查路径是否应该被忽略"""
        # 常见的忽略目录
        ignore_dirs = {
            "node_modules",
            ".git",
            "__pycache__",
            ".pytest_cache",
            ".venv",
            "venv",
            ".env",
            "dist",
            "build",
            ".next",
            ".cache",
        }

        for part in path.parts:
            if part in ignore_dirs:
                return True
        return False

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行glob搜索"""
        try:
            pattern = arguments.get("pattern", "").strip()
            rel_path = arguments.get("path", "").strip()
            # case_sensitive = arguments.get("case_sensitive", False)  # TODO: 实现大小写敏感支持

            if not pattern:
                return ToolResult(
                    success=False,
                    content="pattern is required",
                    error="missing_pattern",
                )
            
            await self._send_progress(ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=f"Finding {pattern}",
            ))

            # 解析搜索路径
            if rel_path:
                search_dir = Path(self._workspace_path) / rel_path
            else:
                search_dir = Path(self._workspace_path)

            search_dir = search_dir.resolve()

            # 安全检查
            workspace = Path(self._workspace_path).resolve()
            try:
                search_dir.relative_to(workspace)
            except ValueError:
                return ToolResult(
                    success=False,
                    content=f"Path is outside workspace: {search_dir}",
                    error="path_outside_workspace",
                )

            if not search_dir.exists():
                return ToolResult(
                    success=False,
                    content=f"Directory not found: {search_dir}",
                    error="directory_not_found",
                )

            # 执行glob搜索
            matches = []
            for match in search_dir.glob(pattern):
                if match.is_file():
                    # 检查是否应该忽略
                    if self._should_ignore(match):
                        continue

                    matches.append(match)

            # 按修改时间排序（最新的在前）
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            # 构建输出
            if matches:
                content_lines = [
                    f"Found {len(matches)} file(s) matching '{pattern}' within {search_dir}, "
                    f"sorted by modification time (newest first):"
                ]
                for match in matches:
                    content_lines.append(str(match))
                content = "\n".join(content_lines)
            else:
                content = f"No files found matching '{pattern}' within {search_dir}"

            return ToolResult(
                success=True,
                content=content,
                data={
                    "pattern": pattern,
                    "search_dir": str(search_dir),
                    "matches": [str(m) for m in matches],
                    "count": len(matches),
                },
            )

        except Exception as e:
            logger.error(f"Glob search failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to search files: {str(e)}",
                error=str(e),
            )


class SearchFileContentTool(BaseTool):
    """在文件内容中搜索的工具 (SearchText)"""

    def get_name(self) -> str:
        return "search_file_content"

    def get_description(self) -> str:
        return (
            "Search for a regular expression pattern within the content of files in a specified directory. "
            "Can filter files by a glob pattern. "
            "Returns the lines containing matches, along with their file paths and line numbers."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The regular expression (regex) to search for (e.g., 'function\\s+myFunction')",
                },
                "path": {
                    "type": "string",
                    "description": "The directory to search within (relative to workspace root). Defaults to workspace root",
                },
                "include": {
                    "type": "string",
                    "description": "A glob pattern to filter which files are searched (e.g., '*.js', 'src/**/*.{ts,tsx}')",
                },
            },
            "required": ["pattern"],
        }

    def _should_search_file(self, file_path: Path, include_pattern: Optional[str] = None) -> bool:
        """检查文件是否应该被搜索"""
        # 忽略常见的二进制文件和大文件
        ignore_extensions = {
            ".pyc",
            ".pyo",
            ".so",
            ".dylib",
            ".dll",
            ".exe",
            ".bin",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".pdf",
            ".zip",
            ".tar",
            ".gz",
        }

        if file_path.suffix.lower() in ignore_extensions:
            return False

        # 检查文件大小（忽略>10MB的文件）
        try:
            if file_path.stat().st_size > 10 * 1024 * 1024:
                return False
        except OSError:
            return False

        # 如果提供了include模式，检查是否匹配
        if include_pattern:
            if not fnmatch.fnmatch(file_path.name, include_pattern):
                return False

        return True

    def _search_in_file(self, file_path: Path, pattern: str) -> List[Dict[str, Any]]:
        """在文件中搜索模式"""
        matches = []
        try:
            regex = re.compile(pattern)
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    if regex.search(line):
                        matches.append(
                            {
                                "line_number": line_num,
                                "line_content": line.rstrip("\n\r"),
                            }
                        )
        except (UnicodeDecodeError, OSError):
            # 跳过无法读取的文件
            pass
        except re.error as e:
            logger.warning(f"Invalid regex pattern: {e}")

        return matches

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行文件内容搜索"""
        try:
            pattern = arguments.get("pattern", "").strip()
            rel_path = arguments.get("path", "").strip()
            include_pattern = arguments.get("include")

            if not pattern:
                return ToolResult(
                    success=False,
                    content="pattern is required",
                    error="missing_pattern",
                )
            
            search_path = rel_path if rel_path else "workspace"
            await self._send_progress(ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=f"Searching {pattern} in {search_path}",
            ))

            # 解析搜索路径
            if rel_path:
                search_dir = Path(self._workspace_path) / rel_path
            else:
                search_dir = Path(self._workspace_path)

            search_dir = search_dir.resolve()

            # 安全检查
            workspace = Path(self._workspace_path).resolve()
            try:
                search_dir.relative_to(workspace)
            except ValueError:
                return ToolResult(
                    success=False,
                    content=f"Path is outside workspace: {search_dir}",
                    error="path_outside_workspace",
                )

            if not search_dir.exists():
                return ToolResult(
                    success=False,
                    content=f"Directory not found: {search_dir}",
                    error="directory_not_found",
                )

            # 遍历目录搜索
            all_matches = []
            for file_path in search_dir.rglob("*"):
                if not file_path.is_file():
                    continue

                if not self._should_search_file(file_path, include_pattern):
                    continue

                matches = self._search_in_file(file_path, pattern)
                if matches:
                    relative_path = file_path.relative_to(search_dir)
                    all_matches.append(
                        {
                            "file": str(relative_path),
                            "matches": matches,
                        }
                    )

            # 构建输出
            if all_matches:
                total_matches = sum(len(m["matches"]) for m in all_matches)
                content_lines = [
                    f"Found {total_matches} matches for pattern '{pattern}' in path '{search_dir}'"
                ]
                if include_pattern:
                    content_lines[0] += f" (filter: '{include_pattern}')"
                content_lines[0] += ":"
                content_lines.append("---")

                for file_match in all_matches:
                    content_lines.append(f"File: {file_match['file']}")
                    for match in file_match["matches"]:
                        content_lines.append(
                            f"L{match['line_number']}: {match['line_content']}"
                        )
                    content_lines.append("---")

                content = "\n".join(content_lines)
            else:
                content = f"No matches found for pattern '{pattern}'"
                if include_pattern:
                    content += f" (filter: '{include_pattern}')"

            return ToolResult(
                success=True,
                content=content,
                data={
                    "pattern": pattern,
                    "search_dir": str(search_dir),
                    "matches": all_matches,
                    "total_matches": sum(len(m["matches"]) for m in all_matches) if all_matches else 0,
                },
            )

        except Exception as e:
            logger.error(f"Search file content failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to search file content: {str(e)}",
                error=str(e),
            )


class ReplaceTool(BaseTool):
    """替换文件内容的工具 (Edit)"""

    def get_name(self) -> str:
        return "replace"

    def get_description(self) -> str:
        return (
            "Replace text within a file. "
            "By default, replaces a single occurrence, but can replace multiple occurrences when expected_replacements is specified. "
            "This tool is designed for precise, targeted changes and requires significant context around the old_string "
            "to ensure it modifies the correct location."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The path to the file to modify (relative to workspace root)",
                },
                "old_string": {
                    "type": "string",
                    "description": (
                        "The exact literal text to replace. "
                        "CRITICAL: This string must uniquely identify the single instance to change. "
                        "It should include at least 3 lines of context before and after the target text, "
                        "matching whitespace and indentation precisely. "
                        "If old_string is empty, attempts to create a new file with new_string as content."
                    ),
                },
                "new_string": {
                    "type": "string",
                    "description": "The exact literal text to replace old_string with",
                },
                "expected_replacements": {
                    "type": "integer",
                    "description": "The number of occurrences to replace. Defaults to 1",
                    "default": 1,
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        }

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行文件替换操作"""
        try:
            rel_path = arguments.get("file_path", "").strip()
            old_string = arguments.get("old_string", "")
            new_string = arguments.get("new_string", "")
            expected_replacements = arguments.get("expected_replacements", 1)

            if not rel_path:
                return ToolResult(
                    success=False,
                    content="file_path is required",
                    error="missing_file_path",
                )

            # 解析路径
            file_path = Path(self._workspace_path) / rel_path
            file_path = file_path.resolve()
            
            await self._send_progress(ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=f"Replacing {rel_path}",
            ))

            # 安全检查
            workspace = Path(self._workspace_path).resolve()
            try:
                file_path.relative_to(workspace)
            except ValueError:
                return ToolResult(
                    success=False,
                    content=f"Path is outside workspace: {file_path}",
                    error="path_outside_workspace",
                )

            # 如果old_string为空，创建新文件
            if not old_string:
                if file_path.exists():
                    return ToolResult(
                        success=False,
                        content=f"Cannot create file: {file_path} already exists",
                        error="file_already_exists",
                    )

                # 创建父目录
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # 写入新文件
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_string)

                return ToolResult(
                    success=True,
                    content=f"Created new file: {file_path} with provided content",
                    data={
                        "path": str(file_path),
                        "size": len(new_string),
                    },
                )

            # 读取文件
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    content=f"File not found: {file_path}",
                    error="file_not_found",
                )

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 计算出现次数
            occurrences = content.count(old_string)

            if occurrences == 0:
                return ToolResult(
                    success=False,
                    content=f"Failed to edit, 0 occurrences found of:\n{old_string}",
                    error="string_not_found",
                )

            if occurrences != expected_replacements:
                return ToolResult(
                    success=False,
                    content=(
                        f"Failed to edit, expected {expected_replacements} occurrences "
                        f"but found {occurrences} of:\n{old_string}"
                    ),
                    error="unexpected_occurrence_count",
                )

            # 执行替换
            new_content = content.replace(old_string, new_string, expected_replacements)

            # 写入文件
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return ToolResult(
                success=True,
                content=f"Successfully modified file: {file_path} ({occurrences} replacements)",
                data={
                    "path": str(file_path),
                    "replacements": occurrences,
                    "old_length": len(content),
                    "new_length": len(new_content),
                },
            )

        except Exception as e:
            logger.error(f"Replace failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Failed to replace text: {str(e)}",
                error=str(e),
            )


# 导出所有工具
__all__ = [
    "ListDirectoryTool",
    "ReadFileTool",
    "WriteFileTool",
    "GlobTool",
    "SearchFileContentTool",
    "ReplaceTool",
]

