# Fresh-window bet: recommended answers + golden set

**Question:** How should stitch, audit/revise, and Product A obey the
fresh-window bet — and which public pre-sorted corpus do we flatten to
judge whether the loop re-organizes documents?

**Ticket date:** 2026-08-20
**Map:** [Fresh-window bet](../.scratch/fresh-window-bet/map.md)

This is a wayfinder-research ticket. Claims are traced to fetched
primaries. Siblings: [ralp-loop.md](ralp-loop.md),
[stitch-methods.md](stitch-methods.md), [audit-pass.md](audit-pass.md).

The destination grilling already locked: spec not a build this pass;
**every** model call follows the bet; long text is **chunk-then-merge**.
[Lightning chunk budget](../.scratch/fresh-window-bet/issues/01-lightning-chunk-budget.md)
locked 80k characters per call. These four answers hang off that.

---

## Answer

| Ticket | Recommended | In one line |
|---|---|---|
| [Stitch under the bet](../.scratch/fresh-window-bet/issues/02-stitch-under-the-bet.md) | **A** | Stitch names **piles**. Entire input = the cluster table (fresh window; minibatch / chunk-then-merge if huge). Do not re-read PDFs. |
| [One file per call](../.scratch/fresh-window-bet/issues/03-one-file-per-call.md) | **A** | Audit and revise are **exactly one file**, full extracted text, fresh window. The group walk is only the work order. 12-file blurbs go. |
| [Product A in scope](../.scratch/fresh-window-bet/issues/04-product-a-in-scope.md) | **A** | Pass 1 / pass 2 **calls** follow the bet. Merge stays **code-union** of per-chunk JSON. No second Lightning merge. |
| Golden set (new) | **English MultiEURLEX L1→L2** | Flatten a stratified **400–800** sample, hide gold folders, score hierarchical F1 + L1 parent recall. Keep a tiny **in-repo** fixture for CI. |

Override vs the last grilling prior: destination grilling leaned stitch = A and
audit = A (same as research) but Product A = “in, strip CTE, code merge”
was already A. The user later asked **C** for “every call including tag.”
Research does **not** walk that back for tag — tag stays one-file +
chunk-then-merge. It **does** refuse “every call must re-read every PDF,”
including stitch. Stitch’s relevant input is the pile table.

---

## Why this answer

### Q1 — Stitch is piles, not pages (A)

**TnT-LLM** (Wan et al., KDD ’24, §3.1) never puts full documents in the
taxonomy window. Stage 1 summarizes each item (our tag). Stage 2 takes
**minibatches of those summaries** (batch ~200, Appendix C) and a tight
schema: name + description that can classify new points. Update =
evaluate → list issues → rewrite. Hierarchy = **rerun Stage 2 on each
subgroup**. Cluster-then-label (sample 200 members, name the pile) is
the **losing** baseline (§5.2.1) — and even that baseline used
**summaries**, not PDFs.

**TaxoGen** (Zhang et al., KDD 2018): a node is a **cluster**. Split;
**push general members back to the parent** (Alg. 1). Local embedding
retrains on a topic sub-corpus — that is training data, not an LLM
window full of files.

**Lost in the Middle** (Liu et al., TACL 2024) is why **B loses the
bet**. Multi-document QA is U-shaped: best at start/end, worst in the
middle. With 20–30 docs, GPT-3.5 can fall **below closed-book**. They
tested a **30B-class** model (MPT-30B-Instruct). Stuffing every
member’s text into stitch is that failure mode. Option **C** (tree only
from per-file clerks) cannot see sibling piles or push-up.

**Tie-break:** if today’s cluster rows are too thin, thicken the
**table** (member counts, tag-side blurbs, candidate names) — do not
reopen PDFs.

### Q2 — Audit / revise: one file, full text (A)

Placement is a **single-item judgment**. Liu et al.’s **oracle** is one
relevant document. Their multi-doc setting (exactly the “12 files in one
window” shape) is where accuracy collapses. Option **B** (12 full texts
in one window) is **worse** than today’s blurbs. Option **C** keeps the
12-pack **and** throws away the page — that is how Agriculture dissolved.

**TnT-LLM** assigns and scores **each instance**. Minibatches are only
for taxonomy *generation* (a different job — that is stitch). **Zheng et
al.** (MT-Bench / LLM-as-a-Judge) grade **one** answer per call, or a
pairwise of **two**; even two answers show position bias (~65% swap
consistency on GPT-4). None of the three papers batch-score 12
placements.

**Conflict we keep:** TnT-LLM Stage 2 batches summaries to *update the
tree*. That is stitch, not audit. GPT-3.5 already broke on that batched
update. Do not copy it onto clerk calls.

### Q3 — Product A is in; code merge is the bet (A)

Pass 1 already chunks extracted text. The bet on those **calls** is:
one set task, full coverage via chunk-then-merge, fresh window, no
handover/CTE flavor. The **reduce** is not a second model.

**Presidio** (official Analyzer): many recognizers return
`RecognizerResult` spans; `process_batch` / `BatchAnalyzerEngine`
collects lists **in code**. There is no official “LLM over the whole
file” path and no LLM reduce of detections.

**NIST SP 800-122** (§4.2.1, OECD Collection Limitation + Data
Quality): minimum necessary use; accurate, complete, **not invented**.
A Lightning merge that re-ingests every identifier is extra PII use and
a hallucination surface.

**Lost in the Middle** also fails a **JSON key-value** retrieval task
in the middle of a stuffed context — an argument against stuffing all
chunk JSONs into a second merge call.

Product B still needs an LLM reduce (a synthesized tree). Product A’s
output is structured spans/tags. Same bet on the **calls**; different
merge.

### Golden set — English MultiEURLEX L1→L2, then our own tiny fixture

There is no public “messy office dump with a gold tree.” The methodical
split is: **score the organizer** on a labeled tree, **score the
reader** on a dirty folder, **CI** on a synthetic fixture.

**MultiEURLEX** (Chalkidis et al., EMNLP 2021) is the only corpus that
is a real topic tree, full text, public, and not student/HR PII: 65k EU
laws, EUROVOC hierarchy, English 55k/5k/5k chronological split,
CC-BY-4.0 on the EU text (HF YAML also marks `cc-by-sa-4.0` — treat
the **card body / EUR-Lex notice** as the license: CC-BY-4.0,
acknowledge source, mark changes). Gold is **multi-label**. EUROVOC
usually does not assign a node *and* its ancestors; rebuild paths by
walking each concept to L1. Use **level-1 + level-2** (21 → ~127
heads). Do not treat L4–L8 as a stand-alone tree (card: many docs are
labeled at L3).

**Load the 2021 parallel set**, not the 2022 cut:

```text
load_dataset("coastalcph/multi_eurlex", "en")
```

`nlpaueb/multi_eurlex` is now Xenouleas et al. 2022 “Non-Parallel”
(5 languages, 11k/1k/5k, plus MT). Wrong gold set.

**Recipe:** stratify ~20–40 English docs per L1 → **~420–840**. Prefer
the **test** split (2010s; harder chronological drift — the paper’s
own warning). Flatten into one inbox (hide folder names). Score
**hierarchical F1** (ancestor-expanded) and **L1 parent recall**. The
paper’s metric is **mean R-Precision** on label ranking — report it
only if we also emit a ranked label list.

**In-repo CI:** 8–12 invented snippets + `gold.json` + a scorer. Do
**not** vendor 400 EU laws. `sort-sample` (18 files) stays the smoke;
it is not the golden set (we planted the labels ourselves).

**Not first:** RCV1-v2 full text (NIST/Reuters agreement;
`sklearn.fetch_rcv1` is TF-IDF, not files). Reuters-21578 (research-only
Reuters copyright; **135 flat** TOPICS). Govdocs1 subset0 (real mixed
files, **no** gold tree — extract score only). 20 Newsgroups (flat toy).
Enron (privacy). The CTE dump (field trial, not publishable).

---

## Where it was found

### Stitch / one-file / Product A (shared primaries)

- **TnT-LLM** — Wan et al., KDD 2024 — https://arxiv.org/abs/2403.12173 —
  Stage 1 summarize / Stage 2 minibatch evaluate→rewrite; name+rule;
  hierarchy = rerun on subgroups; per-instance assign/eval
- **TaxoGen** — Zhang et al., KDD 2018 — https://arxiv.org/abs/1812.09551 —
  node = cluster; split; push-up (Alg. 1)
- **Lost in the Middle** — Liu et al., TACL 2024 —
  https://aclanthology.org/2024.tacl-1.9/ — multi-doc U-curve; 30B-class
  model; JSON key-value middle-fail; more stuffed docs ≠ better
- **LLM-as-a-Judge** — Zheng et al., 2023 — https://arxiv.org/abs/2306.05685 —
  single-answer / pairwise only; position bias
- **Presidio Analyzer** — https://data-privacy-stack.github.io/presidio/analyzer/
  — recognizers + code-collected spans; batch is independent texts
- **NIST SP 800-122** — https://nvlpubs.nist.gov/nistpubs/legacy/sp/nistspecialpublication800-122.pdf
  — minimization; data quality (do not invent)

### Golden set

- **MultiEURLEX** — Chalkidis, Fergadiotis, Androutsopoulos, EMNLP 2021 —
  https://arxiv.org/abs/2109.00904 — 65k EU laws, EUROVOC L1–L3 gold,
  chronological split, English 55k/5k/5k, mean/median 1200/460 words
- **Official 23-language card** — https://huggingface.co/datasets/coastalcph/multi_eurlex
  — `load_dataset('coastalcph/multi_eurlex', 'en')`; body license
  CC-BY-4.0 / Decision 2011/833/EU; YAML also lists `cc-by-sa-4.0`
  (conflict: follow the EUR-Lex notice in the card body)
- **Reuters-21578 README** — Lewis —
  https://www.daviddlewis.com/resources/testcollections/reuters21578/readme.txt
  — research-only Reuters copyright; flat 135 TOPICS
- **RCV1-v2 LYRL2004 README** — Lewis —
  http://www.ai.mit.edu/projects/jmlr/papers/volume5/lewis04a/lyrl2004_rcv1v2_README.htm
  — Topics tree exists; redistributable artifacts are matrices, not text

---

## Conflicts we did not paper over

1. **TnT-LLM batches summaries to grow the tree.** That supports stitch
   option A (table in, minibatch), not audit option B/C.
2. **HF YAML `cc-by-sa-4.0` vs card body CC-BY-4.0.** The body quotes
   the EU / EUR-Lex notice (acknowledge + mark changes). Use that;
   do not assume ShareAlike until Publications Office says so.
3. **`nlpaueb/multi_eurlex` ≠ 2021 gold.** 2022 non-parallel cut.
4. **Paper metric is mRP, not hierarchical F1.** Folder recovery needs
   a path/set metric we compute ourselves.
5. **This map’s Out of scope** previously said MultiEURLEX scoring is
   later. The user asked for the golden set now — it is a **scoring
   fixture**, not a change to the clerk-call spec. Implementation of
   the downloader still waits until the spec map is clear.
