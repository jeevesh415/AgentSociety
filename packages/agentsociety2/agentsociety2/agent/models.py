"""PersonAgent 的数据模型定义。

本模块定义了 PersonAgent 使用的所有 Pydantic 数据模型，包括：

- **情感系统**: EmotionType, Emotion, EmotionUpdateResult
- **需求系统**: NeedType, Need, Satisfactions, NeedAdjustment, NeedAdjustmentResult
- **计划系统**: PlanStepStatus, PlanStep, PlanStepEvaluation, Plan
- **意图系统**: Intention, IntentionUpdate
- **认知系统**: CognitionUpdateResult, CognitionIntentionUpdateResult
- **Skill 选择**: SkillSelection
- **ReAct 系统**: ReActInstructionResponse, ReActInstructionResponseWithTemplate
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class EmotionType(str, Enum):
    """情感类型枚举（基于 OCC 模型）。

    包含 21 种离散情感类型，用于描述 Agent 的主导情感状态。
    """

    JOY = "Joy"
    DISTRESS = "Distress"
    RESENTMENT = "Resentment"
    PITY = "Pity"
    HOPE = "Hope"
    FEAR = "Fear"
    SATISFACTION = "Satisfaction"
    RELIEF = "Relief"
    DISAPPOINTMENT = "Disappointment"
    PRIDE = "Pride"
    ADMIRATION = "Admiration"
    SHAME = "Shame"
    REPROACH = "Reproach"
    LIKING = "Liking"
    DISLIKING = "Disliking"
    GRATITUDE = "Gratitude"
    ANGER = "Anger"
    GRATIFICATION = "Gratification"
    REMORSE = "Remorse"
    LOVE = "Love"
    HATE = "Hate"


class Emotion(BaseModel):
    """六维情感强度向量。

    每个维度的值为 0-10 的整数，表示该情感的强度。

    Attributes:
        sadness: 悲伤强度
        joy: 喜悦强度
        fear: 恐惧强度
        disgust: 厌恶强度
        anger: 愤怒强度
        surprise: 惊讶强度
    """

    sadness: int = Field(default=5, ge=0, le=10)
    joy: int = Field(default=5, ge=0, le=10)
    fear: int = Field(default=5, ge=0, le=10)
    disgust: int = Field(default=5, ge=0, le=10)
    anger: int = Field(default=5, ge=0, le=10)
    surprise: int = Field(default=5, ge=0, le=10)


class Satisfactions(BaseModel):
    """四维需求满意度。

    每个维度的值为 0.0-1.0 的浮点数，表示该需求的满足程度。

    Attributes:
        satiety: 饱食满意度（饥饿）
        energy: 精力满意度（休息）
        safety: 安全满意度
        social: 社交满意度
    """

    satiety: float = Field(default=0.7, ge=0.0, le=1.0)
    energy: float = Field(default=0.3, ge=0.0, le=1.0)
    safety: float = Field(default=0.9, ge=0.0, le=1.0)
    social: float = Field(default=0.8, ge=0.0, le=1.0)


NeedType = Literal["satiety", "energy", "safety", "social", "whatever"]
"""需求类型：饱食、精力、安全、社交、或无特定需求。"""


class Need(BaseModel):
    """当前需求状态。

    Attributes:
        need_type: 需求类型
        description: 需求描述（如 "我感到饥饿"）
        reasoning: 选择该需求的理由
    """

    need_type: NeedType = Field(description="需求类型")
    description: str = Field(description="需求描述")
    reasoning: str = Field(default="", description="选择理由")


class PlanStepStatus(str, Enum):
    """计划步骤状态枚举。

    Attributes:
        PENDING: 未开始
        IN_PROGRESS: 执行中
        COMPLETED: 已完成
        FAILED: 已失败
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class PlanStepEvaluation(BaseModel):
    """计划步骤执行评估结果。

    Attributes:
        success: 步骤是否成功完成
        evaluation: 评估结果描述
        consumed_time: 消耗时间（分钟）
    """

    success: bool = Field(description="步骤是否成功")
    evaluation: str = Field(description="评估结果描述")
    consumed_time: int = Field(default=10, ge=0, description="消耗时间（分钟）")


class PlanStep(BaseModel):
    """计划步骤。

    Attributes:
        intention: 步骤意图/目标
        status: 当前状态
        start_time: 开始时间
        evaluation: 执行评估结果
    """

    intention: str = Field(description="步骤意图")
    status: PlanStepStatus = Field(default=PlanStepStatus.PENDING)
    start_time: Optional[datetime] = Field(default=None)
    evaluation: Optional[PlanStepEvaluation] = Field(default=None)


class Plan(BaseModel):
    """执行计划。

    由意图生成的多步执行计划，通过 ReAct 循环与环境交互执行。

    Attributes:
        target: 计划目标
        reasoning: 生成理由
        steps: 计划步骤列表
        index: 当前执行步骤索引
        completed: 是否已完成
        failed: 是否已失败
        start_time: 计划开始时间
        end_time: 计划结束时间
    """

    target: str = Field(description="计划目标")
    reasoning: str = Field(default="")
    steps: list[PlanStep] = Field(description="计划步骤列表")
    index: int = Field(default=0, ge=0)
    completed: bool = Field(default=False)
    failed: bool = Field(default=False)
    start_time: Optional[datetime] = Field(default=None)
    end_time: Optional[datetime] = Field(default=None)

    def to_adjust_needs_prompt(self) -> str:
        """生成用于需求调整的提示文本。"""
        execution_results = []
        for step in self.steps:
            eval_result = step.evaluation
            if eval_result:
                execution_results.append(
                    f"Step: {step.intention}, Result: {eval_result.evaluation}"
                )
        evaluation_results = (
            "\n".join(execution_results) if execution_results else "No execution results"
        )
        return f"Goal: {self.target}\nExecution situation:\n{evaluation_results}\n"


class CognitionUpdateResult(BaseModel):
    """认知更新结果。

    Attributes:
        thought: 更新的思考/内心独白
        emotion: 更新的情感强度
        emotion_types: 主导情感类型
    """

    thought: str = Field(description="更新的思考")
    emotion: Emotion = Field(description="更新的情感强度")
    emotion_types: EmotionType = Field(description="情感类型")


class EmotionUpdateResult(BaseModel):
    """情感更新结果。

    Attributes:
        emotion: 更新的情感强度
        emotion_types: 主导情感类型
        conclusion: 情感变化结论
    """

    emotion: Emotion = Field(description="更新的情感强度")
    emotion_types: EmotionType = Field(description="情感类型")
    conclusion: Optional[str] = Field(default=None)


class NeedAdjustment(BaseModel):
    """单项需求调整。

    Attributes:
        need_type: 需求类型
        adjustment_type: 调整类型（增加/减少/维持）
        new_value: 调整后的新值
        reasoning: 调整理由
    """

    need_type: NeedType = Field(description="需求类型")
    adjustment_type: Literal["increase", "decrease", "maintain"] = Field(description="调整类型")
    new_value: float = Field(ge=0.0, le=1.0, description="调整后的新值")
    reasoning: str = Field(default="")


class NeedAdjustmentResult(BaseModel):
    """需求调整结果。

    Attributes:
        adjustments: 调整列表
        reasoning: 整体调整理由
    """

    adjustments: list[NeedAdjustment] = Field(description="调整列表")
    reasoning: str = Field(default="")


class Intention(BaseModel):
    """意图（基于计划行为理论 TPB）。

    Attributes:
        intention: 意图描述
        priority: 优先级（数字越小优先级越高）
        attitude: 态度评分 (0.0-1.0)
        subjective_norm: 主观规范评分 (0.0-1.0)
        perceived_control: 感知控制力评分 (0.0-1.0)
        reasoning: 生成理由
    """

    intention: str = Field(description="意图描述")
    priority: int = Field(ge=1, description="优先级（数字越小越高）")
    attitude: float = Field(ge=0.0, le=1.0)
    subjective_norm: float = Field(ge=0.0, le=1.0)
    perceived_control: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(default="")


class IntentionUpdate(BaseModel):
    """意图更新结果。

    Attributes:
        intentions: 候选意图列表（按优先级排序）
        reasoning: 更新理由
    """

    intentions: list[Intention] = Field(description="候选意图列表")
    reasoning: str = Field(default="")


class CognitionIntentionUpdateResult(BaseModel):
    """认知与意图的合并更新结果。

    这是 cognition skill 的主要输出，通过一次 LLM 调用完成：
    1. 需求调整
    2. 当前需求确定
    3. 情感/思考更新
    4. 意图形成

    Attributes:
        need_adjustment: 需求调整结果
        current_need: 当前确定的需求
        cognition_update: 情感与思考更新结果
        intention_update: 意图更新结果
    """

    need_adjustment: NeedAdjustmentResult = Field(description="需求调整结果")
    current_need: Need = Field(description="当前需求结果")
    cognition_update: CognitionUpdateResult = Field(description="情感与思考更新结果")
    intention_update: IntentionUpdate = Field(description="意图更新结果")


class SkillSelection(BaseModel):
    """Skill Selector 的输出。

    LLM 根据当前 observation 和状态，选择本步需要激活的 dynamic skill。

    Attributes:
        selected_skills: 选中的 skill 名称列表
        reasoning: 选择理由
    """

    selected_skills: list[str] = Field(description="本步需要激活的技能名称列表")
    reasoning: str = Field(default="", description="选择理由")


class ReActInstructionResponse(BaseModel):
    """ReAct 循环中的指令响应。

    Attributes:
        reasoning: 生成该指令的理由
        instruction: 发送给环境路由的指令
        status: 可选的状态（如 "success", "fail", "in_progress"）
    """

    reasoning: str = Field(default="")
    instruction: str = Field(default="")
    status: Optional[str] = Field(default=None)


class ReActInstructionResponseWithTemplate(ReActInstructionResponse):
    """带模板变量支持的 ReAct 指令响应。

    当 template_mode_enabled=True 时使用，支持变量占位符。

    Attributes:
        instruction: 带变量占位符的指令（如 "Move to {{location}}"）
        variables: 变量字典（如 {"location": "home"}）
    """

    instruction: str = Field(
        default="",
        description="Action instruction with {variable_name} placeholders."
    )
    variables: Dict[str, Any] = Field(default_factory=dict)


NEED_DESCRIPTION = """## Understanding Human Needs

As a person, you have various **needs** that drive your behavior and decisions. Each need has an associated **satisfaction level** (ranging from 0.0 to 1.0), where lower values indicate less satisfaction and higher urgency. When a satisfaction level drops below a certain **threshold**, the corresponding need becomes urgent and should be addressed.

### Types of Needs

Your needs are organized by priority, with lower priority numbers indicating higher urgency:

#### 1. **Satiety** (Priority 1 - Highest)
- **Meaning**: The need to eat food to satisfy your hunger
- **When it becomes urgent**: When `satiety` drops below the threshold (typically at meal times)
- **Can interrupt other plans**: Yes - This is a basic survival need that can interrupt any ongoing activity

#### 2. **Energy** (Priority 2)
- **Meaning**: The need to rest, sleep or do some leisure or relaxing activities to recover your energy
- **When it becomes urgent**: When `energy` drops below the threshold (typically at night or after prolonged activity)
- **Can interrupt other plans**: Yes - Fatigue can make it difficult to continue other activities effectively

#### 3. **Safety** (Priority 3)
- **Meaning**: The need to maintain or improve your safety level, such as by working, moving to a safe place, or maintaining financial security
- **When it becomes urgent**: When `safety` drops below the threshold (often related to income, currency, or physical safety)
- **Can interrupt other plans**: No - Safety needs are important but typically don't require immediate interruption of ongoing activities

#### 4. **Social** (Priority 4)
- **Meaning**: The need to satisfy your social needs, such as going out with friends, chatting with friends, or maintaining social relationships
- **When it becomes urgent**: When `social` drops below the threshold (often when you have few friends or haven't socialized recently)
- **Can interrupt other plans**: No - Social needs are important for well-being but can usually be planned for

#### 5. **Whatever** (Priority 5 - Lowest)
- **Meaning**: You have no specific urgent needs right now and can do whatever you want
- **When it applies**: When all other needs are satisfied above their thresholds
- **Can interrupt other plans**: No - This is a passive state
"""
