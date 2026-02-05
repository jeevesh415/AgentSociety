import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from io_adapter import ChainlitIOAdapter

async def main(io: "ChainlitIOAdapter"):
    """
    Runs a comprehensive, step-by-step demo of all IO Adapter features.
    """
    await io.print("🚀 **Starting Comprehensive UI Feature Demo**...")
    await io.print("This demo will showcase all available IO capabilities.", type="text")
    await asyncio.sleep(2)

    # 1. Text Input
    await io.print("---", type="text")
    name = await io.input("First, let's get some text input. What is your name?")
    await io.print(f"Hello, **{name}**! Welcome to the comprehensive demo.", type="text")
    await asyncio.sleep(2)

    # 2. Different Print Types
    await io.print("---", type="text")
    await io.print("Next, let's look at the different `print` types.", type="text")
    await asyncio.sleep(1)
    await io.print("This is a `result` type message, great for summaries.", type="result")
    await asyncio.sleep(1)
    await io.print(
        "print('This is a `code` type message.')", type="code", language="python"
    )
    await asyncio.sleep(1)
    await io.print("This is a `log` message. It will appear in its own collapsible step below the main output.", type="log")
    await asyncio.sleep(2)

    # 3. Button Choices
    await io.print("---", type="text")
    choice = await io.ask_choices(
        "Now for button-based input. Which feature do you like most so far?",
        ["Buttons", "Images", "Code Blocks"]
    )
    if choice:
        await io.print(f"You picked **{choice}**. Excellent choice!", type="result")
    else:
        await io.print("You didn't make a choice in time.", type="text")
    await asyncio.sleep(2)

    # 4. Image Display
    await io.print("---", type="text")
    await io.print("Here is an image, displayed using `type='image'`. It can be a URL or a local path.")
    await io.print("https://picsum.photos/400/300", type="image", name="Random Demo Image")
    await asyncio.sleep(2)
    
    # 5. File Download
    await io.print("---", type="text")
    await io.print("And finally, here is a file for you to download, using `send_file()`.")
    await io.send_file("demo.txt", name="demo-report.txt")
    await asyncio.sleep(1)
    
    await io.print("\n✅ **Demo Completed!**", type="text")
    await io.print("You can now add your own experiments to `config.py` and use all these features.", type="result")
