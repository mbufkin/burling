# Fresh-window bet

Label: `wayfinder:map`

## Destination

A locked spec: every Burling model call follows **the bet** — one set task, extracted text via **chunk-then-merge**, **fresh window** each call. Tag’s silent 12k cap and CTE audience examples go. This map ends at the spec; the next session implements.

## Notes

- Repo: `Desktop/burling-v2`. Tracker: local markdown (this folder).
- Skills: grilling, domain-modeling, research. Language: [CONTEXT.md](../../CONTEXT.md).
- Runtime: Lightning (Nemotron 3.5 30B) on gb10 llama.cpp, local-only. Do not point Burling at the NVIDIA cloud proxy.
- Acceptance story for the spec is `sort-sample` (18 public-style files). The CTE dump is a private field trial, not this destination.
- Plan, don’t implement, unless a later ticket’s Notes say otherwise.

## Decisions so far

<!-- destination grilling, 2026-08-20 — not a child ticket; named here so the route is visible -->

- Destination grilling — spec not a build this effort; the bet applies to every model call (including tag); “entire document” means chunk-then-merge, not a silent truncate.
- [Lightning chunk budget](issues/01-lightning-chunk-budget.md) — default 80k chars (~16k tokens) per call; 12k is a habit; do not fill the live 512K window.
- [Stitch under the bet](issues/02-stitch-under-the-bet.md) — piles, not pages; cluster table is the entire input.
- [One file per call](issues/03-one-file-per-call.md) — audit/revise = one file + full extracted text; 12-file batches go.
- [Product A in scope](issues/04-product-a-in-scope.md) — pass 1/2 follow the bet; merge is code-union.
- [Golden dataset](issues/05-golden-dataset.md) — English MultiEURLEX L1→L2, ~400–800, flatten and score.
- [Test documentation](issues/06-test-documentation.md) — three layers; sunburst is not a pass.

Locked spec: [SPEC.md](SPEC.md). Scoreboard: [TEST.md](TEST.md).

## Not yet specified

- Field-perfect JSON schemas (SPEC has intent; implementers may tighten).
- Dissolve seatbelt + ghost-id repair (implementation; required by TEST Layer 0).
- MultiEURLEX downloader (implementation; scorer must run on the CI fixture first).

## Out of scope

- Implementing the spec (next session after this map is clear).
- Re-running the 871-doc CTE field trial as the proof.
- Wiring Burling to Ollama or the NVIDIA hosted API.
- RCV1 full text, Reuters-21578 as the OSS tree demo, Enron, 20 Newsgroups as the headline gold.
