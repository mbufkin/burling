# When it works

Locked with [SPEC.md](SPEC.md) on 2026-08-20.
This is the scoreboard for the fresh-window bet. If a layer is not
green, the spec is not implemented — a pretty sunburst does not count.

Three layers. Each answers a different question. Do **not** skip ahead.
CI is the only layer that runs in GitHub Actions (no GPU). Layers 1–2
need Lightning on gb10 llama.cpp.

| Layer | Question | Corpus | Model? | Who runs it |
|---|---|---|---|---|
| **0 — Contract** | Did we follow the bet in code? | fixtures + prompt strings | No | CI on every PR |
| **1 — Smoke** | Can Lightning organize *any* tiny folder and stop when worse? | `sort-sample` (18 planted texts) | Yes | You, on gb10 |
| **2 — Gold** | Did we recover a known public tree? | MultiEURLEX EN L1→L2 (~400–800) | Yes | You, after Layer 1 is green |

`tiny-dump` is Product A (PII), not a sort score. The CTE-manager dump
is a field trial — never the pass/fail. Govdocs1 is extract-only and
out of this spec’s “it works.”

**On disk tonight:** `python -m burling.fetch_gold --corpus 20newsgroups`
writes a public 400-file inbox under `.data/20newsgroups/` (gitignored).
That is a real folder tree we can run. It is **not** Layer 2
(MultiEURLEX still needs the 2.8 GB pull). See [docs/golden-set.md](../../docs/golden-set.md).

---

## Layer 0 — Contract (CI, no GPU)

**Command (already in CI):**

```bash
cd /Users/michaelbufkin/Desktop/burling-v2
python -m unittest discover -s burling/tests -p "test_*.py" -v
python -m burling.run --priors-only --intake burling/tests/fixtures/tiny-dump
```

### Already green (do not regress)

| Test | What “works” means |
|---|---|
| `test_priors` + `test_fixture_dump` + `--priors-only` | SSN/card fail-closed; synthetic dump only |
| `test_tag_rich.test_prompt_does_not_force_handover_frame` | Tag system has no “for a successor” |
| `test_stitch_tags.test_stitch_prompt_lets_tree_emerge` | Stitch system has no “handoff map” |
| `test_apply_audit` | Apply moves; `flags-rose` / `no-applies` stop; one-file children fold; split rewrite |
| `test_audit.test_tree_order_is_parent_then_child_not_random` | Group walk is ordered |
| `test_extract_zip` | Zip-slip rejected; members become files |
| `test_browse_graph` | Two-parent node; singularity not minted |

`test_audit.test_group_max_constant_is_the_documented_cap` still
asserts `AUDIT_GROUP_MAX == 12`. That constant **must die or become
1** when the spec is implemented — update this test in the same
commit.

### Must be green before Layer 1 (write these in the implement session)

| Gate | Pass | Fail |
|---|---|---|
| **No silent 12k** | Tag/pass1 use the 80k chunker; a fixture >12k chars is split; no `[:12000]` / `DOC_CAP` | `tag_rich.DOC_CAP` still truncates |
| **One file per clerk call** | Audit/revise prompt builder emits **exactly one** `rel_path` and includes extracted text (not a 280-char summary) | Prompt lists 12 files or only blurbs |
| **Stitch is a table** | Stitch prompt contains cluster labels/counts; a planted file body string does **not** appear | Member PDF/text pasted into stitch |
| **Product A merge is code** | Pass 1 reduce has no `chat()` / `complete()` | A second Lightning call concatenates chunk JSON |
| **No district flavor** | Prompts/tests assert absence of `central-cte`, `campus-admin`, `successor`, `handoff`, `handover` | Any of those strings in user-facing prompts |
| **Dissolve seatbelt** | Dissolving a parent with living children is refused **or** children are moved onto a real remaining node; assignments never point at missing ids | Ghost `region_ids` after dissolve (Agriculture bug) |
| **CI gold fixture** | 8–12 invented snippets + `gold.json`; scorer computes hierarchical F1 + L1 parent recall on a **known** placement file (no model) | Scorer only exists as a notebook; EU-law text in git |

Layer 0 is how we know the **bet is wired**. It does not prove Lightning
is a good clerk.

---

## Layer 1 — Smoke (`sort-sample`)

**Question:** On 18 public-style files, does Lightning organize, check,
and refuse to make the tree worse — without inventing Dallas ISD?

**Gold (filename prefix → planted family):**

| Prefix | Family | Files |
|---|---|---|
| `ag-` | Agriculture | soil-test, irrigation-schedule, seed-catalog-notes |
| `env-` | Environment | wetland-survey, air-quality-brief, recycling-audit |
| `finance-` | Finance | budget-worksheet, savings-goal, tax-checklist |
| `health-` | Health | clinic-hours, vaccine-faq, heat-advisory |
| `sports-` | Sports | league-standings, trail-race, pool-schedule |
| `transport-` | Transport | rail-timetable, harbor-pilot, bike-lane-memo |

Names on the map may differ (`Farming` vs `Agriculture`). Score the
**family**, not the string.

**Command (after implement; Lightning on gb10):**

```bash
python -m burling.run --config burling/config.sort-sample.yaml --ralp --ralp-rounds 3
```

Read `RALP.md`, `regions.json`, `AUDIT.md`. Open `topic-map.html`.

### Pass (all must hold)

1. **Six families on the tree.** Each planted family has a real topic
   (or a clearly named child of one). Needs review is not a family.
2. **Primary home matches prefix.** For each of the 18 files, the first
   `region_ids` entry walks up to that file’s planted family.
   Score: **18/18** primary-home hits. (A second home is allowed.)
3. **No ghosts.** Every `region_ids` value exists in `regions.json`.
   Agriculture (or its rename) is still a node if any `ag-` file
   points at it.
4. **Stop is honest.** Final stop is `flags-rose`, `no-applies`, or
   `flag-rate` — not a crash, not “we hit max-rounds after the tree
   got worse and we applied anyway.”
5. **The bet held on the wire.** Trace/log for a tag call shows one
   file and extracted text (not 12k-truncated if the file is short).
   An audit call’s user message contains **one** path and the file
   body. A stitch call’s user message does **not** contain
   `A soil test from the north field` (that sentence is only in
   `ag-soil-test.txt`).
6. **No CTE story.** `RALP.md` / prompts do not mention Dallas ISD,
   CTE, successor, or handover.

### Fail (any one)

- A planted family **vanishes** and its files sit on ghost ids
  (the restitch we already saw).
- Primary-home hits **≤ 14/18** (two families smeared).
- Flag rate rises **and** that round’s apply still ran.
- Audit still sends 12 blurbs.
- We call it a pass because “18/18 tagged.” Tags are notes, not the map.

Layer 1 is how we know the **loop works**. It is not a public benchmark.

---

## Layer 2 — Gold (MultiEURLEX English L1→L2)

**Question:** If we hide the folders, do we recover a tree a stranger
already published?

**Recipe (from the spec):**

```text
load_dataset("coastalcph/multi_eurlex", "en")
```

- Chronological **test** split, stratified **~20–40 docs per L1**
  (~420–840). Publish the CELEX id list.
- Materialize `gold/{L1}/{L2}/{celex_id}.txt` (symlink if multi-label).
- Flatten to one inbox. The model must not see gold path names.
- Cite Chalkidis et al., EMNLP 2021. Follow the EUR-Lex notice
  (CC-BY-4.0: acknowledge + mark changes).

**Metrics (compute ourselves; the paper reports mRP, not this):**

| Metric | What it means | Pass bar (first run) |
|---|---|---|
| **L1 parent recall** | Gold L1 domain appears among the file’s ancestor topics | **≥ 0.50** mean over files, and **beat one-shot stitch** on the same sample |
| **Hierarchical F1** | Predicted and gold paths expanded to ancestors, then F1 | **Beat the one-shot baseline** on the same CELEX list |
| **Ghost rate** | Assignments pointing at missing nodes | **0** |

“Beat one-shot” is mandatory. If RALP does not beat compact stitch +
no-audit on the same sample, the loop is theater.

**Fail:** scoring the CTE dump; using `nlpaueb/multi_eurlex` (2022
cut); treating `sklearn.fetch_rcv1` as documents; committing the 400
EU texts to git; claiming the paper’s mRP without a ranked label list.

Layer 2 is how we know it works on **any dump with a hidden gold
tree**. Do not start it until Layer 1 is green.

---

## How to read a run (so we don’t fool ourselves)

| Artifact | Trust it for |
|---|---|
| Unit test output | Contracts (Layer 0) |
| `RALP.md` | Stop reason, flag rate per round, whether revise ran |
| `regions.json` + assignments | Primary home, ghosts, family coverage |
| Prompt traces / `run.log` | One file? Full text? Table-only stitch? |
| `topic-map.html` | Human sanity, **not** a score |
| `AUDIT.md` | Flags are a queue, not gold |

**Does not mean it works**

- The sunburst drew.
- 18/18 or 871/871 tagged.
- Flag rate went down after we deleted a real topic.
- “It feels organized” with no primary-home table.

---

## Implement-session checklist

Copy this into the PR that implements the spec:

- [ ] Layer 0: new contract tests listed above are in `burling/tests/`
- [ ] `AUDIT_GROUP_MAX` is 1 (or the audit builder never batches files)
- [ ] `DOC_CAP` / silent 12k truncate gone
- [ ] `central-cte` / handover strings gone from prompts
- [ ] Dissolve seatbelt test (ghost ids impossible)
- [ ] Synthetic `gold.json` scorer in CI
- [ ] Layer 1 run on Lightning; table of 18 primary homes pasted in the PR
- [ ] Stop reason recorded (`flags-rose` / `no-applies` / `flag-rate`)
- [ ] Layer 2 recipe script exists; first scored sample may be a follow-up PR if HF is slow, but the scorer must already run on the CI fixture
