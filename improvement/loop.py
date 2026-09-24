import json
import re
from pathlib import Path
from agent.provider import simple_chat

_IMPROVER_SYSTEM = (
    "You are a prompt engineer improving a medical scheduling agent's system prompt. "
    "Given failing transcripts, identify the root cause and output a targeted patch as JSON. "
    "Return ONLY valid JSON — no prose, no markdown fences."
)

_PATCH_SCHEMA = (
    '{"root_cause": "...", "section_to_modify": "...", '
    '"append_after_marker": "exact line from prompt to insert after", "new_content": "lines to insert"}'
)


def load_prompt(path: str) -> str:
    return Path(path).read_text()


def save_prompt(content: str, path: str) -> None:
    Path(path).write_text(content)


def _format_failures(failures: list[dict]) -> str:
    parts = [
        f"### {f['scenario_id']}\nTranscript:\n{f['transcript']}\n"
        f"Det checks: {json.dumps(f['deterministic'])}\n"
        f"Judge reasoning: {json.dumps(f.get('llm_reasoning', {}))}"
        for f in failures
    ]
    return "\n\n".join(parts)


def generate_patch(current_prompt: str, failures: list[dict], client, provider: str) -> dict:
    prompt = (
        f"Current system prompt:\n<prompt>\n{current_prompt}\n</prompt>\n\n"
        f"Failing scenarios:\n{_format_failures(failures)}\n\n"
        f"Output a JSON patch:\n{_PATCH_SCHEMA}"
    )
    raw   = simple_chat(client, [{"role": "user", "content": prompt}], _IMPROVER_SYSTEM, provider, max_tokens=1024, temperature=0)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    return json.loads(match.group()) if match else {}


def apply_patch(prompt: str, patch: dict) -> str:
    marker, content = patch.get("append_after_marker", ""), patch.get("new_content", "")
    if marker and marker in prompt:
        return prompt.replace(marker, f"{marker}\n{content}", 1)
    return prompt + f"\n\n{content}"


def check_regressions(before: list[dict], after: list[dict]) -> list[str]:
    before_map = {r["scenario_id"]: r["passed"] for r in before}
    after_map  = {r["scenario_id"]: r["passed"] for r in after}
    return [sid for sid, passed in before_map.items() if passed and not after_map.get(sid)]


def improvement_loop(scenarios, v1_path: str, v2_path: str, client, provider: str) -> tuple[list, list, dict]:
    from eval.harness import run_eval
    results_v1 = run_eval(scenarios, v1_path, client, provider)
    failures   = [r for r in results_v1 if not r["passed"]]
    if not failures:
        return results_v1, results_v1, {"patch": {}, "regressions": [], "note": "All passed — no improvement needed"}
    patch      = generate_patch(load_prompt(v1_path), failures, client, provider)
    save_prompt(apply_patch(load_prompt(v1_path), patch), v2_path)
    results_v2  = run_eval(scenarios, v2_path, client, provider)
    regressions = check_regressions(results_v1, results_v2)
    return results_v1, results_v2, {"patch": patch, "regressions": regressions}
