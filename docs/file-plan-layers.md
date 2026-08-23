# Layered file plan

**Question:** How do folders get named, if the 30B can already file?

**Answer:** A closed workplace file plan (Navy-style: prescribed series,
then nest). The clerk walks the tree: pick the locked `main` that fits,
then at each child **reuse** one already there, **invent** the first, or
**combine** siblings that are the same kind of thing. Combine **rehomes**
already-filed files into the broader folder. Unmapped only when the body
has no substance, with a written reason.

This is for a leaving employee's drive, not newspaper topics. `personal`
is a real folder so those files can be deleted. `unmapped` is empty /
no-substance, not "not work."

Everyday organize is `--walk`, not `--ralp` and not bag-of-tags stitch.
`--layers` (tag all files, then roll-up) and `--clerk` (stitch a plan,
then pick) were earlier tests. Navy source for the steal:
[military-document-sorting.md](military-document-sorting.md).

---

## Locked rule

| Layer | On the file | Becomes a folder? |
|---|---|---|
| `main` | One approved workplace series | Yes — browse root |
| `sub` | Reuse / invent / combine under that series | Yes |
| `detail` | Same walk one level down | Yes, depth ≤ 3. Else `facet`. |
| Combine parent | Broader name over two+ existing siblings | Yes — old siblings nest under it, or become `facet` at depth 3 |

**Approved mains:** personnel, operations, administration, finance, legal,
technology, customers, facilities, security, communications, training,
health, personal. Unknown mains are coerced (closest series) or retried.
**personal:** not work. Own folder so it can be deleted after exit.
**unmapped:** no substance (unsubscribe, empty). Not a 14th series. The
reason field must say what is missing.
**One home:** each file sits in exactly one walked path.
**Combine rehomes:** if windows + macos become operating-systems, files
already in those folders move. A new series is a list change, not a
model invent.

Done when: every filed file has exactly one `region_ids` entry; no node
is deeper than 3; no channel/year head exists; leftover layer-4 tags are
`facet`, not children.

---

## Steps (gold / `--walk`)

1. **Main.** One fresh window, full extracted text (80k cap). Pick one
   approved series, or `unmapped` with a reason. Done when: the id is on
   the closed list, or the body has no subject.

2. **Sub.** Show the children already in that series (name + count).
   Reuse one, invent the first, or combine two or more. Combine runs in
   code: those siblings move. Done when: the child id is existing,
   newly invented, the combine-into name, or empty (file sits on main).

3. **Detail.** Same question under that sub. Empty is allowed. Depth
   caps at 3.

4. **Build the tree in Python** from the walked homes. No second
   taxonomist call. No fat-min collapse — the first file in a series
   invents a sub on purpose. Done when: `regions.json` is written and
   mean homes per file is 1.0.

Do not loop apply/revise. Roll-up of mains is skipped: the workplace
list is already the closed plan (Navy does not merge 2000 with 7000).

20 Newsgroups gold is the wrong purity check for a workplace plan
(hockey is `personal`, not a failed file). Use it to see whether the
walk reused and combined, not whether L1 matches newsgroups.

---

## What the model is for

| Call | Input | Output |
|---|---|---|
| Main | one file | approved series or unmapped+reason |
| Child | one file + existing siblings | reuse / invent / combine / empty |
| Rehome / tree / depth 3 | — | code |

---

## CLI

```
python -m burling.run --walk --config burling/config.gold-20news-walk-gb10.yaml
```

Writes `/home/lenovo/gold-20news/walk`. Does not touch `gold-20news/output`
(RALP), `gold-20news/clerk`, `gold-20news/layers`, or
`gold-20news/layers-workplace`.
