# Spec: fresh-window bet

Locked 2026-08-20. Map: [Fresh-window bet](map.md).
Language: [CONTEXT.md](../../CONTEXT.md).
Trail: [docs/fresh-window-bet.md](../../docs/fresh-window-bet.md).

This file is the destination. The next session implements it. Do not
implement from this document in the charting session.

---

## Destination (done when this file is true in code)

Every Burling model call follows **the bet**: one set task, extracted
text (or the call’s entire *relevant* input) via **chunk-then-merge**,
**fresh window**. No silent 12k truncate. No CTE / handover flavor in
prompts. Clerk calls re-read the page. Stitch names piles from a table.
Product A merge stays in code. We judge organize-quality on a public
gold tree, not Dallas ISD.

---

## Runtime (already decided)

- Model: Lightning (Nemotron 3.5 30B) on gb10 llama.cpp `:8080`.
- Not Ollama. Not the NVIDIA cloud proxy.
- Body default: **80,000 characters** per call (~16k tokens). Reserve
  8,192 tokens for system + JSON. Prefer `/tokenize` when wired:
  `chunk_tokens=16000`, `threshold_tokens=20000`.
- Do not fill the live 512K window.

---

## Call contracts

| Call | Unit | Entire relevant input | Merge |
|---|---|---|---|
| **Pass 1** (PII / custody) | One file, chunked | Extracted text of that chunk | **Code-union** of per-chunk JSON / spans |
| **Pass 2** (leftover vs work) | One file, chunked | Extracted text | Code-union / last-chunk rule already in pass 2 |
| **Tag** | One file, chunked | Extracted text (drop `DOC_CAP` silent slice) | Code-union of chunk tag JSON |
| **Stitch** | Cluster **table** (minibatches if huge) | Cluster labels, counts, short blurbs — **not** PDFs | Evaluate → issues → rewrite; split / push-up / rerun on subgroups |
| **Audit** | **Exactly one file** | Full extracted text (+ current home, also-under) | Chunk-then-merge if the file is long |
| **Revise** | **Exactly one mixed group’s rule**, but **one file at a time** when judging members | Full extracted text of that file + the group’s current name/rule | Code applies keep / rename / split / dissolve after the file-level votes |

**Refuse**

- 12-file audit batches (blurbs or full text).
- Silent `text[:12000]`.
- Audience examples like `central-cte`, `campus-admin`, “successor”,
  “handoff”.
- Stitch that pastes member PDFs.
- Lightning merge of Product A chunk JSONs.
- Dissolve a parent while children still exist, or leave files on
  ghost ids (implementation must seatbelt this; it is in scope for
  the build, not a new decision).

**JSON shape (intent, not field-perfect)**

- Tag: tags, summary, audiences (generic), record-ish facts — no
  district enum.
- Stitch: `{name, description, members[], action?}` where description
  is a **classifying rule**.
- Audit: `{path, verdict: confirm|wrong-parent|missing-parent|leftover-should-place|cannot-tell, better_home?}`.
- Revise (after file votes, one group): `{action: keep|rename|split|dissolve, rule, children?}`.

---

## Golden set (scoring, not the CTE dump)

**Public gold:** English MultiEURLEX, EUROVOC **L1 → L2**.

```
load_dataset("coastalcph/multi_eurlex", "en")
```

- ~400–800 docs, stratified by L1 (~20–40 per domain).
- Prefer the chronological **test** split.
- Materialize `gold/{L1}/{L2}/{celex_id}.txt` (symlink if multi-label).
- Flatten = copy into one inbox; hide gold paths from the model.
- Score: hierarchical F1 (ancestor-expanded) + L1 parent recall.
- Cite Chalkidis et al., EMNLP 2021. License: follow the EUR-Lex
  notice on the card (**CC-BY-4.0**, acknowledge + mark changes).
  HF YAML also lists `cc-by-sa-4.0` — do not assume ShareAlike
  beyond the body notice.

**CI fixture:** 8–12 invented snippets + `gold.json`. No EU-law text
in git. `sort-sample` stays smoke.

**Not the gold:** RCV1 full text, Reuters-21578, 20 Newsgroups as
headline, Govdocs1 (extract only), Enron, CTE-manager.

---

## Acceptance

Scoreboard: [TEST.md](TEST.md). Short version:

1. **Layer 0 (CI):** no silent 12k; one-file clerk prompts; stitch is a
   table; Product A merge has no extra Lightning call; no CTE/handover
   strings; dissolve cannot leave ghost ids; synthetic gold scorer
   runs without a model.
2. **Layer 1 (Lightning + `sort-sample`):** 18/18 primary homes match
   the planted family; six families still on the tree; stop is
   `flags-rose` / `no-applies` / `flag-rate`; audit traces show one
   file + extracted text.
3. **Layer 2 (MultiEURLEX):** L1 parent recall and hierarchical F1
   **beat one-shot stitch** on the same CELEX list; ghost rate 0.

A populated `topic-map.html` is not acceptance.
