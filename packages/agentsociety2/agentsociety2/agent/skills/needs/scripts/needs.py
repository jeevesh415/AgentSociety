"""needs skill (subprocess mode).

执行方式: python needs.py --args-json '{"observation":"...","tick":1}'
在 agent workspace (cwd) 中读写 needs.json / current_need.txt。

支持的逻辑：
1. 自然衰减：satiety -0.02, energy -0.03 per tick
2. 关键词触发调整
3. 阈值判定
4. 优先级排序
5. 中断规则判断
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import json_repair


# 默认阈值（与旧版Agent一致）
DEFAULT_THRESHOLDS = {
    "satiety": 0.2,  # T_H: 饥饿阈值
    "energy": 0.2,   # T_D: 能量阈值
    "safety": 0.2,   # T_P: 安全阈值
    "social": 0.3,   # T_C: 社交阈值
}

# 默认初始满意度（与旧版Agent一致）
DEFAULT_SATISFACTIONS = {
    "satiety": 0.7,  # 饱足感初始值
    "energy": 0.3,   # 能量初始值
    "safety": 0.9,   # 安全初始值
    "social": 0.8,   # 社交初始值
}

# 自然衰减率
DECAY_RATES = {
    "satiety": 0.02,
    "energy": 0.03,
    "safety": 0.0,   # 安全不自然衰减
    "social": 0.0,   # 社交不自然衰减
}

# 需求优先级（数字越小优先级越高）
NEED_PRIORITY = {
    "satiety": 1,
    "energy": 2,
    "safety": 3,
    "social": 4,
    "whatever": 5,
}

# 中断规则：哪些需求可以中断当前计划
CAN_INTERRUPT = {
    "satiety": True,   # 饥饿可以中断任何活动
    "energy": True,    # 疲劳可以中断任何活动
    "safety": False,   # 安全需求不会立即中断
    "social": False,   # 社交需求不会立即中断
    "whatever": False, # whatever不中断
}


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _load_or_init_needs(path: Path) -> dict[str, float]:
    """加载或初始化需求满意度。使用与旧版Agent一致的默认值。"""
    if not path.exists():
        return DEFAULT_SATISFACTIONS.copy()
    text = path.read_text(encoding="utf-8")
    data = json_repair.loads(text)
    return {
        "satiety": float(data.get("satiety", DEFAULT_SATISFACTIONS["satiety"])),
        "energy": float(data.get("energy", DEFAULT_SATISFACTIONS["energy"])),
        "safety": float(data.get("safety", DEFAULT_SATISFACTIONS["safety"])),
        "social": float(data.get("social", DEFAULT_SATISFACTIONS["social"])),
    }


def _load_thresholds(path: Path) -> dict[str, float]:
    """加载阈值配置。"""
    if not path.exists():
        return DEFAULT_THRESHOLDS.copy()
    text = path.read_text(encoding="utf-8")
    data = json_repair.loads(text)
    thresholds = data.get("thresholds", {})
    return {
        "satiety": float(thresholds.get("satiety", DEFAULT_THRESHOLDS["satiety"])),
        "energy": float(thresholds.get("energy", DEFAULT_THRESHOLDS["energy"])),
        "safety": float(thresholds.get("safety", DEFAULT_THRESHOLDS["safety"])),
        "social": float(thresholds.get("social", DEFAULT_THRESHOLDS["social"])),
    }


def _apply_natural_decay(needs: dict[str, float]) -> None:
    """应用自然衰减。"""
    for need_type, rate in DECAY_RATES.items():
        if rate > 0:
            needs[need_type] = _clamp(needs[need_type] - rate)


def _apply_observation_adjustments(needs: dict[str, float], obs: str) -> list[dict]:
    """根据观察文本调整需求，返回调整记录列表。"""
    adjustments = []
    obs_lower = obs.lower()

    # 进食相关
    if any(k in obs_lower for k in ("hungry", "food", "eat", "meal", "restaurant", "cafe", "lunch", "dinner", "breakfast")):
        old = needs["satiety"]
        needs["satiety"] = _clamp(needs["satiety"] + 0.15)
        adjustments.append({"need_type": "satiety", "adjustment_type": "increase", "old": old, "new": needs["satiety"], "reason": "Detected food/eating related content"})

    # 休息相关
    if any(k in obs_lower for k in ("sleep", "rest", "tired", "bed", "home", "relax")):
        old = needs["energy"]
        needs["energy"] = _clamp(needs["energy"] + 0.15)
        adjustments.append({"need_type": "energy", "adjustment_type": "increase", "old": old, "new": needs["energy"], "reason": "Detected rest/sleep related content"})

    # 危险相关
    if any(k in obs_lower for k in ("danger", "unsafe", "threat", "attack", "rob", "hurt", "injury")):
        old = needs["safety"]
        needs["safety"] = _clamp(needs["safety"] - 0.2)
        adjustments.append({"need_type": "safety", "adjustment_type": "decrease", "old": old, "new": needs["safety"], "reason": "Detected danger related content"})

    # 社交相关
    if any(k in obs_lower for k in ("friend", "chat", "talk", "social", "conversation", "meet", "party", "together")):
        old = needs["social"]
        needs["social"] = _clamp(needs["social"] + 0.1)
        adjustments.append({"need_type": "social", "adjustment_type": "increase", "old": old, "new": needs["social"], "reason": "Detected social interaction content"})

    # 工作相关（消耗能量）
    if any(k in obs_lower for k in ("work", "job", "busy", "task", "project", "deadline")):
        old = needs["energy"]
        needs["energy"] = _clamp(needs["energy"] - 0.05)
        adjustments.append({"need_type": "energy", "adjustment_type": "decrease", "old": old, "new": needs["energy"], "reason": "Detected work related content"})

    # 安全环境
    if any(k in obs_lower for k in ("safe", "secure", "home", "protected")):
        old = needs["safety"]
        needs["safety"] = _clamp(needs["safety"] + 0.1)
        adjustments.append({"need_type": "safety", "adjustment_type": "increase", "old": old, "new": needs["safety"], "reason": "Detected safe environment content"})

    return adjustments


def _determine_current_need(needs: dict[str, float], thresholds: dict[str, float]) -> str:
    """
    根据阈值和优先级确定当前最紧迫的需求。

    规则：
    1. 按优先级顺序检查每个需求（satiety > energy > safety > social）
    2. 如果需求值 <= 阈值，则该需求紧迫
    3. 返回优先级最高的紧迫需求
    4. 如果没有紧迫需求，返回 "whatever"
    """
    # 按优先级顺序检查（优先级越低越紧急）
    for need_type in ["satiety", "energy", "safety", "social"]:
        if needs[need_type] <= thresholds[need_type]:
            return need_type

    return "whatever"


def _should_interrupt_plan(current_need: str, needs: dict[str, float], thresholds: dict[str, float]) -> bool:
    """
    判断当前需求是否应该中断正在执行的计划。

    中断规则：
    - satiety (饥饿): 可以中断任何活动（基本生存需求）
    - energy (疲劳): 可以中断任何活动（无法有效继续）
    - safety: 不会立即中断，但需要被考虑
    - social: 不会立即中断
    """
    if current_need == "whatever":
        return False

    # 检查该需求是否可以中断
    if CAN_INTERRUPT.get(current_need, False):
        # 检查需求是否确实紧迫（低于阈值）
        if needs[current_need] <= thresholds[current_need]:
            return True

    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--args-json", default="{}")
    ns = parser.parse_args()
    raw = ns.args_json or "{}"
    args = json_repair.loads(raw)

    cwd = Path.cwd()
    needs_path = cwd / "needs.json"
    current_need_path = cwd / "current_need.txt"

    # 加载当前需求状态
    needs = _load_or_init_needs(needs_path)
    thresholds = _load_thresholds(needs_path)

    # 获取观察文本
    obs = str(args.get("observation", ""))

    # 1. 应用自然衰减
    _apply_natural_decay(needs)

    # 2. 根据观察调整需求
    adjustments = _apply_observation_adjustments(needs, obs)

    # 3. 确定当前最紧迫的需求
    current_need = _determine_current_need(needs, thresholds)

    # 4. 判断是否应该中断当前计划
    should_interrupt = _should_interrupt_plan(current_need, needs, thresholds)

    # 构建输出数据
    output_needs = {
        **needs,
        "current_need": current_need,
        "thresholds": thresholds,
        "can_interrupt": CAN_INTERRUPT,
        "should_interrupt_plan": should_interrupt,
    }

    # 写入文件
    needs_path.write_text(json.dumps(output_needs, ensure_ascii=False, indent=2), encoding="utf-8")
    current_need_path.write_text(current_need, encoding="utf-8")

    # 输出结果
    print(
        json.dumps(
            {
                "ok": True,
                "current_need": current_need,
                "needs": needs,
                "thresholds": thresholds,
                "adjustments": adjustments,
                "should_interrupt_plan": should_interrupt,
                "tick": args.get("tick"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
