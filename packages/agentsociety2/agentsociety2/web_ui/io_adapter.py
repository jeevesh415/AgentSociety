"""
Chainlit IO Adapter - Universal Interface Adapter
Converts Console I/O (print/input) into Rich Chainlit Web UI Interactions.

This module provides a standardized way to interact with the Chainlit UI from
any backend logic, enabling console-based applications to leverage a modern,
interactive web interface without significant code changes.

Core Features:
- Rich Outputs: Supports plain text, logs, results, code blocks, and images.
- User Inputs: Handles both free-text input and button-based choices.
- File Handling: Allows offering files for download.
- Context Management: Designed to be used with `async with` for safe activation
  and deactivation.
- Console Fallback: All UI interactions gracefully fall back to standard
  console behavior when not in a Chainlit session.

Basic Usage:

1. Write your application logic in a function that accepts the adapter `io`.
   This function can be in any file, e.g., `my_experiment.py`.

   ```python
   # my_experiment.py
   from typing import TYPE_CHECKING
   if TYPE_CHECKING:
       from io_adapter import ChainlitIOAdapter

   async def main(io: "ChainlitIOAdapter"):
       await io.print("Welcome to the demonstration!")

       # Get free-text input
       name = await io.input("What is your name?")
       await io.print(f"Hello, {name}!")

       # Ask a multiple-choice question with buttons
       choice = await io.ask_choices("Pick a color:", ["Red", "Blue"])
       if choice:
           await io.print(f"You chose {choice}.", type="result")

       # Display an image from a path or URL
       await io.print("path/to/your/logo.png", type="image")

       # Offer a file for download
       await io.send_file("path/to/your/report.pdf")
   ```

2. Register your application in `config.py`.

   ```python
   # config.py
   EXPERIMENTS = [
       {
           "name": "My Awesome Experiment",
           "commands": ["my_exp", "1"],
           "module_path": "my_experiment",
           "function_name": "main",
           "description": "Runs my awesome experiment."
       }
   ]
   ```

3. Run the main `app.py` launcher. The new experiment will be available.
"""

import asyncio
import sys
import logging
import re
from contextlib import asynccontextmanager
from typing import Optional, Any, Callable, Union
from io import StringIO
import os
import chainlit as cl


class ChainlitIOAdapter:
    """
    Chainlit IO Adapter - Intercepts and converts print/input to Web UI interactions.

    This class manages the state of the Chainlit session and provides methods
    to send different types of content (text, logs, results, code) to the UI.
    """

    # ANSI Escape Sequence Regex
    ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def __init__(
        self,
        message_author: str = "System",
        enable_streaming: bool = True,
        buffer_size: int = 100,
        use_step: bool = True,
        step_name: str = "Experiment Logs",
    ):
        """
        Initialize the ChainlitIOAdapter.

        Args:
            message_author (str): Name of the message sender. Default: "System".
            enable_streaming (bool): Whether to enable streaming output. Default: True.
            buffer_size (int): Buffer size (number of lines) before flushing. Default: 100.
            use_step (bool): Whether to use a Step for log output (collapsible). Default: True.
            step_name (str): Name of the log Step. Default: "Experiment Logs".
        """
        self.message_author = message_author
        self.enable_streaming = enable_streaming
        self.buffer_size = buffer_size
        self.use_step = use_step
        self.step_name = step_name
        self.log_step_name = "System Logs"

        # State flags
        self.is_active = False
        self.is_chainlit_session = False

        # Output buffers
        self._output_buffer = []
        self._current_message: Optional[Union[cl.Message, cl.Step]] = None
        self._main_message: Optional[cl.Message] = None
        self._log_step: Optional[cl.Step] = None
        self._system_log_step: Optional[cl.Step] = None

        # Original stdout/stderr backup
        self._original_stdout = None
        self._original_stderr = None

        # Attached Logger Handlers
        self._attached_handlers = []

    async def __aenter__(self):
        """Enter async context manager."""
        await self.activate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        await self.deactivate()

    async def activate(self):
        """
        Activate the adapter - Detect if running in a Chainlit session.
        Initializes the main message and log steps if in a session.
        """
        try:
            # Check if in Chainlit context
            ctx = cl.context.session
            self.is_chainlit_session = ctx is not None
            self.is_active = True

            if self.is_chainlit_session:
                # Create main message for status/progress
                self._main_message = cl.Message(
                    content="🚀 Experiment Initializing...", author=self.message_author
                )
                await self._main_message.send()

                if self.use_step:
                    # Create log Step, attached to main message
                    self._log_step = cl.Step(name=self.step_name, type="run")
                    self._log_step.parent_id = self._main_message.id
                    self._log_step.output = ""
                    await self._log_step.send()
                    self._current_message = self._log_step
                else:
                    # If not using Step, create a new message for output stream
                    self._current_message = cl.Message(
                        content="", author=self.message_author
                    )
                    await self._current_message.send()

        except Exception:
            self.is_chainlit_session = False
            self.is_active = False

    async def deactivate(self):
        """Deactivate the adapter - Flush buffers and clean up."""
        if self._output_buffer:
            await self._flush_buffer()

        # Update status if using Step
        if self._log_step:
            await self._log_step.update()

        if self._system_log_step:
            await self._system_log_step.update()

        # Remove attached Logger Handlers
        for logger, handler in self._attached_handlers:
            logger.removeHandler(handler)
        self._attached_handlers.clear()

        self.is_active = False
        self._current_message = None
        self._main_message = None
        self._log_step = None
        self._system_log_step = None

    async def update_progress(self, content: str):
        """
        Update progress information (displayed in the main message).

        Args:
            content (str): The progress message to display.
        """
        if self.is_chainlit_session and self._main_message:
            self._main_message.content = content
            await self._main_message.update()
        elif not self.is_chainlit_session:
            # Console mode: use carriage return to overwrite line
            print(f"\r{content}", end="", flush=True)

    async def attach_logger(self, logger: logging.Logger):
        """
        Attach a Logger to Chainlit, directing its output to a dedicated Log Step.

        Args:
            logger (logging.Logger): The logger instance to attach.
        """
        if not self.is_chainlit_session:
            return

        # Create dedicated System Logs Step
        if not self._system_log_step and self._main_message:
            self._system_log_step = cl.Step(name=self.log_step_name, type="run")
            self._system_log_step.parent_id = self._main_message.id
            self._system_log_step.output = ""
            await self._system_log_step.send()

        # Add Handler
        handler = ChainlitLogHandler(self)
        # Set format, consistent with console
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Record for cleanup
        self._attached_handlers.append((logger, handler))

    async def log(self, content: str):
        """
        Method specifically for Logger output.

        Args:
            content (str): The log content.
        """
        if not self.is_chainlit_session:
            return

        # Ensure System Log Step exists
        if not self._system_log_step and self._main_message:
            self._system_log_step = cl.Step(name=self.log_step_name, type="run")
            self._system_log_step.parent_id = self._main_message.id
            self._system_log_step.output = ""
            await self._system_log_step.send()

        if self._system_log_step:
            # Strip ANSI codes
            content = self.ANSI_ESCAPE.sub("", content)
            # Remove backticks
            content = content.replace("`", "")

            self._system_log_step.output += content + "\n"
            await self._system_log_step.update()

    async def print_text(
        self, *args, sep: str = " ", end: str = "\n", flush: bool = False, **kwargs
    ):
        """
        Output standard text information.

        Args:
            *args: Content to print.
            sep (str): Separator. Default: " ".
            end (str): End character. Default: "\n".
            flush (bool): Whether to flush immediately. Default: False.
        """
        # Construct output text
        text = sep.join(str(arg) for arg in args) + end

        # Strip ANSI color codes
        text = self.ANSI_ESCAPE.sub("", text)

        if self.is_chainlit_session:
            # Chainlit Session - Send to UI
            self._output_buffer.append(text)

            if flush or len(self._output_buffer) >= self.buffer_size:
                await self._flush_buffer()
        else:
            # Non-Chainlit Session - Use standard print
            print(text, end="", **kwargs)

    async def print_result(self, content: str):
        """
        Output experiment results.

        Args:
            content (str): The result content.
        """
        if self.is_chainlit_session:
            await self._flush_buffer()
            await cl.Message(content=content, author="📊 Result").send()
        else:
            print(f"\n[RESULT]\n{content}\n")

    async def print_code(self, code: str, language: str = "python"):
        """
        Output code block.

        Args:
            code (str): The code content.
            language (str): The programming language. Default: "python".
        """
        if self.is_chainlit_session:
            await self._flush_buffer()
            content = f"```{language}\n{code}\n```"
            await cl.Message(content=content, author="💻 Code").send()
        else:
            print(f"\n```{language}\n{code}\n```\n")

    async def print_image(self, path: str, name: str = "image", size: str = "medium"):
        """
        Output an image. Can be a local path or a URL.

        Args:
            path (str): Path or URL to the image.
            name (str): Name of the image. Default: "image".
            size (str): Size of the image ("small", "medium", "large"). Default: "medium".
        """
        if self.is_chainlit_session:
            await self._flush_buffer()
            # Create an Image element and send it in a message
            # For URLs, we need to use url parameter instead of path
            if path.startswith("http://") or path.startswith("https://"):
                image = cl.Image(url=path, name=name, display="inline", size=size)
            else:
                image = cl.Image(path=path, name=name, display="inline", size=size)
            await cl.Message(
                content="", elements=[image], author=self.message_author
            ).send()
        else:
            print(f"\n[IMAGE: {name} at {path}]\n")

    async def print(self, *args, type: str = "text", **kwargs):
        """
        Universal print method.

        Args:
            *args: Content to print.
            type (str): Output type ("text", "log", "result", "code", "image").
            **kwargs: Additional arguments for print (sep, end, flush, language, name, size).
        """
        if type == "log":
            # For log, we usually expect a single string or we join args
            content = kwargs.get("sep", " ").join(str(a) for a in args)
            await self.log(content)
        elif type == "result":
            content = kwargs.get("sep", " ").join(str(a) for a in args)
            await self.print_result(content)
        elif type == "code":
            # Assume first arg is code, second is language (optional)
            code = args[0] if args else ""
            lang = kwargs.get("language", "python")
            await self.print_code(code, lang)
        elif type == "image":
            # Assume first arg is path
            path = args[0] if args else ""
            name = kwargs.get("name", "image")
            size = kwargs.get("size", "medium")
            await self.print_image(path, name=name, size=size)
        else:
            # Default to text
            await self.print_text(*args, **kwargs)

    async def _flush_buffer(self):
        """Flush output buffer to Chainlit UI."""
        if not self._output_buffer:
            return

        content = "".join(self._output_buffer)
        # Ensure ANSI codes are stripped again
        content = self.ANSI_ESCAPE.sub("", content)

        # Remove symbols that might cause Markdown code block rendering issues
        # 1. Remove backticks `
        content = content.replace("`", "")
        # 2. Remove potential headers # (if at start of line) - Optional
        # content = re.sub(r'(?m)^#+', '', content)

        self._output_buffer.clear()

        try:
            if self._current_message:
                # Update existing message/Step (streaming)
                if isinstance(self._current_message, cl.Step):
                    self._current_message.output += content
                else:
                    self._current_message.content += content
                await self._current_message.update()
            else:
                # If no current message (and not using Step), send new message
                if not self.use_step:
                    msg = cl.Message(content=content, author=self.message_author)
                    await msg.send()
                    if self.enable_streaming:
                        self._current_message = msg
                else:
                    # Defensive: Recreate Step if lost
                    if self.is_chainlit_session and self._main_message:
                        self._log_step = cl.Step(name=self.step_name, type="run")
                        self._log_step.parent_id = self._main_message.id
                        self._log_step.output = content
                        await self._log_step.send()
                        self._current_message = self._log_step

        except Exception as e:
            # Ignore errors caused by session end
            error_str = str(e)
            if "Session not found" in error_str or "Connection closed" in error_str:
                return

            # Fallback to standard output for other errors
            print(f"[Chainlit Error] {e}")
            print(content, end="")

    async def input(self, prompt: str = "", timeout: int = 300) -> str:
        """
        Async alternative to input().

        Args:
            prompt (str): Prompt message.
            timeout (int): Timeout in seconds. Default: 300.

        Returns:
            str: User input string.
        """
        if self.is_chainlit_session:
            # Flush previous output to ensure prompt is at the end
            await self._flush_buffer()

            # Chainlit Session - Use interactive AskUserMessage
            try:
                res = await cl.AskUserMessage(
                    content=prompt or "Please enter your input:", timeout=timeout
                ).send()

                if res:
                    return res.get("output", "")
                else:
                    return ""
            except asyncio.TimeoutError:
                await self.print(f"⏱️ Input timeout after {timeout}s")
                return ""
            except Exception as e:
                await self.print(f"❌ Input error: {e}")
                return ""
        else:
            # Non-Chainlit Session - Use standard input
            return input(prompt)

    async def ask_choices(
        self, content: str, choices: list[str], timeout: int = 300
    ) -> Optional[str]:
        """
        Ask the user to choose from a list of options via buttons.

        Args:
            content (str): The prompt message to display.
            choices (list[str]): A list of strings, where each string is a button label.
            timeout (int): Timeout in seconds. Default: 300.

        Returns:
            Optional[str]: The label of the chosen button, or None if timeout or no selection.
        """
        if self.is_chainlit_session:
            await self._flush_buffer()

            # Create a list of cl.Action from the choices
            actions = [
                cl.Action(name=choice, payload={"value": choice}, label=choice)
                for choice in choices
            ]

            try:
                res = await cl.AskActionMessage(
                    content=content,
                    actions=actions,
                    timeout=timeout,
                    author=self.message_author,
                ).send()

                if res:
                    return res.get("payload", {}).get("value")
                else:
                    return None
            except asyncio.TimeoutError:
                await self.print(f"⏱️ Input timeout after {timeout}s")
                return None
            except Exception as e:
                await self.print(f"❌ Input error: {e}")
                return None
        else:
            # Console fallback
            print(f"\n{content}")
            for i, choice in enumerate(choices, 1):
                print(f"{i}. {choice}")

            while True:
                try:
                    user_choice = int(input(f"Enter your choice (1-{len(choices)}): "))
                    if 1 <= user_choice <= len(choices):
                        return choices[user_choice - 1]
                    else:
                        print("Invalid choice, please try again.")
                except ValueError:
                    print("Please enter a number.")

    async def send_file(self, path: str, name: Optional[str] = None):
        """
        Send a file to the user for download.

        Args:
            path (str): Path to the file.
            name (Optional[str]): Optional display name for the file.
        """
        if self.is_chainlit_session:
            await self._flush_buffer()

            elements = [
                cl.File(
                    path=path, name=name or os.path.basename(path), display="inline"
                )
            ]

            await cl.Message(
                content=f"Attached file: `{name or os.path.basename(path)}`",
                elements=elements,
                author=self.message_author,
            ).send()
        else:
            print(f"\n[FILE: {name or os.path.basename(path)} at {path}]\n")

    def enable_global_redirect(self):
        """
        ⚠️ Advanced: Globally redirect print to Chainlit.

        Note: This affects ALL print() calls, including third-party libraries.
        Use only in fully controlled environments.
        """
        if self._original_stdout is not None:
            return  # Already redirected

        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr

        sys.stdout = _ChainlitStdoutProxy(self)
        sys.stderr = _ChainlitStdoutProxy(self, is_error=True)

    def disable_global_redirect(self):
        """Restore original stdout/stderr."""
        if self._original_stdout is None:
            return

        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr

        self._original_stdout = None
        self._original_stderr = None

    def get_logging_handler(self) -> logging.Handler:
        """Get a logging.Handler to forward logs to Chainlit."""
        return ChainlitLogHandler(self)


class ChainlitLogHandler(logging.Handler):
    """Custom Logging Handler to forward logs to ChainlitIOAdapter."""

    def __init__(self, adapter: ChainlitIOAdapter):
        super().__init__()
        self.adapter = adapter

    def emit(self, record):
        try:
            msg = self.format(record)
            # In Chainlit session, we need to send asynchronously
            # But logging.emit is synchronous
            # We use adapter's logic (creating task)

            if self.adapter.is_chainlit_session:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Use dedicated log method
                    asyncio.create_task(self.adapter.log(msg))
            else:
                # Fallback to stderr if not in session or no loop
                print(msg, file=sys.stderr)
        except Exception:
            self.handleError(record)


class _ChainlitStdoutProxy:
    """Internal class: stdout/stderr proxy object."""

    def __init__(self, adapter: ChainlitIOAdapter, is_error: bool = False):
        self.adapter = adapter
        self.is_error = is_error
        self._buffer = StringIO()

    def write(self, text: str):
        """Intercept write calls."""
        if self.adapter.is_chainlit_session:
            # In Chainlit, handle asynchronously
            # Buffer first, wait for next flush
            self._buffer.write(text)
        else:
            # Write directly to original stdout
            if self.adapter._original_stdout:
                self.adapter._original_stdout.write(text)

    def flush(self):
        """Flush buffer."""
        content = self._buffer.getvalue()
        if content and self.adapter.is_chainlit_session:
            # Create async task to send message
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.adapter.print(content, end="", flush=True))
            except Exception:
                pass
        self._buffer = StringIO()


# ============= Convenience Decorators =============


def chainlit_compatible(func):
    """
    Decorator: Make a function compatible with Chainlit UI.

    Example:
        @chainlit_compatible
        async def my_function():
            io = get_current_io_adapter()
            await io.print("Hello from UI!")
    """

    async def wrapper(*args, **kwargs):
        adapter = ChainlitIOAdapter()
        async with adapter:
            # Inject adapter into context
            _current_adapter.set(adapter)
            try:
                return await func(*args, **kwargs)
            finally:
                _current_adapter.set(None)

    return wrapper


# Global Context Variable
from contextvars import ContextVar

_current_adapter: ContextVar[Optional[ChainlitIOAdapter]] = ContextVar(
    "chainlit_io_adapter", default=None
)


def get_current_io_adapter() -> ChainlitIOAdapter:
    """
    Get the current IO adapter.

    Returns:
        ChainlitIOAdapter: The current adapter instance.

    Raises:
        RuntimeError: If not called within a chainlit_compatible decorator.
    """
    adapter = _current_adapter.get()
    if adapter is None:
        raise RuntimeError(
            "Not in a Chainlit context. "
            "Please use @chainlit_compatible decorator or "
            "create ChainlitIOAdapter manually."
        )
    return adapter


# ============= Sync Wrapper (For compatibility with sync code) =============


class SyncIOWrapper:
    """Sync IO Wrapper - For calling from synchronous code."""

    def __init__(self, adapter: ChainlitIOAdapter):
        self.adapter = adapter

    def print(self, *args, **kwargs):
        """Sync print (creates async task)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.adapter.print(*args, **kwargs))
            else:
                loop.run_until_complete(self.adapter.print(*args, **kwargs))
        except Exception:
            # Fallback to standard print
            print(*args, **kwargs)

    def input(self, prompt: str = "") -> str:
        """Sync input (blocks)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Cannot use run_until_complete in running event loop
                raise RuntimeError(
                    "Cannot use synchronous input in running event loop. "
                    "Please use async version: await adapter.input()"
                )
            return loop.run_until_complete(self.adapter.input(prompt))
        except Exception as e:
            print(f"Error: {e}")
            return input(prompt)


def wrap_sync(adapter: ChainlitIOAdapter) -> SyncIOWrapper:
    """Wrap adapter as synchronous version."""
    return SyncIOWrapper(adapter)


# ============= Universal Utility Functions =============


async def smart_print(
    io: Optional[ChainlitIOAdapter], *args, type: str = "text", **kwargs
):
    """
    Smart Print Function - Decides output method based on IO adapter presence.

    Args:
        io (ChainlitIOAdapter | None): Adapter instance or None.
        *args: Content to print.
        type (str): Output type ("text", "log", "result", "code").
        **kwargs: Additional print arguments (sep, end, flush, etc.).
    """
    if io:
        await io.print(*args, type=type, **kwargs)
    else:
        # Console fallback
        if type == "code":
            print("```")
            print(*args, **kwargs)
            print("```")
        elif type == "result":
            print("\n[RESULT] ", end="")
            print(*args, **kwargs)
        else:
            print(*args, **kwargs)
