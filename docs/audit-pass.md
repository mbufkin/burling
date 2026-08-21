# Audit pass: do we have one, and what should it be?

**Question:** After tags and stitch, should gb10 take time to make sure
files are in the right place? Do we already have that pass?

**Ticket date:** 2026-08-20
**Corpus:** CTE-manager dump (~670 queued, OCR recover + full re-tag in
flight). Browse tree is A+B stitch + Method C polyhierarchy.

This note is a wayfinder-research ticket. Claims are traced to fetched
primaries, not model priors. Siblings:
[tag-then-stitch.md](tag-then-stitch.md),
[stitch-methods.md](stitch-methods.md),
[browse-map.md](browse-map.md).

---

## Answer

**No. We do not have a placement audit pass.**

What looks like review today is something else:

| Existing thing | What it actually does |
|---|---|
| **Pass 2** (`--pass 2`) | Personal leftover vs work record. Never asks “is this under Trailer Compliance?” |
| **`needs_review` on tags** | Thin tags, low confidence, or extract failed |
| **`needs_review` on stitch** | File has no region, or landed in the leftover bin |
| **`REVIEW-QUEUE.md`** | Pass 2 / isolate leftovers for a human |
| **“Human approve” in Pass B docs** | Designed, **not implemented** |

Your instinct is right: after the tree exists, the box should **check
placements**, not invent a new handover story and not re-tag from scratch.

The literature’s audit is **three layers**, not one slow chat:

| Layer | Who | Unit | Job |
|---|---|---|---|
| **L1 — graph checks** | Local code, no model | Nodes / edges | Orphans, cycles, singleton folders, BT/NT that fail “child ⊆ parent”, polyhierarchy identity (same node both ways) |
| **L2 — placement verifier** | Nemotron, slow on purpose | One file × its *current* homes | Confirm, flag, or propose a move. Uses existing tags + path. Does **not** mint a new tree |
| **L3 — sample gate** | You, on the flag queue | Disputed nodes + a small file sample | Accept / reject / rename. Not 670 files by hand |

**Do not ship L2 alone.** That is the unvalidated “model grades itself”
loop the Microsoft validation paper names. L1 is cheap and catches
structural lies. L3 is a short queue, not a ceremony.

**Do not re-run Pass A as the audit.** No fetched source treats
“tag the corpus again” as QA.

---

## Why this answer

### We really do not have this pass

`burling/run.py` exposes priors, pass 1, pass 2, `--map`, `--tags`,
`--stitch`. There is no `--audit`. Pass 2’s system prompt is a records
clerk for tax vs work. Stitch `needs_review` is “unassigned,” not “wrong
folder.”

`docs/tag-then-stitch.md` already listed **human approve** as step 4 of
Pass B. `docs/stitch-methods.md` still marks it **open**. Method C
(`browse_graph.py`) only *induces* the two-parent graph; it never asks
whether a file belongs on those parents.

### The third pass is real, and it is not Pass A/B again

Every primary we fetched has a **check after generate**:

- **TnT-LLM** (Wan et al., arXiv:2403.12173, §3.1): after generate/update,
  a **review prompt** that “checks the formatting and quality of the
  output taxonomy.” Update = evaluate the *given* taxonomy on new data,
  list issues, modify — not rebuild.
- **Taxonomy Builder** (ACL 2022): model proposes clusters; human
  include / reject / defer, then picks a parent. Rejected phrases never
  re-enter. Throughput they report: ~200 candidates/hour.
- **NN/g Taxonomy 101 + Tree Testing:** after structure exists, review
  with SMEs and **tree-test** (“where does this resource live?”). Card
  sort *generates* a tree; it is not the evaluation pass. AI
  classification “will make mistakes.”
- **ISO 25964-1:** “human intellect is usually involved in the selection
  of indexing terms.” BT/NT is valid only if the narrower scope falls
  **completely** inside the broader. Polyhierarchy is allowed; the
  concept’s attributes must be the **same wherever it occurs**.
- **SKOS + qSKOS:** SKOS integrity is a short machine checklist (one
  prefLabel, related ≠ hierarchical). qSKOS adds orphans, disconnected
  clusters, cycles — and says those flags still need a **maintainer**.

Consensus: **check the current structure. Do not start over.**

### Deterministic checks cannot tell you “right folder”

TnT-LLM: automatic metrics need gold rules and are “less applicable”
for abstract taxonomy quality. qSKOS: its counts are “quantitative
indicators” that “require further investigation.” So L1 is necessary
and insufficient. That is where the box earns its keep (L2).

### The box as auditor is allowed — as a verifier, not as the gold

**Conflict (do not paper over it):**

| Side | Claim |
|---|---|
| TnT-LLM | Ships a model review prompt and LLM pairwise judges |
| ISO, NN/g, Taxonomy Builder, Shah et al. | Human gate is what makes the taxonomy *valid* |

TnT-LLM’s own tie-break: LLM-as-judge is “subject to biases… **combine
and validate** with human metrics on **small corpora**.” Shah et al.
(arXiv:2309.13063, same lab, not an independent 6th source): an
LLM-only taxonomy is “not externally validated” and can create a
feedback loop. Their Phase 2 is humans coding samples until
disagreement drops, *then* the model applies the same scheme.

So: **Nemotron should take time on each placed file** (your opportunity).
It should answer “keep / move / flag” against the *existing* homes.
It should not be the last word.

### What L2 should look like on this corpus

Per file that already has regions (and for fat `needs-review` leftovers):

```
Given: path, Pass A tags, summary, current region_ids (and “also under”).
Ask:  confirm | wrong-parent | missing-parent | leftover-should-place | cannot-tell
Do not: invent programs, mention a successor, re-emit a tag cloud.
```

Pairwise check from TnT-LLM: “this home vs a random other home vs
none” — a cheap way to catch “this quote is only under Events and
never under Purchasing.”

Coverage check they use: honest **Other** rate. Ours is already the
unmapped / needs-review bin. Audit should *not* stuff that bin into
a topic to look finished.

L1 on the whole graph, every stitch:

- singleton folders (NN/g singularities; our Method C `k ≥ 5` is the
  same spirit)
- orphan tags / disconnected leftover clusters (qSKOS)
- BT/NT that fail scope-inclusion (ISO)
- two parents that are not the **same** node (ISO polyhierarchy identity
  — Trailer→Compliance and Compliance→Trailer must share one id)

L3 is you opening `AUDIT.md`: the flags, not the 410 confirms.

### Why not “one long think on the whole tree”

The 3515-tag stitch already proved Nemotron’s JSON breaks on a giant
inventory. An audit of 670 files as **one prompt** would fail the same
way. TnT-LLM reviews in minibatches. Taxonomy Builder reviews
**candidates**. The unit is **one file or one node**, with resume.

---

## Where it was found

- **ISO 25964-1:2011** — [iso.org/standard/53657.html](https://www.iso.org/standard/53657.html)
  / [niso.org/schemas/iso25964](https://niso.org/schemas/iso25964)
  — BT/NT scope-inclusion; polyhierarchy + identity; human term
  selection. Full clauses 13–14 paywalled; used official summary +
  preview terms 2.3 / 2.34 / 2.37 / 2.42.
- **SKOS Reference (W3C, 2009)** — [w3.org/TR/skos-reference](https://www.w3.org/TR/skos-reference/)
  plus **qSKOS** (Mader et al., TPDL 2012)
  [eprints.cs.univie.ac.at/3444/1/finding_skos_quality_issues.pdf](https://eprints.cs.univie.ac.at/3444/1/finding_skos_quality_issues.pdf)
  — machine integrity; orphans / cycles / disconnected clusters as
  maintainer flags, not auto-fixes.
- **NN/g Taxonomy 101 + Tree Testing** —
  [nngroup.com/articles/taxonomy-101](https://www.nngroup.com/articles/taxonomy-101/),
  [nngroup.com/articles/tree-testing](https://www.nngroup.com/articles/tree-testing/)
  — singularities; SME review; tree test as the placement eval; AI
  tagging needs spot-check.
- **TnT-LLM**, Wan et al., arXiv:2403.12173 —
  [arxiv.org/abs/2403.12173](https://arxiv.org/abs/2403.12173)
  — review prompt after generate; evaluate-then-modify (not rebuild);
  coverage + pairwise accuracy; hybrid judge on a sample.
- **Taxonomy Builder**, ACL HCINLP 2022 —
  [aclanthology.org/2022.hcinlp-1.1.pdf](https://aclanthology.org/2022.hcinlp-1.1.pdf)
  — human admit/reject/parent of machine candidates; do not regenerate.

Corroboration (same Microsoft lab as TnT-LLM, **not** a 6th independent
source): Shah et al., arXiv:2309.13063 — human validation phase is what
makes an LLM taxonomy externally valid.

**Not used as a source:** the Medium “chaos to clarity” post (first-party
blog, not a paper).

---

## How the model works through the tree (implemented)

Wait for recover + re-tag + stitch to finish. Then:

```
python -m burling.run --config /path/to/config.yaml --audit
```

Resume is the default (`audit-state.json`). `--audit-force` redoes done chunks.
`--limit N` runs N chunks (useful to watch one topic first).

### Work order (not random)

1. **L1** writes `AUDIT-GRAPH.md` — empty nodes, one-file children,
   fat branches (≥40 files), unassigned count, child-vs-parent scope drift.
2. **L2** walks the stitch tree **depth-first**: parent topic, then each
   child (sorted by label). `needs-review` is last among siblings.
   Unassigned files are a final group.
3. A multi-home file is audited **once**, in its deepest real region.
   Other homes appear as `also under` so a missing second parent can
   still be flagged.
4. Files inside a group are sorted by path.

### Fat groups (graceful, documented)

One call holds at most **12 files** (`AUDIT_GROUP_MAX`). That is the
JSON / attention budget — the 3515-tag stitch is why we refuse a
bigger dump.

If Curriculum has 147 files:

- Plan row: `147 files → 13 chunks`
- Each prompt says `CHUNK 3 of 13` and `you are continuing the SAME group`
- `AUDIT-PLAN.md` records the split as a **workaround**
- L1 also flags the node as `fat-branch` so the real fix is a
  granular child (Method C), not a larger prompt

A failed chunk is marked `failed` and the next group still runs
(GOLDEN RULE). Re-run `--audit` to retry failed / unfinished chunks.

### Time and space for L2

Timeout is raised to ≥600s and `max_tokens` to ≥4096 for audit calls
only. The model sees the group label, parent, tree id list, and the
chunk’s files (path, tags, also-under, short summary). It returns
per-file verdicts plus `group_notes` (is this pile mixed? too fat?).

### What you read

| File | Role |
|---|---|
| `AUDIT-PLAN.md` | Work order + why any group was split |
| `AUDIT-GRAPH.md` | L1 only |
| `AUDIT.md` | L3 queue: flags, failed chunks, group notes |
| `audit.json` / `audit-state.json` | Machine resume |

Confirms stay put. You fix the flag list, not 670 files.

No second full tag. No handover prompt.
