# Burling — consultant ship review

**Date:** 21 August 2026
**Audience:** an outside reviewer, not the implementer
**Status of the live gold job:** `--walk` on gb10, 338 / 400 files, ~8 s/file, **0 combine/rehome events** as of 16:35 UTC. This brief does not wait for that job. Treat those numbers as in-flight.

You are being asked to review work that the operator intends to treat as the organize path that ships. The question is not “does a 30B sort Usenet.” The question is: **is the file-plan system correct, constrained, and ready to point at a real leaving-employee drive.**

Read this file first. Then the pointers in §14. Do not reconstruct intent from `README.md` alone — it still describes an older product.

---

## 1. What we want from you

A written review, not a rewrite. For each item in §13, say **ship / ship with conditions / do not ship**, and name the evidence.

We are not asking you to:

- pick a different model, or move off Lightning Q8 on `127.0.0.1:8080`
- restore 20 Newsgroups gold folders
- re-open `--ralp` as everyday organize
- invent a 14th top-level series from leftovers

We are asking you whether the **locked clerk SOP** (closed workplace series → walk down the live tree → one home) is sound enough to run on a real handover, and what must be true before that run.

---

## 2. The job, stated as a records problem

An employee leaves. Their laptop / Drive / shares land as a flat dump. A stranger (records, IT, the manager) must:

1. **Browse** related work without knowing the author’s folder names.
2. **Isolate personal** material so a human can delete it after exit.
3. **Leave empty / test / unsubscribe residue** in a leftover bin — not as a new type.
4. **Never let the harness delete a file.**

The analog we stole is U.S. military filing, not newspaper taxonomy and not TaxoGen. Navy / Army / Air Force / OSD manuals prescribe a file plan *before* the document exists. The clerk reads the subject and assigns the closest approved code. Year, office, and channel are arrangement, not series. A new series is a formal change, not something a model mints from the pile. Source note: [military-document-sorting.md](military-document-sorting.md) (claims traced to .mil / archives.gov / govinfo.gov / ecfr.gov).

**Product sentence we are shipping toward:** one file, one home, on a closed functional file plan, nested at most three folders deep, walked as the pile is filed.

That is **organize**. It is not “put these 400 newsgroup posts back into `rec.sport.hockey`.”

---

## 3. There are two programs in one repo. Review that.

| Program | CLI | What it is | Ship status |
|---|---|---|---|
| **Product A — review** | default `burling.run`, `--priors-only`, `--pass 1/2`, `--map` | Regex PII + local model keep/review/delete-candidate. Human confirms deletes. Governed `map.yml` facets (program × function × …). | Documented in `README.md`. Older, still present. Not what the last two weeks optimized. |
| **Product B — organize** | `--walk` (intended). `--layers`, `--clerk`, `--ralp` are prior experiments. | Closed workplace series + live tree walk. Browse map for a stranger. | This is what we want reviewed as the organize path. README still calls `--ralp` the experimental organizer. |

A consultant who only reads the README will review the wrong product. A consultant who only reads `walk_plan.py` will miss that Product A still exists, still talks to a model, and still has the same local-only / no-auto-delete constraints.

**Review this split.** Shipping organize as a flag salad on top of a PII-review CLI is a product risk, not just a docs lag.

---

## 4. Locked invariants (treat a violation as a defect)

These are enforced in code where noted. A prompt that “asks the same thing” is not enough — Nemotron still emitted `usenet-1993` as a stitch head until we stripped it in Python.

| Invariant | Rule | Where it is enforced |
|---|---|---|
| Local only | Model URL host must be `127.0.0.1` / `localhost` / `::1` | `burling/ollama_client.py` `assert_local_only` |
| Never auto-delete | Harness writes candidate lists only | `SECURITY.md`; `policy.never_delete` |
| One home | Each file has exactly one `region_ids` entry | `walk_plan.WalkState.place`, clerk `apply_clerk` |
| Closed L0 | Mains ∈ {personnel, operations, administration, finance, legal, technology, customers, facilities, security, communications, training, health, personal} or `unmapped` | `WORKPLACE_MAINS` + `coerce_main` |
| No 14th series | Unknown main is aliased, retried, or (last resort) `operations` — never minted | `coerce_main`, `choose_main_model` |
| `personal` ≠ `unmapped` | Not-work with a subject → `personal` (delete bin). No substance → `unmapped` + reason | prompts + `coerce_main_choice` |
| Channel / year are not heads | `usenet`, `email`, `1993`, … | `file_plan.is_banned_head` |
| Depth ≤ 3 | Fourth layer is `facet` on the assignment | `MAX_BROWSE_DEPTH = 3` |
| Fresh window | One HTTP chat = this job’s system prompt + this user message. No prior files in context | `ollama_client.chat` per call |
| Extracted text | Model sees what extract/OCR actually read, cap 80k chars | `LAYER_DOC_CAP`; extract module |
| Model proposes, code decides | JSON is coerced. Invalid combine / banned child / reserved name is dropped | `coerce_main_choice`, `coerce_child_choice`, `WalkState.rehome` |

**Do not accept a design that gives the 30B `regions.json` to mutate.** That is `--ralp`. We already ran it.

---

## 5. How organize actually works (`--walk`)

Module: `burling/walk_plan.py`. Spec: [file-plan-layers.md](file-plan-layers.md). Ubiquitous language: [CONTEXT.md](../CONTEXT.md).

### 5.1 Per file (sequential; order matters)

For each document, in intake-list order:

1. **Main (one call).** Closed enum. `unmapped` only if the body has no topical substance; `reason` required. Empty extract short-circuits with `reason=extract missing` and does not call the model.
2. **Sub (one call).** User message lists **existing children of that main** (id + file count). Model returns `reuse` | `invent` | `combine` | `empty`.
3. **Detail (one call, if a sub exists).** Same contract one level down. `empty` is allowed.

If `action` is missing, code infers it: two+ existing ids in `merge` → combine; name already a sibling → reuse; else invent.

Cost: **2–3 Lightning calls per file**. The in-flight gold walk is ~8 s/file on Nemotron 3.5 Lightning 30B Q8, llama-server `:8080`, `n_ctx=524288`, thinking disabled in the client (`enable_thinking: false`). ~400 files ≈ 50–60 minutes. That is acceptable for a handover; it is not a background tag.

### 5.2 Combine / rehome (the Navy closest-folder move)

If the model names two or more **already existing** siblings and a broader `into`:

- Code requires `len(merge) ≥ 2`, `into` not banned / not vague / not a reserved series id.
- Files already under those siblings **move**.
- Old sibling names nest as the next layer when depth allows (`technology/windows` → `technology/operating-systems/windows`).
- At depth 3 the old name becomes `facet`, never a fourth folder.

This is the only invent-of-structure after L0, and it is **not** a new main. Combining `windows` + `macos` does not mint a 14th series.

**Live gold observation:** 337 files filed, **0 combines**. The path is unit-tested. It has not yet earned its keep on this corpus. That is a review item (§13.4).

### 5.3 What the model is not for

Building or rewriting the browse tree. No apply/revise loop. No stitch that invents L0. No roll-up of the 13 workplace mains (Navy does not merge 2000 with 7000). `--layers` still has a roll-up call for *open* discovery; the workplace walk skips it.

### 5.4 Tree write

Homes in `walk-state.json` are the source of truth. `regions.json` is derived in Python (`build_walk_regions`). Thin first-children are **not** collapsed — the first file in a series invents a sub on purpose. That is a deliberate break from the earlier `fat_min ≈ 8` seatbelt and from TaxoGen “push general members back to the parent.” Expect 1-document folders early in a run. Review whether that is acceptable on a real drive.

---

## 6. Paths we already ran and rejected as everyday organize

Same 400 hashed 20 Newsgroups files (by-date test split, 20 groups × 20 docs). Same Lightning box. Trees written to **separate** folders so they can be compared. Do not overwrite `gold-20news/output` (RALP).

| Method | What owned the tree | Nodes | Homes/file | Purity | Primary L1 | Honest leftover | Why it is not the ship path |
|---|---|---:|---:|---:|---:|---|---|
| v1 compact stitch | Model invents drawers from a tag cloud | 22 | 3.42 | 47.2% | 17.5% | — | Multi-home. Channel/year heads. |
| v2/v3 A+B stitch | Extra cluster machinery | 18 | 3.23 | 54.0% | 11.8% | — | Worse L1 than compact. Machinery did not earn its keep. |
| v4 `--ralp` (3 rounds) | Model apply/revise | **274 walked** (meta said 21), depth 5 | 3.09 | 13.2% | 37.5% | 180 ghost ids | Higher L1, worse map. Flags 78% → 68%, never hit a seatbelt, hit `max-rounds`. |
| `--clerk` | Stitch invents flat plan, then one home | 10 | **1.0** | 52.2% | **55.5%** | 61 in Unmapped folder | Filing worked. Drawer invention failed (two Hardwares, no Medicine, unused Needs review, no nest). |
| `--layers` open | Independent 3-layer tags + roll-up | 30 | 1.0 | 52.0% | 49.0% | 11 empty mains | Roll-up prompt taught `hockey` as a main; code dropped every group (23→23 roots). Hardware ate 166/400. |
| `--layers` workplace | Closed 13 mains, no walk | 18 | 1.0 | — | 17% (wrong metric) | 2 honest empties | Hardware became a **sub**. Finance unused. **communications = 137** (new junk drawer). 12 files sat under `communications/unmapped` (sub named `unmapped` — now banned in walk coerce). |

Sources: [bakeoff-20news.md](bakeoff-20news.md) (stitch/RALP rows); later clerk/layers rows from the gb10 runs recorded in session notes. Primary L1 on 20news is a **reconstruction** metric. We locked **purity + mean homes ≈ 1.0** as the browse scores, and then locked a **workplace** plan for which 20news L1 is the wrong test (hockey → `personal`).

**What we kept from those runs**

- The 30B can file into a closed list (clerk).
- The 30B cannot be trusted to *name* the list (stitch, RALP, roll-up-as-posed).
- One home is non-negotiable for browse.
- Channel/year heads must be banned in code.
- “Doesn’t fit” is not `unmapped`. `unmapped` is no substance.

---

## 7. The closed file plan (L0)

Workplace / employee-exit, not newspaper topics. `personal` is a **delete bin**, not a Navy mission series. That is a deliberate steal for this product.

| Series | Function |
|---|---|
| personnel | Hiring, reviews, 1:1s, org |
| operations | Doing the work (projects, deliverables, plans) |
| administration | Policies, process, governance |
| finance | Invoices, expenses, budgets, purchasing |
| legal | Contracts, compliance, IP, disputes |
| technology | Software, IT, systems, networks |
| customers | Sales, support, accounts |
| facilities | Office, physical gear, supplies |
| security | Access, incidents |
| communications | Official comms *as a job* (press, gov relations). Not “this is email.” |
| training | Onboarding, courses |
| health | Workplace medical / safety |
| personal | Not work — isolate so a human can delete |
| unmapped | No substance — human decides; not a 14th type |

Aliases in code (not a 14th type): `hardware` → `facilities`, `software`/`it` → `technology`, `sports`/`faith`/`religion` → `personal`, etc. See `MAIN_ALIASES` in `burling/layer_plan.py`.

A 14th series is a **list change** reviewed by a human, then shipped as a constant. The model does not get that job.

---

## 8. Runtime, data, and isolation

| Item | Fact |
|---|---|
| Repo (this brief) | `/Users/michaelbufkin/Desktop/burling-v2` |
| Remote checkout | `gb10:/home/lenovo/burling` (user `lenovo`) |
| Organize model | `/home/lenovo/llama.cpp/models/nemotron35-lightning-30b.gguf` (Q8 Lightning) via llama-server `:8080`, OpenAI-compatible API. Do not move this test to Ollama or the NVIDIA cloud proxy. |
| Gold inbox | `gb10:/home/lenovo/gold-20news/inbox` — 400 hashed `.txt`; `gold.json` holds the hidden newsgroup labels |
| File list only | `gold-20news/output/tags.json` — reused as the 400-row roster. Walk **re-reads** each file; it does not reuse those free-form tags as the path. |
| In-flight output | `gold-20news/walk/` (`walk-state.json`, `regions.json`, `PROGRESS.json`, `walk.log`) |
| Do not overwrite | `gold-20news/output` (RALP), `clerk/`, `layers/`, `layers-workplace/` |
| Local gold texts | `Desktop/burling-v2/.data/20newsgroups/` (gitignored) |
| Intended later gold | English MultiEURLEX L1→L2 (Zenodo 2.8 GB). **Not on disk.** 20news is the stand-in, and the wrong domain for a workplace plan. |

---

## 9. Security and data handling (non-optional)

From [SECURITY.md](../SECURITY.md) and `AGENTS.md`:

1. Local models only. A change that sends intake text off-box is a security bug even if tests pass.
2. Never auto-delete.
3. Ledger redacts formatted SSN / Luhn cards. This is **not** a de-identification product. Regex + 30B will miss identifiers. The original dump stays offline until a human confirms the delete list.
4. Do not commit `intake/`, `corpus/`, or real `output/`.

Product A (PII review) and Product B (organize) share (1)–(4). Organize additionally writes titles and summaries derived from file text into `regions.json` / HTML maps. On a real handover those maps **are** the dump, in browseable form. Review retention of those artifacts.

---

## 10. Known defects and design risks (do not discover these as surprises)

1. **Two products, one CLI.** README / `--help` still lead with review + `--ralp`. Ship docs are behind the code.
2. **Gold domain mismatch.** 20 Newsgroups *is* forum mail. A workplace clerk will stuff hockey, guns, and atheism into `communications` or `personal`. Primary L1 falling to ~17% on the workplace `--layers` run is **expected**, not a filing regression. We do not yet have a public *workplace handover* gold set.
3. **Walk is order-dependent.** File 1 invents the first sub. File 200 sees a different sibling list. Shuffle the inbox, get a different tree. Combine (if it fires) mutates earlier homes. That is intended; it is also a reproducibility and review problem.
4. **Combine has not fired on the live gold walk** (0 / 337 at the time of writing). Either the prompt is still posing “invent a near-duplicate,” or this corpus’s locked mains do not produce combinable siblings, or both. Unit tests prove the *code* rehomes. They do not prove the *30B* will ask for it.
5. **Last-resort main is `operations`.** If the model will not pick an approved series after one retry, we file under operations rather than mint a series or dump to unmapped. That can become a junk drawer on a messy drive.
6. **No fat-min on `--walk`.** Stranger-browse may see many 1-file children. The earlier seatbelt (~8) hid that; it also hid the first invented sub.
7. **JSON fragility.** llama.cpp `response_format=json_object` plus one retry. Clerk still had 6 YAML-shaped misses (`home:` / `reason:`). Walk already saw a truncated JSON on a child call; the retry recovered. One file must not kill the run (`OPERATOR_STOP` / per-file failure notes).
8. **Reserved-child ban.** Approved mains and `unmapped` cannot be child ids. That stops `communications/unmapped`. It also stops a legitimate `operations/training` if someone wanted training as a sub rather than a root. Training is an L0 series. Review whether that rigidity is right.
9. **Headline gold (MultiEURLEX) is not fetched.** We said it is the Layer-2 scoreboard and then scored 20news because it was on disk.
10. **No real handover has been run** on the walk path. The only employee-exit evidence is the *prompt*, not a corpus.
11. **Product A prior art (TAR, Purview SIT + classifier, Presidio)** is written in [PRIOR-ART.md](PRIOR-ART.md) and is largely unimplemented as a trained policy. Organize stole the military SOP instead. Do not confuse those two research threads.

---

## 11. Tests that exist vs tests that do not

**Exists (CI-shaped, no GPU):** `burling/tests/test_walk_plan.py` — coerce main/child, banned names, rehome at sub and detail, first-file invent + second-file reuse, combine-then-place, empty extract does not call the chooser. Plus existing clerk / layer / extract / local-only tests.

**Does not exist:**

- Integration test that Lightning returns combinable JSON on a planted 3-file fixture (`windows`, `macos`, `linux`).
- Property test that shuffle(order) still yields one home, depth ≤ 3, closed L0.
- Workplace-sample gold (offer letter, W-2, invoice, vacation photo, empty `.txt`).
- Scoring that treats `personal` as success for recreation/belief on 20news (so we stop quoting Primary L1 as if it were the product).

`python3 -m unittest discover -s burling/tests -p "test_*.py"` is the gate after harness changes. It does not certify a 400-file Lightning walk.

---

## 12. What “ready to ship” would mean (our draft; argue with it)

Organize is ready to point at a **real** drive only if all of the following are true:

1. One home, depth ≤ 3, closed L0, no channel/year heads — held on the gold walk *and* on a planted workplace fixture.
2. `personal` is a real, isolatable folder; `unmapped` is small and each row has a reason a human can read.
3. Combine either fires on near-duplicate siblings in a fixture, or we drop it from the ship story (do not advertise rehome if the model never requests it).
4. README / CLI / `CONTEXT.md` describe `--walk` as organize and `--ralp` as a finished negative experiment.
5. A human has walked the HTML map of at least one non-Usenet dump and has not needed a 14th series.
6. Security review of `regions.json` + topic-map HTML as a browseable copy of the dump.

The in-flight 20news walk can satisfy (1) on *mechanics*. It cannot satisfy (5).

---

## 13. Review questions

Answer each. “Looks fine” is not an answer.

1. **Product identity.** Should organize ship as a mode of Burling, or as a separate front door? What does a leaving-employee operator run on day one?
2. **Closed L0.** Are these 13 series + `personal` + `unmapped` the right civilian analog of Navy’s 13 SSICs for an *arbitrary* knowledge-worker dump (not a school district, not a newsroom)? Which two would you merge or rename before a real drive?
3. **Walk vs prescribe-then-file.** We rejected stitch-invented L0. We also rejected independent 3-layer tags that never see siblings. Is sequential walk + rehome the right third thing, or should L1/L2 also be a closed table (Navy secondary/tertiary codes) so the model only *picks*?
4. **Combine.** Given 0 combines on ~337 gold files: keep, change the question, or delete the feature until a fixture proves the 30B will request it?
5. **Order dependence.** Is a non-deterministic (order-sensitive) browse tree acceptable if one-home and closed-L0 hold? If not, what replay rule do you want (two-pass: invent-all then file; or freeze names after N files)?
6. **Thin children.** First file invents a sub even when it is the only document. Ship that, or restore a fat-min (~8) *after* the walk?
7. **Fallback to `operations`.** Acceptable fail-closed, or should a failed main after retry go to a human queue instead?
8. **Evaluation.** What score do we put on the box if 20news Primary L1 is the wrong test? Propose a workplace fixture (counts + expected series) we can run in CI without Lightning, and a Lightning smoke that is not Usenet.
9. **Product A.** Leave PII-review in-tree as-is, or freeze it until organize has one operator story?
10. **Security.** Is writing full-text-derived summaries into a shareable HTML map acceptable on a handover that may contain tax IDs? What must never leave the box?

---

## 14. What to read (in this order)

| Order | Path | Why |
|---|---|---|
| 1 | This file | Scope and claims |
| 2 | [CONTEXT.md](../CONTEXT.md) | Ubiquitous language. If a word is not here, do not invent a synonym in the review. |
| 3 | [file-plan-layers.md](file-plan-layers.md) | Locked walk SOP |
| 4 | [military-document-sorting.md](military-document-sorting.md) | Prior art for L0 + one home |
| 5 | `burling/walk_plan.py` | Implementation. Interface: `WalkState`, `walk_one`, `coerce_*`, `run_walk_plan` |
| 6 | `burling/tests/test_walk_plan.py` | What we actually proved without a GPU |
| 7 | [bakeoff-20news.md](bakeoff-20news.md) + §6 above | Negative results for stitch / RALP |
| 8 | [SECURITY.md](../SECURITY.md) | Fail-closed rules |
| 9 | [fresh-window-bet.md](fresh-window-bet.md) | Why one file / full extract / no 12-file blurbs |
| 10 | [ralp-loop.md](ralp-loop.md) | What `--ralp` was, so you do not recommend we “just loop again” |
| 11 | `README.md` | What a stranger from GitHub still thinks the product is |

Do not treat `.scratch/fresh-window-bet/` as ship spec; it is the research that produced the bet. Do not treat `gold-20news/output` as the current organizer — that is the finished RALP tree.

---

## 15. How to inspect the in-flight walk (does not start a second job)

On gb10:

```bash
cd /home/lenovo/burling
python3 -m burling.run --status --config burling/config.gold-20news-walk-gb10.yaml
# or
tail -f /home/lenovo/gold-20news/walk.log
```

When it hits `walk-done`, the artifacts to attach to your review are:

- `gold-20news/walk/regions.json` — `meta.homes_mean`, `meta.unmapped`, `meta.combines`, `meta.nodes`
- `gold-20news/walk/walk-state.json` — `combines[]`, per-file `reason` on unmapped
- `gold-20news/walk/REGIONS.md` / `regions.html` — what a stranger would actually walk

Score Primary L1 against `gold.json` only as a **purity / clustering** sanity check, and say so. Do not use it as a ship gate for a workplace file plan.

---

## 16. Operator position (so you can disagree with it)

We believe:

- Filing skill of the 30B is adequate when the question is a closed enum plus the live sibling list.
- Folder *invention* at L0 is not a model job.
- Code must remain the records office (coerce, rehome, depth, banned heads).
- The remaining product risk is the **file plan and the walk question**, not another 400-file RALP loop.
- 20 Newsgroups was the right *mechanical* corpus (public, pre-sorted, on disk) and the wrong *domain* corpus. Shipping on Usenet scores would be a category error.

If you disagree, say which belief is wrong and what evidence would change it. Do not recommend we “let the model do all the steps.” We already did that. It produced 274 nodes, 3 homes per file, and 180 ghosts.
