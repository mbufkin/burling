# Layered file plan

**Question:** How do folders get named, if the 30B can already file?

**Answer:** Put a 3-layer subject path on the document. Folders are unique
prefixes of those paths. When there are too many mains, one roll-up call
invents a parent (cleaning + cooking → housekeeping). A stranger walks at
most three folders, and only that deep when the parent is fat and mixed.
The fourth layer never becomes a folder.

Everyday organize is **`--walk`**: pick a locked workplace series, then reuse
or invent a child. Combine is a later maintain call on fat mixed drawers
(`burling/maintain_plan.py`). `--layers` (independent 3-layer tags, then one
roll-up) is the previous test. `--clerk` (stitch a plan, then pick) and
`--ralp` are older loops. Navy source for the steal:
[military-document-sorting.md](military-document-sorting.md).

---

## Locked rule

| Layer | On the file | Becomes a folder? |
|---|---|---|
| Roll-up parent | Added later, only if unique mains > ~12 | Yes — browse root (Housekeeping) |
| `main` | Broad subject (cleaning, sports) | Yes |
| `sub` | Narrower inside main (kitchen, hockey) | Yes, when the parent pile is fat and mixed |
| `detail` | Narrower still (grease-trap, playoffs) | Yes only when there is **no** roll-up parent, the pile is fat and mixed, and this is still depth ≤ 3. If a roll-up parent already occupies a slot, `detail` stays a tag. |

**Fat** means about 8 or more documents in that node. Tagged `sub` / `detail` folders open only when fat.
**Mixed** is the roll-up gate: a new parent needs two or more mains (cleaning + cooking). It does not flatten a fat Sports/Hockey pile.
**One home:** each file sits in the deepest folder that survived those cuts.
**Unmapped:** empty or banned `main` (channel, year, usenet, email). Not a new type.

Done when: every tagged file has exactly one `region_ids` entry; no node is
deeper than 3; no channel/year head exists; `detail` that would be a 4th
folder is stored on the assignment as `facet`, not as a child.

---

## Steps (gold / `--layers`)

1. **Tag** each file, one fresh window, full extracted text (80k cap).
   Output `{"main","sub","detail","summary"}`.
   Done when: `layer-tags.json` has one `status=done` row per document (or
   `unmapped` main). Resume skips done rows.

2. **Roll-up** unique `main` values, one call, only if there are more than
   12. The prompt lists **mains and counts only** — no sample `sub`s
   (`hockey` under `sports` is already nested; showing it made the model
   treat the sub as a main). Model proposes parents whose children are
   copied from that list. Code rejects channel/year, vague parents
   (`discussion`, `misc`, `files`), a parent with only one child, and any
   child that is not a main.
   Done when: `rollup.json` maps every main to itself or to one parent, and
   the number of roots is ≤ 12 or the model had nothing valid to merge.

3. **Build the tree in Python.** No second taxonomist call. Prefix the
   roll-up parent, cap depth at 3, drop thin/unmixed children, one home.
   Done when: `regions.json` is written and mean homes per file is 1.0.

4. **Score** purity + one-home against `gold.json`. Primary L1 is a
   diagnostic, not the product score.

Do not loop apply/revise. Combining folders is the roll-up call, not a
per-file audit.

---

## What the model is for

| Call | Input | Output |
|---|---|---|
| Tag | one file | 3-layer path |
| Roll-up | unique mains + counts (no subs) | parent groups |
| Tree / collapse | — | code |
| Clerk pick | — | not this path; the path *is* the home |

---

## CLI

```
python -m burling.run --layers --config burling/config.gold-20news-layers-gb10.yaml
```

Writes `/home/lenovo/gold-20news/layers`. Does not touch `gold-20news/output`
(RALP) or `gold-20news/clerk`.
