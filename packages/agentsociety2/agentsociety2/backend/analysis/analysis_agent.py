"""
分析代理

使用 LLM 分析实验结果、生成洞察并创建综合报告的智能代理。
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from agentsociety2.logger import get_logger
from agentsociety2.config import get_llm_router_and_model
from litellm import AllMessageValues

from .models import ExperimentContext, AnalysisResult
from .utils import parse_llm_json_response, parse_llm_json_to_model, get_analysis_skills


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
        skills = get_analysis_skills()
        user_content = (f"{skills}\n\n---\n\n{initial_prompt}") if skills else initial_prompt
        messages: List[AllMessageValues] = [{"role": "user", "content": user_content}]

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

        return f"""## Experiment

**Experiment ID**: {context.experiment_id} | **Hypothesis ID**: {context.hypothesis_id}
**Hypothesis**: {context.design.hypothesis}
**Status**: {context.execution_status.value} | **Completion**: {context.completion_percentage:.1f}% | **Duration**: {f"{context.duration_seconds:.2f}s" if context.duration_seconds else "Unknown"}

**Errors**: {chr(10).join([f"- {err}" for err in context.error_messages]) if context.error_messages else "None"}

{hypothesis_md_block}
{experiment_md_block}
{custom_instructions or ""}

Return one JSON object: insights (list), findings (list), conclusions (string), recommendations (list).
```json
{{ "insights": [], "findings": [], "conclusions": "", "recommendations": [] }}
```"""

    def _parse_analysis_response(self, content: str) -> Dict[str, Any]:
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
        insights = parsed.get("insights", [])
        findings = parsed.get("findings", [])
        conclusions = parsed.get("conclusions", "")
        recommendations = parsed.get("recommendations", [])

        judgment_prompt = f"""Evaluate the analysis (experiment {context.experiment_id}).
Generated: {len(insights)} insights, {len(findings)} findings, conclusions, {len(recommendations)} recommendations.

Return JSON: success, reason, should_retry, retry_instruction.
```json
{{ "success": true, "reason": "", "should_retry": false, "retry_instruction": "" }}
```"""

        response = await self.llm_router.acompletion(
            model=self.model_name,
            messages=[{"role": "user", "content": judgment_prompt}],
            temperature=self.temperature,
        )

        content = response.choices[0].message.content or ""
        return parse_llm_json_to_model(content, AnalysisJudgment)

    def _format_analysis_for_feedback(self, parsed: Dict[str, Any]) -> str:
        return json.dumps(parsed, indent=2, ensure_ascii=False)
