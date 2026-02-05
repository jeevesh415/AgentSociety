"""
分析代理

使用 LLM 分析实验结果、生成洞察并创建综合报告的智能代理。
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from agentsociety2.logger import get_logger
from agentsociety2.config import get_llm_router_and_model, extract_json
from litellm import AllMessageValues

from .models import ExperimentContext, AnalysisResult
from .utils import parse_llm_json_response, parse_llm_json_to_model


class AnalysisJudgment(BaseModel):
    """分析结果判断"""

    success: bool
    reason: str
    should_retry: bool = False
    retry_instruction: str = ""


class AnalysisAgent:
    """使用 LLM 分析实验的智能分析代理。"""

    def __init__(
        self,
        llm_router=None,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """
        初始化分析代理。

        Args:
            llm_router: LLM 路由实例
            model_name: 使用的模型名称
            temperature: LLM 温度参数
        """
        self.logger = get_logger()
        self.temperature = temperature

        if llm_router is None:
            self.llm_router, self.model_name = get_llm_router_and_model("default")
        else:
            self.llm_router = llm_router
            self.model_name = model_name or "default"

        self.logger.info(f"Analysis agent initialized with model: {self.model_name}")

    async def analyze(
        self,
        context: ExperimentContext,
        custom_instructions: Optional[str] = None,
    ) -> AnalysisResult:
        """
        执行实验的综合分析。

        Args:
            context: 包含设计和结果的实验上下文
            custom_instructions: 可选的定制分析指令

        Returns:
            包含 insights、findings 和 recommendations 的 AnalysisResult
        """
        self.logger.info(f"Starting analysis for experiment {context.experiment_id}")

        initial_prompt = self._build_analysis_prompt(context, custom_instructions)
        messages: List[AllMessageValues] = [{"role": "user", "content": initial_prompt}]

        max_retries = 5
        parsed = None

        for attempt in range(max_retries):
            self.logger.info(
                f"Generating analysis using {self.model_name} (attempt {attempt + 1}/{max_retries})"
            )

            response = await self.llm_router.acompletion(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
            )

            content = response.choices[0].message.content or ""
            parsed = self._parse_analysis_response(content)

            judgment = await self._judge_analysis_result(parsed, context)

            has_content = (
                len(parsed.get("insights", [])) > 0
                or len(parsed.get("findings", [])) > 0
                or bool(parsed.get("conclusions", "").strip())
            )
            if (
                judgment.success
                or not judgment.should_retry
                or attempt >= max_retries - 1
                or (judgment.should_retry and attempt >= 1 and has_content)
            ):
                if judgment.should_retry and attempt >= 1 and has_content:
                    self.logger.info(
                        "Stopping retry: analysis already has content (guarding against endless retries)."
                    )
                break

            self.logger.info(f"Analysis needs improvement: {judgment.reason}")
            feedback_message = f"""Previous analysis result:
```json
{self._format_analysis_for_feedback(parsed)}
```

Analysis: {judgment.reason}

What to improve: {judgment.retry_instruction}

Please generate an improved analysis."""
            messages.append({"role": "user", "content": feedback_message})

        if not parsed:
            parsed = {
                "insights": [],
                "findings": [],
                "conclusions": "Analysis could not be completed.",
                "recommendations": [],
            }

        result = AnalysisResult(
            experiment_id=context.experiment_id,
            hypothesis_id=context.hypothesis_id,
            insights=parsed.get("insights", []),
            findings=parsed.get("findings", []),
            conclusions=parsed.get("conclusions", ""),
            recommendations=parsed.get("recommendations", []),
            generated_at=datetime.now(),
        )

        self.logger.info(f"Analysis completed")
        return result

    def _build_analysis_prompt(
        self,
        context: ExperimentContext,
        custom_instructions: Optional[str] = None,
    ) -> str:
        """
        构建综合分析提示词。
        """
        hypothesis_md_block = ""
        if getattr(context.design, "hypothesis_markdown", None):
            hypothesis_md_block = f"""

## Hypothesis Document (HYPOTHESIS.md)

```markdown
{context.design.hypothesis_markdown}
```"""

        experiment_md_block = ""
        if getattr(context.design, "experiment_markdown", None):
            experiment_md_block = f"""

## Experiment Design Document (EXPERIMENT.md)

```markdown
{context.design.experiment_markdown}
```"""

        return f"""Analyze the following experiment.

## Experiment Information

**Experiment ID**: {context.experiment_id}
**Hypothesis ID**: {context.hypothesis_id}
**Hypothesis**: {context.design.hypothesis}

**Execution Status**: {context.execution_status.value}
**Completion**: {context.completion_percentage:.1f}%
**Duration**: {f"{context.duration_seconds:.2f}s" if context.duration_seconds else "Unknown"}

**Error Messages**:
{chr(10).join([f"- {err}" for err in context.error_messages]) if context.error_messages else "No errors"}

{hypothesis_md_block}
{experiment_md_block}

{custom_instructions or ""}

Return a JSON object:
```json
{{
    "insights": [...],
    "findings": [...],
    "conclusions": "...",
    "recommendations": [...]
}}
```"""

    def _parse_analysis_response(self, content: str) -> Dict[str, Any]:
        """
        解析 LLM 分析响应。

        Args:
            content: LLM 原始响应文本

        Returns:
            包含 insights, findings, conclusions, recommendations 的字典
        """
        data = parse_llm_json_response(content)

        return {
            "insights": data.get("insights", []),
            "findings": data.get("findings", []),
            "conclusions": data.get("conclusions", ""),
            "recommendations": data.get("recommendations", []),
        }

    async def _judge_analysis_result(
        self,
        parsed: Dict[str, Any],
        context: ExperimentContext,
    ) -> AnalysisJudgment:
        """
        使用 LLM 判断分析结果是否完整和准确。

        Args:
            parsed: 解析后的分析结果
            context: 实验上下文

        Returns:
            AnalysisJudgment 判断结果
        """
        insights = parsed.get("insights", [])
        findings = parsed.get("findings", [])
        conclusions = parsed.get("conclusions", "")
        recommendations = parsed.get("recommendations", [])

        judgment_prompt = f"""Evaluate the analysis result:

## Experiment Context
- Experiment ID: {context.experiment_id}
- Hypothesis: {context.design.hypothesis}
- Completion: {context.completion_percentage:.1f}%
- Status: {context.execution_status.value}

## Generated Analysis
- Insights: {len(insights)} items
- Findings: {len(findings)} items
- Conclusions: {len(conclusions)} characters
- Recommendations: {len(recommendations)} items

Accept the analysis when it contains substantive insights, findings, or conclusions; only set should_retry when the response is clearly incomplete or off-task. Do not require full run metadata to accept a valid design-based analysis.

Return JSON:
```json
{{
    "success": true/false,
    "reason": "brief explanation",
    "should_retry": true/false,
    "retry_instruction": "what to improve if should_retry is true"
}}
```"""

        response = await self.llm_router.acompletion(
            model=self.model_name,
            messages=[{"role": "user", "content": judgment_prompt}],
            temperature=self.temperature,
        )

        content = response.choices[0].message.content or ""
        return parse_llm_json_to_model(content, AnalysisJudgment)

    def _format_analysis_for_feedback(self, parsed: Dict[str, Any]) -> str:
        """格式化分析结果用于反馈。"""
        return json.dumps(parsed, indent=2, ensure_ascii=False)

    def _format_variables(self, variables: Dict[str, Any]) -> str:
        """
        格式化变量用于提示词显示。

        Args:
            variables: 变量名到值的字典

        Returns:
            格式化的变量字符串表示
        """
        if not variables:
            return "None"

        lines = []
        for key, value in variables.items():
            lines.append(f"- {key}: {value}")

        return "\n".join(lines)
