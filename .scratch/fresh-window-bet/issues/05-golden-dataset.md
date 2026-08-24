# Golden dataset

Type: research
Status: resolved
Blocked by:

## Question

Which public, pre-sorted document set do we flatten and use as gold to
judge whether organize → audit → revise recovers the folders — without
using the CTE dump or inventing the labels ourselves?

## Recommended (research, 2026-08-20)

**English MultiEURLEX, EUROVOC level-1 → level-2**, ~400–800 docs
stratified by L1, preferably from the chronological **test** split.
Load `coastalcph/multi_eurlex` + `'en'` (not the 2022 `nlpaueb` cut).
Gold folders = L1 descriptor / L2 descriptor / `{celex_id}.txt`
(symlink if multi-label). Flatten = one inbox, hide paths. Score
hierarchical F1 (ancestor-expanded) + L1 parent recall.

In-repo CI: tiny synthetic tree + `gold.json` (not EU-law text).
`sort-sample` stays smoke. Govdocs1 scores extract only. RCV1 / Reuters
/ Enron / CTE are not the OSS gold.

Trail: [docs/fresh-window-bet.md](../../../docs/fresh-window-bet.md).

## Answer

Locked 2026-08-20. Golden set = English MultiEURLEX, EUROVOC L1→L2, ~400–800 stratified docs from `coastalcph/multi_eurlex` + `'en'`. Flatten, hide gold paths, score hierarchical F1 + L1 parent recall. In-repo CI = tiny synthetic tree, not EU-law text.
