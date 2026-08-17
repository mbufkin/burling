"""CLI: build the queue, run pass 1 (tags), run pass 2 (delete flags), write reports.

GOLDEN RULE: one file must not kill the run. Timeouts and corrupt files are
noted on that document; Ctrl+C still stops the job.

Usage (from the clone root):

    python -m burling.run --priors-only --intake burling/tests/fixtures/tiny-dump
    python -m burling.run --intake /path/to/handover
    python -m burling.run --pass 1 --limit 20
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
        description="Two-pass local document review: tag, then flag personal files."
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

    stats = write_reports(cfg)
    print_status(cfg)
    print(
        f"map ready: {stats['delete_candidates']} delete candidates, "
        f"{stats['review']} still in review queue"
    )
    print("Nothing was deleted. Read burling/output/DELETE-CANDIDATES.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
