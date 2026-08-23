"""Live RALP test tracker — second terminal, redraws in place.

    python -m burling.ralp_tracker --config burling/config.sort-sample.yaml

Ctrl+C stops the tracker only. The run keeps going.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from burling.io_util import load_json
from burling.paths import load_config, output_dir
from burling.progress import (
    WATCH_INTERVAL,
    _age_seconds,
    _bar,
    _enable_ansi,
    console_safe,
    format_duration,
    progress_file,
)

# Professional palette (works on dark Terminal.app / iTerm).
RST = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YEL = "\033[33m"
RED = "\033[31m"
WHITE = "\033[37m"

STAGES = (
    ("queue", "Extract"),
    ("tags", "Tags"),
    ("stitch", "Stitch"),
    ("audit", "Audit"),
    ("apply", "Apply"),
    ("revise", "Revise"),
    ("done", "Done"),
)


def _clip(text: str, n: int = 72) -> str:
    text = str(text or "").replace("\n", " ")
    if len(text) <= n:
        return text
    return "…" + text[-(n - 1) :]


def _tail_log(path: Path, n: int = 5) -> list[str]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    keep = [ln for ln in lines if ln.strip()][-n:]
    return [_clip(ln, 78) for ln in keep]


def _pipeline_state(out: Path, live: dict) -> list[tuple[str, str, str]]:
    """(marker, label, detail) for the RALP pipeline."""
    stage = str(live.get("stage") or "idle")
    current = live.get("current") or 0
    total = live.get("total") or 0
    has_tags = (out / "tags.json").is_file()
    has_regions = (out / "regions.json").is_file()
    has_audit = (out / "AUDIT.md").is_file()
    ralp = load_json(out / "ralp-state.json", {}) or {}
    rounds = list(ralp.get("rounds") or [])
    last = rounds[-1] if rounds else {}
    stop = ralp.get("stop")

    def mark(done: bool, live_here: bool) -> str:
        if live_here:
            return f"{YEL}●{RST}"
        if done:
            return f"{GREEN}✓{RST}"
        return f"{DIM}○{RST}"

    extract_live = stage in {"queue"}
    tags_live = stage in {"tags"}
    stitch_live = stage in {"stitch"} or (
        has_tags and not has_regions and stage not in {"queue", "tags"}
    )
    audit_live = str(stage).startswith("audit")
    apply_live = "RALP" in stage and "apply" in stage
    done = bool(stop) or stage in {"audit-done"} and (out / "RALP.md").is_file()

    extract_n = ""
    q = load_json(out / "queue.json", {}) or {}
    if isinstance(q, dict) and q.get("total"):
        extract_n = f"{q.get('total')} files"
    elif total:
        extract_n = f"{total} files"

    tags_n = f"{current} / {total}" if tags_live else ("ready" if has_tags else "waiting")
    if has_tags and not tags_live:
        try:
            tags_n = f"{json.loads((out / 'tags.json').read_text()).get('count') or 'ok'} tagged"
        except (OSError, json.JSONDecodeError):
            tags_n = "ready"

    stitch_n = "ready" if has_regions else ("running" if stitch_live else "waiting")
    audit_n = "waiting"
    if audit_live:
        audit_n = f"{current} / {total}  round {len(rounds) + 1}"
    elif has_audit:
        audit_n = f"round {len(rounds) or 1} written"

    apply_n = "waiting"
    if last:
        apply_n = (
            f"R{last.get('round')}: {last.get('applied', 0)} moved  "
            f"flag {float(last.get('flag_rate') or 0):.0%}"
        )
    if stop:
        apply_n += f"  stop {stop}"

    return [
        (mark(not extract_live, extract_live), "Extract", extract_n or "waiting"),
        (mark(has_tags and not tags_live, tags_live), "Tags", tags_n),
        (mark(has_regions and not stitch_live, stitch_live), "Stitch / organize", stitch_n),
        (mark(has_audit and not audit_live, audit_live), "Audit (group-at-a-time)", audit_n),
        (mark(bool(rounds) and not apply_live, apply_live or bool(last)), "Apply + revise", apply_n),
        (mark(done, False), "RALP stop", stop or ("in progress" if not done else stop)),
    ]


def render_tracker(cfg: dict) -> str:
    out = output_dir(cfg)
    live = load_json(progress_file(cfg), {}) or {}
    stage = str(live.get("stage") or "idle")
    pct = float(live.get("percent") or 0)
    current = live.get("current") or 0
    total = live.get("total") or 0
    eta = format_duration(live.get("eta_seconds") or 0)
    rate = live.get("seconds_per_file") or 0
    age = _age_seconds(live.get("updated_at"))
    on_file = format_duration(age) if age is not None else "—"
    hung = ""
    if age is not None and age > 180 and not str(stage).endswith("-done"):
        hung = f"  {RED}quiet >3m — model may still be thinking{RST}"
    now = _clip(live.get("rel_path") or "waiting for first file", 70)

    stage_title = {
        "queue": "Extract",
        "queue-done": "Extract done",
        "tags": "Tags  ·  description pass",
        "tags-done": "Tags done",
        "stitch": "Stitch  ·  organize groups",
        "audit": "Audit  ·  group-at-a-time",
        "audit-done": "Audit pass done",
        "idle": "Waiting for the run",
    }.get(stage, stage)

    raw_model = str((cfg.get("ollama") or {}).get("model") or "local")
    api = str((cfg.get("ollama") or {}).get("api") or "ollama").strip().lower()
    # Friendly name for the NVIDIA Lightning GGUF already on gb10 llama.cpp.
    if "lightning" in raw_model.lower() or "nemotron35" in raw_model.lower():
        model = "Nemotron 3.5 Lightning 30B  ·  llama.cpp :8080"
    elif api in {"openai", "openai-compatible", "llamacpp", "llama.cpp"}:
        model = f"{Path(raw_model).name}  ·  llama.cpp"
    else:
        model = raw_model
    intake = str((cfg.get("paths") or {}).get("intake_dir") or "")
    if "gold-20news" in intake or "20newsgroups" in intake:
        suite = f"{BOLD}Gold · 20 Newsgroups{RST}  {DIM}·{RST}  400 public files  {DIM}·{RST}  gb10"
    elif "sort-sample" in intake:
        suite = f"{BOLD}Test 1 of 3{RST}  {DIM}·{RST}  sort-sample  {DIM}(18 public-style files){RST}"
    else:
        suite = f"{BOLD}RALP{RST}  {DIM}·{RST}  {Path(intake).name or 'intake'}"
    width = 78
    rule = f"{DIM}{'─' * width}{RST}"
    lines = [
        "",
        f"{BOLD}{CYAN}  Burling{RST}  {DIM}·{RST}  {suite}",
        f"  {DIM}RALP{RST}  organize → audit → apply → revise → audit again",
        f"  {DIM}Model{RST}  {model}   {DIM}Ctrl+C stops this window only{RST}",
        rule,
        f"  {DIM}Stage{RST}     {BOLD}{stage_title}{RST}",
        f"  {GREEN}{_bar(pct, 36)}{RST}  {BOLD}{pct:5.1f}%{RST}    {current} of {total}",
        f"  {DIM}File{RST}      {WHITE}{now}{RST}",
        f"  {DIM}Pace{RST}      {rate}s / file     ETA  {eta}     this file  {on_file}{hung}",
        rule,
        f"  {BOLD}Pipeline{RST}",
    ]
    for mark, label, detail in _pipeline_state(out, live):
        lines.append(f"    {mark}  {label:<26} {DIM}{detail}{RST}")

    # Detached gb10 jobs write run.log next to output/, not inside it.
    log_path = out.parent / "run.log"
    if not log_path.is_file():
        log_path = out / "ralp-run.log"
    tail = _tail_log(log_path, 4)
    lines.append(rule)
    lines.append(f"  {BOLD}Recent log{RST}  {DIM}{log_path.name}{RST}")
    if tail:
        for ln in tail:
            lines.append(f"  {DIM}{ln}{RST}")
    else:
        lines.append(f"  {DIM}(no log yet){RST}")
    lines.append(rule)
    lines.append(f"  {DIM}updated  {live.get('updated_at') or '—'}{RST}")
    lines.append("")
    return "\n".join(lines) + "\n"


def watch(cfg: dict, *, interval: float = WATCH_INTERVAL) -> int:
    _enable_ansi()
    painted = 0
    try:
        while True:
            try:
                panel = render_tracker(cfg)
            except (PermissionError, OSError, json.JSONDecodeError, ValueError):
                time.sleep(max(0.2, interval))
                continue
            height = panel.count("\n")
            if painted:
                sys.stdout.write(f"\033[{painted}A\033[J")
            sys.stdout.write(console_safe(panel))
            sys.stdout.flush()
            painted = height
            time.sleep(max(0.2, interval))
    except KeyboardInterrupt:
        sys.stdout.write("\n  tracker stopped  (the RALP run is unchanged)\n")
        sys.stdout.flush()
        return 0
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live RALP test tracker")
    parser.add_argument("--config", help="config.yaml for the run you are watching")
    parser.add_argument("--once", action="store_true", help="Print one frame and exit")
    args = parser.parse_args(argv)
    cfg = load_config(Path(args.config) if args.config else None)
    if args.once:
        sys.stdout.write(render_tracker(cfg))
        return 0
    return watch(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
