"""CLI: review, tag, stitch, audit, and RALP (organize→audit→revise).

GOLDEN RULE: one file must not kill the run. Timeouts and corrupt files are
noted on that document; Ctrl+C still stops the job.

Usage (from the clone root):

    python -m burling.run --priors-only --intake burling/tests/fixtures/tiny-dump
    python -m burling.run --intake /path/to/handover
    python -m burling.run --pass 1 --limit 20
    python -m burling.run --map --intake /path/to/handover
    python -m burling.run --report
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from burling.paths import load_config
from burling.progress import print_status, watch_status
from burling.queue import build_queue
from burling.reports import write_reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Two-pass local document review + taxonomy topic map."
    )
    parser.add_argument(
        "--intake",
        help="Folder of handover files. Default: burling/intake/",
    )
    parser.add_argument(
        "--config",
        help="Optional config.yaml override",
    )
    parser.add_argument(
        "--priors-only",
        action="store_true",
        help="Inventory + regex PII scan only (no model). Safe first smoke.",
    )
    parser.add_argument(
        "--pass",
        dest="only_pass",
        choices=["1", "2"],
        help="Run only this model pass (queue must already exist)",
    )
    parser.add_argument(
        "--map",
        action="store_true",
        help="Taxonomy-first topic map only (uses map.yml; queue must exist or use with --intake).",
    )
    parser.add_argument(
        "--map-force",
        action="store_true",
        help="With --map, re-place documents that already have a placement.",
    )
    parser.add_argument(
        "--tags",
        action="store_true",
        help="Pass A rich free-form tags only (see docs/tag-then-stitch.md).",
    )
    parser.add_argument(
        "--tags-force",
        action="store_true",
        help="With --tags, re-tag documents that already have rich_tags. "
        "With --layers, re-tag 3-layer paths already in layer-tags.json. "
        "With --walk, re-file documents already in walk-state.json.",
    )
    parser.add_argument(
        "--stitch",
        action="store_true",
        help="Pass B: stitch output/tags.json into nested regions (needs Pass A).",
    )
    parser.add_argument(
        "--stitch-method",
        choices=["ab", "compact", "clerk"],
        default="ab",
        help="With --stitch: ab = normalize+cluster (default); "
        "compact = original top-180 raw tags; "
        "clerk = compact + ban channel/year heads.",
    )
    parser.add_argument(
        "--clerk",
        action="store_true",
        help="Older test: one clerk stitch, then one home per file. "
        "Ship path is --walk (docs/file-plan-layers.md).",
    )
    parser.add_argument(
        "--layers",
        action="store_true",
        help="Previous test: independent 3-layer tags, then roll-up. "
        "Ship path is --walk (docs/file-plan-layers.md).",
    )
    parser.add_argument(
        "--walk",
        action="store_true",
        help="Organize: pick a locked main, then reuse / invent / combine "
        "at each child. Combine rehomes siblings (docs/file-plan-layers.md).",
    )
    parser.add_argument(
        "--census",
        action="store_true",
        help="Test: fold mains toward ~12 from ids+counts, then fold one "
        "main's subs the same way.",
    )
    parser.add_argument(
        "--census-dive",
        help="With --census, which main to fold next (follows the mains "
        "map, so hardware may now be tech).",
    )
    parser.add_argument(
        "--spike",
        action="store_true",
        help="20news NVIDIA spike: main → combine → sub → detail → review. "
        "Requires policy.public_corpus (not CTE).",
    )
    parser.add_argument(
        "--spike-until",
        choices=[
            "main",
            "combine-mains",
            "sub",
            "combine-subs",
            "detail",
            "combine-details",
        ],
        help="With --spike, stop after this stage (default: all stages).",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Pass C: L1 graph checks + L2 group-at-a-time placement audit (needs --stitch).",
    )
    parser.add_argument(
        "--audit-force",
        action="store_true",
        help="With --audit, redo chunks that already have status=done.",
    )
    parser.add_argument(
        "--ralp",
        action="store_true",
        help="Organize → audit → apply → revise mixed groups → audit again "
        "(docs/ralp-loop.md). Works on any --intake folder.",
    )
    parser.add_argument(
        "--ralp-rounds",
        type=int,
        default=3,
        help="With --ralp, max organize/audit cycles (default 3).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process at most N documents this run (resume later)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Rewrite Markdown reports from the current ledger and exit",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Live progress panel (redraws every second). Open in a second terminal.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="With --status, print one snapshot and exit instead of watching.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip extract; continue pending pass 1 / pass 2 from the ledger.",
    )
    args = parser.parse_args(argv)

    cfg = load_config(Path(args.config) if args.config else None)
    if args.intake:
        cfg["paths"]["intake_dir"] = str(Path(args.intake).resolve())

    if args.status:
        if args.once:
            print_status(cfg)
            return 0
        return watch_status(cfg)

    if args.report:
        stats = write_reports(cfg)
        print(f"reports written for {stats['documents']} documents")
        return 0

    # --spike: staged main/combine/sub/detail on a public corpus (NVIDIA NIM).
    if args.spike:
        from burling.spike_plan import run_spike

        run_spike(
            cfg,
            limit=args.limit,
            force=args.tags_force,
            until=args.spike_until or "combine-details",
        )
        return 0

    # --census: 400-file tag roster, then top-down combine. Experiment, not ship.
    if args.census:
        from burling.census_plan import run_census

        run_census(cfg, dive_main=args.census_dive)
        return 0

    # --walk: locked main, then reuse / invent / combine. Ship organize path.
    if args.walk:
        from burling.walk_plan import run_walk_plan

        run_walk_plan(
            cfg,
            resume=args.resume,
            limit=args.limit,
            force=args.tags_force,
        )
        return 0

    # --layers: independent 3-layer tags → roll-up → Python tree.
    if args.layers:
        from burling.layer_plan import run_layer_plan

        run_layer_plan(
            cfg,
            resume=args.resume,
            limit=args.limit,
            force=args.tags_force,
        )
        return 0

    # --clerk: one stitch (banned heads) → one home per file. Not a loop.
    if args.clerk:
        from burling.file_plan import run_file_plan

        run_file_plan(cfg, resume=args.resume, limit=args.limit)
        return 0

    # --ralp: organize → audit → apply → revise → audit (any intake).
    if args.ralp:
        from burling.ralp import run_ralp

        run_ralp(cfg, max_rounds=max(1, args.ralp_rounds))
        return 0

    # --audit: L1 graph + L2 group-at-a-time placement check (needs regions.json).
    if args.audit:
        from burling.audit import run_audit

        run_audit(cfg, force=args.audit_force, limit=args.limit)
        return 0

    # --stitch: Pass B tag→region hierarchy (requires Pass A tags.json).
    if args.stitch:
        from burling.stitch_tags import run_stitch

        run_stitch(cfg, method=args.stitch_method)
        return 0

    # --tags: Pass A rich free-form tagging (before Pass B stitch).
    if args.tags and args.only_pass is None and not args.priors_only and not args.map:
        skip_queue = bool(args.resume)
        if not skip_queue and args.intake:
            print("Building queue (extract + regex priors)...")
            queue = build_queue(cfg)
            print(f"Queued {queue['total']} files from {queue['intake']}")
        from burling.tag_rich import run_rich_tags

        n = run_rich_tags(cfg, limit=args.limit, force=args.tags_force)
        print(f"rich-tagged {n} document(s)")
        return 0

    # --map alone: place onto governed taxonomy (after inventory exists).
    if args.map and args.only_pass is None and not args.priors_only:
        skip_queue = bool(args.resume)
        if not skip_queue and args.intake:
            print("Building queue (extract + regex priors)...")
            queue = build_queue(cfg)
            print(f"Queued {queue['total']} files from {queue['intake']}")
        from burling.classify_map import run_map

        n = run_map(cfg, limit=args.limit, force=args.map_force)
        write_reports(cfg)
        print(f"map placed {n} document(s)")
        return 0

    skip_queue = bool(args.resume or args.only_pass)
    if skip_queue:
        print("Resuming from ledger (not re-extracting; skipped files are retried)...")
    else:
        print("Building queue (extract + regex priors)...")
        queue = build_queue(cfg)
        print(f"Queued {queue['total']} files from {queue['intake']}")

    if args.priors_only:
        stats = write_reports(cfg)
        print_status(cfg)
        print("priors-only done. Run without --priors-only to start model passes.")
        return 0

    if args.only_pass in (None, "1"):
        from burling.pass1 import run_pass1

        n = run_pass1(cfg, limit=args.limit)
        print(f"pass 1 tagged {n} document(s)")

    if args.only_pass in (None, "2"):
        from burling.pass2 import run_pass2

        n = run_pass2(cfg, limit=args.limit)
        print(f"pass 2 judged {n} document(s)")

    # Full run: after PII passes, place every doc on the governed topic map.
    if args.only_pass is None:
        from burling.classify_map import run_map

        n = run_map(cfg, limit=args.limit, force=args.map_force)
        print(f"topic map placed {n} document(s)")

    stats = write_reports(cfg)
    print_status(cfg)
    print(
        f"review ready: {stats['delete_candidates']} delete candidates, "
        f"{stats['review']} still in review queue"
    )
    print("Nothing was deleted. Read burling/output/DELETE-CANDIDATES.md")
    print("Topic map: burling/output/TOPIC-MAP.md and topic-map.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
