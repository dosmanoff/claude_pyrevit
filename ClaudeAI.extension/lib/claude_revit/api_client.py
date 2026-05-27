"""Stdlib-only HTTP client for the Anthropic Messages API.

We deliberately avoid the official `anthropic` SDK so the extension has
no pip dependencies — pyRevit users get a clean drop-in.

The public entry point is `run_turn`, which takes a conversation
history plus a `tool_dispatcher` callable and drives the tool-use loop
until the model returns `end_turn` (or hits MAX_TOOL_ROUNDS).
"""

import json
import ssl
import urllib.error
import urllib.request

from . import config


class AnthropicError(Exception):
    pass


def test_api_key(key):
    """Cheap connectivity + auth check. Returns (ok: bool, message: str)."""
    if not key:
        return False, "No API key provided."
    req = urllib.request.Request(
        config.ANTHROPIC_BASE_URL + "/v1/models?limit=1",
        method="GET",
    )
    req.add_header("x-api-key", key)
    req.add_header("anthropic-version", config.ANTHROPIC_VERSION)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            json.loads(resp.read().decode("utf-8"))  # validate shape
        return True, "OK — key accepted."
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = ""
        if e.code == 401:
            return False, "401 Unauthorized — key is invalid."
        return False, "HTTP {}: {}".format(e.code, body[:200])
    except urllib.error.URLError as e:
        return False, "Network error: {}".format(e)


def _post_messages(payload):
    """Single HTTP call to /v1/messages. Returns the parsed JSON body."""
    api_key = config.get_api_key()
    if not api_key:
        raise AnthropicError(
            "No Anthropic API key found. Set ANTHROPIC_API_KEY env var or "
            "create lib/claude_revit/_local_config.py with ANTHROPIC_API_KEY."
        )

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        config.ANTHROPIC_BASE_URL + "/v1/messages",
        data=body,
        method="POST",
    )
    req.add_header("x-api-key", api_key)
    req.add_header("anthropic-version", config.ANTHROPIC_VERSION)
    req.add_header("content-type", "application/json")

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = ""
        raise AnthropicError(
            "Anthropic API error {}: {}".format(e.code, err_body)
        )
    except urllib.error.URLError as e:
        raise AnthropicError("Network error talking to Anthropic: {}".format(e))


def _with_cache_control(blocks):
    """Mark the last block as cacheable so the system prompt + tools schema
    can be reused across turns (5-min TTL on Anthropic's side)."""
    if not blocks:
        return blocks
    blocks = list(blocks)
    last = dict(blocks[-1])
    last["cache_control"] = {"type": "ephemeral"}
    blocks[-1] = last
    return blocks


def run_turn(
    messages,
    system_prompt,
    tools_schema,
    tool_dispatcher,
    on_progress=None,
):
    """Drive a single user turn through the tool-use loop.

    Args:
        messages: full conversation history (user/assistant message dicts).
                  This list IS MUTATED — assistant + tool_result messages
                  are appended to it as the loop runs.
        system_prompt: plain string.
        tools_schema: list of tool definitions.
        tool_dispatcher: callable (tool_name, tool_input) -> dict or string.
                         Anything raised becomes a tool_result with is_error.
        on_progress: optional callable(stage, detail) for UI updates.

    Returns:
        dict with keys:
          'text'         — final assistant text shown to the user
          'usage_total'  — cumulative token usage across all rounds in this turn
          'rounds'       — how many API calls were made
          'stopped_by'   — 'end_turn' | 'cap' | 'cancelled'
    """
    system_blocks = _with_cache_control(
        [{"type": "text", "text": system_prompt}]
    )
    cached_tools = _with_cache_control(tools_schema)

    usage_total = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }
    rounds = 0
    final_text_parts = []
    stopped_by = "cap"

    for _ in range(config.MAX_TOOL_ROUNDS):
        rounds += 1
        if on_progress:
            on_progress("api_call", "round {}".format(rounds))

        payload = {
            "model": config.get_model(),
            "max_tokens": config.DEFAULT_MAX_TOKENS,
            "system": system_blocks,
            "tools": cached_tools,
            "messages": messages,
        }
        resp = _post_messages(payload)

        u = resp.get("usage", {}) or {}
        for k in usage_total:
            usage_total[k] += u.get(k, 0) or 0

        content = resp.get("content", []) or []
        # Always append assistant turn verbatim before tool_result.
        messages.append({"role": "assistant", "content": content})

        stop_reason = resp.get("stop_reason")
        if stop_reason != "tool_use":
            for block in content:
                if block.get("type") == "text":
                    final_text_parts.append(block.get("text", ""))
            stopped_by = stop_reason or "end_turn"
            break

        # tool_use path: run each tool_use block, gather tool_result blocks.
        tool_results = []
        for block in content:
            if block.get("type") != "tool_use":
                continue
            tool_name = block.get("name")
            tool_input = block.get("input") or {}
            tool_use_id = block.get("id")

            if on_progress:
                on_progress("tool", "{}".format(tool_name))

            try:
                result = tool_dispatcher(tool_name, tool_input)
                is_error = False
            except Exception as e:
                result = "Tool {} raised: {}".format(tool_name, e)
                is_error = True

            if not isinstance(result, str):
                try:
                    result = json.dumps(result, ensure_ascii=False, default=str)
                except Exception:
                    result = str(result)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": result,
                "is_error": is_error,
            })

        messages.append({"role": "user", "content": tool_results})
        # loop and call the API again

    return {
        "text": "\n".join(p for p in final_text_parts if p).strip(),
        "usage_total": usage_total,
        "rounds": rounds,
        "stopped_by": stopped_by,
    }
