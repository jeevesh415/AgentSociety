#!/usr/bin/env python3
"""
数据分析代理

智能代理，自主决定：
- 分析哪些数据
- 如何分析
- 创建哪些可视化
- 如何呈现结果

代理可以使用 code-executor 等工具执行分析代码。
"""

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentsociety2.logger import get_logger
from agentsociety2.config import get_llm_router_and_model, get_model_name
from litellm import AllMessageValues

from .models import ExperimentContext, AnalysisResult, SUPPORTED_ASSET_FORMATS
from .tool_executor import ToolExecutor, collect_experiment_files
from .utils import parse_llm_json_response


class DataAnalysisAgent:
    """
    数据分析代理，决定分析策略和执行方式。
    
    该代理：
    1. 检查可用数据源
    2. 决定分析内容和方式
    3. 可使用 code-executor 运行分析代码
    4. 决定创建哪些可视化
    5. 确定如何呈现结果
    """
    
    def __init__(
        self,
        llm_router=None,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        workspace_path: Optional[Path] = None,
    ):
        """
        初始化数据分析代理。
        
        Args:
            llm_router: LLM路由实例（可选，未提供时自动创建）
            model_name: 使用的模型名称（为None时使用"default"层级）
            temperature: LLM温度参数
            workspace_path: 工作空间根目录
        """
        self.logger = get_logger()
        self.temperature = temperature
        self.workspace_path = workspace_path or Path.cwd()
        
        if llm_router is None:
            self.llm_router, self.model_name = get_llm_router_and_model("default")
            self.logger.info(f"Using data analysis LLM model: {self.model_name}")
        else:
            self.llm_router = llm_router
            if model_name is None:
                self.model_name = get_model_name("default")
            else:
                self.model_name = model_name
        
        self.logger.info(f"Data analysis agent initialized with model: {self.model_name}")
    
    async def analyze_data(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        db_path: Path,
        output_dir: Path,
    ) -> Dict[str, Any]:
        """
        自主分析实验数据并决定分析策略。
        
        代理将：
        1. 检查可用数据
        2. 发现可用工具
        3. 让LLM决定分析策略和使用的工具
        4. 执行LLM决定的工具
        5. 决定创建哪些可视化
        6. 生成分析结果
        
        Args:
            context: 实验上下文
            analysis_result: 之前的分析结果
            db_path: 实验数据库路径
            output_dir: 输出目录
            
        Returns:
            包含分析计划、工具执行结果、可视化和结果的字典
        """
        self.logger.info("Starting autonomous data analysis...")
        
        data_summary = self._examine_data_sources(db_path)
        
        # Import here to avoid circular import
        from agentsociety2.backend.tools.registry import get_registry
        tool_registry = get_registry()
        tool_executor = ToolExecutor(self.workspace_path, output_dir, tool_registry=tool_registry)
        available_tools = tool_executor.discover_tools()
        self.logger.info(f"Discovered {len(available_tools)} available tools")
        
        # 多轮对话：让LLM根据执行结果调整策略
        analysis_plan = await self._decide_analysis_strategy(
            context, analysis_result, data_summary, available_tools
        )
        
        tool_results = {}
        if analysis_plan.get("tools_to_use"):
            tool_results = await self._execute_tools_with_feedback(
                tool_executor, analysis_plan.get("tools_to_use", []), db_path, output_dir,
                context, analysis_result, data_summary
            )
        
        visualization_plan = await self._decide_visualizations(
            context, analysis_result, data_summary, tool_results
        )
        
        generated_charts = []
        if visualization_plan:
            generated_charts = await self._generate_visualizations(
                visualization_plan, db_path, output_dir, tool_executor
            )
        
        return {
            "analysis_plan": analysis_plan,
            "tool_results": tool_results,
            "visualization_plan": visualization_plan,
            "generated_charts": generated_charts,
        }
    
    
    def _examine_data_sources(self, db_path: Path) -> Dict[str, Any]:
        """
        检查可用数据源并提供基本信息。
        
        Args:
            db_path: 实验数据库路径
            
        Returns:
            数据源摘要字典，包含数据库路径与存在性
        """
        summary = {
            "database": {
                "path": str(db_path),
                "exists": db_path.exists(),
            },
        }
        
        self.logger.info(f"数据库: {summary['database']['path']}")
        return summary
    
    async def _decide_analysis_strategy(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        data_summary: Dict[str, Any],
        available_tools: Dict[str, Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        让LLM决定分析哪些数据以及如何分析。
        
        Args:
            context: 实验上下文
            analysis_result: 之前的分析结果
            data_summary: 可用数据源摘要
            available_tools: 可用工具字典（可选）
            
        Returns:
            包含分析计划的字典：
            - analysis_strategy: 分析策略描述
            - tools_to_use: 要执行的工具列表
        """
        # 格式化可用工具列表
        tools_list = ""
        if available_tools:
            builtin_tools = {k: v for k, v in available_tools.items() if v.get("type") == "builtin"}
            if builtin_tools:
                tools_list = self._format_tools_list(builtin_tools)
            else:
                tools_list = "No built-in tools available"
        
        prompt = f"""You are a data analysis expert. Decide how to analyze the experiment data.

## Experiment context

**Hypothesis**: {context.design.hypothesis}
**Completion**: {context.completion_percentage:.1f}%
**Status**: {context.execution_status.value}

## Previous insights

{chr(10).join([f"- {insight}" for insight in analysis_result.insights[:5]])}

## Available data

### Database

**Path**: {data_summary['database']['path']}
Schema will be discovered by the code executor when needed.

## Available tools

**Built-in tools**:
{tools_list if tools_list else 'None'}

## Output

Return a JSON analysis plan:

```json
{{
  "analysis_strategy": "Overall analysis strategy",
  "tools_to_use": [
    {{
      "tool_name": "tool_name",
      "tool_type": "builtin|code_executor",
      "action": "what you want to do",
      "parameters": {{}}
    }}
  ]
}}
```"""

        messages: List[AllMessageValues] = [
            {
                "role": "system",
                "content": "You are a data analysis expert. Decide the analysis strategy and which tools to run."
            },
            {"role": "user", "content": prompt}
        ]
        
        self.logger.info(f"Calling LLM model: {self.model_name} (decide_analysis_strategy)")
        
        response = await self.llm_router.acompletion(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature,
        )
        
        content = response.choices[0].message.content or ""
        
        # 解析JSON响应
        plan = self._parse_json_response(content, "analysis_plan")
        
        self.logger.info(f"Analysis strategy decided: {plan.get('analysis_strategy', 'N/A')[:100]}")
        return plan
    
    async def _execute_tools_with_feedback(
        self,
        tool_executor: 'ToolExecutor',
        tools_to_use: List[Dict[str, Any]],
        db_path: Path,
        output_dir: Path,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        data_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        通过多轮对话执行工具：让LLM根据结果调整策略。
        """
        results = {}
        conversation_history = []
        max_iterations = 3
        
        for iteration in range(max_iterations):
            # Execute current batch of tools
            current_tools = tools_to_use if iteration == 0 else []
            
            if iteration > 0:
                # 让LLM根据之前的结果调整策略
                adjustment = await self._adjust_strategy_based_on_results(
                    context, analysis_result, data_summary, results, conversation_history
                )
                if not adjustment.get("tools_to_use"):
                    break
                current_tools = adjustment.get("tools_to_use", [])
            
            for i, tool_spec in enumerate(current_tools):
                tool_name = tool_spec.get("tool_name", f"tool_{i}")
                tool_type = tool_spec.get("tool_type", "code_executor")
                parameters = tool_spec.get("parameters", {})
                
                self.logger.info(f"执行工具: {tool_name} (类型: {tool_type}, 第{iteration + 1}轮)")
                
                exec_parameters = parameters.copy()
                if tool_type == "code_executor":
                    exec_parameters["db_path"] = str(db_path)
                    exec_parameters["code_description"] = tool_spec.get("action", "")
                    exec_parameters["extra_files"] = collect_experiment_files(db_path)
                
                result = await tool_executor.execute_tool(
                    tool_name=tool_name,
                    tool_type=tool_type,
                    parameters=exec_parameters,
                )
                
                results[tool_name] = result
                conversation_history.append({
                    "tool": tool_name,
                    "result": result,
                    "iteration": iteration + 1,
                })
                
                self.logger.info(f"Tool {tool_name} execution: {'success' if result.get('success') else 'failed'}")
        
        return results
    
    async def _adjust_strategy_based_on_results(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        data_summary: Dict[str, Any],
        current_results: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        让LLM根据工具执行结果调整分析策略。
        """
        prompt = f"""Based on the tool execution results, decide whether to adjust the analysis strategy.

## Experiment context
**Hypothesis**: {context.design.hypothesis}
**Completion**: {context.completion_percentage:.1f}%

## Tool execution results
{self._format_tool_results(current_results)}

## Recent history
{chr(10).join([f"- Iteration {h['iteration']}: {h['tool']} - {'Success' if h['result'].get('success') else 'Failed'}" for h in conversation_history[-5:]])}

## Task
Assess whether the results are sufficient. If sufficient, return an empty tools_to_use. Otherwise, propose next tools.

```json
{{
  "assessment": "assessment of current results",
  "tools_to_use": [
    {{
      "tool_name": "tool_name",
      "tool_type": "code_executor",
      "action": "what you want to do next",
      "parameters": {{}}
    }}
  ]
}}
```"""

        messages: List[AllMessageValues] = [
            {
                "role": "system",
                "content": "You are a data analysis expert. Review results and decide whether to run more tools."
            },
            {"role": "user", "content": prompt}
        ]
        
        response = await self.llm_router.acompletion(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature,
        )
        
        content = response.choices[0].message.content or ""
        return self._parse_json_response(content, "strategy_adjustment")
    

    
    async def _decide_visualizations(
        self,
        context: ExperimentContext,
        analysis_result: AnalysisResult,
        data_summary: Dict[str, Any],
        analysis_results: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        让LLM决定创建哪些可视化。
        """
        prompt = f"""You are a data visualization expert. Decide which visualizations to create.

## Experiment context
**Hypothesis**: {context.design.hypothesis}
**Completion**: {context.completion_percentage:.1f}%

## Analysis insights
{chr(10).join([f"- {insight}" for insight in analysis_result.insights[:5]])}

## Available data
**Database**: `{data_summary['database']['path']}`

## Tool execution history
{self._format_tool_results(analysis_results)}

## Output

Return a JSON visualization plan:

```json
{{
  "visualizations": [
    {{
      "use_tool": true,
      "tool_name": "code_executor",
      "tool_description": "what to visualize and how to extract the data"
    }}
  ]
}}
```
"""

        messages: List[AllMessageValues] = [
            {"role": "system", "content": "You are a data visualization expert. Choose the most useful visualizations."},
            {"role": "user", "content": prompt}
        ]
        
        self.logger.info(f"Calling LLM model: {self.model_name} (decide_visualizations)")
        
        response = await self.llm_router.acompletion(
            model=self.model_name,
            messages=messages,
            temperature=self.temperature,
        )
        
        content = response.choices[0].message.content or ""
        
        # 解析JSON响应
        plan_data = self._parse_json_response(content, "visualization_plan")
        visualizations = plan_data.get("visualizations", [])
        
        self.logger.info(f"LLM decided to create {len(visualizations)} visualizations")
        return visualizations
    
    async def _generate_visualizations(
        self,
        visualization_plan: List[Dict[str, Any]],
        db_path: Path,
        output_dir: Path,
        tool_executor,
    ) -> List[Path]:
        """
        使用LLM的计划通过code-executor工具生成可视化。
        
        Args:
            visualization_plan: LLM的可视化计划
            db_path: 数据库文件路径
            output_dir: 可视化输出目录
            tool_executor: ToolExecutor实例
            
        Returns:
            生成的图表文件路径列表
        """
        generated_charts = []
        
        if not visualization_plan:
            return generated_charts
        
        use_tools = any(viz.get("use_tool") or viz.get("tool_name") for viz in visualization_plan)
        
        if use_tools and tool_executor is not None:
            self.logger.info("使用工具生成可视化（LLM驱动）")
            
            for viz in visualization_plan:
                if viz.get("use_tool") or viz.get("tool_name"):
                    tool_name = viz.get("tool_name", "code_executor")
                    tool_description = viz.get("tool_description", viz.get("description", ""))
                    
                    if tool_description:
                        tool_spec = {
                            "tool_name": f"viz_{tool_name}",
                            "tool_type": "code_executor",
                            "action": f"Generate visualization: {tool_description}",
                            "parameters": {
                                "db_path": str(db_path),
                                "code_description": tool_description,
                                "extra_files": collect_experiment_files(db_path),
                            }
                        }
                        
                        result = await tool_executor.execute_tool(
                            tool_name=tool_name,
                            tool_type="code_executor",
                            parameters=tool_spec["parameters"],
                        )
                        
                        if result.get("success"):
                            artifacts = result.get("artifacts", [])
                            for artifact_path_str in artifacts:
                                artifact_path = Path(artifact_path_str)
                                if artifact_path.exists() and artifact_path.is_file():
                                    file_ext = artifact_path.suffix.lower()
                                    if file_ext in SUPPORTED_ASSET_FORMATS:
                                        dest_path = output_dir / artifact_path.name
                                        src_resolved = artifact_path.resolve(strict=False)
                                        dst_resolved = dest_path.resolve(strict=False)
                                        if src_resolved == dst_resolved:
                                            generated_charts.append(dest_path)
                                            self.logger.info(
                                                f"✅ 可视化已在输出目录中，跳过复制：{artifact_path.name}"
                                            )
                                            continue

                                        shutil.copy2(artifact_path, dest_path)
                                        generated_charts.append(dest_path)
                                        self.logger.info(
                                            f"✅ 已复制可视化：{artifact_path.name} -> {dest_path}"
                                        )
                        else:
                            self.logger.warning(f"工具执行失败：{result.get('error', '未知错误')}")
        
        return generated_charts
    
    def _parse_json_response(self, content: str, context: str = "") -> Dict[str, Any]:
        """
        解析LLM响应中的JSON
        """
        return parse_llm_json_response(content)
    
    def _format_tools_list(self, tools: Dict[str, Dict[str, Any]]) -> str:
        """
        格式化可用工具列表以便包含在提示词中。
        
        Args:
            tools: 工具名称到工具信息的字典映射
            
        Returns:
            按类别组织的格式化markdown字符串
        """
        if not tools:
            return "No built-in tools available"
        
        # 优先显示文件操作工具
        file_tools = ["read_file", "write_file", "list_directory", "glob", "search_file_content"]
        other_tools = []
        
        for tool_name, tool_info in tools.items():
            description = tool_info.get("description", "No description available")
            entry = f"- **{tool_name}**: {description}"
            if tool_name in file_tools:
                file_tools[file_tools.index(tool_name)] = entry
            else:
                other_tools.append(entry)
        
        # 过滤掉原始字符串，保留格式化条目
        file_tools = [e for e in file_tools if isinstance(e, str) and e.startswith("-")]
        
        lines = []
        if file_tools:
            lines.append("**File Operations**:")
            lines.extend(file_tools)
        if other_tools:
            if lines:
                lines.append("")
            lines.append("**Other Tools**:")
            lines.extend(other_tools)
        
        return "\n".join(lines)
    
    def _format_tool_results(self, tool_results: Dict[str, Any]) -> str:
        """
        格式化工具执行结果以便包含在提示词中。
        
        Args:
            tool_results: 工具名称到执行结果的字典映射
            
        Returns:
            总结工具执行结果的格式化markdown字符串
        """
        if not tool_results:
            return "No tool execution results available"
        
        lines = []
        for tool_name, result in tool_results.items():
            success = result.get("success", False)
            lines.append(f"\n**{tool_name}**: {'✅ Success' if success else '❌ Failed'}")
            
            if success:
                if "stdout" in result:
                    stdout = result["stdout"][:500]
                    lines.append(f"Output: {stdout}")
                if "result" in result:
                    result_str = str(result["result"])[:500]
                    lines.append(f"Result: {result_str}")
            else:
                error = result.get("error", "Unknown error")
                lines.append(f"Error: {error}")
        
        return "\n".join(lines) if lines else "No results"
    
    async def close(self):
        """
        清理资源。
        """
        pass
