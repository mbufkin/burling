# Pass B stitch: are we using best-practice methods?

**Question:** After Pass A emits thousands of free-form tags, how should Pass B
induce a browse hierarchy? Is one local-LLM call that emits a nested JSON tree
best practice, or should we replace it?

**Ticket date:** 2026-08-20
**Corpus that failed the one-shot stitch:** 670 CTE handover docs, 3515 unique
tags (most singletons). Workaround: send the 180 most frequent tags, map the
long tail by token overlap → 8 top-level / 16 nodes, 3515/3515 tag strings
mapped, **410/670 docs** in a browse region.

This note is a wayfinder-research ticket. Claims below are traced to fetched
primary sources, not model priors. See [tag-then-stitch.md](tag-then-stitch.md)
for the original design recommendation.

---

## Answer

**Partly.** The *design* in `docs/tag-then-stitch.md` already matches the
literature: tag richly first, then **normalize → cluster → induce BT/NT →
human approve → assign documents**. That pipeline is best practice.

The *implementation* of Pass B is **not** best practice. No primary source we
fetched validates “dump the whole tag inventory into one `chat()` and parse a
complete nested JSON tree.” The closest published analogue (Moraes et al.)
runs that JSON step on a **short, pre-filtered keyword list for one
micro-category**, and they warn that LLM context fails above ~1k nodes.

The 180-tag cap + leftover token-overlap mapper is a **defensible bootstrap**
(TaxoGen and Taxonomy Builder also keep only frequent/top-k terms). It is
**not** a finished stitch. Optimizing “100% of tag strings appear in
`tag_to_region`” is the wrong objective: ISO/NN/g care about **concepts**,
and document coverage (410/670) is the number that matters for a handoff map.

**Replace the one-shot tree with this local-only sequence:**

1. **Normalize synonyms** into preferred / non-preferred terms (ISO 25964-1 /
   SKOS) before any hierarchy.
2. **Cluster concepts** (tag co-occurrence on the 670 docs, and/or local
   embeddings), not 3515 raw strings.
3. **Name clusters with Nemotron** — one small call per cluster (preferred
   terms + 3–5 doc titles), BERTopic LlamaCPP pattern. Never send 3515 tags.
4. **Grow the tree recursively** (TnT-LLM / Microsoft top-down): meta-categorize
   cluster labels into ~8–15 roots, then recurse only into fat branches.
   Target depth 2–3 and tens of nodes.
5. **Assign documents**, not leftover strings. Keep an honest Other /
   unassigned bin.
6. **Human accept/rename/merge** on the *node list* (hours), not on 3515 tags.

Keep the current compact stitch only as a seed while that lands.

---

## Why this answer

Decisive evidence:

- **TnT-LLM never one-shots a tag inventory.** Taxonomy generation is
  iterative minibatches (they use batch size 200), then classification, then
  optional recursion into subgroups. They sample a “small-to-medium”
  representative subset on purpose.
- **Microsoft’s own practitioner pipeline** (Liu & Li) states the full corpus
  is “too large to fit in context.” Bottom-up = embed → cluster → label each
  cluster → meta-categorize. Top-down = sample → small root set → classify →
  recurse per branch. LLM cost is O(1) if you skip per-doc compression.
- **TaxoGen** builds a tree by *recursive clustering of terms*, and treats a
  node as a **cluster of coherent terms**, not one node per string. They
  reject string-per-node as high-redundancy / low-coverage.
- **ISO 25964-1 / SKOS** require equivalence (preferred vs non-preferred)
  *before* BT/NT. A narrower concept’s scope must fall **entirely** inside
  the broader. Polyhierarchy is allowed. Humans usually choose the terms.
- **NN/g Taxonomy 101** tells builders to avoid “singularities” (terms with
  only one piece of content) and to control synonyms so `RFP` / `Proposal` /
  `SOW` do not split retrieval. Our 3005 singleton tags are exactly that
  anti-pattern if they become first-class nodes.
- **BERTopic** separates embed → cluster → c-TF-IDF → optional LLM labels on
  a handful of representatives. Official docs include local `LlamaCPP`. The
  hierarchy is a dendrogram of topic vectors, not an LLM JSON dump.
- **Taxonomy Builder (ACL 2022):** in a timed session, analysts accepted only
  **16%** of machine clusters. Automatic trees are a proposal, not a
  handoff.

Why alternatives lost:

| Approach | Why it lost for *this* dump |
|---|---|
| One-shot nested JSON of all 3515 tags | No source validates it; banking paper’s JSON step is per micro-list; we already saw truncated/invalid JSON twice. |
| Cap at 180 + token-overlap leftovers (current) | Fine as a seed; token overlap maps spelling, not concepts (ISO 2.11 / 2.18). Explains 100% tag-string coverage with 260 docs still outside browse regions. |
| BERTopic-on-documents alone | Supported locally, but the hierarchy is topic *similarity*, not ISO BT/NT. Still useful as the cluster engine under step 2. |
| Microsoft’s “exactly one category per doc” | Conflicts with ISO polyhierarchy and with our own requirement (a Showcase quote is purchasing ∧ showcase). Use their *clustering* steps, not their single-label constraint. |

**Conflict we did not paper over:** clustering methods often force 100%
assignment; BERTopic and NN/g keep outliers / refuse singularities. We side
with the latter: an Other bin is more honest than stuffing singletons into
the tree.

**Caveat:** TnT-LLM results are GPT-4/3.5 on Bing chats. Banking evals show
local 7B–Mixtral trailing Gemini on parent prediction. Nemotron-via-llama.cpp
is untested in these papers — expect weaker BT/NT than GPT-4, which is why
the LLM should only *name* small clusters, not emit the global tree.

---

## Where it was found

Depth: 5+ independent primaries (wayfinder default is 3; this ticket asked
for alternatives, so coverage was expanded). ISO Clauses 10 and 13 (full
construction workflow) were **not** fetched — the 152-page text is paywalled.

- **TnT-LLM** (Wan et al., Microsoft Research, 2024) — https://arxiv.org/abs/2403.12173 — iterative minibatch taxonomy, then classify, recurse into subgroups; never one-shot a full inventory.
- **ISO 25964-1:2011** — https://www.iso.org/standard/53657.html (abstract + Clause 2 sample; full text unread) — concept ≠ term; preferred/non-preferred; BT/NT scope rule; polyhierarchy; humans usually pick terms.
- **SKOS Reference + Primer** (W3C) — https://www.w3.org/TR/skos-reference/ · https://www.w3.org/TR/skos-primer/ — `prefLabel`/`altLabel`; a concept may have several broader concepts; `broader` is not transitive by default.
- **TaxoGen** (Zhang et al., KDD 2018) — https://arxiv.org/abs/1812.09551 — unsupervised term taxonomy via recursive spherical clustering + adaptive embeddings; node = term cluster.
- **BERTopic** (Grootendorst, 2022 + official docs) — https://arxiv.org/abs/2203.05794 · https://maartengr.github.io/BERTopic/algorithm/algorithm.html — embed/UMAP/HDBSCAN/c-TF-IDF; LLM labels clusters only; official LlamaCPP hook; hierarchy is a dendrogram.
- **Liu & Li, “From chaos to clarity”** (Data Science + AI at Microsoft, 2026-01-13) — https://medium.com/data-science-at-microsoft/from-chaos-to-clarity-building-taxonomies-from-unstructured-text-using-large-language-models-c1303db3adb1 — first-party 4/5-step cluster-then-label and sample-then-recurse; full corpus does not fit in context; humans still review. Practitioner article, not a peer-reviewed experiment.
- **Moraes et al.** (2024) — https://arxiv.org/abs/2401.06790 — closest JSON-hierarchy analogue, but only after YAKE/LDA filter on a *micro-category* word list; they state LLM context is the limiter.
- **Taxonomy Builder** (Hungerford, Surdeanu, et al., ACL 2022) — https://acanthology.org/2022.hcinlp-1.1/ — human retain full control; ~16% of clusters accepted in one timed session.
- **NN/g Taxonomy 101** (Laubheimer) — https://www.nngroup.com/articles/taxonomy-101/ — controlled vocabulary vs navigation; synonym control; avoid singularities; stakeholder review.

---

## Method comparison (what to build next)

| Method | Use for CTE-manager stitch? | Local-only? | Failure mode |
|---|---|---|---|
| **A. Normalize pref/non-pref first** | **Required.** `curriculum_admin` / `curriculum-admin` / `curriculum-administration` are one concept. | Yes | Over-merge of quasi-synonyms (ISO: that is a vocabulary *decision*). |
| **B. Cluster concepts, then label** | **Required.** Co-occurrence on 670 docs + local embeddings. Nemotron names each cluster only. | Yes | k-means needs *k*; HDBSCAN leaves noise (keep it as Other). |
| **C. Recursive taxonomy-then-classify** | **Required for depth.** Meta-categorize cluster labels, recurse on fat branches. | Yes, many small chats | Bad roots propagate; run 2–3 trials and pick. |
| **D. BERTopic on documents** | **Engine for B**, not a replacement for ISO BT/NT. | Yes (LlamaCPP) | Dendrogram ≠ broader/narrower scope. |
| **E. Human accept/reject nodes** | **Required before handoff.** Review tens of nodes, not 3515 tags. | Yes | Skipping it ships a 16%-precision tree (Taxonomy Builder). |
| **F. Cap + leftover token overlap (current)** | **Seed only.** Keep `regions.yml` as a draft until A–E land. | Yes | Tag-string coverage ≠ document coverage; overlap ≠ concept. |
| One-shot JSON of all tags | **Do not retry.** | Fragile | Truncation / invalid JSON (already observed). |

---

## What the code does today vs what the design asked for

`docs/tag-then-stitch.md` Pass B already listed: normalize, cluster, induce
hierarchy (one call *or recursive*), human approve, assign docs.

`burling/stitch_tags.py` used to skip normalize/cluster and jump to
“one induce call over the inventory.” After that crashed, it capped the
inventory and assigned leftovers by token Jaccard (method F).

**2026-08-20 implementation:** `burling/tag_concepts.py` now runs **A then B**
locally before the compact stitch:

1. `normalize_concepts` — kebab + token-set equivalence (`curriculum_admin` /
   `curriculum-admin` / `curriculum-administration`; `cte-middle-school` /
   `middle-school-cte`).
2. `cluster_concepts` — greedy co-occurrence, but only when concepts also
   share a content token (so `work-email` does not glue onto `curriculum-admin`).
3. Compact stitch on **cluster labels** (still capped at 180, count ≥ 2).
4. `expand_aliases` maps every SKOS altLabel after the model returns.

Still not done: recursive C (Nemotron names each cluster / fat branches) and
human E (accept/rename nodes). Do not re-run Pass A; `tags.json` is the input.
