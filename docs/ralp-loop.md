# RALP: organize → audit → revise → audit

**Question:** How should a capable ~30B model organize *any* document
dump — not one-shot word tags — and keep checking until placements feel
stable?

**Ticket date:** 2026-08-20
**Sample:** `burling/tests/fixtures/sort-sample/` (public-style texts,
no district dump)

This is a wayfinder-research ticket. Claims are traced to fetched
primaries. Siblings: [audit-pass.md](audit-pass.md),
[stitch-methods.md](stitch-methods.md), [browse-map.md](browse-map.md).

---

## Answer

**RALP** is a **R**evise-**A**udit **L**oop for **P**lacement. The 30B
does organizational work on **groups** (name, decision rule, split,
merge). Code clusters, applies edits, and stops the cycle. One-shot
“assign some words” is the failing baseline in every source we fetched.

```
summarize files
    → code clusters a level
    → 30B names each group + writes a rule
    → audit a *new* batch / one group at a time
    → apply moves + 30B revise mixed groups
    → audit again
    → stop when new-batch yield falls (not when the model repeats itself)
```

That loop is what `--ralp` runs. It is **corpus-agnostic**: the only
domain input is a generic use-case line (“organize so a stranger can
find related files”). No handover story, no district seed labels.

The public sample is `sort-sample` first (CI + smoke). A labeled
benchmark (MultiEURLEX English L1) is how you *score* the tree later;
Govdocs1 is how you score extract, not organization.

---

## Why this answer

### One-shot tags under-use the 30B

**TnT-LLM** (Wan et al., KDD ’24, §1, §3.1): conventional
cluster-then-label is “reading tea leaves.” The LLM should
**produce and refine a label taxonomy iteratively**. Each category is
a **name + description that can classify new points**, not a keyword
list. The update prompt has three jobs: evaluate the current table on
**new** data, list issues, rewrite the table. After N minibatch
updates, a review prompt checks quality and **bans** Other / General /
Miscellaneous as taxonomy nodes.

That is exactly “ask the 30B to do more than assign some words.”

### Organization is recursive split + push-up, not a tag cloud

**TaxoGen** (Zhang et al., KDD 2018, §4): a node is a **cluster of
coherent terms**. Split top-down; **general** members stay on the
parent (`r < δ`); recluster; stop the inner loop when nothing else
promotes. Then go deeper on **local** evidence. Ablations that skip
this produce children that are the same topic as the parent.

Conflict we keep: TaxoGen splits every node to a fixed \(K\) down to
\(L_{\max}\) and calls auto-\(K\) future work. We keep a **depth cap**
as a safeguard, but we only recurse when audit says the group is
**mixed**, not because a folder is large (NN/g singularity + their
own “same-topic child” failure).

### Do not stop because the model “looks stable”

**Cormack & Grossman TAR** (SIGIR 2014): CAL reviews the next
**top-scoring uncoded batch**, retrains, and **does not** freeze at
“stabilization” (that is SAL/SPL, and it loses). Stop when yield /
density vs effort is “enough.” Reviewers (and models) are fallible;
gold is a later pass.

Tie-break: TnT’s “stop after N updates + review” is a hyperparameter.
TAR is decisive that **“the table looked good once” is the wrong
stop.** RALP stops when a **fresh** audit applies ~0 moves or the
flag rate falls under a threshold — analog of yield drop.

### Consensus vs this repo yesterday

All three: iterate on unseen material; audit then revise; work a
**group with a rule**, not a keyword; coarse then fine; one label
pass is not gold.

What we had: Pass A tags (useful description) → one compact stitch →
one audit that **wrote a queue and stopped**. 621 flags / 250
confirms is TAR’s “do not freeze” warning in numbers.

Polyhierarchy (ISO / SKOS) still applies at **document** level. TnT
wants exclusive *category lists*; TaxoGen keeps general terms on the
parent. We keep exclusive **tag→node** maps and allow a file two
homes.

None of the three evaluate MultiEURLEX, Reuters-21578, or Govdocs1.
Using `sort-sample` / MultiEURLEX as the demo is our evaluation
choice, not a claim those papers own.

---

## Where it was found

- **TnT-LLM** — Wan et al., [arXiv:2403.12173](https://arxiv.org/abs/2403.12173), KDD ’24 — generate / update (eval + issues + rewrite on the next minibatch) / review; summaries first; hierarchy = rerun Stage 2 per subgroup; no invented catch-all nodes.
- **TaxoGen** — Zhang et al., [arXiv:1812.09551](https://arxiv.org/abs/1812.09551), KDD 2018 — recursive spherical clustering; representativeness push-up; local re-embed; stop inner loop when no general terms remain.
- **Evaluation of Machine-Learning Protocols for TAR** — Cormack & Grossman, [SIGIR 2014](https://doi.org/10.1145/2600428.2609601) — CAL vs SAL/SPL; do not stop at classifier stabilization; code the next batch; one human/model pass is not gold.

---

## What `--ralp` does

1. **Summarize / tag** if `tags.json` is missing (description pass — still useful).
2. **Organize** if `regions.json` is missing (cluster + 30B name/rule).
3. **Fold singularities in code** — one-file / empty children go back to the parent (NN/g). Top-level topics stay.
4. **Audit** group-at-a-time (`--audit`).
5. **Stop without applying** if this audit’s flag rate is *higher* than the last (yield rose = last edits hurt).
6. **Apply** `wrong-parent` / `missing-parent` / `leftover-should-place` when `better_home` is a real node.
7. **Revise** any group with a wrong-parent (not a pile of three): 30B may rename, split, or dissolve.
8. Repeat from 4 until `flags-rose`, applied=0, flag rate < `stop_flag_rate`, or `max_rounds`.

`--ralp` works on **any** `--intake` folder. The CTE dump is one
intake, not the product.
