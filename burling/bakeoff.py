"""Bake-off: original compact stitch vs later organize versions.

Same cached ``tags.json``. No re-tag. Each method writes its own output
folder so the RALP tree is not overwritten.

    python -m burling.bakeoff --config burling/config.gold-20news-gb10.yaml

Versions (oldest → newest):

1. compact — original Pass B (top 180 raw tags, one JSON tree)
2. ab — synonym normalize + cluster, then one tree call
3. ab-fold — (2) plus fold one-file children in code (no extra model)
4. ralp — already-finished 3-round loop (scored in place)
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from burling.paths import load_config, output_dir
from burling.ralp import dissolve_singularities, persist_payload
from burling.score_gold import format_table, score_regions
from burling.stitch_tags import load_tag_records, stitch_from_records


def _cfg_with_output(cfg: dict, out: Path) -> dict:
    nxt = dict(cfg)
    paths = dict(cfg.get("paths") or {})
    paths["output_dir"] = str(out)
    nxt["paths"] = paths
    return nxt


def run_bakeoff(
    cfg: dict,
    *,
    gold_path: Path,
    tags_path: Path,
    dest: Path,
    ralp_output: Path | None,
) -> Path:
    """Run compact + A+B + fold; score those plus an existing RALP tree."""
    dest.mkdir(parents=True, exist_ok=True)
    records = load_tag_records(cfg, tags_path)
    if not records:
        raise RuntimeError(f"no tags at {tags_path}")

    rows: list[dict] = []
    steps = [
        ("v1-compact", "compact", "Original: top-180 raw tags, one tree call"),
        ("v2-ab", "ab", "A+B: normalize + cluster, one tree call"),
    ]
    for name, method, note in steps:
        out = dest / name
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        print(f"BAKEOFF {name}: {note}", flush=True)
        stitch_from_records(_cfg_with_output(cfg, out), records, method=method)
        rows.append(score_regions(out / "regions.json", gold_path))

    # v3: same A+B tree, fold singularities in code (NN/g). No Lightning call.
    v2 = dest / "v2-ab" / "regions.json"
    v3 = dest / "v3-ab-fold"
    if v3.exists():
        shutil.rmtree(v3)
    v3.mkdir(parents=True)
    payload = json.loads(v2.read_text(encoding="utf-8"))
    notes = dissolve_singularities(payload)
    persist_payload(_cfg_with_output(cfg, v3), payload)
    print(f"BAKEOFF v3-ab-fold: folded {len(notes)} thin children", flush=True)
    rows.append(score_regions(v3 / "regions.json", gold_path))

    if ralp_output and (ralp_output / "regions.json").is_file():
        print("BAKEOFF v4-ralp: scoring existing 3-round tree (no rerun)", flush=True)
        scored = score_regions(ralp_output / "regions.json", gold_path)
        scored["method"] = "ralp-3rounds"
        rows.append(scored)

    report = dest / "BAKEOFF.md"
    lines = [
        "# Organize bake-off (20 Newsgroups gold)",
        "",
        "Same 400 hashed files. Same cached `tags.json`. Lightning / llama.cpp.",
        "No re-tag. Primary L1 is the score that matters — any-home inflates",
        "when a file sits in three folders.",
        "",
        format_table(rows),
        "",
        "## What each method is",
        "",
        "| Id | What ran | Model calls |",
        "|---|---|---|",
        "| v1-compact | Original Pass B: 180 frequent raw tags → one JSON tree | 1 stitch |",
        "| v2-ab | Normalize synonyms, cluster, stitch cluster labels | 1 stitch |",
        "| v3-ab-fold | v2 + fold 1-file children in code | 0 extra |",
        "| v4-ralp | v2-style stitch + 3 audit/apply/revise rounds | already done |",
        "",
        "## Majority primary label per gold topic",
        "",
    ]
    for r in rows:
        lines.append(f"### {r['method']}")
        lines.append("")
        for g, pairs in (r.get("majority_primary") or {}).items():
            pretty = ", ".join(f"{lab} ({n})" for lab, n in pairs)
            lines.append(f"- **{g}** → {pretty}")
        lines.append("")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"BAKEOFF done → {report}", flush=True)
    print(format_table(rows), flush=True)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gold-set organize bake-off")
    parser.add_argument("--config", help="YAML with llama.cpp / Lightning settings")
    parser.add_argument("--gold", help="gold.json (filename → gold paths)")
    parser.add_argument("--tags", help="Cached tags.json (no re-tag)")
    parser.add_argument("--dest", help="Folder for v1/v2/v3 outputs + BAKEOFF.md")
    parser.add_argument(
        "--ralp-output",
        help="Existing RALP output dir to score as v4 (default: config output_dir)",
    )
    args = parser.parse_args(argv)
    cfg = load_config(Path(args.config) if args.config else None)
    out = output_dir(cfg)
    gold = Path(args.gold) if args.gold else out.parent / "gold.json"
    tags = Path(args.tags) if args.tags else out / "tags.json"
    dest = Path(args.dest) if args.dest else out.parent / "bakeoff"
    ralp = Path(args.ralp_output) if args.ralp_output else out
    run_bakeoff(cfg, gold_path=gold, tags_path=tags, dest=dest, ralp_output=ralp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
