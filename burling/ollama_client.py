"""Talk to a local model only (Ollama or OpenAI-compatible llama.cpp).

PII must not leave this machine. Non-localhost URLs are refused.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse


def assert_local_only(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError(
            f"Refusing non-local model URL {url!r}. This harness reviews personal "
            "files and is local-only by design (config policy.local_only)."
        )


def parse_model_json(text: str, *, context: str = "model response") -> dict:
    """Accept fenced JSON, raw JSON, or the first {...} blob. Small models are messy."""
    if not text or not str(text).strip():
        raise ValueError(f"{context}: empty model response")
    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.I)
    if fence:
        raw = fence.group(1).strip()
    try:
        data = json.loads(raw, strict=False)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(raw[start : end + 1], strict=False)
        if isinstance(data, dict):
            return data
    raise ValueError(f"{context}: no JSON object found; starts with {raw[:120]!r}")


def _stage_for(step: str) -> str:
    if step.startswith("pass1"):
        return "pass1"
    if step.startswith("pass2"):
        return "pass2"
    if step.startswith("map"):
        return "map"
    return "other"


def _record_tokens(cfg: dict, prompt: int, completion: int, step: str) -> None:
    try:
        from burling.progress import record_tokens

        record_tokens(cfg, prompt, completion, _stage_for(step))
    except Exception:
        # Progress I/O must never fail a model pass.
        pass


def _post_json(url: str, payload: dict, *, timeout: int, step: str, label: str) -> dict:
    """POST JSON with one timeout retry. GOLDEN RULE: one hung call must not kill the run."""
    assert_local_only(url)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except TimeoutError as exc:
            last_exc = exc
            print(f"  timeout on {step} (attempt {attempt + 1}/2)", flush=True)
        except urllib.error.URLError as exc:
            last_exc = exc
            reason = str(exc.reason).lower() if getattr(exc, "reason", None) else str(exc).lower()
            if "timed out" in reason:
                print(f"  timeout on {step} (attempt {attempt + 1}/2)", flush=True)
                continue
            raise RuntimeError(
                f"{step}: cannot reach {label} at {url}. Start the local server, then retry. ({exc})"
            ) from exc
    raise TimeoutError(f"{step}: {label} timed out after {timeout}s") from last_exc


def _chat_ollama(cfg: dict, messages: list[dict], *, step: str) -> dict:
    ollama = cfg["ollama"]
    url = ollama["url"].rstrip("/") + "/api/chat"
    payload = {
        "model": ollama["model"],
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": ollama.get("temperature", 0.1),
        },
    }
    data = _post_json(
        url,
        payload,
        timeout=ollama.get("timeout_seconds", 180),
        step=step,
        label="Ollama",
    )
    content = (data.get("message") or {}).get("content") or ""
    parsed = parse_model_json(content, context=step)
    _record_tokens(
        cfg,
        int(data.get("prompt_eval_count") or 0),
        int(data.get("eval_count") or 0),
        step,
    )
    return parsed


def _chat_openai(cfg: dict, messages: list[dict], *, step: str) -> dict:
    """llama.cpp / OpenAI-compatible /v1/chat/completions (localhost only)."""
    ollama = cfg["ollama"]
    base = ollama["url"].rstrip("/")
    # Accept either http://127.0.0.1:8080 or .../v1
    if base.endswith("/v1"):
        url = base + "/chat/completions"
    else:
        url = base + "/v1/chat/completions"

    payload: dict = {
        "model": ollama["model"],
        "messages": messages,
        "temperature": ollama.get("temperature", 0.1),
        "max_tokens": int(ollama.get("max_tokens", 2048)),
        "stream": False,
        # Prefer structured JSON when the server supports it.
        "response_format": {"type": "json_object"},
    }
    # Nemotron / DeepSeek-style reasoning burns the token budget unless disabled.
    if ollama.get("enable_thinking", False) is False:
        payload["chat_template_kwargs"] = {"enable_thinking": False}

    data = _post_json(
        url,
        payload,
        timeout=ollama.get("timeout_seconds", 300),
        step=step,
        label="OpenAI-compatible local server",
    )
    choice = ((data.get("choices") or [{}])[0]).get("message") or {}
    content = choice.get("content") or ""
    if not str(content).strip():
        # Fallback if thinking leaked into reasoning_content and content stayed empty.
        content = choice.get("reasoning_content") or ""
    parsed = parse_model_json(content, context=step)
    usage = data.get("usage") or {}
    _record_tokens(
        cfg,
        int(usage.get("prompt_tokens") or 0),
        int(usage.get("completion_tokens") or 0),
        step,
    )
    return parsed


def chat(cfg: dict, messages: list[dict], *, step: str) -> dict:
    """Route to Ollama (/api/chat) or OpenAI-compatible llama.cpp (/v1/chat/completions).

    Best practice: set ``ollama.api`` explicitly in config.yaml:
      - ``ollama`` (default) for Ollama
      - ``openai`` for llama-server and other /v1 endpoints
    """
    api = str((cfg.get("ollama") or {}).get("api") or "ollama").strip().lower()
    if api in {"openai", "openai-compatible", "llamacpp", "llama.cpp"}:
        return _chat_openai(cfg, messages, step=step)
    return _chat_ollama(cfg, messages, step=step)
