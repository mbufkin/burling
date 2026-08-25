#!/usr/bin/env python3
"""Build a public-safe topic map from the organize-drama sample corpus.

Best practice: LinkedIn never films a live dump. This walks the committed
synthetic fixture (burling/tests/fixtures/organize-drama), then restamps
the sunburst with SAMPLE_CHROME so the masthead says Burling, not Dallas ISD.

  python tools/build_linkedin_demo.py              # gold clerk (same as CI)
  python tools/build_linkedin_demo.py --model      # real local --walk

Gold uses the labeled choosers from test_organize_drama so the ring is
filmable without a GPU. --model is the authentic clerk: Ollama files
every sample document. Output stays under .scratch/; only topic-map.html
is copied to docs/linkedin/ for the recorder.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from burling.file_plan import UNMAPPED_ID
from burling.layer_plan import kebab
from burling.map_html import SAMPLE_CHROME
from burling.paths import load_config
from burling.queue import build_queue
from burling.score_placements import load_labels
from burling.stitch_tags import _region_index, write_stitch_topic_map
from burling.walk_plan import run_walk_plan

DRAMA = PROJECT / "burling" / "tests" / "fixtures" / "organize-drama"
DEST = PROJECT / "docs" / "linkedin"
SCRATCH = PROJECT / ".scratch" / "linkedin-demo"
ANDON_DOC = "special/legacy-export.txt"
SKIP_NAMES = frozenset({"labels.json", "README.md"})


def _ignore(_directory: str, names: list[str]) -> list[str]:
    return [n for n in names if n in SKIP_NAMES]


def gold_main(*, rel_path: str, text: str, labels: dict) -> dict:
    if rel_path not in labels:
        return {"main": UNMAPPED_ID, "reason": "fixture artifact"}
    if rel_path == ANDON_DOC:
        return {"main": "", "reason": "no topical substance"}
    return {"main": labels[rel_path]["main"], "reason": "gold label"}


def gold_main_after_fix(*, rel_path: str, text: str, labels: dict) -> dict:
    if rel_path not in labels:
        return {"main": UNMAPPED_ID, "reason": "fixture artifact"}
    if rel_path == ANDON_DOC:
        return {"main": "security", "reason": "operator assignment", "summary": ""}
    return {"main": labels[rel_path]["main"], "reason": "gold label"}


def gold_child(*, rel_path: str, text: str, labels: dict, **_kw) -> dict:
    sub = kebab((labels.get(rel_path) or {}).get("sub") or "")
    if not sub:
        return {"action": "empty"}
    return {"name": sub}


def no_combine(**_kw) -> dict:
    """Gold demo does not fold drawers. Combine is a later maintain call."""
    return {"groups": []}


def publish_sample_map(output: Path, dest: Path) -> Path:
    """Restamp the walk map with sample chrome and copy the HTML out."""
    regions = output / "regions.json"
    payload = json.loads(regions.read_text(encoding="utf-8"))
    write_stitch_topic_map(
        output,
        payload,
        _region_index(payload.get("regions") or []),
        chrome=SAMPLE_CHROME,
    )
    dest.mkdir(parents=True, exist_ok=True)
    html = dest / "topic-map.html"
    shutil.copyfile(output / "topic-map.html", html)
    return html


def run_gold(cfg: dict) -> None:
    labels = load_labels(DRAMA / "labels.json")

    def main(**kw):
        return gold_main(labels=labels, **kw)

    def child(**kw):
        return gold_child(labels=labels, **kw)

    def main_fix(**kw):
        return gold_main_after_fix(labels=labels, **kw)

    run_walk_plan(
        cfg,
        choose_main=main,
        choose_child=child,
        choose_combine=no_combine,
    )
    run_walk_plan(
        cfg,
        resume=True,
        choose_main=main_fix,
        choose_child=child,
        choose_combine=no_combine,
    )


def run_model(cfg: dict) -> None:
    cfg.setdefault("walk", {})["andon_stop"] = False
    run_walk_plan(cfg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        nargs="?",
        const="qwen2.5:7b",
        help="Real local --walk (default model qwen2.5:7b). Omit for gold clerk.",
    )
    args = parser.parse_args(argv)

    intake = SCRATCH / "intake"
    output = SCRATCH / "output"
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    shutil.copytree(DRAMA, intake, ignore=_ignore)

    cfg = load_config()
    cfg["paths"]["intake_dir"] = str(intake)
    cfg["paths"]["output_dir"] = str(output)
    if args.model:
        cfg.setdefault("ollama", {})["model"] = args.model
        print(f"model walk with {args.model}", flush=True)
    else:
        print("gold clerk walk (no GPU)", flush=True)

    build_queue(cfg, intake=intake)
    if args.model:
        run_model(cfg)
    else:
        run_gold(cfg)

    html = publish_sample_map(output, DEST)
    body = html.read_text(encoding="utf-8")
    if "Dallas ISD" in body:
        raise SystemExit("sample map still contains Dallas ISD — chrome failed")
    print(f"sample map → {html}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
