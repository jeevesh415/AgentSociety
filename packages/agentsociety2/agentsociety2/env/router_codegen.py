"""
Code Generation Router Implementation
通过代码生成的方式调用环境模块中的@tool标记的接口
"""

import ast
import asyncio
import inspect
import json
import math
import os
import pickle
import random
import re
import sys
from datetime import datetime
from io import StringIO
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from agentsociety2.storage import ReplayWriter

import numpy as np
from agentsociety2.env.base import EnvBase
from agentsociety2.env.benchmark import (
    EnvRouterBenchmarkData,
)
from agentsociety2.env.router_base import RouterBase
from agentsociety2.logger import get_logger
from litellm import AllMessageValues

__all__ = ["CodeGenRouter"]


def _get_debug_info(description: str = "") -> str:
    """获取当前文件、行号和阶段描述的调试信息"""
    frame = inspect.currentframe()
    if frame and frame.f_back:
        caller_frame = frame.f_back
        filename = os.path.basename(caller_frame.f_code.co_filename)
        lineno = caller_frame.f_lineno
        return f"[{filename}:{lineno}] {description}"
    return description


class CodeGenRouter(RouterBase):
    """
    代码生成式Router：通过生成Python代码的方式调用环境模块中的@tool标记的接口。

    工作流程：
    1. 收集所有环境模块的工具信息
    2. 使用类似 pyi 文件的 Python 代码格式向LLM提供环境模块描述和工具信息
       （包含 pydantic BaseModel 定义和模块类定义）
    3. LLM生成Python代码来调用工具
    4. 使用AST解析检查代码安全性
    5. 通过compile和exec执行代码，捕获打印输出
    6. 根据执行结果和打印输出生成最终响应
    """

    # 允许的内置函数
    ALLOWED_BUILTINS = {
        "print",
        "len",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "dict",
        "tuple",
        "set",
        "range",
        "enumerate",
        "zip",
        "min",
        "max",
        "sum",
        "abs",
        "round",
        "sorted",
        "reversed",
        "any",
        "all",
        "isinstance",
        "type",
        "getattr",
        "hasattr",
        "dir",
    }

    # 禁止的AST节点类型（黑名单）
    FORBIDDEN_AST_NODES = {
        ast.ClassDef,  # 禁止定义类
        ast.Delete,  # 禁止del语句
        ast.Global,
        ast.Nonlocal,  # 禁止全局/非局部变量声明
        ast.With,
        ast.AsyncWith,  # 禁止with语句
        ast.Assert,  # 禁止assert
    }

    # 允许导入的模块白名单
    ALLOWED_MODULES = {
        "collections",
        "itertools",
        "functools",
        "operator",
        "copy",
        "decimal",
        "fractions",
        "statistics",
        "string",
        "re",
        "datetime",
        "json",
        "math",
        "random",
        "numpy",
        "np",  # numpy的别名
    }

    # 危险模块列表
    DANGEROUS_MODULES = {
        "os",
        "sys",
        "subprocess",
        "shutil",
        "pickle",
        "marshal",
        "ctypes",
        "socket",
        "urllib",
        "http",
        "ftplib",
        "smtplib",
        "__builtin__",
        "__builtins__",
        "builtins",
    }

    OBSERVE_INSTRUCTION = "Collect environment observations by calling all available observe tools. For tools that require agent parameters (like agent_id, id, or person_id), extract the agent ID from the ctx dictionary. Store all observation results in results['observations']."
    STATISTICS_INSTRUCTION = "Collect environment statistics by calling all available statistics tools. Store all statistics results in results['statistics']."

    def __init__(
        self,
        env_modules: list[EnvBase],
        max_body_code_lines: int = 10,
        max_steps: int = 10,
        max_llm_call_retry: int = 3,
        log_path: str = "logs/instruction_log.pkl",
        replay_writer: Optional["ReplayWriter"] = None,
    ):
        super().__init__(
            env_modules=env_modules,
            max_steps=max_steps,
            max_llm_call_retry=max_llm_call_retry,
            replay_writer=replay_writer,
        )

        # Pre-generate all tools pyi code in a dictionary: key is (readonly, kind)
        # kind can be None, "observe", "statistics", etc.
        self._tools_pyi_dict: Dict[Tuple[bool, str | None], str] = {}
        self._log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        # Collect all tools info once
        all_tools_info = self._collect_tools_info()

        # Generate writable tools pyi code (kind=None)
        all_tools_info = self._filter_tools_info(
            all_tools_info, readonly=None, kind=None
        )
        self._tools_pyi_dict[(False, None)] = self._format_tools_pyi(
            all_tools_info, max_body_code_lines
        )

        # Generate readonly tools pyi code (kind=None)
        readonly_tools_info = self._filter_tools_info(
            all_tools_info, readonly=True, kind=None
        )
        self._tools_pyi_dict[(True, None)] = self._format_tools_pyi(
            readonly_tools_info, max_body_code_lines
        )

        # Generate readonly observe tools pyi code
        readonly_observe_tools_info = self._filter_tools_info(
            all_tools_info, readonly=True, kind="observe"
        )
        self._tools_pyi_dict[(True, "observe")] = self._format_tools_pyi(
            readonly_observe_tools_info, max_body_code_lines
        )

        # Generate readonly statistics tools pyi code
        readonly_statistics_tools_info = self._filter_tools_info(
            all_tools_info, readonly=True, kind="statistics"
        )
        self._tools_pyi_dict[(True, "statistics")] = self._format_tools_pyi(
            readonly_statistics_tools_info, max_body_code_lines
        )

        self._modules = {module.name: module for module in self.env_modules}

        # Code will be generated using LLM in init method
        self._observe_code = ""
        self._statistics_code = ""

        # Flag to track if LLM code generation has been attempted
        self._llm_code_generated = False

        # 记录所有agent的指令、context和生成的代码
        self._instruction_log: List[EnvRouterBenchmarkData] = []
        self._instruction_log_lock: asyncio.Lock = asyncio.Lock()

    async def ask(
        self, ctx: dict, instruction: str, readonly: bool = False
    ) -> Tuple[dict, str]:
        """
        使用代码生成方式处理指令。

        Args:
            ctx: 上下文字典
            instruction: 指令字符串
            readonly: 是否只读模式

        Returns:
            (ctx, answer) 元组
        """
        # 添加当前时间信息到 ctx，以便生成的代码可以访问
        self._add_current_time_to_ctx(ctx)

        get_logger().debug(
            f"{_get_debug_info('开始处理指令')} - instruction: {instruction}, readonly: {readonly}, ctx: {ctx}"
        )

        await self._log_instruction(
            instruction=instruction,
            context=ctx,
            readonly=readonly,
        )

        if not self.env_modules:
            get_logger().warning("No environment modules available")
            return (
                ctx,
                "No environment modules available to handle the request.",
            )

        pre_generated_code = None

        # 检测特殊指令：<observe> 和 <statistics>
        instruction_stripped = instruction.strip()
        if instruction_stripped == "<observe>":
            pre_generated_code = self._observe_code
            instruction = self.OBSERVE_INSTRUCTION
        elif instruction_stripped == "<statistics>":
            pre_generated_code = self._statistics_code
            instruction = self.STATISTICS_INSTRUCTION

        # 重试循环
        retry_count = 0
        previous_code = None
        previous_errors = []
        dialog_history: List[AllMessageValues] = []  # 维护对话历史

        get_logger().debug(
            f"{_get_debug_info('开始代码生成重试循环')} - max_retries: {self.max_llm_call_retry}"
        )

        while retry_count <= (
            self.max_llm_call_retry if pre_generated_code is None else 0
        ):
            if not pre_generated_code:
                get_logger().debug(
                    f"{_get_debug_info('构建代码生成prompt')} - retry_count: {retry_count}, has_previous_code: {previous_code is not None}, previous_errors_count: {len(previous_errors) if previous_errors else 0}"
                )

                # 构建代码生成提示词（第一次调用时构建，重试时不再构建）
                if retry_count == 0:
                    prompt = self._build_codegen_prompt(
                        instruction, ctx, readonly, None
                    )
                    # 第一次调用，初始化对话历史
                    dialog_history = [{"role": "user", "content": prompt}]
                else:
                    # 重试时，将之前的代码作为assistant消息添加到对话历史
                    if previous_code:
                        dialog_history.append(
                            {"role": "assistant", "content": previous_code}
                        )
                    # 构建错误信息并添加到对话历史
                    error_message = self._build_error_message(previous_errors)
                    dialog_history.append({"role": "user", "content": error_message})

                get_logger().debug(
                    f"{_get_debug_info('prompt构建完成')} - dialog_history length: {len(dialog_history)}"
                )

                # 调用LLM生成代码（使用多轮对话）
                code = await self._generate_code(dialog_history)
                get_logger().info("--------------------------------")
                get_logger().info(
                    f"[Attempt {retry_count + 1}/{self.max_llm_call_retry + 1}] Generated code:"
                )
                get_logger().info(code)
                get_logger().info("--------------------------------")

                if not code:
                    if retry_count < self.max_llm_call_retry:
                        retry_count += 1
                        error_msg = "Failed to generate code from LLM."
                        previous_errors.append(error_msg)
                        previous_code = None  # 没有生成代码，所以previous_code为None
                        get_logger().warning(
                            f"Failed to generate code, retrying ({retry_count}/{self.max_llm_call_retry})..."
                        )
                        continue
                    return {}, "Failed to generate code after retries."

                # 将生成的代码添加到对话历史（作为assistant消息）
                dialog_history.append({"role": "assistant", "content": code})

                # 验证代码安全性
                get_logger().debug(
                    f"{_get_debug_info('开始验证代码安全性')} - code length: {len(code)}"
                )
                is_safe, safety_violation = self._validate_code_safety(code)
                get_logger().debug(
                    f"{_get_debug_info('代码安全性验证完成')} - is_safe: {is_safe}, violation: {safety_violation if not is_safe else 'None'}"
                )
                if not is_safe:
                    if retry_count < self.max_llm_call_retry:
                        retry_count += 1
                        previous_code = code
                        previous_errors.append(safety_violation)
                        get_logger().warning(
                            f"Code failed safety check, retrying ({retry_count}/{self.max_llm_call_retry})..."
                        )
                        continue
                    return (
                        {},
                        f"Generated code failed safety check after retries: {safety_violation}",
                    )
            else:
                code = pre_generated_code

            # 执行代码
            get_logger().debug(
                f"{_get_debug_info('准备执行生成的代码')} - code length: {len(code)}, readonly: {readonly}"
            )
            try:
                execution_result = await self._execute_code(code, ctx, readonly)
                get_logger().debug(
                    f"{_get_debug_info('代码执行完成')} - success: {execution_result.get('success', False)}"
                )

                # 检查执行是否成功
                if not execution_result.get("success", False):
                    error = execution_result.get("error", "Unknown error")
                    if retry_count < self.max_llm_call_retry:
                        retry_count += 1
                        previous_code = code  # 代码已经在对话历史中了
                        previous_errors.append(error)
                        get_logger().warning(
                            f"Code execution failed: {error}, retrying ({retry_count}/{self.max_llm_call_retry})..."
                        )
                        continue
                    else:
                        return (
                            ctx,
                            f"Code execution failed after retries: {error}",
                        )

                # 执行成功，检查返回的status
                print_outputs = execution_result.get("print_outputs", [])
                results = execution_result.get("results", {})
                status = results.get("status", "unknown")
                error = execution_result.get("error", "")

                get_logger().debug(
                    f"{_get_debug_info('代码执行成功，检查status')} - status: {status}, print_outputs_count: {len(print_outputs)}"
                )

                # 构建过程文本
                process_text = "\n".join(print_outputs) if print_outputs else "无输出"
                if error:
                    process_text += f"\n\nError: {error}"
                process_text = f"```\n{process_text}\n```"

                # 根据执行结果和打印输出生成最终响应
                final_answer, determined_status = await self.generate_final_answer(
                    ctx, instruction, results, process_text, status, error
                )
                results["status"] = determined_status

                get_logger().debug(
                    f"{_get_debug_info('最终答案生成完成')} - answer length: {len(final_answer)}, status: {status}"
                )

                # 如果status是unknown，说明LLM没有正确设置status，视为执行失败
                if determined_status == "unknown":
                    get_logger().warning(
                        f"{_get_debug_info('警告：LLM代码没有设置status')} - 生成的代码未设置results['status']，将视为执行失败"
                    )
                    determined_status = "fail"
                    results["status"] = "fail"
                    results["reason"] = (
                        "Generated code did not set results['status'], which is mandatory"
                    )

                return results, final_answer

            except Exception as e:
                error_msg = str(e)
                if retry_count < self.max_llm_call_retry:
                    retry_count += 1
                    previous_code = code  # 代码已经在对话历史中了
                    previous_errors.append(error_msg)
                    get_logger().warning(
                        f"Code execution exception: {error_msg}, retrying ({retry_count}/{self.max_llm_call_retry})..."
                    )
                    continue
                else:
                    get_logger().error(
                        f"Code execution failed after retries: {error_msg}"
                    )
                    return (
                        {},
                        f"Code execution failed after retries: {error_msg}",
                    )

        # 理论上不应该到达这里
        return {}, "Failed to generate and execute code after all retries."

    async def _clean_coroutines_from_results(self, results: dict) -> dict:
        """
        递归检查results中的所有内容，找到未被await的coroutine对象，并await获取其值。
        这是一个后处理函数，用于清理LLM生成代码中可能遗留的coroutine对象。

        Args:
            results: 执行结果字典

        Returns:
            清理后的results字典，所有coroutine都被await并转换为实际值
        """

        visited = set()  # 跟踪已访问的对象ID，避免循环引用导致的无限递归

        async def clean_value(value: Any) -> Any:
            """递归清理单个值"""
            # 如果是coroutine，await它
            if inspect.iscoroutine(value):
                get_logger().debug(f"Found unawaited coroutine, awaiting it: {value}")
                try:
                    return await value
                except Exception as e:
                    get_logger().warning(
                        f"Failed to await coroutine: {str(e)}, using string representation"
                    )
                    return f"<unawaited_coroutine: {type(value).__name__}>"

            # 如果是dict，递归处理每个值
            elif isinstance(value, dict):
                # 检查是否已经访问过这个对象（避免循环引用）
                obj_id = id(value)
                if obj_id in visited:
                    get_logger().debug(
                        f"Detected circular reference in dict, skipping: {type(value).__name__}"
                    )
                    return "<circular_reference>"

                visited.add(obj_id)
                try:
                    cleaned_dict = {}
                    for k, v in value.items():
                        cleaned_dict[k] = await clean_value(v)
                    return cleaned_dict
                finally:
                    visited.remove(obj_id)

            # 如果是list，递归处理每个元素
            elif isinstance(value, (list, tuple)):
                # 检查是否已经访问过这个对象（避免循环引用）
                obj_id = id(value)
                if obj_id in visited:
                    get_logger().debug(
                        f"Detected circular reference in list/tuple, skipping: {type(value).__name__}"
                    )
                    return "<circular_reference>"

                visited.add(obj_id)
                try:
                    cleaned_list = [await clean_value(item) for item in value]
                    return (
                        cleaned_list if isinstance(value, list) else tuple(cleaned_list)
                    )
                finally:
                    visited.remove(obj_id)

            # 其他类型直接返回
            else:
                return value

        return await clean_value(results)

    async def _log_instruction(
        self,
        instruction: str,
        context: dict,
        readonly: bool,
        results: dict | None = None,
    ) -> None:
        """
        线程安全地记录agent的指令执行信息。
        每条指令立即写入文件（追加模式），避免程序中断导致数据丢失。

        Args:
            instruction: 指令字符串
            context: 执行上下文
            readonly: 是否只读模式
            results: 执行结果（可选，用于后处理清理coroutines）
        """
        # 清理context中的coroutines
        if isinstance(context, dict):
            context = await self._clean_coroutines_from_results(context)

        log_entry = EnvRouterBenchmarkData(
            instruction=instruction,
            context=context,
            readonly=readonly,
        )
        async with self._instruction_log_lock:
            self._instruction_log.append(log_entry)
            try:
                with open(self._log_path, "wb") as f:
                    pickle.dump(self._instruction_log, f)
            except Exception as e:
                get_logger().warning(
                    f"Failed to pickle instruction log: {str(e)}, skipping file write"
                )

    async def init(self, start_datetime: datetime):
        """
        Initialize the router with the start datetime and generate code using LLM.
        """
        await super().init(start_datetime)

        # 在async上下文中初始化锁
        get_logger().debug("Initialized instruction log lock")

        # Generate code using LLM if not already done
        if not self._llm_code_generated:
            # Generate observe code using LLM (using same logic as regular code generation)
            if (True, "observe") in self._tools_pyi_dict:
                llm_observe_code = await self._generate_observe_code()
                if llm_observe_code:
                    self._observe_code = llm_observe_code
                    get_logger().info("Generated observe code using LLM")
                else:
                    raise ValueError("Failed to generate observe code")
            # Generate statistics code using LLM (using same logic as regular code generation)
            if (True, "statistics") in self._tools_pyi_dict:
                llm_statistics_code = await self._generate_statistics_code()
                if llm_statistics_code:
                    self._statistics_code = llm_statistics_code
                    get_logger().info("Generated statistics code using LLM")
                else:
                    raise ValueError("Failed to generate statistics code")
            self._llm_code_generated = True

    async def dump(self) -> dict:
        """
        Dump router state to a serializable dict, including instruction logs.
        """
        # 调用父类的dump方法获取基础状态
        base_dump = await super().dump()

        # 添加指令日志
        async with self._instruction_log_lock:
            base_dump["instruction_log"] = self._instruction_log.copy()

        return base_dump

    async def load(self, dump_data: dict):
        """
        Load router state from a dict produced by dump().
        """
        # 调用父类的load方法恢复基础状态
        await super().load(dump_data)

        # 恢复指令日志
        try:
            instruction_log = dump_data.get("instruction_log", [])
            if isinstance(instruction_log, list):
                async with self._instruction_log_lock:
                    self._instruction_log = instruction_log.copy()
                get_logger().debug(
                    f"Loaded {len(instruction_log)} instruction log entries"
                )
        except Exception as e:
            get_logger().warning(f"Failed to load instruction log: {str(e)}")

    def _collect_tools_by_kind(self, kind: str) -> List[Dict[str, Any]]:
        """
        收集所有指定kind的工具信息。

        Args:
            kind: 工具类型，可以是 "observe" 或 "statistics"

        Returns:
            工具信息列表，每个元素包含：
            {
                "module_name": "模块名",
                "tool_name": "工具名",
                "tool_description": "工具描述",
                "parameters": {...},  # 工具参数schema
                "has_agent_param": bool,  # 是否包含agent相关参数（agent_id/id/person_id）
                "agent_param_name": str | None,  # agent参数的具体名称
            }
        """
        tools = []

        for module in self.env_modules:
            tool_kinds_dict = getattr(module.__class__, "_tool_kinds", {})
            registered_tools = getattr(module.__class__, "_registered_tools", {})

            for tool_name, tool_kind in tool_kinds_dict.items():
                if tool_kind != kind:
                    continue

                # 获取工具对象
                tool_obj = registered_tools.get(tool_name)
                if not tool_obj:
                    continue

                # 获取工具的参数信息
                parameters = (
                    tool_obj.parameters if hasattr(tool_obj, "parameters") else {}
                )
                param_properties = parameters.get("properties", {})

                # 检查是否有agent相关的参数（agent_id, id, person_id等）
                all_params = set(param_properties.keys())
                agent_related_params = {"agent_id", "id", "person_id"}
                has_agent_param = bool(all_params & agent_related_params)

                # 确定具体的参数名（优先使用person_id，然后是agent_id，最后是id）
                agent_param_name = None
                if "person_id" in all_params:
                    agent_param_name = "person_id"
                elif "agent_id" in all_params:
                    agent_param_name = "agent_id"
                elif "id" in all_params:
                    agent_param_name = "id"

                tools.append(
                    {
                        "module_name": module.name,
                        "tool_name": tool_name,
                        "tool_description": (
                            tool_obj.description
                            if hasattr(tool_obj, "description")
                            else ""
                        ),
                        "parameters": parameters,
                        "has_agent_param": has_agent_param,
                        "agent_param_name": agent_param_name,
                    }
                )

        return tools

    async def _generate_observe_code(self) -> str:
        """
        使用LLM生成观察代码，用于调用所有observe类型的工具。
        使用与其他普通文本相同的代码生成逻辑。

        Returns:
            生成的Python代码字符串，如果生成失败则返回空字符串
        """
        get_logger().debug(f"{_get_debug_info('开始生成observe代码')}")

        if (True, "observe") not in self._tools_pyi_dict:
            get_logger().debug(f"{_get_debug_info('observe工具不存在')} - 跳过代码生成")
            return ""

        # 构建指令：收集环境观察信息
        instruction = self.OBSERVE_INSTRUCTION

        # 使用空的上下文（在实际执行时会使用真实的ctx）
        ctx = {"id": 123}

        get_logger().debug(
            f"{_get_debug_info('构建observe代码生成prompt')} - instruction: {instruction}"
        )

        # 使用与其他普通文本相同的代码生成逻辑
        prompt = self._build_codegen_prompt(
            instruction=instruction,
            ctx=ctx,
            readonly=True,
            kind="observe",
        )

        # 调用LLM生成代码
        dialog_history: List[AllMessageValues] = [{"role": "user", "content": prompt}]
        code = await self._generate_code(dialog_history)
        get_logger().info(f"Generated observe code: {code}")
        get_logger().debug(
            f"{_get_debug_info('observe代码生成完成')} - code length: {len(code)}"
        )

        if not code:
            raise ValueError("Failed to generate observe code")

        # 验证代码安全性
        is_safe, safety_violation = self._validate_code_safety(code)
        if not is_safe:
            get_logger().warning(
                f"Generated observe code failed safety check: {safety_violation}"
            )
            raise ValueError(
                f"Generated observe code failed safety check: {safety_violation}"
            )

        return code.strip()

    async def _generate_statistics_code(self) -> str:
        """
        使用LLM生成统计代码，用于调用所有statistics类型的工具。
        使用与其他普通文本相同的代码生成逻辑。

        Returns:
            生成的Python代码字符串，如果生成失败则返回空字符串
        """
        get_logger().debug(f"{_get_debug_info('开始生成statistics代码')}")

        if (True, "statistics") not in self._tools_pyi_dict:
            get_logger().debug(
                f"{_get_debug_info('statistics工具不存在')} - 跳过代码生成"
            )
            return ""

        # 构建指令：收集环境统计信息
        instruction = self.STATISTICS_INSTRUCTION

        # 使用空的上下文（在实际执行时会使用真实的ctx）
        ctx = {}

        get_logger().debug(
            f"{_get_debug_info('构建statistics代码生成prompt')} - instruction: {instruction}"
        )

        # 使用与其他普通文本相同的代码生成逻辑
        prompt = self._build_codegen_prompt(
            instruction=instruction,
            ctx=ctx,
            readonly=True,
            kind="statistics",
        )

        # 调用LLM生成代码
        dialog_history: List[AllMessageValues] = [{"role": "user", "content": prompt}]
        code = await self._generate_code(dialog_history)
        get_logger().info(f"Generated statistics code: {code}")
        get_logger().debug(
            f"{_get_debug_info('statistics代码生成完成')} - code length: {len(code)}"
        )
        if not code:
            raise ValueError("Failed to generate statistics code")

        # 验证代码安全性
        is_safe, safety_violation = self._validate_code_safety(code)
        if not is_safe:
            get_logger().warning(
                f"Generated statistics code failed safety check: {safety_violation}"
            )
            raise ValueError(
                f"Generated statistics code failed safety check: {safety_violation}"
            )

        return code.strip()

    def _build_codegen_prompt(
        self,
        instruction: str,
        ctx: dict,
        readonly: bool,
        kind: str | None = None,
    ) -> str:
        """
        构建代码生成的提示词，使用类似 pyi 文件的 Python 代码格式提供环境模块和工具信息。

        Args:
            instruction: 指令字符串
            ctx: 上下文字典
            readonly: 是否只读模式
            kind: 工具类型筛选（可选），如 "observe" 或 "statistics"，如果提供则只显示该类型的工具
        """
        get_logger().debug(
            f"{_get_debug_info('开始构建代码生成prompt')} - instruction: {instruction[:100]}..., readonly: {readonly}, kind: {kind}"
        )

        # 从预生成的字典中获取 pyi 格式的工具信息
        key = (readonly, kind)
        tools_pyi = self._tools_pyi_dict[key]
        get_logger().debug(
            f"{_get_debug_info('获取工具pyi代码')} - tools_pyi length: {len(tools_pyi)}"
        )

        # 构建上下文信息的repr形式
        context_repr = repr(ctx)
        module_repr = repr(self._modules)

        prompt = f"""# Code Generation Task

You are a code generation assistant. Your task is to generate Python code that calls environment module tools based on the given agent input, including instruction and context.

## Available Environment Modules and Tools

The following Python code (similar to .pyi stub files) contains all available environment modules and their tools:

```python
{tools_pyi}
```

You can access the environment modules using the `modules` variable.
```python
modules = {module_repr}
```

## Agent Input

### Instruction

The instruction is the task that the agent needs to accomplish:

<instruction>{instruction}</instruction>

### Context

The context is a Python dictionary containing the agent input data. You can access values from context using the `ctx` variable.

```python
ctx = {context_repr}
```

## Code Generation Requirements

1. **Generate Python code** that accomplishes the instruction by calling appropriate tools from the environment modules.

2. **Store results** in the `results` dictionary and **MUST set results['status']** at the end:
   ```python
   results['step1'] = result
   results['status'] = 'success'        # or 'in_progress', 'fail', 'error'
   ```

3. **Provide semantic print statements** to explain what you're doing:
   ```python
   print("Getting user information...")
   print(f"Query result: {{result}}")
   ```

## Status Meanings

- **success**: The task has been completed successfully. All required operations finished without errors.
- **in_progress**: The task is still being executed or more steps are needed. The agent need to check whether it is done in the next steps.
- **fail**: The task could not be completed (e.g., unsupported instruction, missing data, invalid input). Include detailed reason in results.
- **error**: An error occurred during code execution. Must include error details in results['error'].

## Important Notes

- The code will be executed in a controlled environment with access to:
  - `ctx`: The context dictionary (Python dict), contains current time, agent id, and other information.
  - `modules`: Dictionary of environment modules (keyed by module name)
  - `results`: Dictionary to store intermediate results
  - `print()`: For semantic output (captured for final summary)
  - Imported allowed modules: collections, itertools, functools, operator, copy, decimal, fractions, statistics, string, re, datetime, json, math, random, numpy (as np). These modules are already imported and can be used directly without importing.

- You CAN import modules from the allowed list above using: `import module_name` or `from module_name import ...`
- Do NOT import any modules outside of the allowed list
- Do NOT use dangerous operations like file I/O, network access, etc.
- Do NOT use `eval`, `exec`, `compile` or similar functions
- Use meaningful variable names and comments
- IMPORTANT: ALWAYS USE `await` TO CALL TOOLS (ASYNC FUNCTIONS)

## CRITICAL REMINDER

**NEVER forget to set results['status'] at the END of your code!**
Even if your code works perfectly, if you don't set results['status'], the execution will FAIL.
This is the LAST thing your code must do before it ends.

## Output Format

Generate ONLY the Python code, without any markdown code blocks or explanations. The code should start directly with Python statements.

Your generated code:"""

        get_logger().debug(
            f"{_get_debug_info('prompt构建完成')} - prompt length: {len(prompt)}, prompt preview: {prompt[:500]}..."
        )

        return prompt

    def _build_error_message(
        self,
        previous_errors: List[str],
    ) -> str:
        """
        构建错误信息消息，用于多轮对话中的错误反馈。
        注意：之前的代码已经作为assistant消息添加到对话历史中了，这里只包含错误信息。

        Args:
            previous_errors: 错误信息列表

        Returns:
            错误信息消息字符串
        """
        errors_text = "\n".join(
            [f"- {i+1}. {error}" for i, error in enumerate(previous_errors)]
        )

        error_message = f"""The code I generated failed during execution. Here's what went wrong:

## Errors

{errors_text}

Please analyze the errors carefully and fix the code by addressing all the issues mentioned above. Common issues include:
- Incorrect function names or module names
- Wrong parameter types or missing required parameters
- Incorrect usage of async/await
- Type mismatches
- Missing imports or incorrect variable names
- Logic errors

Please generate the corrected code:"""

        return error_message

    async def _generate_code(self, dialog_history: List[AllMessageValues]) -> str:
        """
        调用LLM生成代码，支持多轮对话。

        Args:
            dialog_history: 对话历史列表，包含多轮对话消息
        """
        get_logger().debug(
            f"{_get_debug_info('准备调用LLM生成代码')} - model: {self.codegen_model_name}, dialog_history length: {len(dialog_history)}"
        )
        get_logger().debug(
            f"{_get_debug_info('发送给LLM的对话历史')}:\n{dialog_history}"
        )

        try:
            response = await self.acompletion_with_system_prompt(
                model="coder",
                messages=dialog_history,
            )

            raw_code = response.choices[0].message.content or ""  # type: ignore
            get_logger().debug(
                f"{_get_debug_info('收到LLM响应')} - raw response length: {len(raw_code)}"
            )
            get_logger().debug(
                f"{_get_debug_info('LLM返回的完整response')}:\n{raw_code}"
            )

            # 移除可能的markdown代码块标记
            code = self._extract_code_from_markdown(raw_code)
            get_logger().debug(
                f"{_get_debug_info('提取代码完成')} - extracted code length: {len(code)}"
            )

            return code.strip()

        except Exception as e:
            get_logger().error(
                f"{_get_debug_info('LLM代码生成失败')} - error: {str(e)}"
            )
            return ""

    def _extract_code_from_markdown(self, text: str) -> str:
        """从markdown代码块中提取代码"""
        pattern = r"```(?:python)?\s*\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        return matches[0].strip() if matches else text.strip()

    def _validate_code_safety(self, code: str) -> Tuple[bool, str]:
        """
        使用AST解析检查代码安全性

        Returns:
            (is_safe, violation_message) 元组
            - is_safe: 是否通过安全检查
            - violation_message: 如果未通过，包含具体的违规信息；如果通过，为空字符串
        """
        violations = []

        try:
            tree = ast.parse(code, mode="exec")
            dangerous_functions = {
                "eval",
                "exec",
                "compile",
                "__import__",
                "open",
                "input",
            }

            def is_dangerous_module(name: str) -> bool:
                # 先检查是否在白名单中
                if name in self.ALLOWED_MODULES:
                    return False
                # 再检查是否在危险模块列表中
                return name in self.DANGEROUS_MODULES or (
                    name.startswith("_") and name != "__future__"
                )

            for node in ast.walk(tree):
                # 检查禁止的节点类型
                if type(node) in self.FORBIDDEN_AST_NODES:
                    node_type_name = type(node).__name__
                    violation_msg = f"Forbidden AST node type: {node_type_name}"
                    violations.append(violation_msg)
                    get_logger().warning(violation_msg)
                    # 继续检查其他违规项，收集所有违规信息

                # 检查危险的函数调用
                if isinstance(node, ast.Call):
                    if (
                        isinstance(node.func, ast.Name)
                        and node.func.id in dangerous_functions
                    ):
                        violation_msg = f"Dangerous function call: {node.func.id}()"
                        violations.append(violation_msg)
                        get_logger().warning(violation_msg)
                    elif isinstance(node.func, ast.Attribute) and node.func.attr in {
                        "eval",
                        "exec",
                        "compile",
                    }:
                        violation_msg = f"Dangerous method call: {node.func.attr}()"
                        violations.append(violation_msg)
                        get_logger().warning(violation_msg)

                # 检查导入语句
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if is_dangerous_module(alias.name):
                            violation_msg = f"Dangerous import: import {alias.name}"
                            violations.append(violation_msg)
                            get_logger().warning(violation_msg)
                elif (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and is_dangerous_module(node.module)
                ):
                    violation_msg = f"Dangerous import: from {node.module} import ..."
                    violations.append(violation_msg)
                    get_logger().warning(violation_msg)

            if violations:
                violation_message = (
                    "Code safety check failed. Violations found:\n"
                    + "\n".join([f"- {v}" for v in violations])
                )
                return False, violation_message

            return True, ""

        except SyntaxError as e:
            violation_message = f"Code syntax error: {str(e)}"
            get_logger().error(violation_message)
            return False, violation_message
        except Exception as e:
            violation_message = f"Code validation error: {str(e)}"
            get_logger().error(violation_message)
            return False, violation_message

    async def _execute_code(
        self, code: str, ctx: dict, readonly: bool
    ) -> Dict[str, Any]:
        """执行生成的代码，捕获打印输出"""
        get_logger().debug(
            f"{_get_debug_info('开始执行代码')} - code length: {len(code)}, readonly: {readonly}, ctx keys: {list(ctx.keys())}"
        )
        get_logger().debug(f"{_get_debug_info('即将执行的代码')}:\n{code}")

        results = {}

        # 创建一个安全的__import__函数，只允许导入白名单中的模块
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            """安全的导入函数，只允许导入白名单中的模块"""
            if name not in self.ALLOWED_MODULES:
                print(f"Import of module '{name}' is not allowed. Ignored. Allowed modules: {', '.join(sorted(self.ALLOWED_MODULES))}")
                return None
            # 使用内置的__import__函数进行实际导入
            return __import__(name, globals, locals, fromlist, level)

        # 导入白名单中允许的模块（保留现有的默认导入）
        allowed_modules = {}
        import collections
        import copy
        import decimal
        import fractions
        import functools
        import itertools
        import operator
        import statistics
        import string

        allowed_modules.update(
            {
                "collections": collections,
                "itertools": itertools,
                "functools": functools,
                "operator": operator,
                "copy": copy,
                "decimal": decimal,
                "fractions": fractions,
                "statistics": statistics,
                "string": string,
                "re": re,
                "datetime": datetime,
                "json": json,
                "math": math,
                "random": random,
                "numpy": np,
                "np": np,
            }
        )

        # 构建受限的__builtins__字典，包含允许的内置函数和__import__
        restricted_builtins = {
            k: v for k, v in __builtins__.items() if k in self.ALLOWED_BUILTINS
        }
        restricted_builtins["__import__"] = safe_import  # 添加安全的__import__函数
        
        exec_globals = {
            "__builtins__": restricted_builtins,  # __builtins__中已包含__import__
            "ctx": ctx,
            "modules": self._modules,
            "results": results,
            "print": print,  # 直接使用print，输出会被StringIO捕获
            # 添加允许的模块（保留现有的默认导入）
            **allowed_modules,
            # 添加一些常用的__builtins__类型
            "Exception": Exception,
            "RuntimeError": RuntimeError,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "SyntaxError": SyntaxError,
            "NameError": NameError,
            "AttributeError": AttributeError,
            "IndexError": IndexError,
            "KeyError": KeyError,
        }
        exec_locals = {}

        # 捕获标准输出
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            is_async = "async" in code or "await" in code
            get_logger().debug(
                f"{_get_debug_info('检测代码类型')} - is_async: {is_async}"
            )

            async def execute_with_timeout():
                """在10秒超时内执行代码"""
                if is_async:
                    # 包装成async函数执行
                    get_logger().debug(
                        f"{_get_debug_info('处理异步代码')} - 包装为async函数"
                    )
                    indented_code = "\n".join(
                        "    " + line if line.strip() else "" for line in code.split("\n")
                    )
                    async_code = f"async def _generated_main():\n{indented_code}"

                    compiled = compile(async_code, "<generated_async>", "exec")
                    exec(compiled, exec_globals, exec_locals)

                    main_func = exec_locals.get("_generated_main")
                    if main_func:
                        get_logger().debug(
                            f"{_get_debug_info('执行异步函数')} - 调用_generated_main"
                        )
                        await main_func()
                    else:
                        raise RuntimeError("Async function not found after compilation")
                else:
                    # 同步代码直接执行
                    get_logger().debug(f"{_get_debug_info('执行同步代码')} - 直接编译执行")
                    compiled_code = compile(code, "<generated>", "exec")
                    exec(compiled_code, exec_globals, exec_locals)

            # 使用 asyncio.wait_for 添加 10 秒超时
            try:
                await asyncio.wait_for(execute_with_timeout(), timeout=10)
            except asyncio.TimeoutError:
                raise TimeoutError("Code execution timeout: exceeded 10 seconds limit")

            output = captured_output.getvalue()
            print_outputs = [
                line.strip() for line in output.split("\n") if line.strip()
            ]

            get_logger().debug(
                f"{_get_debug_info('代码执行成功')} - results keys: {list(results.keys())}, print_outputs_count: {len(print_outputs)}, output length: {len(output)}"
            )
            get_logger().debug(f"{_get_debug_info('执行结果')} - results: {results}")
            get_logger().debug(
                f"{_get_debug_info('打印输出')} - print_outputs: {print_outputs}"
            )

            return {
                "results": results,
                "output": output,
                "print_outputs": print_outputs,
                "success": True,
            }

        except Exception as e:
            error_msg = str(e)
            get_logger().error(
                f"{_get_debug_info('代码执行错误')} - error: {error_msg}"
            )
            import traceback

            traceback.print_exc()
            captured_output_value = captured_output.getvalue()
            get_logger().debug(
                f"{_get_debug_info('执行失败时的输出')} - output: {captured_output_value}"
            )
            return {
                "results": results,
                "output": captured_output_value,
                "print_outputs": [],
                "error": error_msg,
                "success": False,
            }
        finally:
            sys.stdout = old_stdout
