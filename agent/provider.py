import json
import os
import re
import time

ANT_MODEL  = "claude-sonnet-4-6"
GROQ_AGENT = "qwen/qwen3.8-27b"
GROQ_FAST  = "qwen/qwen3.8-27b"


def make_client(provider: str = "groq"):
    if provider == "groq":
        from openai import OpenAI
        return OpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.getenv("GROQ_API_KEY"))
    from anthropic import Anthropic
    return Anthropic()


# ── Format converters (internal ↔ provider) ──────────────────────────────────

def _groq_tools(ant_tools: list) -> list:
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
             "parameters": t["input_schema"]}} for t in ant_tools]


def _ant_tool_result(m: dict, out: list) -> None:
    tr = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
    if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
        out[-1]["content"].append(tr)
    else:
        out.append({"role": "user", "content": [tr]})


def _ant_msgs(messages: list) -> list:
    """Internal (OpenAI-style) messages → Anthropic API format."""
    out = []
    for m in messages:
        if m["role"] == "tool":
            _ant_tool_result(m, out)
        elif m["role"] == "assistant" and m.get("tool_calls"):
            body = ([{"type": "text", "text": m["content"]}] if m.get("content") else [])
            body += [{"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["input"]} for tc in m["tool_calls"]]
            out.append({"role": "assistant", "content": body})
        else:
            out.append({"role": m["role"], "content": m.get("content") or ""})
    return out


# ── Single-step chat (with tool support) ─────────────────────────────────────

def _pack(text, calls, messages) -> tuple:
    new_msg = {"role": "assistant", "content": text or None, "tool_calls": calls} if calls \
              else {"role": "assistant", "content": text}
    return text, calls, messages + [new_msg], not bool(calls)


def chat_step_ant(client, messages: list, system: str, tools: list, max_tokens: int = 1024) -> tuple:
    resp  = client.messages.create(model=ANT_MODEL, max_tokens=max_tokens,
                                   system=system, tools=tools, messages=_ant_msgs(messages))
    text  = next((b.text for b in resp.content if hasattr(b, "text")), "")
    calls = [{"id": b.id, "name": b.name, "input": b.input} for b in resp.content if b.type == "tool_use"]
    return _pack(text, calls, messages)


def _oai_tcs(raw_tcs: list) -> list:
    return [{"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in raw_tcs]


def _groq_create(client, **kwargs):
    for wait in [5, 15, 30]:
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            if "429" in str(e) and "TPD" not in str(e):
                print(f"\n  [rate limit — retrying in {wait}s]", end=" ", flush=True)
                time.sleep(wait)
            else:
                raise
    return client.chat.completions.create(**kwargs)


def chat_step_groq(client, messages: list, system: str, tools: list, max_tokens: int = 1024) -> tuple:
    msgs   = [{"role": "system", "content": system}] + messages
    kwargs = dict(model=GROQ_AGENT, max_tokens=max_tokens, messages=msgs)
    if tools:
        kwargs.update(tools=_groq_tools(tools), tool_choice="auto")
    msg   = _groq_create(client, **kwargs).choices[0].message
    calls = [{"id": tc.id, "name": tc.function.name, "input": json.loads(tc.function.arguments)}
             for tc in (msg.tool_calls or [])]
    text  = _strip_think(msg.content or "")
    new_msg = {"role": "assistant", "content": text or None, "tool_calls": _oai_tcs(msg.tool_calls)} \
              if calls else {"role": "assistant", "content": text}
    return text, calls, messages + [new_msg], not bool(calls)


def chat_step(client, messages: list, system: str, tools: list, provider: str, max_tokens: int = 1024) -> tuple:
    if provider == "anthropic":
        return chat_step_ant(client, messages, system, tools, max_tokens)
    return chat_step_groq(client, messages, system, tools, max_tokens)


# ── Simple text-only chat (judge + patient simulator) ────────────────────────

def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def simple_chat(client, messages: list, system: str, provider: str,
                max_tokens: int = 512, temperature: float | None = None) -> str:
    if provider == "anthropic":
        kw = dict(model=ANT_MODEL, max_tokens=max_tokens, system=system, messages=messages)
        if temperature is not None:
            kw["temperature"] = temperature
        return client.messages.create(**kw).content[0].text
    msgs = [{"role": "system", "content": system}] + messages
    kw   = dict(model=GROQ_FAST, max_tokens=max_tokens, messages=msgs)
    if temperature is not None:
        kw["temperature"] = max(temperature, 0.01)
    raw = _groq_create(client, **kw).choices[0].message.content or ""
    return _strip_think(raw)
