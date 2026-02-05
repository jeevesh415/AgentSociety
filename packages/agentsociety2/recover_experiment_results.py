"""
从日志中恢复已完成实验的结果

使用方法：
1. 如果实验正在运行，按 Ctrl+C 中断
2. 运行此脚本：python recover_experiment_results.py <config_file> <console_log_file>
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

from agentsociety2.designer.exp_executor import ExperimentExecutor, ExperimentResult
from agentsociety2.mcp import CreateInstanceRequest
from datetime import datetime
import json_repair


def parse_console_log(log_file: Path) -> List[Dict[str, Any]]:
    """从控制台日志中解析已完成的实验信息"""
    completed_experiments = []
    
    if not log_file.exists():
        print(f"日志文件不存在: {log_file}")
        return completed_experiments
    
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # 解析日志行
    current_exp = None
    for line in lines:
        # 匹配实验开始：运行实验 X/18
        exp_start_match = re.search(r"运行实验 (\d+)/(\d+)", line)
        if exp_start_match:
            exp_num = int(exp_start_match.group(1))
            total = int(exp_start_match.group(2))
            current_exp = {
                "experiment_number": exp_num,
                "total": total,
                "experiment_name": None,
                "instance_id": None,
                "num_steps": None,
                "started_at": None,
                "completed_at": None,
            }
            continue
        
        if current_exp is None:
            continue
        
        # 匹配实验名称
        if current_exp["experiment_name"] is None:
            name_match = re.search(r"实验名称: (.+)", line)
            if name_match:
                current_exp["experiment_name"] = name_match.group(1).strip()
                continue
        
        # 匹配步数
        if current_exp["num_steps"] is None:
            steps_match = re.search(r"步数: (\d+)", line)
            if steps_match:
                current_exp["num_steps"] = int(steps_match.group(1))
                continue
        
        # 匹配Instance ID
        if current_exp["instance_id"] is None:
            instance_match = re.search(r"Instance ID: (.+)", line)
            if instance_match:
                current_exp["instance_id"] = instance_match.group(1).strip()
                continue
        
        # 匹配开始时间：开始运行实验: instance_id (...)
        if current_exp["started_at"] is None and current_exp["instance_id"]:
            start_match = re.search(
                rf"(\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}},\d{{3}}).*开始运行实验: {re.escape(current_exp['instance_id'])}",
                line
            )
            if start_match:
                time_str = start_match.group(1)
                try:
                    current_exp["started_at"] = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S,%f").isoformat()
                except:
                    pass
                continue
        
        # 匹配完成时间：实验 instance_id 完成
        if current_exp["completed_at"] is None and current_exp["instance_id"]:
            complete_match = re.search(
                rf"(\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}},\d{{3}}).*实验 {re.escape(current_exp['instance_id'])} 完成",
                line
            )
            if complete_match:
                time_str = complete_match.group(1)
                try:
                    current_exp["completed_at"] = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S,%f").isoformat()
                except:
                    pass
                # 实验完成，保存并重置
                if all([current_exp["experiment_name"], current_exp["instance_id"], current_exp["completed_at"]]):
                    completed_experiments.append(current_exp.copy())
                current_exp = None
                continue
    
    return completed_experiments


async def recover_results_from_instances(
    executor: ExperimentExecutor,
    completed_experiments: List[Dict[str, Any]],
    config_file: Path
) -> List[ExperimentResult]:
    """从MCP服务器恢复已完成实验的结果"""
    results = []
    
    # 加载配置文件以获取实验配置
    with open(config_file, "r", encoding="utf-8") as f:
        config_data = json_repair.loads(f.read())
    
    configs = config_data.get("configs", [])
    config_map = {c.get("instance_id"): c for c in configs}
    
    for exp_info in completed_experiments:
        instance_id = exp_info["instance_id"]
        exp_name = exp_info["experiment_name"]
        
        print(f"正在恢复实验: {exp_name} ({instance_id})...")
        
        # 获取配置
        config_entry = config_map.get(instance_id)
        if not config_entry:
            print(f"  警告: 未找到配置信息，跳过")
            continue
        
        # 创建结果对象
        num_steps = exp_info.get("num_steps") or config_entry.get("num_steps", 200)
        started_at = exp_info.get("started_at") or datetime.now().isoformat()
        completed_at = exp_info.get("completed_at") or datetime.now().isoformat()
        
        result = ExperimentResult(
            instance_id=instance_id,
            experiment_name=exp_name,
            hypothesis_index=config_entry.get("hypothesis_index", 0),
            group_index=config_entry.get("group_index", 0),
            experiment_index=config_entry.get("experiment_index", 0),
            status="completed",
            num_steps=num_steps,
            completed_steps=num_steps,
            started_at=started_at,
            completed_at=completed_at,
            logs=[
                {
                    "timestamp": started_at,
                    "event": "experiment_started",
                    "message": f"从日志恢复的实验",
                },
                {
                    "timestamp": completed_at,
                    "event": "experiment_completed",
                    "message": f"实验完成",
                },
            ],
        )
        
        # 尝试从MCP服务器获取实验结果
        try:
            status_result = await executor._call_mcp_tool(
                "get_instance_status", {"instance_id": instance_id}
            )
            if status_result.get("success"):
                result.final_status = status_result.get("status", {})
            
            results_response = await executor._call_mcp_tool(
                "get_experiment_results", {"instance_id": instance_id}
            )
            if results_response.get("success"):
                result.experiment_results = results_response.get("experiment_results", {})
        except Exception as e:
            print(f"  警告: 无法从MCP服务器获取结果: {e}")
        
        results.append(result)
        print(f"  ✓ 已恢复")
    
    return results


async def main():
    if len(sys.argv) < 3:
        print("使用方法: python recover_experiment_results.py <config_file> <console_log_file>")
        print("\n示例:")
        print("  python recover_experiment_results.py \\")
        print("    log/experiments/20251212/20251212_234556_我想研究声誉博弈_configs.json \\")
        print("    log/experiments/20251212_234556_263_console.log")
        sys.exit(1)
    
    config_file = Path(sys.argv[1])
    console_log_file = Path(sys.argv[2])
    
    if not config_file.exists():
        print(f"错误: 配置文件不存在: {config_file}")
        sys.exit(1)
    
    if not console_log_file.exists():
        print(f"错误: 日志文件不存在: {console_log_file}")
        sys.exit(1)
    
    print("=" * 80)
    print("从日志恢复已完成实验的结果")
    print("=" * 80)
    print(f"配置文件: {config_file}")
    print(f"日志文件: {console_log_file}")
    print()
    
    # 解析日志
    print("正在解析日志文件...")
    completed_experiments = parse_console_log(console_log_file)
    print(f"找到 {len(completed_experiments)} 个已完成的实验")
    
    if not completed_experiments:
        print("没有找到已完成的实验，退出。")
        sys.exit(0)
    
    print("\n已完成的实验:")
    for exp in completed_experiments:
        print(f"  {exp['experiment_number']}. {exp['experiment_name']} ({exp['instance_id']})")
    
    # 恢复结果
    print("\n正在从MCP服务器恢复实验结果...")
    executor = ExperimentExecutor()
    results = await recover_results_from_instances(executor, completed_experiments, config_file)
    
    if not results:
        print("没有成功恢复任何结果。")
        sys.exit(0)
    
    # 保存结果
    print(f"\n正在保存 {len(results)} 个实验结果...")
    json_file, log_file, console_log = executor.save_results(
        results, config_file=config_file
    )
    
    print("\n恢复完成！")
    print(f"  成功恢复: {len(results)} 个实验")
    print(f"  结果文件: {json_file}")
    if log_file:
        print(f"  详细日志: {log_file}")
    if console_log:
        print(f"  控制台日志: {console_log}")


if __name__ == "__main__":
    asyncio.run(main())

