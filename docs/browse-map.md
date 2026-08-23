# Browse map: topic → subtopic → granular, both ways

**Question:** For the CTE handoff map, should we stop at one topic
(“this file is compliance”) and instead browse
**topic → subtopic → granular**, create a group only when enough
documents justify it, allow more than one subtopic, and make the
tree work **both ways** (Compliance → Trailer *and* Trailer →
Compliance)?

**Ticket date:** 2026-08-20
**What you are looking at today:** `topic-map.html` is a *flat* sunburst
(one ring of terms, then files). A document is forced onto
`terms[0]` of one facet. That is why “compliance” feels like a
dead-end label, not a drill path.

This note is a wayfinder-research ticket. Claims are traced to
fetched primaries, not model priors. Sibling notes:
[stitch-methods.md](stitch-methods.md),
[tag-then-stitch.md](tag-then-stitch.md).

---

## Answer

**Yes. That is the right model, and it is the standard one.** The
power is not “this document is Compliance.” The power is a
**compound concept** that you can reach from either parent:

```
Compliance                         Trailer (mobile lab)
└── Trailer compliance     ←same→  └── Compliance
        └── acknowledgment forms, checklists, …
```

`trailer-compliance` is **one node**, not two copies. ISO 25964-1
calls this a **polyhierarchical structure**: a concept may have
more than one broader concept, and *its attributes, narrower
terms, and related terms are the same wherever it occurs*. SKOS
says the same: a concept may have several `skos:broader` at once
(their example: *dog* is narrower than both *mammals* and
*domesticated animals*).

Build the browse tree in **three tiers**, and only split a branch
when the corpus can fill it:

| Tier | Your words | Thesaurus name | When to create it |
|---|---|---|---|
| 1 | Topic | Top concept / BT | ~8–15 roots that a successor would look for (Compliance, Trailer, PD, Purchasing, …) |
| 2 | Subtopic | NT of the topic | Only if **enough docs** share that cut (Trailer under Compliance, PD under Trailer, …). More than one subtopic per topic is normal. |
| 3 | Granular | NT of the subtopic | Only if the subtopic is still too fat (acknowledgment vs PD vs scripts under Trailer). Stop at 2 if the branch is thin. |

**Do not** invent a folder for one file. NN/g calls those
**singularities** — “including concepts associated with only one
piece of content is probably wasted effort.” TaxoGen / TnT-LLM
recurse only into **fat** branches for the same reason.

**Do not** also dump every conceivable parent on every node. NN/g
polyhierarchy: Target puts Nintendo Switch under Video Games *and*
Electronics because those are two real mental models; they do
**not** also put it under Toys. For huge overlap they switch to
**facets** (filters), not a 20-parent tree.

For this dump the best-practice split is:

1. **Thesaurus (backstage)** — polyhierarchy. `trailer-compliance`
   has two BTs: `compliance` and `trailer`. One concept ID.
2. **Map (frontstage)** — a 3-ring sunburst *projected from that
   graph*, plus a facet strip (audience / year / artifact) so you
   are not nesting every dimension into the tree.
3. **Minimum-size gate** before a child is born — e.g. ≥5–8 docs
   (tune on this corpus). Below that, leave the files on the
   parent. That is “only create a group if there is enough to
   justify it.”

What we have now (A+B compact stitch + `terms[0]` sunburst) is a
**seed**, not this map.

---

## Why this answer

Decisive evidence:

- **ISO 25964-1 clause 2.42** defines polyhierarchy and gives the
  exact instrument example: *organs* listed under keyboard
  instruments **and** wind instruments. The note is the rule that
  makes two-way drill work: the concept is the same object in both
  places, not two folders that can drift.
- **ISO 25964-1 clauses 2.3 / 2.37** (BT/NT): the narrower
  concept’s scope must fall **entirely** inside the broader. So
  `trailer-compliance` is a valid NT of Compliance *and* of Trailer
  only if every file in that node is about trailer compliance —
  not “any compliance file that mentioned a trailer once.”
- **SKOS Primer §2.3:** “a SKOS concept can be attached to several
  broader concepts at the same time.” `skos:broader` is
  **not** transitive by default (wheels ⊄ vehicles). That matches
  “click Trailer → see Compliance” without implying every
  compliance file is a trailer file.
- **NN/g Taxonomy 101:** a taxonomy is backstage metadata; the
  sunburst is a *view*. Depth is a design choice (“granularity of
  each tier”). Avoid singularities. Faceted taxonomies are
  several small hierarchies that combine — that is how
  “compliance ∧ trailer” stays powerful without a 6-level folder.
- **NN/g Polyhierarchies:** two-way placement exists to serve
  **two mental models** (someone looking under Compliance, someone
  looking under Trailer). Use restraint. Breadcrumbs must pick a
  **canonical** path even when the node has two parents — that is
  a known tradeoff, not a reason to drop the second parent.
- **NN/g Flat vs deep:** 3 levels is the shallow side of “deep.”
  Generic labels at each level confuse people; specific labels
  (“Trailer compliance”, not “Misc”) are easier. That is why
  “this file is compliance” feels empty.
- **Hedden (practitioner, on Z39.19 / ISO):** polyhierarchy is
  fine *inside* one facet. Do **not** draw BT/NT *across* facets
  (asset × function) as if they were one tree — use combination
  instead. Conflict with a naïve “put Trailer under Compliance
  *and* invent a second Compliance concept under Trailer.”

**Conflict we did not paper over**

| Source | Position | How we tie-break |
|---|---|---|
| ISO / SKOS | One concept, many BTs. Same NTs everywhere. | **Adopt for the thesaurus.** `trailer-compliance` is one ID. |
| NN/g polyhierarchy | Two parents when card-sort / findability shows two homes. Not every possible parent. | **Adopt for which pairs we wire.** Compliance↔Trailer yes; do not also nest it under PD, Purchasing, and Health. |
| Hedden / Z39.19 facets | Do not mix “asset” and “function” as if one hierarchy. | **Adopt for extra dimensions.** Audience, year, artifact type stay **facets**, not a 4th tree level. |
| Microsoft “exactly one category” | One label per doc. | **Reject.** Already rejected in stitch-methods.md; it kills the two-way drill. |

Why “one topic label” lost: it is a **facet value**, not a map.
ISO retrieval is concept-in-context (BT path). A successor who
opens Compliance and cannot see Trailer, or opens Trailer and
cannot see Compliance, is using a monohierarchy — ISO’s *piano
must pick keyboard or strings* failure mode.

---

## Where it was found

Depth: 5 independent primaries.

- **ISO 25964-1:2011** (preview, clauses 2.3, 2.34, 2.37, 2.42) — https://www.iso.org/standard/53657.html · sample PDF — BT/NT scope rule; mono- vs polyhierarchy; organs under keyboard *and* wind; same attributes wherever the concept occurs. Full clauses 10/13 unread (paywall).
- **SKOS Primer** (W3C) — https://www.w3.org/TR/skos-primer/ — several `skos:broader`; `broader` not transitive; top concepts as entry points.
- **NN/g Taxonomy 101** (Laubheimer) — https://www.nngroup.com/articles/taxonomy-101/ — taxonomy ≠ navigation; hierarchical vs faceted; avoid singularities; choose granularity per tier; stakeholder review.
- **NN/g Polyhierarchies** (Laubheimer) — https://www.nngroup.com/articles/polyhierarchy/ — piano / Nintendo Switch; restrain extra parents; facets when overlap is huge; breadcrumbs show a canonical path.
- **NN/g Flat vs. Deep Hierarchies** — https://www.nngroup.com/articles/flat-vs-deep-hierarchy/ — 3 shallow levels vs 5 deep; specific labels beat generic ones.
- **Hedden, “Polyhierarchy in Taxonomies”** — https://www.hedden-information.com/polyhierarchy-in-taxonomies/ — Z39.19/ISO types of hierarchy; do not polyhierarchy *across* facets. Practitioner, not a standard text.

---

## What the current maps do (and why they feel thin)

| Artifact | What it shows | Why it is not the map you described |
|---|---|---|
| `cte-manager-ab-local/topic-map.html` | One ring (Program = first top-level region, Function = first child). Files as leaves. | `map_html._sunburst_payload` keeps `terms[0]` only. A file that is Compliance ∧ Trailer appears under **one** parent. No second ring under Trailer for Compliance. |
| `cte-manager-gb10/topic-map.html` | Pass 1 `map.yml` facets (program / function / audience / …) | Five *sibling* lenses, not topic→subtopic→granular. “Compliance” here is a function chip, not a drill path. |
| `regions.html` | Nested list, multi-home per doc | Closest to the thesaurus, but it is a list, not a two-way graph. Children are stored under one parent only. |

So the tags can already support the map. The **projection**
(sunburst taking the first parent) throws the second path away.

---

## What to build (method C, now specified)

Do **not** re-tag. `tags.json` stays the input.

1. **Keep A+B** (normalize + cluster). Already in
   `burling/tag_concepts.py`.
2. **Induce a graph, not a single tree.** Each cluster may have
   1–2 BTs when both mental models are real (Compliance and
   Trailer). One node id. Recurse only if the cluster still has
   ≥ *k* docs (start *k* = 8; drop to 5 if the tree is too flat).
   Target depth 2–3, tens of nodes — same as stitch-methods.md
   method C.
3. **Project the graph two ways in the sunburst.**
   - Path A: Topic → its NTs → files
   - Path B: the same NT also hangs under its other BT
   Plotly can do this if we emit **unique path ids**
   (`compliance/trailer-compliance/doc` and
   `trailer/trailer-compliance/doc`) pointing at the **same**
   concept id. Values stay document counts; a file may appear
   twice. That is correct for browse, not double-counting for
   inventory (inventory uses concept id, once).
4. **Facets stay orthogonal.** Audience, year, artifact type do
   not become a 4th tree level (Hedden / NN/g). They stay the
   chip row on the map.
5. **Human E.** Approve the *node list* (tens), especially which
   pairs get a second parent. Taxonomy Builder: analysts kept
   ~16% of machine clusters in one session.

Canonical breadcrumb: pick one BT as primary (e.g. the fatter
parent, or the one the user clicked). NN/g: location breadcrumb,
not history.

---

## Worked example (this corpus)

Enough files exist to justify the node (trailer acknowledgment,
checklists, PD, scripts). One concept:

- id: `trailer-compliance`
- BT: `student-health-and-compliance` **and** `mobile-lab` /
  `technology-and-inventory`
- NT (only if fat enough): `trailer-acknowledgment`,
  `trailer-pd`, `trailer-scripts`

A Showcase quote stays `purchasing` ∧ `events-and-showcase` —
same rule, different pair. A singleton `optimal-ed-vr` stays on
the parent or in Needs review. No third tier.

---

## Implementation (2026-08-20)

`burling/browse_graph.py` induces the graph from cached `tags.json`
plus the A+B `regions.json` — no re-tag, no model. The default
**Browse** tab on `compare/cte-manager-ab-local/topic-map.html` is
the 3-ring projection (unique path ids).

Two-parent concepts on this dump (k = 5):

- `trailer-compliance` — Health & Compliance **and** Mobile Lab / Trailer (5 docs)
- `vendor-compliance` — Health & Compliance **and** Procurement (14 docs)
- `cte-student-health` — Health & Compliance **and** Student Pathways (36 docs)

Trailer acknowledgment / PD / scripts stay on the parent: each
is below the split gate. Open Browse, click **Health & Compliance**,
then **Trailer Compliance**; or click **Mobile Lab / Trailer**, then
the same slice.
