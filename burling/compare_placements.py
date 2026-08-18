"""Compare two burling placement runs (e.g. Mac Ollama vs gb10 llama.cpp).

Best practice: join on rel_path, report facet disagreements, and leave both
runs intact so you can re-open TOPIC-MAP.md side by side.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


FACETS = ("program", "function", "audience", "record_type", "lifecycle")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _primary(p: dict, facet: str) -> str:
    terms = p.get(facet) or ["unmapped"]
    return terms[0] if terms else "unmapped"


def _index(data: dict) -> dict[str, dict]:
    out = {}
    for p in data.get("placements") or []:
        key = p.get("rel_path") or p.get("doc_id")
        if key:
            out[key] = p
    return out


def compare(a_path: Path, b_path: Path, *, a_label: str, b_label: str) -> str:
    a = _load(a_path)
    b = _load(b_path)
    ia, ib = _index(a), _index(b)
    keys = sorted(set(ia) | set(ib))

    lines = [
        f"# Placement compare: {a_label} vs {b_label}",
        "",
        f"- A: `{a_path}` ({len(ia)} placements)",
        f"- B: `{b_path}` ({len(ib)} placements)",
        f"- Union paths: {len(keys)}",
        "",
    ]

    only_a = sorted(set(ia) - set(ib))
    only_b = sorted(set(ib) - set(ia))
    if only_a:
        lines.append(f"## Only in {a_label} ({len(only_a)})")
        lines.append("")
        for k in only_a:
            lines.append(f"- `{k}`")
        lines.append("")
    if only_b:
        lines.append(f"## Only in {b_label} ({len(only_b)})")
        lines.append("")
        for k in only_b:
            lines.append(f"- `{k}`")
        lines.append("")

    shared = sorted(set(ia) & set(ib))
    disagree: dict[str, list[str]] = {f: [] for f in FACETS}
    agree_counts = Counter()
    for k in shared:
        pa, pb = ia[k], ib[k]
        for f in FACETS:
            if _primary(pa, f) == _primary(pb, f):
                agree_counts[f] += 1
            else:
                disagree[f].append(k)

    lines.append("## Primary-term agreement (shared paths)")
    lines.append("")
    lines.append("| Facet | Agree | Disagree | Agree % |")
    lines.append("|---|---|---|---|")
    n = len(shared) or 1
    for f in FACETS:
        d = len(disagree[f])
        ag = agree_counts[f]
        lines.append(f"| {f} | {ag} | {d} | {100.0 * ag / n:.1f}% |")
    lines.append("")

    lines.append("## Disagreements by facet")
    lines.append("")
    for f in FACETS:
        rows = disagree[f]
        lines.append(f"### {f} ({len(rows)})")
        lines.append("")
        if not rows:
            lines.append("(none)")
            lines.append("")
            continue
        lines.append(f"| Path | {a_label} | {b_label} |")
        lines.append("|---|---|---|")
        for k in rows:
            lines.append(
                f"| `{k}` | {_primary(ia[k], f)} | {_primary(ib[k], f)} |"
            )
        lines.append("")

    lines.append("## Handoff-note sample (first 8 shared)")
    lines.append("")
    for k in shared[:8]:
        lines.append(f"### `{k}`")
        lines.append(f"- **{a_label}:** {ia[k].get('handoff_note') or ia[k].get('rationale')}")
        lines.append(f"- **{b_label}:** {ib[k].get('handoff_note') or ib[k].get('rationale')}")
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Compare two placements.json runs")
    p.add_argument("a", type=Path, help="placements.json from run A")
    p.add_argument("b", type=Path, help="placements.json from run B")
    p.add_argument("--a-label", default="A")
    p.add_argument("--b-label", default="B")
    p.add_argument("-o", "--out", type=Path, help="Write markdown report here")
    args = p.parse_args(argv)
    md = compare(args.a, args.b, a_label=args.a_label, b_label=args.b_label)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
