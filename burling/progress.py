"""Terminal progress for a long local run.

The run window logs one line per file (scrollback is the audit log).
``python -m burling.run --status`` is a *live* panel: it redraws in place
every second from PROGRESS.json + the ledger. That is safe in a second
PowerShell. ``--once`` prints a single snapshot and exits.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from burling.io_util import atomic_write_json, load_json
from burling.ledger import load_ledger
from burling.paths import output_dir
from burling.trace import utc_now

WATCH_INTERVAL = 1.0
BAR_WIDTH = 28


def console_safe(text: str, stream=None) -> str:
    """Windows cp1252 crashes on odd Unicode in Drive names (e.g. U+2420 symbol-for-space)."""
    enc = getattr(stream or sys.stdout, "encoding", None) or "utf-8"
    return str(text).encode(enc, errors="replace").decode(enc, errors="replace")


def format_duration(seconds: float) -> str:
    """12s, 4m03s, 3h12m — short enough to fit on one terminal line."""
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def progress_file(cfg: dict) -> Path:
    return output_dir(cfg) / "PROGRESS.json"


def tokens_file(cfg: dict) -> Path:
    return output_dir(cfg) / "TOKENS.json"


def format_tokens(n: int) -> str:
    """Human total plus raw count. Overnight 7B runs get into the millions."""
    n = int(n or 0)
    if n >= 1_000_000:
        pretty = f"{n / 1_000_000:.2f}M"
    elif n >= 10_000:
        pretty = f"{n / 1_000:.1f}k"
    else:
        pretty = str(n)
    return f"{n:,}  ({pretty})"


def empty_token_stats() -> dict:
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "calls": 0,
        "pass1_tokens": 0,
        "pass2_tokens": 0,
        "map_tokens": 0,
        "audit_tokens": 0,
        "last_prompt_tokens": 0,
        "last_completion_tokens": 0,
        "updated_at": None,
    }


def record_tokens(cfg: dict, prompt: int, completion: int, stage: str) -> dict:
    """Add one Ollama call to the running total. Written after every call so the live view can read it."""
    path = tokens_file(cfg)
    data = load_json(path, empty_token_stats()) or empty_token_stats()
    for key, default in empty_token_stats().items():
        data.setdefault(key, default)
    prompt = int(prompt or 0)
    completion = int(completion or 0)
    total = prompt + completion
    data["prompt_tokens"] += prompt
    data["completion_tokens"] += completion
    data["total_tokens"] += total
    data["calls"] += 1
    data["last_prompt_tokens"] = prompt
    data["last_completion_tokens"] = completion
    if stage == "pass1":
        data["pass1_tokens"] += total
    elif stage == "pass2":
        data["pass2_tokens"] += total
    elif stage == "map":
        data["map_tokens"] += total
    elif stage == "audit":
        data["audit_tokens"] += total
    data["updated_at"] = utc_now()
    atomic_write_json(path, data)
    return data


def _enable_ansi() -> None:
    """Windows consoles need VT mode before cursor-up redraw works."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint()
        if ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def _bar(pct: float, width: int = BAR_WIDTH) -> str:
    pct = max(0.0, min(100.0, float(pct or 0)))
    filled = int(round(width * pct / 100.0))
    filled = min(width, max(0, filled))
    return "#" * filled + "-" * (width - filled)


def _age_seconds(iso_ts: str | None) -> float | None:
    if not iso_ts:
        return None
    try:
        stamp = datetime.fromisoformat(iso_ts)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - stamp).total_seconds())
    except ValueError:
        return None


class Progress:
    """One stage (queue / pass1 / pass2). Tick once per document, before the work."""

    def __init__(self, cfg: dict, stage: str, total: int, stream=None) -> None:
        self.cfg = cfg
        self.stage = stage
        self.total = max(int(total), 0)
        self.stream = stream or sys.stdout
        self.started = time.monotonic()

    def tick(self, index: int, rel_path: str, *, note: str = "") -> None:
        try:
            elapsed = time.monotonic() - self.started
            rate = elapsed / index if index else 0
            left = max(self.total - index, 0)
            eta = left * rate if index else 0
            pct = (100.0 * index / self.total) if self.total else 0.0
            extra = f"  {note}" if note else ""
            name = rel_path if len(rel_path) < 80 else "…" + rel_path[-79:]
            line = (
                f"[{self.stage} {index}/{self.total} {pct:5.1f}%]  "
                f"elapsed {format_duration(elapsed)}  "
                f"eta {format_duration(eta)}  "
                f"{rate:.0f}s/file  {name}{extra}"
            )
            atomic_write_json(
                progress_file(self.cfg),
                {
                    "stage": self.stage,
                    "current": index,
                    "total": self.total,
                    "percent": round(pct, 1),
                    "rel_path": rel_path,
                    "elapsed_seconds": int(elapsed),
                    "eta_seconds": int(eta),
                    "seconds_per_file": round(rate, 1),
                    "updated_at": utc_now(),
                },
            )
            print(console_safe(line, self.stream), file=self.stream, flush=True)
        except Exception:
            # Progress I/O must not kill the run. The file loop still continues.
            pass

    def finish(self, done: int) -> None:
        try:
            elapsed = time.monotonic() - self.started
            print(
                console_safe(
                    f"[{self.stage} done]  {done}/{self.total} this run  "
                    f"elapsed {format_duration(elapsed)}",
                    self.stream,
                ),
                file=self.stream,
                flush=True,
            )
            atomic_write_json(
                progress_file(self.cfg),
                {
                    "stage": f"{self.stage}-done",
                    "current": done,
                    "total": self.total,
                    "percent": 100.0 if self.total else 0.0,
                    "rel_path": "",
                    "elapsed_seconds": int(elapsed),
                    "eta_seconds": 0,
                    "seconds_per_file": round(elapsed / done, 1) if done else 0,
                    "updated_at": utc_now(),
                },
            )
        except Exception:
            pass


def ledger_status(cfg: dict) -> dict:
    """Counts from the ledger. Safe to call from a second terminal while a run is live."""
    ledger = load_ledger(cfg)
    rows = list((ledger.get("documents") or {}).values())
    extract_ok = sum(1 for r in rows if (r.get("extraction") or {}).get("ok"))
    extract_fail = sum(1 for r in rows if not (r.get("extraction") or {}).get("ok"))
    p1_done = sum(1 for r in rows if (r.get("pass1") or {}).get("status") == "done")
    p2_done = sum(1 for r in rows if (r.get("pass2") or {}).get("status") == "done")
    p1_wait = sum(
        1
        for r in rows
        if (r.get("extraction") or {}).get("ok") and not r.get("pass1")
    )
    p2_wait = sum(
        1
        for r in rows
        if (r.get("extraction") or {}).get("ok") and not r.get("pass2")
    )
    delete = sum(
        1 for r in rows if (r.get("pass2") or {}).get("recommendation") == "delete_candidate"
    )
    ssn = sum(1 for r in rows if "ssn" in (r.get("priors") or {}))
    map_done = sum(
        1 for r in rows if (r.get("placement") or {}).get("status") in {"done", "skipped"}
    )
    map_review = sum(
        1 for r in rows if (r.get("placement") or {}).get("needs_review")
    )
    live = load_json(progress_file(cfg), {}) or {}
    tokens = load_json(tokens_file(cfg), empty_token_stats()) or empty_token_stats()
    return {
        "intake": ledger.get("intake"),
        "documents": len(rows),
        "extract_ok": extract_ok,
        "extract_fail": extract_fail,
        "pass1_done": p1_done,
        "pass1_waiting": p1_wait,
        "pass2_done": p2_done,
        "pass2_waiting": p2_wait,
        "map_done": map_done,
        "map_review": map_review,
        "ssn_flagged": ssn,
        "delete_candidates": delete,
        "live": live,
        "tokens": tokens,
    }


def render_status(cfg: dict) -> str:
    """Fixed-height panel so the live watcher can redraw in place."""
    st = ledger_status(cfg)
    live = st.get("live") or {}
    pct = float(live.get("percent") or 0)
    stage = live.get("stage") or "idle"
    current = live.get("current") or 0
    total = live.get("total") or 0
    eta = format_duration(live.get("eta_seconds") or 0)
    rate = live.get("seconds_per_file") or 0
    age = _age_seconds(live.get("updated_at"))
    on_file = format_duration(age) if age is not None else "—"
    hung = ""
    if age is not None and age > 180 and not str(stage).endswith("-done"):
        hung = "  (quiet >3m — check the run window)"
    now = live.get("rel_path") or "(waiting for first file)"
    if len(now) > 90:
        now = "…" + now[-89:]

    stage_names = {
        "queue": "1/4 extract + regex (not the model yet)",
        "queue-done": "1/4 extract done — starting pass 1",
        "pass1": "2/4 pass 1 tags (local 7B)",
        "pass1-done": "2/4 pass 1 done — starting pass 2",
        "pass2": "3/4 pass 2 keep/delete (local 7B)",
        "pass2-done": "3/4 finished — starting topic map",
        "map": "4/4 topic map (taxonomy placement)",
        "map-done": "4/4 topic map done",
        "idle": "waiting for a run",
    }
    stage_index = {
        "queue": 0,
        "queue-done": 1,
        "pass1": 1,
        "pass1-done": 2,
        "pass2": 2,
        "pass2-done": 3,
        "map": 3,
        "map-done": 4,
    }
    base = stage_index.get(str(stage), 0)
    if str(stage).endswith("-done"):
        overall = min(100.0, base / 4.0 * 100.0)
    else:
        overall = min(100.0, (base + pct / 100.0) / 4.0 * 100.0)

    tok = st.get("tokens") or empty_token_stats()

    lines = [
        "Burling live tracker    refresh 1s    Ctrl+C to stop",
        "",
        f"overall      {_bar(overall)}  {overall:5.1f}%   (queue + pass1 + pass2 + map)",
        f"this stage   {_bar(pct)}  {pct:5.1f}%   {current}/{total}  {stage}",
        f"what         {stage_names.get(str(stage), stage)}",
        f"eta {eta}    {rate}s/file    this file {on_file}{hung}",
        f"now: {now}",
        "",
        f"extract      {st['extract_ok']} ok   /  {st['extract_fail']} failed",
        f"pass 1       {st['pass1_done']} done  /  {st['pass1_waiting']} waiting",
        f"pass 2       {st['pass2_done']} done  /  {st['pass2_waiting']} waiting",
        f"topic map    {st.get('map_done', 0)} placed /  {st.get('map_review', 0)} needs review",
        f"SSN regex    {st['ssn_flagged']}         delete cand {st['delete_candidates']} (not deleted)",
        f"documents    {st['documents']}",
        f"tokens       {format_tokens(tok.get('total_tokens') or 0)}  total",
        f"             in {tok.get('prompt_tokens') or 0:,}  out {tok.get('completion_tokens') or 0:,}  "
        f"calls {tok.get('calls') or 0}  "
        f"p1 {tok.get('pass1_tokens') or 0:,}  p2 {tok.get('pass2_tokens') or 0:,}  "
        f"map {tok.get('map_tokens') or 0:,}",
        f"last call    in {tok.get('last_prompt_tokens') or 0:,}  out {tok.get('last_completion_tokens') or 0:,}",
        f"updated      {live.get('updated_at') or '—'}",
    ]
    return "\n".join(lines) + "\n"


def print_status(cfg: dict, stream=None) -> None:
    stream = stream or sys.stdout
    stream.write(render_status(cfg))
    stream.flush()


def watch_status(cfg: dict, *, interval: float = WATCH_INTERVAL) -> int:
    """Redraw the panel in place until Ctrl+C. This is the live tracker."""
    _enable_ansi()
    painted = 0
    try:
        while True:
            try:
                panel = render_status(cfg)
            except (PermissionError, OSError, json.JSONDecodeError, ValueError):
                # Writer holds the JSON for a moment. Do not kill the tracker.
                time.sleep(max(0.2, interval))
                continue
            height = panel.count("\n")
            if painted:
                # Move up and clear below the cursor so the panel does not scroll.
                sys.stdout.write(f"\033[{painted}A\033[J")
            sys.stdout.write(console_safe(panel))
            sys.stdout.flush()
            painted = height
            time.sleep(max(0.2, interval))
    except KeyboardInterrupt:
        sys.stdout.write("\nstopped live tracker\n")
        sys.stdout.flush()
        return 0
    return 0


def main() -> int:
    """``python -m burling.progress`` — live tracker, no other flags needed."""
    from burling.paths import load_config

    return watch_status(load_config())


if __name__ == "__main__":
    raise SystemExit(main())
