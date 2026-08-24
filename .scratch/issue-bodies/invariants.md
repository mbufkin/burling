## Problem
docs/file-plan-layers.md "Done when" is unenforced: "every filed file has exactly one region_ids entry; no node is deeper than 3; no channel/year head exists". The invariants hold by construction today, but nothing verifies them — a future edit (or a bad model output applied by --ralp) could violate them silently.

## Tasks
1. Add a check_tree_invariants(payload) function (suggest burling/browse_graph.py or walk_plan.py) asserting: single region_ids per file, max depth 3, no reserved/channel-year heads, unmapped has a reason.
2. Call it at the end of run_walk_plan and after each RALP apply; on violation, print the offending nodes and exit non-zero (do not auto-fix).
3. Unit tests: one passing tree, one violation per rule.

## Acceptance
- Injecting a depth-4 node or double-homed file into a fixture payload makes the runner fail loudly with the path named.
