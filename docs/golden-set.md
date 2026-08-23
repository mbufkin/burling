# Public golden set — what we can actually run against

**Question:** Which public, pre-sorted document set do we have on disk
(or can fetch) so we can flatten gold folders and score whether Burling
puts files back?

**Ticket date:** 2026-08-20

This is a research note. Claims go back to the owning corpus page or
paper. Sibling: [fresh-window-bet.md](fresh-window-bet.md).

---

## Answer

**Locked gold (Layer 2) is still English MultiEURLEX** — Chalkidis,
Fergadiotis, Androutsopoulos, EMNLP 2021. Real EUROVOC tree
(topic → subtopic), official Publications Office labels, CC-BY-4.0,
no student/HR PII.

It is **not on disk yet**. The only official file is
`multi_eurlex.tar.gz` (**2.8 GB**, md5 `9f7beeff307418146356cd259b622a2c`)
on Zenodo `10.5281/zenodo.5363165`. The Hugging Face `en` config still
downloads that same tarball, then keeps English. There is no smaller
English-only archive.

**Available tonight (public folder tree):** **20 Newsgroups, by-date
test split** (Rennie’s cut of Lang’s collection). Each file already
lives in a gold folder (`rec.sport.hockey`). We sample 20 docs × 20
groups = **400 files**, flatten to hashed inbox names, keep
`gold.json`. That is a real public sort benchmark. It is **shallower**
than EUROVOC (topic.subtopic in the newsgroup name). It is **not** a
substitute for MultiEURLEX on the scoreboard.

Fetcher (gitignored output under `.data/`):

```bash
cd /Users/michaelbufkin/Desktop/burling-v2
python -m burling.fetch_gold --corpus 20newsgroups
# later, after `pip install datasets` and ~3 GB free pull:
python -m burling.fetch_gold --corpus multieurlex
```

Do **not** use `nlpaueb/multi_eurlex` (2022 5-language cut).
Do **not** use Reuters-21578 as the tree (flat 135 TOPICS, research-only
Reuters copyright). Do **not** use Enron or the CTE dump.

---

## Why this answer

We already locked MultiEURLEX for Layer 2. Re-checking the owning
pages tonight did not change that: Zenodo v1.0.0 is one 2.8 GB tar;
HF `coastalcph/multi_eurlex` `en` lists `download_size` ≈ 2.77 GB.
EURLEX57K is the same family but lacks the reconstructed L1/L2/L3
sets the 2021 paper added.

20 Newsgroups is the only **ready-made public folder tree** that
downloads in minutes. The by-date test split is the usual eval cut
(homepage lists `20news-bydate.tar.gz`). Gold path =
`{comp|rec|sci|talk|…}/{leaf}`. Headers are stripped so Usenet
From/email is less of a Product A mess. TEST.md still says: do not
treat 20 Newsgroups as the **headline** gold. Use it so we have a
public inbox **now**; score MultiEURLEX when the 2.8 GB lands.

---

## Where it was found

- **MultiEURLEX Zenodo v1.0.0** — https://zenodo.org/records/5363165 —
  `multi_eurlex.tar.gz` 2.8 GB; md5 `9f7beeff307418146356cd259b622a2c`;
  DOI 10.5281/zenodo.5363165
- **HF 2021 card** — https://huggingface.co/datasets/coastalcph/multi_eurlex
  — `load_dataset("coastalcph/multi_eurlex", "en")`; body license
  CC-BY-4.0 / Decision 2011/833/EU; `en` still pulls the full tar
- **EMNLP 2021 paper** — https://aclanthology.org/2021.emnlp-main.559/
  / https://arxiv.org/abs/2109.00904 — 65k × 23, EUROVOC L1–L3 gold,
  chronological English 55k/5k/5k
- **20 Newsgroups homepage** — https://qwone.com/~jason/20Newsgroups/
  — `20news-bydate.tar.gz`; train/test by date; 20 gold folders
- **sklearn Figshare mirror** — https://ndownloader.figshare.com/files/5975967
  — SHA256 `8f1b2514ca22a5ade8fbb9cfa5727df95fa587f4c87b786e15c759fa66d95610`
  (qwone.com timed out from this machine; this is the file sklearn ships)

---

## Conflicts

- HF YAML `cc-by-sa-4.0` vs card body **CC-BY-4.0**. Follow the EUR-Lex
  notice in the body.
- `nlpaueb/multi_eurlex` is not the 2021 gold.
- 20 Newsgroups can include poster names/emails in headers — we strip
  headers; it is still Usenet, not office records.
