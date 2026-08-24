"""Score a walk run against organize-drama ground truth (docs/test-corpus.md).

labels.json shape: {rel_path: {"main": str, "sub": str, "note"?: str}}.
A home matches when homes[rel][0] == main, and — when a sub is given —
homes[rel][1] == sub. "unmapped" labels match the unmapped bin.

This is the organize analog of the 20news gold harness: a walk run is
scored, not eyeballed.
"""

from __future__ import annotations

import json
from pathlib import Path

from burling.layer_plan import kebab


def score_run(homes: dict[str, list[str]], labels: dict) -> dict:
    """Join on rel_path; return accuracy plus every miss with both sides."""
    matched = 0
    misses: list[dict] = []
    for rel in sorted(labels):
        want = labels[rel]
        want_main = kebab(want.get("main") or "")
        want_sub = kebab(want.get("sub") or "")
        got = [kebab(part) for part in (homes.get(rel) or [])]
        ok_main = bool(got) and got[0] == want_main
        # A doc labeled without a sub may still land with one; only the
        # series must match. A labeled sub must match exactly.
        ok_sub = not want_sub or (len(got) >= 2 and got[1] == want_sub)
        if ok_main and ok_sub:
            matched += 1
        else:
            misses.append(
                {
                    "rel_path": rel,
                    "expected": "/".join(p for p in (want_main, want_sub) if p),
                    "got": "/".join(got) or "(not filed)",
                }
            )
    total = len(labels)
    return {
        "total": total,
        "matched": matched,
        "accuracy": round(matched / total, 4) if total else 1.0,
        "misses": misses,
    }


def load_labels(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
