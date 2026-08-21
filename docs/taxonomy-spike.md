# Staged taxonomy spike (20 Newsgroups)

Experiment, not the workplace ship path. Tag **one layer** across the corpus,
then fold that layer, then go one layer deeper. Do not pick main/sub/detail
in a single file window.

Public Usenet articles only. Workplace CTE dumps stay on localhost llama.cpp.

## Why this exists

`--layers` asks for a 3-layer path per file, then one roll-up of mains.
A 400-file roster (filenames + child tags) made a 30B fold `hockey` on a
**mains** call. Census then hid children and showed ids+counts only.

This spike tests the opposite order: **all mains → combine → all subs
(per cabinet) → combine → details → combine**.

## CLI

```bash
# Local Lightning 30B (same 20 files, every stage)
python -m burling.run --spike --limit 20 \
  --config burling/config.gold-20news-local-spike.yaml

# NVIDIA NIM proxy (public corpus only; policy.public_corpus required)
python -m burling.run --spike --limit 20 --spike-until combine-mains \
  --config burling/config.gold-20news-nvidia-spike.yaml
```

`--spike-until` stops after a named stage. Resume skips files that already
have that layer. Output: `spike-tags.json` under `paths.output_dir`.

The NIM proxy (`127.0.0.1:8787`) holds the API key. Burling refuses the
proxy unless `policy.public_corpus` is true and the intake is not a CTE path.

## Findings (20-file slice)

Pre-combine mains were tagged per file (Ultra 550B for most; nano 30B for
the last three after a rate-limit switch). Combine then ran on **nano 30B**
with the census prompt: **main ids + counts only**.

**Ids-only combine was too hungry.** Six folds; two were fair at main
(autos+motorcycles → vehicles, macintosh+dos+windows-dos → computing).
Three mixed unlike kinds: astronomy+star-trek → space, politics+theology →
religion, cryptography+Motif GUI → security. Atheism was left beside
religion — the merge that *should* have happened.

**Ultra’s per-file mains were the better clerk.** It kept star-trek off
astronomy, politics off theology, Clipper off Motif. Combine never ran on
Ultra (the job was killed for RPM). The bad tree is nano’s fold, not Ultra’s
tags.

**Summaries change the error, they do not remove it.** Same 20 original
mains, NVIDIA nano 30B:

| Window | What happened |
|---|---|
| Ids + counts only | Six folds; unlike kinds mashed |
| Main + summary **and filename** | Model merged **file ids**. Code rejected every group |
| Summaries grouped **under** each main, no filenames | One fair fold (waco-siege → politics). Missed vehicles/computing/theology |

Local Lightning 30B, same two windows:

| Window | What happened |
|---|---|
| Ids + counts only | One fold: astronomy+star-trek → science-space (same greed) |
| Mains + summaries, no filenames | politics+waco (good); theology+biblical-interpretation (good); **autos+dos** and **cryptography+Motif** (unlike kinds) |

So: names-only over-merges by string kinship (`star-trek` looks like space).
Summaries stop some of that and introduce other false friends (a 4WD car
question and an EMM386 post both “look like tech help”). Showing filenames
makes a small model treat the roster as the merge list. **Code must coerce
merge ids onto the mains list** — the model proposes, the records office
files.

## Prior work (the known issue)

This is taxonomy induction / LLM clustering, not a new filing invention.
The failure mode is documented.

**Microsoft Research — TnT-LLM** (Wan et al., KDD 2024). Two-phase
taxonomy generation then classification, used on Bing Copilot intents
([MSR](https://www.microsoft.com/en-us/research/publication/tnt-llm-text-mining-at-scale-with-large-language-models/),
[arXiv:2403.12173](https://arxiv.org/abs/2403.12173)). The paper’s own
setup is the issue we hit: label **granularity, coverage, and consistency**
are the expensive part; a one-shot taxonomy is not enough, so they iterate
on corpus minibatches. Their taxonomy phase **sees text** (they summarize
then refine). Microsoft’s applied write-up of the same idea is top-down:
sample documents → propose roots → classify → **repeat inside each root**
([Liu, Microsoft Data Science](https://medium.com/data-science-at-microsoft/from-chaos-to-clarity-building-taxonomies-from-unstructured-text-using-large-language-models-c1303db3adb1)).
That is this spike’s stage order. What they do not solve for us: a 30B
will still merge unlike sibling names, and will still merge the wrong
identifiers if the prompt shows a file roster.

**ClusterLLM** (Zhang, Wang, Shang; UCSD; EMNLP 2023) treats combine as
*granularity*: hierarchical merge, then ask the LLM whether two clusters
are the same category using **sampled items**, not the label string
([ACL](https://aclanthology.org/2023.emnlp-main.858/)). That is the
summaries-under-main window, with a pairwise stop instead of “fold toward
12 roots.”

**Chain-of-Layer** (Zeng et al.; Notre Dame + UW; CIKM 2024) refuses a
full tree in one prompt. One layer at a time; a ranking filter drops bad
parent–child links ([arXiv:2402.07386](https://arxiv.org/abs/2402.07386)).
Same job as coerce-groups.

**GoalEx** (Wang et al., EMNLP 2023) recurses into fat clusters and puts
the parent explanation into the child prompt — “each main, then sub.”

**TaxMorph** (Golde et al., EACL 2026) makes rename/merge/split/reorder
first-class taxonomy edits.

None of these file one document into a browse tree with one home and a
closed workplace series. They cluster for search or intent. The records
office (JSON coerce, banned heads, one home) is still Burling.

## What we are not changing yet

Census combine stays **ids + counts** until a pairwise ClusterLLM-style
stop is implemented. Summaries are useful evidence; they are not a license
to pass filenames into a merge call.
