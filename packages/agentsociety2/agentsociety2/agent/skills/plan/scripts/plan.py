"""plan skill — 意图 → 计划生成 → ReAct 执行"""

from __future__ import annotations
from typing import Any


async def run(agent: Any, ctx: dict[str, Any]) -> None:
    from agentsociety2.agent.models import PlanStepStatus

    step_log: list[str] = ctx["step_log"]

    if not agent._intention:
        step_log.append("Plan: skipped (no intention)")
        return

    step_log.append(f"SelectedIntention: {agent._intention.intention}")

    # 检查活跃计划中当前 step 的完成情况
    if agent._plan and not agent._plan.completed and not agent._plan.failed:
        idx = agent._plan.index
        if idx < len(agent._plan.steps):
            cur = agent._plan.steps[idx]
            if cur.status == PlanStepStatus.IN_PROGRESS:
                status = await agent._check_step_completion(cur)
                cur.status = status
                if status == PlanStepStatus.COMPLETED:
                    if idx + 1 < len(agent._plan.steps):
                        agent._plan.index = idx + 1
                    else:
                        agent._plan.completed = True
                        agent._plan.end_time = agent._t
                        await agent._emotion_update_for_plan(agent._plan, completed=True)
                    step_log.append(f"Step {idx} completed")
                elif status == PlanStepStatus.FAILED:
                    cur.status = PlanStepStatus.FAILED
                    agent._plan.failed = True
                    agent._plan.end_time = agent._t
                    await agent._emotion_update_for_plan(agent._plan, completed=False)
                    step_log.append(f"Step {idx} failed")
                else:
                    step_log.append(f"Step {idx} in progress, waiting")

    # 判定是否中断计划
    if agent._plan and not agent._plan.completed and not agent._plan.failed:
        if await agent._should_interrupt_plan():
            step_log.append("Plan interrupted")
            agent._plan = None

    # 无活跃计划则生成新计划
    if agent._plan is None or agent._plan.completed or agent._plan.failed:
        await agent._generate_plan_from_intention(agent._intention)
        step_log.append(f"PlanGen: {agent._plan.target if agent._plan else 'N/A'}")

    # 执行计划步骤
    if not (agent._plan and not agent._plan.completed and not agent._plan.failed):
        return

    idx = agent._plan.index
    if idx >= len(agent._plan.steps):
        return

    cur = agent._plan.steps[idx]
    if cur.status == PlanStepStatus.IN_PROGRESS:
        step_log.append(f"Step {idx} in progress, waiting")
        return

    step_status, step_acts = await agent._step_execution()
    agent._current_step_acts.extend(step_acts)
    step_log.append(f"StepExec: {step_status.value}")

    if step_status == PlanStepStatus.IN_PROGRESS:
        step_log.append("Stopped: step in progress")
        return

    # 当前步骤完成后继续执行后续步骤
    if step_status == PlanStepStatus.COMPLETED:
        while (
            agent._plan
            and not agent._plan.completed
            and not agent._plan.failed
            and agent._plan.index < len(agent._plan.steps)
        ):
            ns, na = await agent._step_execution()
            agent._current_step_acts.extend(na)
            step_log.append(f"StepExec: {ns.value}")
            if ns == PlanStepStatus.IN_PROGRESS:
                step_log.append("Stopped: step in progress")
                break
            if ns == PlanStepStatus.FAILED:
                break
