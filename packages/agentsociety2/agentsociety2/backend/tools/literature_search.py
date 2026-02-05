"""文献检索工具"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from litellm import AllMessageValues

from agentsociety2.backend.tools.base import BaseTool, ToolResult
from agentsociety2.backend.tools.literature_models import LiteratureEntry, LiteratureIndex
from agentsociety2.backend.sse import ToolEvent
from agentsociety2.config import get_llm_router
from agentsociety2.designer.literature_search import search_literature
from agentsociety2.logger import get_logger

logger = get_logger()


class LiteratureSearchTool(BaseTool):
    """Tool for searching academic literature"""

    def __init__(
        self,
        workspace_path: str,
        progress_callback,
        tool_id: str,
    ):
        super().__init__(
            workspace_path=workspace_path,
            progress_callback=progress_callback,
            tool_id=tool_id,
        )
        self._router = get_llm_router("default")

    def get_name(self) -> str:
        return "search_literature"

    def get_description(self) -> str:
        return (
            "Search for academic literature related to a given query. "
            "Use this tool when users need to find related research, understand existing research on a topic, "
            "or need literature support. "
            "Supports Chinese queries (automatically translated to English) and multi-query mode. "
            "Search results are automatically saved and return article titles, abstracts, journals, DOIs, and relevant content snippets."
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (supports Chinese, will be automatically translated to English)",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of articles to return (optional, default 3)",
                    "minimum": 1,
                    "maximum": 20,
                },
                "enable_multi_query": {
                    "type": "boolean",
                    "description": "Whether to enable multi-query mode, splitting complex queries into multiple subtopics (optional, default true)",
                },
            },
            "required": ["query"],
        }

    async def _generate_summary(self, query: str, articles: list, total: int) -> str:
        """Generate a summary using LLM to guide users on next steps"""
        try:
            # Prepare article summaries for LLM context
            article_summaries = []
            for idx, article in enumerate(articles[:10], 1):  # Use up to 10 articles for context
                title = article.get("title", "Unknown Title")
                journal = article.get("journal", "")
                abstract = article.get("abstract", "")
                doi = article.get("doi", "")
                
                article_info = f"{idx}. {title}"
                if journal:
                    article_info += f" ({journal})"
                if abstract:
                    # Limit abstract length
                    abstract_preview = abstract[:300] + "..." if len(abstract) > 300 else abstract
                    article_info += f"\n   Abstract: {abstract_preview}"
                if doi:
                    article_info += f"\n   DOI: {doi}"
                article_summaries.append(article_info)
            
            articles_text = "\n\n".join(article_summaries)
            
            # Create prompt for LLM
            prompt = f"""You are an AI Social Scientist assistant. A literature search has been completed for the query: "{query}"

Found {total} relevant article(s). The article files have been saved to the workspace's `papers` directory.

Here are the key articles found:
{articles_text}

Please generate a helpful summary and guidance for the user. The summary should:
1. Briefly acknowledge the search completion
2. Highlight 2-3 key themes or findings from the articles (if visible in titles/abstracts)
3. Suggest concrete next steps for the research workflow
4. Be encouraging and actionable

Format the response as markdown with clear sections. Keep it concise but informative (around 150-200 words)."""

            # Get model name from router
            model_name = self._router.model_list[0]["model_name"]
            
            # Call LLM
            messages: List[AllMessageValues] = [
                {"role": "user", "content": prompt}
            ]
            
            response = await self._router.acompletion(
                model=model_name,
                messages=messages,
                stream=False,
            )
            
            # Extract content from response
            if hasattr(response, 'choices') and len(response.choices) > 0:
                choice = response.choices[0]
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'): # type: ignore
                    summary = choice.message.content or "" # type: ignore
                else:
                    summary = ""
            else:
                summary = ""
            
            if not summary:
                raise ValueError("Empty response from LLM")
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}", exc_info=True)
            raise

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除非法字符"""
        # 移除或替换非法字符
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        sanitized = re.sub(r'\s+', '_', sanitized)
        sanitized = re.sub(r'_{2,}', '_', sanitized)
        return sanitized[:100]  # 限制长度

    def _format_article_as_markdown(self, article: Dict[str, Any], query: str) -> str:
        """将单个文献格式化为Markdown，增加空行确保Markdown正确显示"""
        lines = []
        lines.append(f"# {article.get('title', 'Untitled Article')}")
        lines.append("")
        lines.append(f"**Search Query:** {query}")
        lines.append("")
        lines.append(f"**Saved At:** {datetime.now().isoformat()}")
        lines.append("")

        if article.get("journal"):
            lines.append(f"**Journal:** {article['journal']}")
            lines.append("")
        if article.get("doi"):
            lines.append(f"**DOI:** {article['doi']}")
            lines.append("")
        if article.get("avg_similarity") is not None:
            lines.append(f"**Similarity Score:** {article['avg_similarity']:.3f}")
            lines.append("")

        if article.get("abstract"):
            lines.append("## Abstract")
            lines.append("")
            lines.append(article["abstract"])
            lines.append("")

        # 添加其他字段
        exclude_fields = {"title", "journal", "doi", "abstract", "avg_similarity"}
        first_extra = True
        for key, value in article.items():
            if key not in exclude_fields and value is not None:
                if first_extra:
                    lines.append("**Other Fields:**")
                    lines.append("")
                    first_extra = False
                lines.append(f"- **{key}:** {value}")
        if not first_extra:
            lines.append("")

        return "\n".join(lines)

    async def _save_literature_to_workspace(self, result: Dict[str, Any]) -> List[str]:
        """将文献检索结果保存到工作区的papers目录"""
        if not self._workspace_path:
            logger.warning("Workspace path not set, cannot save literature files")
            return []

        papers_dir = Path(self._workspace_path) / "papers"
        papers_dir.mkdir(parents=True, exist_ok=True)

        saved_files = []
        timestamp = datetime.now().isoformat().replace(":", "-").replace(".", "-")[:19]

        articles = result.get("articles", [])
        json_entries = []
        
        for idx, article in enumerate(articles):
            title = article.get("title", f"Article_{idx + 1}")
            sanitized_title = self._sanitize_filename(title)
            filename = f"{sanitized_title}_{timestamp}.md"
            filepath = papers_dir / filename

            content = self._format_article_as_markdown(article, result.get("query", ""))
            try:
                filepath.write_text(content, encoding="utf-8")
                saved_files.append(str(filepath))
                
                # 准备JSON条目数据
                entry_data = {
                    "title": article.get("title", ""),
                    "journal": article.get("journal"),
                    "doi": article.get("doi"),
                    "abstract": article.get("abstract"),
                    "avg_similarity": article.get("avg_similarity"),
                    "file_path": str(filepath.relative_to(Path(self._workspace_path))),
                    "file_type": "markdown",
                    "source": "literature_search",
                    "query": result.get("query"),
                    "saved_at": datetime.now().isoformat(),
                }
                
                # 添加其他字段到extra_fields
                exclude_fields = {"title", "journal", "doi", "abstract", "avg_similarity"}
                extra_fields = {}
                for key, value in article.items():
                    if key not in exclude_fields and value is not None:
                        extra_fields[key] = value
                
                if extra_fields:
                    entry_data["extra_fields"] = extra_fields
                
                # 使用Pydantic模型验证和创建条目
                json_entry = LiteratureEntry(**entry_data)
                json_entries.append(json_entry)
            except Exception as e:
                logger.error(f"Failed to save article {idx + 1}: {e}")

        # 保存或更新JSON文件
        json_filename = "literature_index.json"
        json_filepath = papers_dir / json_filename
        
        try:
            # 如果JSON文件已存在，读取现有数据
            existing_index = None
            if json_filepath.exists():
                try:
                    with open(json_filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    existing_index = LiteratureIndex(**data)
                except Exception as e:
                    logger.error(f"Failed to read existing JSON file: {e}, creating new one")
                    existing_index = None
            
            # 创建或更新索引
            if existing_index is None:
                now = datetime.now().isoformat()
                existing_index = LiteratureIndex(
                    entries=[],
                    created_at=now,
                    updated_at=now,
                )
            
            # 合并新数据（避免重复）
            existing_file_paths = {entry.file_path for entry in existing_index.entries}
            for entry in json_entries:
                if entry.file_path not in existing_file_paths:
                    existing_index.entries.append(entry)
            
            # 更新更新时间
            existing_index.updated_at = datetime.now().isoformat()
            
            # 保存更新后的JSON
            with open(json_filepath, "w", encoding="utf-8") as f:
                json.dump(existing_index.model_dump(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved/updated literature index JSON with {len(existing_index.entries)} entries")
        except Exception as e:
            logger.error(f"Failed to save JSON index: {e}", exc_info=True)

        return saved_files

    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """执行文献搜索"""
        try:
            query = arguments.get("query", "")
            if not query:
                return ToolResult(
                    success=False,
                    content="Query cannot be empty",
                    error="query is required",
                )

            top_k = arguments.get("top_k")
            enable_multi_query = arguments.get("enable_multi_query", True)
            
            await self._send_progress(ToolEvent(
                tool_name=self.name,
                tool_id=self._current_tool_id,
                status="progress",
                content=f"Searching: {query[:50]}",
            ))

            logger.info(f"Executing literature search: query={query}, top_k={top_k}")

            # Build call kwargs (search_literature accepts Optional[int] but type checker may not recognize it)
            call_kwargs: Dict[str, Any] = {
                "query": query,
                "router": self._router,
                "enable_multi_query": enable_multi_query,
            }
            if top_k is not None:
                call_kwargs["top_k"] = top_k

            result = await search_literature(**call_kwargs)

            if result is None:
                return ToolResult(
                    success=False,
                    content="Literature search failed, no relevant articles found",
                    error="No results found",
                )

            articles = result.get("articles", [])
            total = result.get("total", len(articles))

            # Save literature results to workspace
            saved_files = []
            if articles and self._workspace_path:
                try:
                    saved_files = await self._save_literature_to_workspace(result)
                    logger.info(f"Saved {len(saved_files)} literature files to workspace")
                except Exception as e:
                    logger.error(f"Failed to save literature to workspace: {e}", exc_info=True)

            # Format results
            if not articles:
                content = f"No articles found related to '{query}'."
                summary = (
                    "No relevant articles found. Suggestions:\n"
                    "1. Try different keywords or broader queries\n"
                    "2. Check spelling\n"
                    "3. Consider using English keywords for search"
                )
            else:
                content_parts = [
                    f"Found {total} article(s) related to '{query}':\n",
                ]
                for idx, article in enumerate(articles[:5], 1):  # Show first 5 articles
                    title = article.get("title", "Unknown Title")
                    journal = article.get("journal", "Unknown Journal")
                    abstract = article.get("abstract", "")
                    doi = article.get("doi", "")
                    avg_sim = article.get("avg_similarity", 0)

                    content_parts.append(f"{idx}. {title}")
                    if journal:
                        content_parts.append(f"   Journal: {journal}")
                    if doi:
                        content_parts.append(f"   DOI: {doi}")
                    if avg_sim > 0:
                        content_parts.append(f"   Similarity: {avg_sim:.3f}")
                    if abstract:
                        abstract_preview = abstract[:200] + "..." if len(abstract) > 200 else abstract
                        content_parts.append(f"   Abstract: {abstract_preview}")
                    content_parts.append("")

                if total > 5:
                    content_parts.append(f"... {total - 5} more article(s) not shown")

                content = "\n".join(content_parts)
                
                # Generate summary using LLM
                try:
                    summary = await self._generate_summary(query, articles, total)
                except Exception as e:
                    logger.warning(f"Failed to generate LLM summary: {e}", exc_info=True)
                    # Fallback to a simple summary if LLM generation fails
                    summary = (
                        f"## Literature Search Completed\n\n"
                        f"Found {total} relevant article(s). Files have been saved to the `papers` directory in your workspace.\n\n"
                        f"### Next Steps:\n"
                        f"1. **Read the Literature**: Review the saved article files\n"
                        f"2. **Filter Articles**: Remove irrelevant articles\n"
                        f"3. **Continue Searching**: Request additional searches if needed\n"
                        f"4. **Generate Hypotheses**: Based on the literature review, start generating research hypotheses"
                    )
                
                # Add summary to content
                content = content + "\n\n" + summary
                
                # Add saved files information
                if saved_files:
                    relative_files = [
                        str(Path(f).relative_to(Path(self._workspace_path)))
                        if self._workspace_path and Path(f).is_relative_to(Path(self._workspace_path))
                        else f
                        for f in saved_files
                    ]
                    content += "\n\n**Saved Files:**\n" + "\n".join(f"- `{f}`" for f in relative_files)

            return ToolResult(
                success=True,
                content=content,
                data={
                    "articles": articles,
                    "total": total,
                    "query": query,
                    "saved_files": saved_files,
                },
            )
        except Exception as e:
            logger.error(f"Literature search tool execution failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content=f"Literature search failed: {str(e)}",
                error=str(e),
            )

