from agent.scheduler import agent_turn
from agent.tools import reset_db
from eval.judge import score_scenario


def _run_scripted_conversation(scenario: dict, prompt_path: str, client, provider: str) -> tuple[str, list]:
    messages, lines, tool_log = [], [], []
    hints = scenario.get("script_hints", [])
    for hint in hints:
        lines.append(f"Patient: {hint}")
        messages.append({"role": "user", "content": hint})
        reply, messages, calls = agent_turn(client, messages, prompt_path, provider)
        tool_log.extend(calls)
        lines.append(f"Clara: {reply}")
    return "\n".join(lines), tool_log


def run_scenario(scenario: dict, prompt_path: str, client, provider: str) -> dict:
    reset_db()
    transcript, tool_log = _run_scripted_conversation(scenario, prompt_path, client, provider)
    result = score_scenario(scenario, transcript, tool_log, client, provider)
    result["transcript"] = transcript
    return result


def run_eval(scenarios: list[dict], prompt_path: str, client, provider: str) -> list[dict]:
    results = []
    for s in scenarios:
        print(f"  → {s['id']} ...", end=" ", flush=True)
        results.append(run_scenario(s, prompt_path, client, provider))
        status = "✓" if results[-1]["passed"] else "✗"
        print(f"{status} ({results[-1]['score']}/{results[-1]['max_score']})")
    return results
