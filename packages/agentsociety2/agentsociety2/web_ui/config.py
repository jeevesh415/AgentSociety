# This file acts as a registry for all runnable experiments.
# The main app.py will read this file to dynamically build the UI and commands.

EXPERIMENTS = [
    {
        "name": "UI Features Demo",
        "commands": ["demo", "start"],
        "module_path": "demo_main",
        "function_name": "main",
        "description": "Showcase advanced UI features like buttons, images, and file downloads.",
    },
    {
        "name": "智能实验 Workflow 设计",
        "commands": ["workflow", "testworkflow", "wf"],
        "module_path": "testworkflow_main",
        "function_name": "main",
        "description": "根据用户实验想法，使用LLM生成实验参数配置，并通过交互式确认和调整完善配置。",
    },
    # To add a new experiment, simply add a new dictionary here following the same structure.
]
