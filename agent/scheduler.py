import json
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from agent.tools import TOOL_DEFINITIONS, dispatch_tool
from agent.provider import make_client, chat_step

_console = Console()


def load_prompt(path: str) -> str:
    return Path(path).read_text()


def _dispatch_all(tool_calls: list, log: list) -> list:
    results = []
    for call in tool_calls:
        result = dispatch_tool(call["name"], call["input"])
        log.append({"name": call["name"], "input": call["input"], "result": result})
        results.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
    return results


def agent_turn(client, messages: list, prompt_path: str, provider: str = "groq") -> tuple[str, list, list]:
    system, log = load_prompt(prompt_path), []
    while True:
        text, calls, messages, done = chat_step(client, messages, system, TOOL_DEFINITIONS, provider)
        if not done:
            messages = messages + _dispatch_all(calls, log)
        else:
            return text, messages, log


def run_interactive(prompt_path: str = "agent/prompts/v1.txt", provider: str = "groq") -> None:
    client, messages = make_client(provider), []
    print(f"Clara — Riverside Medical Clinic [{provider}]. Type 'quit' to exit.\n")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        messages.append({"role": "user", "content": user_input})
        reply, messages, _ = agent_turn(client, messages, prompt_path, provider)
        _console.print("\n[bold cyan]Clara:[/bold cyan]")
        _console.print(Markdown(reply))
        print()
