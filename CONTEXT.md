# Burling

Local-only document review and browse mapping. This glossary is the ubiquitous language for how a local model is allowed to see a file.

## Language

**The bet**:
One set task (a tight instruction plus a JSON contract) and the extracted text of the file, in a fresh window, every model call.
_Avoid_: Blurb-only audit, leftover chat history, silent 12k truncate

**Extracted text**:
Whatever the harness actually read from the file (text layer, OCR, or unpacked member). That is the document the model is allowed to see.
_Avoid_: Entire document (unless you mean extracted text), original bytes, summary-as-source

**Fresh window**:
A new HTTP chat with only this job’s system prompt and this user message. No prior files, no prior groups.
_Avoid_: Session, conversation, context (when you mean chat history)

**Chunk-then-merge**:
If extracted text is longer than one window, split it into overlapping chunks; each chunk is its own fresh window; then combine the chunk answers.
_Avoid_: Truncate, head-only, one giant paste

**Model call**:
Any local chat the harness sends (tag, stitch, audit, revise, and — if this spec includes them — pass 1 / pass 2).
_Avoid_: Clerk call (too narrow once the bet covers every call)

**Set task**:
One job with a named JSON shape and a short rule list. Not “do the whole tree.”
_Avoid_: Pipeline, pass (when you mean one HTTP call)

**Organize**:
Build a discovered browse tree from a dump: main type, then subtype. Not putting files back into gold folders.
_Avoid_: Reconstruct, restore, put back, recover gold

**Browse tree**:
The map a stranger walks. Main types at the top; subtypes only when a pile is fat and mixed.
_Avoid_: Gold tree, taxonomy (when you mean the discovered map)

**Main type**:
The first cut a stranger would use (sports, hardware, faith). Comes from the file’s `main` tag, or from a roll-up parent. Gold does not name it.
_Avoid_: L1, gold L1, category, stitch-invented head

**Subtype**:
A child pile under a main type. Used when the parent is mixed, not to copy a gold leaf name.
_Avoid_: Gold L2, newsgroup, leaf (when you mean the gold folder)

**Layer path**:
Three subject tags on the file, broad → narrow: `main` / `sub` / `detail`. This *is* the folder system. Extra free-form tags are search facets, not heads.
_Avoid_: Bag of 20 unordered tags, stitch-from-a-cloud

**Roll-up**:
One later call that invents a parent over sibling mains when there are too many of them (cleaning + cooking → housekeeping). Inspected as a fourth layer; never a fourth folder.
_Avoid_: Per-file audit merge, RALP split, vague parents (discussion, misc, usenet)

**Browse depth**:
A stranger walks at most three folders, and only that deep when the parent is fat (~8 docs) and mixed (two fat children). The leftover tag stays on the file as `facet`.
_Avoid_: 4-level tree, one-file children, 274-node bush

**Gold set**:
A public pre-sorted corpus used as a purity check — did hockey stay with hockey? Not a reconstruction target.
_Avoid_: Ground truth to restore, put-back score, Primary L1 (as the product score)

**Purity check**:
Files that shared a gold topic sit in the same pile. Folder titles and nesting can be ours.
_Avoid_: Any-home (too generous with 3+ homes), Primary L1 (reconstruction metric)

**File plan**:
The browse heads after a walk: locked series, reuse or invent a child, maintain fat mixed drawers later. Everyday organize (`--walk`). Docs: `docs/file-plan-layers.md`.
_Avoid_: Open taxonomy, invented 14th series, RALP splits, bag-of-tags stitch as the ship path

**Clerk**:
Older test: one stitch names drawers, then one file picks one home. Not the ship path once `--layers` exists.
_Avoid_: Taxonomist, 12-file blurb audit, three-round revise

**Unmapped**:
Honest leftover bin. A human decides. Not a discovered type.
_Avoid_: Needs review as a dump, model-invented head
