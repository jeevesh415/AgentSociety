"""
测试脚本生成器

自动生成测试脚本来验证自定义模块的功能。
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List


class ScriptGenerator:
    """自动生成测试脚本"""

    def __init__(self, workspace_path: str):
        """
        初始化测试脚本生成器

        Args:
            workspace_path: 工作区路径
        """
        self.workspace_path = Path(workspace_path).resolve()

    def build_test_script(self, scan_result: Dict[str, Any]) -> str:
        """
        生成测试脚本代码

        Args:
            scan_result: 扫描结果，包含 agents 和 envs

        Returns:
            测试脚本代码字符串
        """
        agents = scan_result.get("agents", [])
        envs = scan_result.get("envs", [])

        script_lines = [
            '"""自动生成的自定义模块测试脚本',
            '',
            '此脚本由 AgentSociety2 自动生成，用于测试自定义模块。',
            '"""',
            '',
            'import asyncio',
            'import sys',
            'from pathlib import Path',
            'from datetime import datetime',
            '',
            '# 设置路径',
            'workspace_path = Path(r"{}")'.format(str(self.workspace_path)),
            'sys.path.insert(0, str(workspace_path))',
            'agentsociety_path = workspace_path / "packages/agentsociety2"',
            'if agentsociety_path.exists():',
            '    sys.path.insert(0, str(agentsociety_path))',
            '',
            '# 导入测试模块',
        ]

        # 添加导入语句
        agent_imports = []
        env_imports = []

        for agent in agents:
            module_path = agent.get("module_path", "").replace(".py", "").replace("/", ".")
            class_name = agent.get("class_name")
            agent_imports.append(f"from {module_path} import {class_name}")

        for env in envs:
            module_path = env.get("module_path", "").replace(".py", "").replace("/", ".")
            class_name = env.get("class_name")
            env_imports.append(f"from {module_path} import {class_name}")

        script_lines.extend(agent_imports)
        script_lines.extend(env_imports)

        if env_imports:
            script_lines.append('from agentsociety2.env.router_codegen import CodeGenRouter')

        script_lines.extend([
            '',
            '',
            'async def test_agents():',
            '    """测试自定义 Agent"""',
            '    print("=" * 50)',
            '    print("测试自定义 Agent")',
            '    print("=" * 50)',
            '',
        ])

        # 生成 Agent 测试代码
        for agent in agents:
            class_name = agent.get("class_name", "Unknown")
            script_lines.extend([
                f'    # 测试 {class_name}',
                f'    print("\\n--- 测试 {class_name} ---")',
                f'    try:',
                f'        agent = {class_name}(',
                f'            id=0,',
                f'            profile={{"name": "测试用户", "personality": "友好"}}',
                f'        )',
                f'        print("✓ {class_name} 创建成功")',
                f'',
                f'        if hasattr(agent, "mcp_description"):',
                f'            desc = agent.mcp_description()',
                f'            print(f"✓ mcp_description() 返回: {{len(desc)}} 字符")',
                f'',
                f'        if hasattr(agent, "ask"):',
                f'            print("✓ ask() 方法存在")',
                f'        if hasattr(agent, "step"):',
                f'            print("✓ step() 方法存在")',
                f'        if hasattr(agent, "dump"):',
                f'            print("✓ dump() 方法存在")',
                f'        if hasattr(agent, "load"):',
                f'            print("✓ load() 方法存在")',
                f'',
                f'        print(f"✓ {class_name} 基本测试通过\\n")',
                f'    except Exception as e:',
                f'        print(f"✗ {class_name} 测试失败: {{e}}\\n")',
                f'        import traceback',
                f'        traceback.print_exc()',
                '',
            ])

        script_lines.extend([
            '',
            'async def test_envs():',
            '"""测试自定义环境模块"""',
            '    print("=" * 50)',
            '    print("测试自定义环境模块")',
            '    print("=" * 50)',
            '',
        ])

        # 生成环境模块测试代码
        for env in envs:
            class_name = env.get("class_name", "Unknown")
            script_lines.extend([
                f'    # 测试 {class_name}',
                f'    print("\\n--- 测试 {class_name} ---")',
                f'    try:',
                f'        env = {class_name}()',
                f'        print("✓ {class_name} 创建成功")',
                f'',
                f'        if hasattr(env, "mcp_description"):',
                f'            desc = env.mcp_description()',
                f'            print(f"✓ mcp_description() 返回: {{len(desc)}} 字符")',
                f'',
                f'        if hasattr(env, "_registered_tools"):',
                f'            tools = env._registered_tools',
                f'            print(f"✓ 已注册 {{len(tools)}} 个工具")',
                f'            for tool_name in tools:',
                f'                print(f"  - {{tool_name}}")',
                f'',
                f'        if hasattr(env, "step"):',
                f'            print("✓ step() 方法存在")',
                f'',
                f'        print(f"✓ {class_name} 基本测试通过\\n")',
                f'    except Exception as e:',
                f'        print(f"✗ {class_name} 测试失败: {{e}}\\n")',
                f'        import traceback',
                f'        traceback.print_exc()',
                '',
            ])

        script_lines.extend([
            '',
            'async def test_integration():',
            '"""测试 Agent 与环境模块的集成"""',
            '    print("=" * 50)',
            '    print("测试 Agent 与环境集成")',
            '    print("=" * 50)',
            '',
        ])

        # 生成集成测试代码（如果有 Agent 和环境模块）
        if agents and envs:
            agent_class = agents[0].get("class_name")
            env_class = envs[0].get("class_name")
            script_lines.extend([
                f'    try:',
                f'        print("\\n--- 创建环境路由 ---")',
                f'        env = {env_class}()',
                f'        router = CodeGenRouter([env])',
                f'        print(f"✓ 路由创建成功")',
                f'',
                f'        print("\\n--- 创建 Agent ---")',
                f'        agent = {agent_class}(',
                f'            id=0,',
                f'            profile={{"name": "集成测试", "personality": "测试"}}',
                f'        )',
                f'        agent.set_env(router)',
                f'        print("✓ Agent 创建并设置环境")',
                f'',
                f'        print("\\n--- 测试环境查询 ---")',
                f'        try:',
                f'            response = await agent.ask_env(',
                f'                {{"variables": {{}}}},',
                f'                "请描述当前环境状态",',
                f'                readonly=True',
                f'            )',
                f'            print(f"✓ 环境查询成功: {{str(response)[:100]}}...")',
                f'        except Exception as e:',
                f'            print(f"⚠ 环境查询失败（可能需要 LLM 配置）: {{e}}")',
                f'',
                f'        print(f"✓ 集成测试通过\\n")',
                f'    except Exception as e:',
                f'        print(f"✗ 集成测试失败: {{e}}\\n")',
                f'        import traceback',
                f'        traceback.print_exc()',
                '',
            ])
        else:
            script_lines.extend([
                '    print("跳过集成测试（需要同时有 Agent 和环境模块）\\n")',
                '',
            ])

        script_lines.extend([
            '',
            'async def main():',
            '    """主测试函数"""',
            '    print("\\n" + "=" * 50)',
            '    print("开始测试自定义模块")',
            '    print("=" * 50 + "\\n")',
            '',
            '    await test_agents()',
            '    await test_envs()',
            '    await test_integration()',
            '',
            '    print("=" * 50)',
            '    print("测试完成！")',
            '    print("=" * 50)',
            '',
            '',
            'if __name__ == "__main__":',
            '    asyncio.run(main())',
            '',
        ])

        return "\n".join(script_lines)

    async def run_test(self, scan_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        保存并运行测试脚本

        Args:
            scan_result: 扫描结果

        Returns:
            测试结果字典
        """
        if not scan_result.get("agents") and not scan_result.get("envs"):
            return {
                "success": False,
                "error": "未发现任何自定义模块"
            }

        test_script = self.build_test_script(scan_result)
        test_file = self.workspace_path / "test_custom_module.py"

        try:
            # 写入测试脚本
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(test_script)

            # 运行测试脚本
            result = subprocess.run(
                [sys.executable, str(test_file)],
                capture_output=True,
                text=True,
                timeout=30,  # 30 秒超时
                cwd=str(self.workspace_path)
            )

            # 当测试失败时，将stderr作为error返回
            error_msg = None
            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else f"测试失败，返回码: {result.returncode}"

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "test_file": str(test_file),
                "returncode": result.returncode,
                "error": error_msg
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "测试超时（30秒）",
                "stdout": "",
                "test_file": str(test_file),
                "returncode": -1
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "test_file": str(test_file) if test_file.exists() else None,
                "returncode": -1
            }


# 导入 sys 以供 run_test 使用
import sys
