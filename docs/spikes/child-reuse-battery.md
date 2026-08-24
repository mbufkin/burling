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

- Battery states: `/tmp/battery/*.json` on gb10 (kept for re-analysis)
- Scorer: `burling/score_placements.py`
- Log: `output/walk-decisions.jsonl` (#61); sweep: `--sweep` (#62)
