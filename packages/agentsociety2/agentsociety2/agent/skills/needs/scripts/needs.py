"""needs skill (subprocess mode).

执行方式: python needs.py --args-json '{"observation":"...","tick":1}'
在 agent workspace (cwd) 中读写 needs.json / current_need.txt。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import json_repair


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _load_or_init_needs(path: Path) -> dict[str, float]:
    if not path.exists():
        return {"satiety": 0.8, "energy": 0.8, "safety": 0.8, "social": 0.8}
    text = path.read_text(encoding="utf-8")
    data = json_repair.loads(text)
    return {
        "satiety": float(data.get("satiety", 0.8)),
        "energy": float(data.get("energy", 0.8)),
        "safety": float(data.get("safety", 0.8)),
        "social": float(data.get("social", 0.8)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--args-json", default="{}")
    ns = parser.parse_args()
    raw = ns.args_json or "{}"
    args = json_repair.loads(raw)

    cwd = Path.cwd()
    needs_path = cwd / "needs.json"
    current_need_path = cwd / "current_need.txt"
    needs = _load_or_init_needs(needs_path)
    obs = str(args.get("observation", "")).lower()

    # 极简启发式调整，避免把复杂逻辑写死在脚本里。
    needs["energy"] = _clamp(needs["energy"] - 0.03)
    needs["satiety"] = _clamp(needs["satiety"] - 0.02)
    if any(k in obs for k in ("hungry", "food", "eat", "meal")):
        needs["satiety"] = _clamp(needs["satiety"] + 0.15)
    if any(k in obs for k in ("sleep", "rest", "tired")):
        needs["energy"] = _clamp(needs["energy"] + 0.15)
    if any(k in obs for k in ("danger", "unsafe", "threat")):
        needs["safety"] = _clamp(needs["safety"] - 0.2)
    if any(k in obs for k in ("friend", "chat", "talk", "social")):
        needs["social"] = _clamp(needs["social"] + 0.1)

    thresholds = {"satiety": 0.2, "energy": 0.2, "safety": 0.2, "social": 0.3}
    urgency = {
        k: needs[k] - thresholds[k] for k in ("satiety", "energy", "safety", "social")
    }
    current_need = min(urgency.keys(), key=lambda k: urgency[k])

    needs_path.write_text(json.dumps(needs, ensure_ascii=False, indent=2), encoding="utf-8")
    current_need_path.write_text(current_need, encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "current_need": current_need,
                "needs": needs,
                "tick": args.get("tick"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
