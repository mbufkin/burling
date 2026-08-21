"""Talk to a local model (Ollama / llama.cpp) or the NVIDIA NIM *proxy*.

PII must not leave this machine. Direct cloud URLs are refused. The NIM
proxy on 127.0.0.1:8787 is localhost, but it forwards to NVIDIA — so it
is only allowed when ``policy.public_corpus`` is true and the intake is
not a workplace dump (the 20news spike).
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

NIM_PROXY_PORTS = {8787}


def assert_local_only(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError(
            f"Refusing non-local model URL {url!r}. This harness reviews personal "
            "files and is local-only by design (config policy.local_only)."
        )


def _is_nim_proxy(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"} and parsed.port in NIM_PROXY_PORTS


def assert_cloud_allowed(cfg: dict) -> None:
    """NIM proxy is localhost, but the bytes still leave the box.

    Best practice: fail closed. Workplace CTE dumps never go through :8787.
    The 20news spike sets ``policy.public_corpus: true`` on purpose.
    """
    ollama = cfg.get("ollama") or {}
    url = str(ollama.get("url") or "")
    if not _is_nim_proxy(url):
        return
    policy = cfg.get("policy") or {}
    if not policy.get("public_corpus"):
        raise RuntimeError(
            "NVIDIA NIM proxy requires policy.public_corpus: true "
            "(20news / non-sensitive spike only)."
        )
    intake = str((cfg.get("paths") or {}).get("intake_dir") or "").lower()
    if "cte-manager" in intake:
        raise RuntimeError(
            f"Refusing NVIDIA NIM proxy for workplace intake {intake!r}."
        )


def _repair_json(raw: str) -> str:
    """Fix the two Nemotron mistakes that otherwise kill a finished run.

    Best practice: never let one trailing comma or a ``//`` comment take down
    Pass B after hours of tagging. Repair is conservative — only drop trailing
    commas before ``}`` / ``]`` and strip ``//`` line comments.
    """
    # ``// comment`` is not JSON; Nemotron sometimes annotates a region.
    no_comments = re.sub(r"(?m)//[^\n]*", "", raw)
    # Trailing commas: ``{"a": 1,}`` or ``[1, 2,]``.
    return re.sub(r",(\s*[}\]])", r"\1", no_comments)


def parse_model_json(text: str, *, context: str = "model response") -> dict:
    """Accept fenced JSON, raw JSON, or the first {...} blob. Small models are messy.

    Best practice: every candidate blob is tried raw *and* repaired. The old
    second ``json.loads`` was unguarded — a trailing comma raised
    ``JSONDecodeError`` and aborted stitch after tags had already finished.
    """
    if not text or not str(text).strip():
        raise ValueError(f"{context}: empty model response")
    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.I)
    if fence:
        raw = fence.group(1).strip()

    candidates = [raw]
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        candidates.append(raw[start : end + 1])

    last_err: Exception | None = None
    for cand in candidates:
        for blob in (cand, _repair_json(cand)):
            try:
                data = json.loads(blob, strict=False)
            except json.JSONDecodeError as exc:
                last_err = exc
                continue
            if isinstance(data, dict):
                return data
    raise ValueError(f"{context}: no JSON object found; starts with {raw[:120]!r}") from last_err


def _stage_for(step: str) -> str:
    if step.startswith("pass1"):
        return "pass1"
    if step.startswith("pass2"):
        return "pass2"
    if step.startswith("map"):
        return "map"
    if step.startswith("audit"):
        return "audit"
    return "other"


def _record_tokens(cfg: dict, prompt: int, completion: int, step: str) -> None:
    try:
        from burling.progress import record_tokens

        record_tokens(cfg, prompt, completion, _stage_for(step))
    except Exception:
        # Progress I/O must never fail a model pass.
        pass


def _post_json(url: str, payload: dict, *, timeout: int, step: str, label: str) -> dict:
    """POST JSON with timeout / 429 retries. GOLDEN RULE: one hung call must not kill the run."""
    assert_local_only(url)
    body = json.dumps(payload).encode("utf-8")
    last_exc: Exception | None = None
    for attempt in range(3):
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except TimeoutError as exc:
            last_exc = exc
            print(f"  timeout on {step} (attempt {attempt + 1}/3)", flush=True)
        except urllib.error.HTTPError as exc:
            last_exc = exc
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:240]
            except Exception:
                detail = str(exc)
            if exc.code == 429:
                wait = 20 * (attempt + 1)
                print(f"  429 on {step}, sleep {wait}s (attempt {attempt + 1}/3)", flush=True)
                time.sleep(wait)
                continue
            raise RuntimeError(f"{step}: {label} HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            last_exc = exc
            reason = str(exc.reason).lower() if getattr(exc, "reason", None) else str(exc).lower()
            if "timed out" in reason:
                print(f"  timeout on {step} (attempt {attempt + 1}/3)", flush=True)
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
    }
    # llama.cpp likes json_object. NVIDIA NIM often rejects it — leave unset
    # unless the config asks. Then we parse a JSON blob out of the text.
    response_format = ollama.get("response_format")
    if response_format in (None, "", False):
        model_id = str(ollama.get("model") or "")
        if not model_id.startswith("nvidia/") and "nemotron" not in model_id.lower():
            response_format = "json_object"
    if response_format:
        payload["response_format"] = (
            {"type": response_format} if isinstance(response_format, str) else response_format
        )
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
    """Route to Ollama, llama.cpp, or the NVIDIA NIM proxy.

    Best practice: set ``ollama.api`` explicitly in config.yaml:
      - ``ollama`` (default) for Ollama
      - ``openai`` for llama-server and other /v1 endpoints

    GOLDEN RULE: one malformed generation must not kill the run. Retry once
    when the model returns unparseable JSON (common on the large stitch tree).
    """
    assert_cloud_allowed(cfg)
    api = str((cfg.get("ollama") or {}).get("api") or "ollama").strip().lower()
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            if api in {"openai", "openai-compatible", "llamacpp", "llama.cpp"}:
                return _chat_openai(cfg, messages, step=step)
            return _chat_ollama(cfg, messages, step=step)
        except (ValueError, json.JSONDecodeError) as exc:
            last_exc = exc
            print(f"  bad JSON on {step} (attempt {attempt + 1}/2): {exc}", flush=True)
    raise last_exc if last_exc else RuntimeError(f"{step}: JSON parse failed")
