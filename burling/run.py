"""CLI: build the queue, run pass 1 (tags), run pass 2 (delete flags), topic map, reports.

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
