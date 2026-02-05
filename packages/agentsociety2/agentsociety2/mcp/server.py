"""
MCP Server for AgentSociety2 - Provides tools for managing AgentSociety instances.
"""

import argparse
import asyncio
import signal
from typing import Any, Dict, List, Optional, cast

from fastmcp import FastMCP

from agentsociety2.agent import AgentBase
from agentsociety2.env import CodeGenRouter, EnvBase
from agentsociety2.logger import get_logger
from agentsociety2.society.society import AgentSociety

from .models import CreateInstanceRequest
from .registry import (
    REGISTERED_ENV_MODULES,
    REGISTERED_AGENT_MODULES,
)

__all__ = ["create_mcp_server"]


class SocietyInstance:
    """Wrapper for an AgentSociety instance running as an asyncio task."""

    def __init__(self, instance_id: str, society: AgentSociety):
        self.instance_id = instance_id
        self.society = society
        self.status: str = "idle"  # Status: idle, running, error
        self.error_message: Optional[str] = None
        self.run_task: Optional[asyncio.Task] = None  # Current run task if running

    def get_status_dict(self) -> Dict[str, Any]:
        """Get status dictionary for an instance."""
        return {
            "instance_id": self.instance_id,
            "status": self.status,
            "current_time": (
                self.society.current_time.isoformat() if self.society else None
            ),
            "num_agents": len(self.society._agents) if self.society else 0,
            "num_env_modules": (
                len(self.society._env_router.env_modules) if self.society else 0
            ),
        }


class AgentSocietyMCPServer:
    """MCP Server for managing AgentSociety instances."""

    def __init__(self):
        """
        Initialize MCP Server.

        Args:
            log_dir: Base directory for storing instance logs. If provided, each instance will have
                     its logs stored in {log_dir}/{instance_id}/ with commands.jsonl
        """
        self.instances: Dict[str, SocietyInstance] = {}
        self.mcp = FastMCP("AgentSociety2")
        self._register_tools()

    async def _create_env_module(self, env_config: Any) -> EnvBase:
        """Create an environment module from configuration."""
        env_class = None
        for mt, ec in REGISTERED_ENV_MODULES:
            if mt == env_config.module_type:
                env_class = ec
                break

        if env_class is None:
            available_types = [mt for mt, _ in REGISTERED_ENV_MODULES]
            raise ValueError(
                f"Environment module type '{env_config.module_type}' not found in registry. "
                f"Available types: {available_types}"
            )

        return env_class(**env_config.args)

    async def _create_agent(self, agent_config: Any) -> AgentBase:
        """Create an agent from configuration."""
        agent_class = None
        for at, ac in REGISTERED_AGENT_MODULES:
            if at == agent_config.agent_type:
                agent_class = ac
                break

        if agent_class is None:
            available_types = [at for at, _ in REGISTERED_AGENT_MODULES]
            raise ValueError(
                f"Agent type '{agent_config.agent_type}' not found in registry. "
                f"Available types: {available_types}"
            )

        kwargs = {"id": agent_config.agent_id, **agent_config.args}
        return agent_class(**kwargs)

    def _register_tools(self):
        """Register all MCP tools."""

        @self.mcp.tool()
        async def list_environment_modules() -> Dict[str, Any]:
            """
            List all registered environment modules.

            Returns a dictionary with module names and their descriptions.
            Only returns modules that have been registered in REGISTERED_ENV_MODULES.
            """
            try:
                modules = {}

                # Get registered environment modules from constant list
                for module_type, env_class in REGISTERED_ENV_MODULES:
                    try:
                        # Get description using mcp_description classmethod
                        description = env_class.mcp_description()

                        modules[module_type] = {
                            "class_name": module_type,
                            "description": description,
                        }
                    except Exception as e:
                        get_logger().warning(
                            f"Failed to get info for module {module_type}: {e}"
                        )
                        continue

                return {
                    "success": True,
                    "modules": modules,
                    "count": len(modules),
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                }

        @self.mcp.tool()
        async def list_available_agents() -> Dict[str, Any]:
            """
            List all registered agent types.

            Returns a dictionary with agent types and their descriptions.
            Only returns agents that have been registered in REGISTERED_AGENT_MODULES.
            """
            try:
                agents = {}

                # Get registered agent modules from constant list
                for agent_type, agent_class in REGISTERED_AGENT_MODULES:
                    try:
                        # Get description using mcp_description classmethod
                        description = agent_class.mcp_description()

                        agents[agent_type] = {
                            "class_name": agent_type,
                            "description": description,
                        }
                    except Exception as e:
                        get_logger().warning(
                            f"Failed to get info for agent {agent_type}: {e}"
                        )
                        continue

                return {
                    "success": True,
                    "agents": agents,
                    "count": len(agents),
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                }

        @self.mcp.tool()
        async def create_society_instance(request: Dict[str, Any]) -> Dict[str, Any]:
            """
            Create a new AgentSociety instance.

            Args:
                request: CreateInstanceRequest as a dictionary containing:
                    - instance_id: Unique identifier for the instance
                    - llm_config: LLM configuration for the society
                    - env_modules: List of environment module configurations
                    - agents: List of agent configurations
                    - fallback_module_index: Index of fallback environment module
                    - start_t: Simulation start time
                    - tick: Tick duration in seconds

            Returns:
                Dictionary with success status and instance information.
            """
            try:
                req = CreateInstanceRequest.model_validate(request)

                # Check if instance already exists
                if req.instance_id in self.instances:
                    return {
                        "success": False,
                        "error": f"Instance {req.instance_id} already exists",
                    }

                # Validate that at least one environment module is provided
                if len(req.env_modules) == 0:
                    return {
                        "success": False,
                        "error": "At least one environment module is required",
                    }

                # Create environment modules
                env_modules = []
                for env_module_config in req.env_modules:
                    module = await self._create_env_module(env_module_config)
                    env_modules.append(module)
                env_router = CodeGenRouter(env_modules=env_modules)

                # Create agents
                agents = []
                for agent_config in req.agents:
                    agent = await self._create_agent(agent_config)
                    agents.append(agent)

                # Create and initialize AgentSociety
                society = AgentSociety(
                    agents=cast(List[AgentBase], agents),
                    env_router=env_router,
                    start_t=req.start_t,
                )
                await society.init()
                # Create instance wrapper
                instance = SocietyInstance(req.instance_id, society)
                self.instances[req.instance_id] = instance

                return {
                    "success": True,
                    "instance_id": req.instance_id,
                }

            except Exception as e:
                get_logger().error(
                    f"Failed to process create request: {e}", exc_info=True
                )
                return {
                    "success": False,
                    "error": str(e),
                }

        @self.mcp.tool()
        async def get_instance_status(instance_id: str) -> Dict[str, Any]:
            """
            Get the status of an AgentSociety instance.
            This is used to check the progress of async operations like run_instance.

            Args:
                instance_id: The ID of the instance to query

            Returns:
                Dictionary with status information including current_time and status.
                Status can be: 'idle', 'running', 'error'
            """
            try:
                if instance_id not in self.instances:
                    return {
                        "success": False,
                        "error": f"Instance {instance_id} not found",
                    }

                instance = self.instances[instance_id]

                # Check if task is still running
                if instance.run_task and instance.run_task.done():
                    # Task completed, check for exceptions
                    try:
                        await instance.run_task
                        # Task completed successfully, set status back to idle
                        if instance.status == "running":
                            instance.status = "idle"
                            instance.run_task = None
                    except Exception as e:
                        instance.status = "error"
                        instance.error_message = str(e)
                        instance.run_task = None
                        get_logger().error(
                            f"Background task error for instance {instance_id}: {e}",
                            exc_info=True,
                        )

                status_dict = instance.get_status_dict()
                result = {
                    "success": True,
                    "status": status_dict,
                }

                return result

            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                }

        @self.mcp.tool()
        async def list_instances() -> Dict[str, Any]:
            """
            List all AgentSociety instances.

            Returns:
                Dictionary with list of all instances and their statuses.
            """
            try:
                instances = []
                for instance_id, instance in self.instances.items():
                    # Check if task is still running
                    if instance.run_task and instance.run_task.done():
                        try:
                            await instance.run_task
                            # Task completed successfully, set status back to idle
                            if instance.status == "running":
                                instance.status = "idle"
                                instance.run_task = None
                        except Exception:
                            pass

                    instances.append(instance.get_status_dict())

                result = {
                    "success": True,
                    "instances": instances,
                    "count": len(instances),
                }

                return result
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                }

        @self.mcp.tool()
        async def run_instance(
            instance_id: str, num_steps: int = 1, tick: Optional[int] = None
        ) -> Dict[str, Any]:
            """
            Run an AgentSociety instance for a specified number of steps.
            This is an asynchronous operation that returns immediately.
            Use get_instance_status to check the progress and completion status.

            Args:
                instance_id: The ID of the instance to run
                num_steps: Number of steps to execute (default: 1)
                tick: Tick duration in seconds for each step. If not provided, uses the instance's configured tick.

            Returns:
                Dictionary with success status indicating that the run command was accepted.
                Check status via get_instance_status to see completion status.
            """
            try:
                if instance_id not in self.instances:
                    return {
                        "success": False,
                        "error": f"Instance {instance_id} not found",
                    }

                instance = self.instances[instance_id]

                # Check if instance is idle (can only run when idle)
                if instance.status != "idle":
                    return {
                        "success": False,
                        "error": f"Instance is not idle (status: {instance.status}). Only idle instances can be run.",
                    }

                if not instance.society:
                    return {
                        "success": False,
                        "error": "Society not initialized",
                    }

                # Check if already running
                if instance.run_task and not instance.run_task.done():
                    return {
                        "success": False,
                        "error": "Instance is already running",
                    }

                # Use provided tick or default to 1
                step_tick = tick if tick is not None else 1

                # Create run task
                async def _run_steps():
                    try:
                        society = instance.society
                        if not society:
                            raise RuntimeError("Society not initialized")
                        for _ in range(num_steps):
                            await society.step(step_tick)
                    except Exception as e:
                        get_logger().error(
                            f"Error running steps for instance {instance_id}: {e}",
                            exc_info=True,
                        )
                        raise

                instance.run_task = asyncio.create_task(_run_steps())
                instance.status = "running"

                result = {
                    "success": True,
                    "message": f"Run command accepted, executing {num_steps} step(s)",
                    "instance_id": instance_id,
                    "num_steps": num_steps,
                    "tick": step_tick,
                }

                return result

            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                }

        @self.mcp.tool()
        async def ask_instance(instance_id: str, question: str) -> Dict[str, Any]:
            """
            Ask a question to an AgentSociety instance (read-only query).
            Only available when the instance is idle (not running).

            Args:
                instance_id: The ID of the instance
                question: The question to ask

            Returns:
                Dictionary with the answer.
            """
            try:
                if instance_id not in self.instances:
                    return {
                        "success": False,
                        "error": f"Instance {instance_id} not found",
                    }

                instance = self.instances[instance_id]

                # Check if instance is idle (can only ask when idle)
                if instance.status != "idle":
                    return {
                        "success": False,
                        "error": f"Instance is not idle (status: {instance.status}). Only idle instances can be asked.",
                    }

                # Check if running
                if instance.run_task and not instance.run_task.done():
                    return {
                        "success": False,
                        "error": "Cannot ask when instance is running. Instance must be idle.",
                    }

                # Call ask directly
                answer = await instance.society._helper.ask(question)

                result = {
                    "success": True,
                    "answer": answer,
                }

                return result

            except Exception as e:
                result = {
                    "success": False,
                    "error": str(e),
                }
                return result

        @self.mcp.tool()
        async def intervene_instance(
            instance_id: str, instruction: str
        ) -> Dict[str, Any]:
            """
            Intervene in an AgentSociety instance (can modify state).
            Only available when the instance is idle (not running).

            Args:
                instance_id: The ID of the instance
                instruction: The intervention instruction

            Returns:
                Dictionary with the result.
            """
            try:
                if instance_id not in self.instances:
                    return {
                        "success": False,
                        "error": f"Instance {instance_id} not found",
                    }

                instance = self.instances[instance_id]

                # Check if instance is idle (can only intervene when idle)
                if instance.status != "idle":
                    return {
                        "success": False,
                        "error": f"Instance is not idle (status: {instance.status}). Only idle instances can be intervened.",
                    }

                # Check if running
                if instance.run_task and not instance.run_task.done():
                    return {
                        "success": False,
                        "error": "Cannot intervene when instance is running. Instance must be idle.",
                    }

                # Call intervene directly
                intervention_result = await instance.society._helper.intervene(
                    instruction
                )

                result = {
                    "success": True,
                    "result": intervention_result,
                }

                return result

            except Exception as e:
                result = {
                    "success": False,
                    "error": str(e),
                }
                return result

        @self.mcp.tool()
        async def close_instance(instance_id: str) -> Dict[str, Any]:
            """
            Close and cleanup an AgentSociety instance.

            Args:
                instance_id: The ID of the instance to close

            Returns:
                Dictionary with success status.
            """
            try:
                if instance_id not in self.instances:
                    return {
                        "success": False,
                        "error": f"Instance {instance_id} not found",
                    }

                instance = self.instances[instance_id]

                # Cancel run task if exists
                if instance.run_task and not instance.run_task.done():
                    instance.run_task.cancel()
                    try:
                        await instance.run_task
                    except asyncio.CancelledError:
                        pass
                    instance.run_task = None

                # Close society
                await instance.society.close()

                result = {
                    "success": True,
                    "message": f"Instance {instance_id} closed",
                }

                # Remove from instances
                del self.instances[instance_id]

                return result

            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                }

    async def cleanup_all_instances(self) -> None:
        """
        Cleanup all instances by cancelling their tasks.
        This should be called before server shutdown.
        """
        get_logger().info("Cleaning up all instances...")
        instance_ids = list(self.instances.keys())
        for instance_id in instance_ids:
            try:
                instance = self.instances[instance_id]

                # Cancel run task if exists
                if instance.run_task and not instance.run_task.done():
                    instance.run_task.cancel()
                    try:
                        await instance.run_task
                    except asyncio.CancelledError:
                        pass
                    del self.instances[instance_id]
                    get_logger().info(f"Instance {instance_id} cleaned up")

            except Exception as e:
                get_logger().error(
                    f"Error cleaning up instance {instance_id}: {e}", exc_info=True
                )

        # Clear all instances
        self.instances.clear()
        get_logger().info("All instances cleaned up")

    async def run(self, host: str = "0.0.0.0", port: int = 8000, path: str = "/mcp"):
        """
        Run the MCP server with Streamable HTTP transport.

        Args:
            host: Host to bind to
            port: Port to bind to
            path: HTTP path for streamable_http endpoint (default: /mcp)
        """

        # Setup signal handlers in the event loop
        def setup_signal_handlers():
            """Setup signal handlers in the event loop."""
            loop = asyncio.get_running_loop()

            def signal_handler():
                """Handle shutdown signals."""
                get_logger().info("Received shutdown signal, cleaning up...")
                # Schedule cleanup on the event loop
                asyncio.create_task(self._shutdown_async())

            try:
                loop.add_signal_handler(signal.SIGINT, signal_handler)
                loop.add_signal_handler(signal.SIGTERM, signal_handler)
            except NotImplementedError:
                # On Windows, signal handlers may not be supported
                get_logger().warning("Signal handlers not supported on this platform")

        setup_signal_handlers()
        await self.mcp.run_http_async(host=host, port=port, path=path)

    async def _shutdown_async(self) -> None:
        """Async shutdown handler that cleans up all instances."""
        try:
            get_logger().info("Shutting down server, cleaning up all instances...")
            await self.cleanup_all_instances()
            get_logger().info("Cleanup completed, stopping server...")
        except Exception as e:
            get_logger().error(f"Error during async shutdown: {e}", exc_info=True)
        finally:
            # Cancel all running tasks to allow graceful shutdown
            # The event loop will exit when run_http_async completes or is cancelled
            tasks = [
                task
                for task in asyncio.all_tasks()
                if task is not asyncio.current_task()
            ]
            for task in tasks:
                task.cancel()


def create_mcp_server() -> AgentSocietyMCPServer:
    """
    Create and return an MCP server instance.
    """
    return AgentSocietyMCPServer()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Start the AgentSociety MCP Server with Streamable HTTP transport."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to listen on (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to listen on (default: 8000)"
    )
    parser.add_argument(
        "--path", type=str, default="/mcp", help="HTTP path endpoint (default: /mcp)"
    )

    args = parser.parse_args()

    print("Starting AgentSociety MCP Server with Streamable HTTP transport")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Endpoint: http://{args.host}:{args.port}{args.path}")
    print("\nServer is ready to accept connections...")
    print("Press Ctrl+C to stop the server")
    print()

    server = create_mcp_server()

    asyncio.run(server.run(host=args.host, port=args.port, path=args.path))
