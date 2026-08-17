"""Talk to local Ollama only. PII must not leave this machine."""

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


def chat(cfg: dict, messages: list[dict], *, step: str) -> dict:
    ollama = cfg["ollama"]
    url = ollama["url"].rstrip("/") + "/api/chat"
    assert_local_only(url)
    payload = {
        "model": ollama["model"],
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": ollama.get("temperature", 0.1),
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    timeout = ollama.get("timeout_seconds", 180)
    last_exc: Exception | None = None
    data = None
    # One retry. A hung guidebook must not kill a 400-file overnight run.
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
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
                f"{step}: cannot reach Ollama at {url}. Start Ollama, then retry. ({exc})"
            ) from exc
    if data is None:
        raise TimeoutError(f"{step}: Ollama timed out after {timeout}s") from last_exc
    content = (data.get("message") or {}).get("content") or ""
    parsed = parse_model_json(content, context=step)
    # Ollama reports tokenizer counts on the same response. Record them so the
    # live tracker can show a running total without a second API.
    prompt = int(data.get("prompt_eval_count") or 0)
    completion = int(data.get("eval_count") or 0)
    stage = "other"
    if step.startswith("pass1"):
        stage = "pass1"
    elif step.startswith("pass2"):
        stage = "pass2"
    try:
        from burling.progress import record_tokens

        record_tokens(cfg, prompt, completion, stage)
    except Exception:
        # Progress I/O must never fail a model pass.
        pass
    return parsed
