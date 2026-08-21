# Recommendation: many free-form tags → stitch into nested groups

**Question:** For Meg-style handoff dumps, should the model emit lots of tags
per document, then a later step stitch related things together
(e.g. *trailer* → *trailer compliance*, *trailer PD*)?

**Short answer:** Yes — **tag richly first, then stitch**. Do **not** ask one
call to both invent every detail *and* place the doc in a finished hierarchy.
That is the failure mode we already hit (one primary term, or Nemotron
knowledge trapped in `rationale` while facets said `unmapped`).

---

## What you want (trailer example)

```
mobile-lab / trailer
├── trailer-compliance   (acknowledgment forms, checklists)
├── trailer-pd           (summer PD decks about trailer visits)
├── trailer-scripts      (video scripts)
└── trailer-ops          (schedules, campus logistics)
```

A quote for Showcase booklets should carry **both** `purchasing-quote` and
`showcase-2026` — not a forced pick of one program word.

---

## What the literature says

### 1. Separate *description* from *organization*

NN/g: a **taxonomy** is a controlled metadata structure for describing content;
it is **not** the same as the browse map users see. Faceted / multi-label
description is normal; forcing one folder-like primary is optional.
([Taxonomy 101](https://www.nngroup.com/articles/taxonomy-101/))

**Implication for burling:** Pass A = rich multi-label tags (description).
Pass B = hierarchy / regions (organization). The HTML map is Pass B’s view.

### 2. Hierarchies are broader/narrower *concepts*, not folder dumps

ISO 25964-1: hierarchical links are **BT/NT** (broader/narrower concept): the
narrower’s scope falls wholly inside the broader. Also **RT** (related) for
non-parent links, and preferred vs non-preferred synonyms.
([ISO 25964 overview](https://www.isko.org/cyclo/thesaurus);
[ISO 25964-1](https://www.iso.org/standard/53657.html))

**Implication:** Stitching should produce a small thesaurus-like tree
(`trailer` BT ← `trailer-compliance` NT), not 200 flat unique strings.

### 3. Bottom-up then meta-group is a standard LLM pipeline

Microsoft’s published pattern for unknown category spaces:

1. extract semantic signals from docs  
2. cluster / group  
3. label clusters  
4. **meta-categorize** cluster labels into a smaller hierarchy  

Top-down (invent taxonomy first, then classify) is better when the scheme is
already known. Meg’s dump is closer to **bottom-up discovery** with a light
human gate.
([From chaos to clarity…](https://medium.com/data-science-at-microsoft/from-chaos-to-clarity-building-taxonomies-from-unstructured-text-using-large-language-models-c1303db3adb1))

Microsoft Research **TnT-LLM**: summarize → generate taxonomy → classify, and
**recurse** into subgroups for deeper levels (exactly “trailer then trailer PD”).
([TnT-LLM, arXiv:2403.12173](https://arxiv.org/abs/2403.12173))

Banking taxonomy work: extract candidate terms → LLM organizes into hierarchy →
then tag against that hierarchy.
([arXiv:2401.06790](https://arxiv.org/abs/2401.06790))

### 4. Human stays in the loop for the stitch

HCI taxonomy builders keep the user accepting/rejecting proposed nodes and
placing them in the tree (ACL Taxonomy Builder).
([ACL 2022 Taxonomy Builder](https://aclanthology.org/2022.hcinlp-1.1.pdf))

Enterprise practice: bottom-up tags are fine for discovery; **governance**
(merge/rename/deprecate) keeps the map from rotting.
([Enterprise Knowledge — taxonomy governance](https://enterprise-knowledge.com/taxonomy-governance-best-practices/))

---

## Recommended burling pipeline (AAA shape)

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌──────────┐
│ Extract text │ ──▶ │ Pass A: TAG      │ ──▶ │ Pass B: STITCH  │ ──▶ │ Map HTML │
│ (+ PII soft) │     │ many free tags   │     │ cluster + BT/NT │     │ + handoff│
└─────────────┘     │ + short summary  │     │ human approve   │     └──────────┘
                    └──────────────────┘     └─────────────────┘
```

### Pass A — Tag (per document, Nemotron earns its keep)

Emit **many** labels, not 1–2 facet primaries:

| Field | Purpose |
|---|---|
| `tags` | 8–25 free-form kebab or phrase tags (topics, programs, artifacts, audiences, events, years) |
| `entities` | Named programs/events/vendors **without** personal PII |
| `summary` | 3–6 sentence handoff blurb |
| `focus_flags` | Soft PII / “look here” suggestions only |

Example for Trailer Acknowledgment:

```json
{
  "tags": [
    "mobile-lab", "trailer", "campus-acknowledgment", "compliance",
    "safety-protocol", "scheduling", "principal-signoff", "2026-2027",
    "career-exploration", "on-campus-field-trip"
  ],
  "summary": "Campus principal initials required actions before a Mobile Lab visit…"
}
```

**Do not** coerce to a single `program` in this pass.

### Pass B — Stitch (corpus-level, once per dump)

Input: the **union of all tags** (+ optional embeddings).

1. **Normalize** — merge near-duplicates (`trailer` / `mobile-lab-trailer` / `Mobile Lab`).
2. **Cluster** — tags that co-occur on the same docs (and/or embedding neighbors).
3. **Induce hierarchy** — one model call (or recursive TnT-style calls) that
   proposes BT/NT groups: `mobile-lab` → `trailer-compliance`, `trailer-pd`, …
4. **Human approve** — accept / rename / merge nodes (lightweight checklist).
5. **Assign** — each doc inherits the regions whose tags it carries (multi-home OK).

Polyhierarchy is fine: a Showcase quote can sit under **purchasing** *and*
**showcase-events** (ISO polyhierarchy; records practice).

### Pass C — Map view

Sunburst / treemap from **approved regions**, with docs as leaves. Filters =
facets derived from tag clusters (audience, year, artifact type), not a second
forced classify.

---

## Why not “one model call that tags and maps”?

| Approach | Failure |
|---|---|
| Single primary program (current map.yml classify) | Undersells Nemotron; loses multi-homing (quote = purchasing ∧ showcase) |
| Free tags with no stitch | Tag soup; no “trailer family” |
| Stitch without rich tags | Hierarchy invents structure the docs never supported |
| Tags → stitch (recommended) | Matches bottom-up LLM taxonomy + ISO BT/NT + handoff UX |

---

## What to retire / keep

| Keep | Change |
|---|---|
| PII as **suggestion / focus list** only | Already softened in SUMMARY copy |
| Local-only model policy | Unchanged |
| `map.yml` | Become the **approved stitch output** (or seed), not the only allowed Pass A vocabulary |
| Compare Mac vs gb10 | Compare **tag coverage + stitch quality**, not single-term agree % |

---

## Suggested first prototype (when you say go)

1. Pass A on Meg’s 28 docs via gb10 Nemotron → `tags.jsonl`
2. Pass B stitch → draft `regions.yml` (trailer / pathful / showcase / …)
3. HTML map from regions (docs multi-listed)
4. You approve region names once; re-run only Pass B if tags already cached

No full PII re-pass required for this prototype.
