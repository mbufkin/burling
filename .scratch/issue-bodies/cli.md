## Problem
run.py --help exposes failed experiments as first-class flags: --clerk ("Older test") and --layers ("Previous test"). docs/file-plan-layers.md names --walk as the ship path. Top-tier projects do not ship dead experiments in the primary CLI surface.

## Tasks
1. Demote --clerk and --layers to a hidden/experimental group (suppress from default --help, e.g. argparse help=argparse.SUPPRESS, or gate behind --experimental).
2. Keep the modules importable and tested — this is about CLI surface, not deletion.
3. Update run.py module docstring and README to present --walk as the organize path, --ralp as the loop variant.

## Acceptance
- python -m burling.run --help shows only supported paths at top level.
- Hidden flags still function; tests covering clerk/layers still pass.
