# Spike findings: child-reuse prompt × combine sweep (gb10, repeated battery)

Question: does the reuse-first CHILD_SYSTEM rewrite improve organize quality,
and what does the --sweep cleanup pass cost/gain? Single-run comparisons were
unresolvable because run-to-run variance (±5-10pts strict) swamped prompt
effects. Protocol: 3 walks per arm against organize-drama (67 docs, Nemotron
3.5 Lightning 30B via llama-server), every tree scored against labels.json
before and after --sweep.

## Results (mean [min-max] over n=3)

| Arm | Strict sub % | Mains % | Drawers | Singletons | Depth-3+ |
|---|---|---|---|---|---|
| baseline walk | 14.7 [14.7-14.7] | 96.0 [94-97] | 30.3 | 21.7 | 31.0 |
| reuse walk    | **27.4 [22.1-32.4]** | 94.0 [93-96] | 42.7 | 30.7 | 52.3 |

## Conclusions

1. **Adopted: reuse-first child prompts.** Strict sub accuracy roughly
   doubles (+12.7pts mean) with non-overlapping ranges across arms. The
   trade: trees get bigger and deeper (more drawers, more depth-3 homes).
   Main-series choice is prompt-insensitive (~94-97%) — the 30B picks
   mains well under any wording.
2. **The combine sweep scores neutral-to-slightly-negative** (-1.5..-2.9
   strict on reuse trees, ±0 on baseline). Its real value is structural:
   fewer one-file drawers, shallower trees, logged proposals. Kept as the
   opt-in `--sweep` flag, not part of the default ship path.
3. **Variance discipline**: any future prompt/model comparison on this
   corpus needs n>=3 per arm. Single runs mislead — an earlier single-run
   read called this same prompt change "not a win."

## Artifacts

- Battery walk-states (n=3 per arm, pre/post sweep):
  `docs/spikes/battery/{baseline,reuse}-{1,2,3}-{pre,post}.json`
- Scorer: `burling/score_placements.py`
- Walk-call log: `output/walk-decisions.jsonl` (#61); sweep: `--sweep` (#62)

Re-analyze locally:
```
python3 - <<'PY'
import json
from burling.score_placements import score_run, load_labels
labels = load_labels(__import__('pathlib').Path("burling/tests/fixtures/organize-drama/labels.json"))
ws = json.load(open("docs/spikes/battery/reuse-1-post.json"))
print(score_run(ws["homes"], labels))
PY
```

## Round 2 — menu-locked sub-drawers (#spike/child-vocab)

Diagnosis from round 1: across 6 runs the model invented ~115 distinct
sub-drawers; only ~17 ever matched ground truth. Mains score ~96% because
they are menu-locked; subs were free kebab invention.

Fix: `file_plan.WORKPLACE_CHILDREN` — per-main approved drawer vocabulary,
config-overridable (`walk.children`, disable with `false`; mains without an
entry stay free-invention, e.g. `customers` whose drawers are account names).

| Arm | Strict sub % | Mains % | Drawers | Singletons |
|---|---|---|---|---|
| reuse, no menu (n=3) | 27.4 [22–32] | 94.0 | 42.7 | 30.7 |
| **vocab menu (n=3)** | **79.9 [76–85]** | 95.5 | 39.7 | 22.3 |

Remaining misses decompose as: `customers` label/taxonomy mismatch (account
drawers are open-ended by design), ~4–5 wrong-main docs per run concentrated
in genuinely ambiguous files (travel-expense-policy, delivery-receiving-log),
and the andon fixture (excluded from intake).

Verdict: sub-drawer accuracy is a vocabulary problem, not a model problem.
Menus move it from ~1/4 to ~4/5 correct; the rest needs org-specific plan
data (per-account drawers), not better prompts.
