# Stitch under the bet

Type: grilling
Status: resolved
Blocked by:

## Question

Tag, audit, and revise can each be “one file (or one file-chunk), one job.” Stitch today is one taxonomist call over **clusters**, not files. How does stitch obey the bet without pasting the whole dump into one window?

Decisions to lock: stitch reads member extracted text per cluster (fresh window each cluster, then a thin tree-join call), or stitch only names piles from tags because tag already read the extracted text, or something else.

## Recommended (research, 2026-08-20)

**A.** Stitch’s job is piles, not pages. Entire input = the cluster table (fresh window; TnT-LLM minibatch evaluate→issues→rewrite / chunk-then-merge if huge). JSON = name + classifying rule. Hierarchy = split, push general members to parent, rerun on subgroups. Do not re-read PDFs (B). Do not build the tree from per-file clerks only (C).

Trail: [docs/fresh-window-bet.md](../../../docs/fresh-window-bet.md).

## Answer

**A.** Locked 2026-08-20. Stitch names piles from the cluster table. Fresh window; minibatch / chunk-then-merge if the table is huge. Name + classifying rule. Split, push-up, rerun on subgroups. No PDF re-read. No clerk-only tree.
