"""
Chainlit Web UI - Generic Experiment Launcher
Provides a configurable Web UI entry point for running various experiments.
"""

import importlib
from typing import Optional

import chainlit as cl

from .io_adapter import ChainlitIOAdapter, _current_adapter
from .config import EXPERIMENTS


def build_welcome_message():
    """Builds the welcome message from the experiments config."""
    welcome_msg = "# 🎭 AgentSociety Web UI\n\n"

    welcome_msg += "Welcome! Experience the interactive UI features demo.\n\n"

    if EXPERIMENTS:
        exp = EXPERIMENTS[0]
        commands = " or ".join(f"`{c}`" for c in exp["commands"])
        welcome_msg += f"**{exp['description']}**\n\n"
        welcome_msg += f"Type {commands} to start the demo.\n\n"

    welcome_msg += "---\n\nType your command below to begin!"
    return welcome_msg


@cl.on_chat_start
async def on_chat_start():
    """Called when the Chainlit session starts."""
    await cl.Message(content=build_welcome_message()).send()
    cl.user_session.set("experiment_running", False)


@cl.on_message
async def on_message(message: cl.Message):
    """Handle user messages and route to the correct experiment."""
    user_input = message.content.strip().lower()

    if cl.user_session.get("experiment_running", False):
        await cl.Message(
            content="⚠️ An experiment is already running. Please wait for it to complete."
        ).send()
        return

    if user_input == "help":
        await show_help()
        return

    # Find the experiment to run
    selected_experiment = None
    for exp in EXPERIMENTS:
        if user_input in exp["commands"]:
            selected_experiment = exp
            break

    if selected_experiment:
        await run_experiment(selected_experiment)
    else:
        await cl.Message(
            content=f"❓ Unrecognized command: `{message.content}`\n\nPlease type `help` to view available commands."
        ).send()


async def show_help():
    """Dynamically display help information."""
    help_text = "## 📖 Command Help\n\n**Available Commands:**\n"
    for exp in EXPERIMENTS:
        commands = " or ".join(f"`{c}`" for c in exp["commands"])
        help_text += f"- {commands} - {exp['description']}\n"

    help_text += "- `help` - Show this help message\n"
    await cl.Message(content=help_text).send()


async def run_experiment(experiment_config: dict):
    """Generic function to run a selected experiment."""
    cl.user_session.set("experiment_running", True)

    adapter = ChainlitIOAdapter(
        message_author=experiment_config["name"],
        enable_streaming=True,
        use_step=False,
    )

    try:
        module_path = experiment_config["module_path"]
        function_name = experiment_config["function_name"]

        await cl.Message(
            content=f"🚀 Starting **{experiment_config['name']}**..."
        ).send()

        # Activate adapter
        await adapter.activate()
        _current_adapter.set(adapter)

        try:
            # Dynamically import the module and run the main function
            experiment_module = importlib.import_module(module_path)
            main_func = getattr(experiment_module, function_name)

            # Run the experiment's main function, passing the I/O adapter
            await main_func(io=adapter)

            await cl.Message(
                content=f"✅ **{experiment_config['name']}** Completed!"
            ).send()

        except ModuleNotFoundError:
            await cl.Message(
                content=f"❌ Error: The module `{module_path}` was not found."
            ).send()
        except AttributeError:
            await cl.Message(
                content=f"❌ Error: The function `{function_name}` was not found in module `{module_path}`."
            ).send()
        except Exception as e:
            await cl.Message(
                content=f"❌ Experiment Execution Error:\n```\n{str(e)}\n```"
            ).send()
        finally:
            # Cleanup
            await adapter.deactivate()
            _current_adapter.set(None)

    finally:
        cl.user_session.set("experiment_running", False)


@cl.on_chat_end
async def on_chat_end():
    """Cleanup on session end."""
    await cl.Message(content="👋 Thank you for using the AgentSociety UI!").send()


if __name__ == "__main__":
    print("⚠️ This script is meant to be run with Chainlit: `chainlit run app.py -w`")
