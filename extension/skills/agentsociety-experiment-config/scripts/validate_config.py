#!/usr/bin/env python3
"""实验配置验证脚本

通过实例化实际的 agent 类和环境模块来验证配置。
这是最严格的验证方式，确保配置可以真正运行。

Usage:
    python scripts/validate_config.py --hypothesis-id 1 --experiment-id 1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# 加载环境变量
workspace_root = Path(__file__).resolve().parents[4]
env_file = workspace_root / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)

# 添加 Python 路径
sys.path.insert(0, str(workspace_root / "packages" / "agentsociety2"))

from agentsociety2.logger import get_logger
from agentsociety2.society.models import InitConfig, StepsConfig
from agentsociety2.registry import (
    get_registered_env_modules,
    get_registered_agent_modules,
)

logger = get_logger()


class ConfigValidator:
    """配置验证器"""

    def __init__(self, workspace_path: Path):
        self.workspace_path = Path(workspace_path).resolve()
        self.logger = get_logger()

    def get_experiment_paths(
        self, hypothesis_id: str, experiment_id: str
    ) -> dict[str, Path]:
        """获取实验相关路径"""
        hyp_dir = self.workspace_path / f"hypothesis_{hypothesis_id}"
        exp_dir = hyp_dir / f"experiment_{experiment_id}"
        init_dir = exp_dir / "init"

        return {
            "workspace": self.workspace_path,
            "hypothesis": hyp_dir,
            "experiment": exp_dir,
            "init": init_dir,
            "sim_settings": hyp_dir / "SIM_SETTINGS.json",
            "init_config": init_dir / "init_config.json",
            "steps_yaml": init_dir / "steps.yaml",
        }

    def read_sim_settings(self, hyp_dir: Path) -> dict[str, Any]:
        """读取 SIM_SETTINGS.json"""
        sim_settings_file = hyp_dir / "SIM_SETTINGS.json"
        if sim_settings_file.exists():
            try:
                return json.loads(sim_settings_file.read_text(encoding="utf-8"))
            except Exception as e:
                self.logger.error(f"解析 SIM_SETTINGS.json 失败: {e}")
        return {}

    def validate_env_modules(
        self, init_config: InitConfig, env_module_types: list[str]
    ) -> dict[str, Any]:
        """验证环境模块配置"""
        try:
            env_type_map = {
                module_type: env_class
                for module_type, env_class in get_registered_env_modules()
            }

            validation_details = []
            errors = []

            for module_type in env_module_types:
                # 检查模块是否注册
                if module_type not in env_type_map:
                    available = list(env_type_map.keys())
                    errors.append(
                        f"环境模块类型 '{module_type}' 未注册。"
                        f"可用类型: {available}"
                    )
                    continue

                # 检查配置中是否包含此模块
                module_config = None
                for mc in init_config.env_modules:
                    if mc.module_type == module_type:
                        module_config = mc
                        break

                if module_config is None:
                    errors.append(
                        f"配置中缺少环境模块 '{module_type}'。"
                        f"已配置: {[m.module_type for m in init_config.env_modules]}"
                    )
                    continue

                env_class = env_type_map[module_type]
                module_kwargs = module_config.kwargs

                # 尝试实例化（最严格的验证）
                try:
                    instance = env_class(**module_kwargs)
                    validation_details.append({
                        "module_type": module_type,
                        "class": env_class.__name__,
                        "status": "ok",
                        "kwargs": module_kwargs,
                    })
                    self.logger.debug(
                        f"成功实例化环境模块 {module_type}: {env_class.__name__}"
                    )
                except Exception as e:
                    import traceback
                    errors.append(
                        f"环境模块 '{module_type}' ({env_class.__name__}) 实例化失败: {str(e)}"
                    )
                    return {
                        "success": False,
                        "errors": errors,
                        "details": [{
                            "module_type": module_type,
                            "class": env_class.__name__,
                            "error": str(e),
                            "kwargs": module_kwargs,
                            "traceback": traceback.format_exc(),
                        }],
                    }

            return {
                "success": len(errors) == 0,
                "errors": errors,
                "details": validation_details,
            }

        except Exception as e:
            self.logger.error(f"验证环境模块失败: {e}", exc_info=True)
            return {
                "success": False,
                "errors": [f"验证错误: {str(e)}"],
            }

    def validate_agents(
        self, init_config: InitConfig, agent_types: list[str]
    ) -> dict[str, Any]:
        """验证 agent 配置"""
        try:
            agent_type_map = {
                agent_type: agent_class
                for agent_type, agent_class in get_registered_agent_modules()
            }

            if not init_config.agents:
                return {
                    "success": False,
                    "errors": ["配置中没有 agents"],
                }

            # 验证第一个 agent 作为样本
            agent_config = init_config.agents[0]
            agent_type = agent_config.agent_type
            agent_id = agent_config.agent_id
            init_kwargs = agent_config.kwargs.copy()

            # 检查 agent 类型是否注册
            if agent_type not in agent_types:
                return {
                    "success": False,
                    "errors": [
                        f"Agent 类型 '{agent_type}' 不在 SIM_SETTINGS.json 的选择中。"
                        f"选择的类型: {agent_types}"
                    ],
                }

            if agent_type not in agent_type_map:
                available = list(agent_type_map.keys())
                return {
                    "success": False,
                    "errors": [
                        f"Agent 类型 '{agent_type}' 未注册。可用类型: {available}"
                    ],
                }

            agent_class = agent_type_map[agent_type]

            # 确保 id 字段存在且为整数
            if "id" not in init_kwargs:
                init_kwargs["id"] = int(agent_id)
            else:
                init_kwargs["id"] = int(init_kwargs["id"])

            # 尝试实例化
            try:
                instance = agent_class(**init_kwargs)
                self.logger.debug(
                    f"成功实例化 agent {agent_type} (id={agent_id}): "
                    f"{agent_class.__name__}"
                )
                return {
                    "success": True,
                    "details": {
                        "agent_type": agent_type,
                        "class": agent_class.__name__,
                        "agent_id": agent_id,
                        "status": "ok",
                        "total_agents": len(init_config.agents),
                    },
                }
            except Exception as e:
                import traceback
                return {
                    "success": False,
                    "errors": [
                        f"Agent '{agent_type}' (id={agent_id}, class={agent_class.__name__}) "
                        f"实例化失败: {str(e)}"
                    ],
                    "details": {
                        "agent_type": agent_type,
                        "class": agent_class.__name__,
                        "agent_id": agent_id,
                        "kwargs": init_kwargs,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    },
                }

        except Exception as e:
            self.logger.error(f"验证 agents 失败: {e}", exc_info=True)
            return {
                "success": False,
                "errors": [f"验证错误: {str(e)}"],
            }

    def validate(
        self, hypothesis_id: str, experiment_id: str
    ) -> dict[str, Any]:
        """验证实验配置"""
        paths = self.get_experiment_paths(hypothesis_id, experiment_id)

        # 检查假设目录
        if not paths["hypothesis"].exists():
            return {
                "success": False,
                "errors": [f"假设目录不存在: {paths['hypothesis']}"],
                "stage": "hypothesis_exists",
            }

        # 检查实验目录
        if not paths["experiment"].exists():
            return {
                "success": False,
                "errors": [f"实验目录不存在: {paths['experiment']}"],
                "stage": "experiment_exists",
            }

        # 读取 SIM_SETTINGS.json
        sim_settings = self.read_sim_settings(paths["hypothesis"])
        agent_types = sim_settings.get("agentClasses", [])
        env_module_types = sim_settings.get("envModules", [])

        if not agent_types:
            return {
                "success": False,
                "errors": ["SIM_SETTINGS.json 中未选择 agent 类型"],
                "stage": "sim_settings",
            }

        if not env_module_types:
            return {
                "success": False,
                "errors": ["SIM_SETTINGS.json 中未选择环境模块"],
                "stage": "sim_settings",
            }

        # 检查 init_config.json
        if not paths["init_config"].exists():
            return {
                "success": False,
                "errors": [f"init_config.json 不存在: {paths['init_config']}"],
                "stage": "init_config_exists",
            }

        # 加载并验证 init_config.json
        try:
            config_data = json.loads(paths["init_config"].read_text(encoding="utf-8"))
            init_config = InitConfig.model_validate(config_data)
        except Exception as e:
            return {
                "success": False,
                "errors": [f"init_config.json 加载失败: {str(e)}"],
                "stage": "init_config_parse",
            }

        # 检查 steps.yaml
        if not paths["steps_yaml"].exists():
            return {
                "success": False,
                "errors": [f"steps.yaml 不存在: {paths['steps_yaml']}"],
                "stage": "steps_yaml_exists",
            }

        # 验证 steps.yaml
        try:
            import yaml
            steps_data = yaml.safe_load(paths["steps_yaml"].read_text(encoding="utf-8"))
            steps_config = StepsConfig.model_validate(steps_data)
        except Exception as e:
            return {
                "success": False,
                "errors": [f"steps.yaml 验证失败: {str(e)}"],
                "stage": "steps_yaml_parse",
            }

        # 验证环境模块
        env_result = self.validate_env_modules(init_config, env_module_types)
        if not env_result["success"]:
            return {
                "success": False,
                "errors": env_result.get("errors", []),
                "stage": "env_module_validation",
                "details": env_result.get("details", []),
            }

        # 验证 agents
        agent_result = self.validate_agents(init_config, agent_types)
        if not agent_result["success"]:
            return {
                "success": False,
                "errors": agent_result.get("errors", []),
                "stage": "agent_validation",
                "details": agent_result.get("details", {}),
            }

        # 所有验证通过
        return {
            "success": True,
            "message": "配置验证成功！",
            "summary": {
                "hypothesis_id": hypothesis_id,
                "experiment_id": experiment_id,
                "env_modules": env_module_types,
                "agent_types": agent_types,
                "env_modules_count": len(init_config.env_modules),
                "agents_count": len(init_config.agents),
                "init_config": str(paths["init_config"]),
                "steps_yaml": str(paths["steps_yaml"]),
                "start_t": steps_config.start_t,
                "steps_count": len(steps_config.steps),
            },
            "env_validation": env_result.get("details", []),
            "agent_validation": agent_result.get("details", {}),
        }


def main():
    parser = argparse.ArgumentParser(
        description="验证实验配置（通过实例化实际类）"
    )
    parser.add_argument("--hypothesis-id", required=True, help="假设 ID")
    parser.add_argument("--experiment-id", required=True, help="实验 ID")
    parser.add_argument("--workspace", default=".", help="工作空间路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    workspace_path = Path(args.workspace).resolve()
    validator = ConfigValidator(workspace_path)

    result = validator.validate(args.hypothesis_id, args.experiment_id)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["success"]:
            print("✓ " + result.get("message", "验证成功"))
            print()
            print("摘要:")
            summary = result.get("summary", {})
            print(f"  假设: {summary.get('hypothesis_id')}")
            print(f"  实验: {summary.get('experiment_id')}")
            print(f"  环境模块: {', '.join(summary.get('env_modules', []))}")
            print(f"  Agent 类型: {', '.join(summary.get('agent_types', []))}")
            print(f"  环境模块数: {summary.get('env_modules_count', 0)}")
            print(f"  Agent 数: {summary.get('agents_count', 0)}")
            print(f"  开始时间: {summary.get('start_t', '')}")
            print(f"  步骤数: {summary.get('steps_count', 0)}")
            print(f"  配置文件: {summary.get('init_config', '')}")
            print(f"  步骤文件: {summary.get('steps_yaml', '')}")

            if args.verbose:
                print()
                print("环境模块验证详情:")
                for detail in result.get("env_validation", []):
                    print(f"  - {detail['module_type']} ({detail['class']}): {detail['status']}")

                print()
                print("Agent 验证详情:")
                agent_detail = result.get("agent_validation", {})
                print(f"  - {agent_detail.get('agent_type')} ({agent_detail.get('class')}): "
                      f"{agent_detail.get('status')} (总数: {agent_detail.get('total_agents', 0)})")
            return 0
        else:
            print("✗ 验证失败")
            print()
            print(f"阶段: {result.get('stage', 'unknown')}")
            print("错误:")
            for e in result.get("errors", []):
                print(f"  ✗ {e}")

            if args.verbose and "details" in result:
                print()
                print("错误详情:")
                details = result["details"]
                if isinstance(details, list):
                    for d in details:
                        for k, v in d.items():
                            if k != "traceback":
                                print(f"  {k}: {v}")
                elif isinstance(details, dict):
                    for k, v in details.items():
                        if k != "traceback":
                            print(f"  {k}: {v}")
                if isinstance(details, list) and details and "traceback" in details[0] and args.verbose:
                    print()
                    print("Traceback:")
                    print(details[0]["traceback"])
                elif isinstance(details, dict) and "traceback" in details and args.verbose:
                    print()
                    print("Traceback:")
                    print(details["traceback"])
            return 1


if __name__ == "__main__":
    sys.exit(main())
