# Burling

Two-pass local review of the CTE handover dump. Same shape as Loom’s TAR queue
([mbufkin/loom](https://github.com/mbufkin/loom) `docs/BETS.md` Bets 0, 1, 2, 6, 9):

1. **Queue** every file, one by one, resumable, cached by content hash.
2. **Pass 1** tags what the document contains (the map).
3. **Pass 2** says keep / review / delete-candidate (personal, SSN, student PII).

The harness **never deletes**. You confirm `output/DELETE-CANDIDATES.md` by hand.

All model calls go to **local Ollama**. Personal files do not leave this machine.

## Why two passes

Litigation-style Technology-Assisted Review does not deep-read for deletion on
the first look. First you classify the corpus so you can see what you were
given. Then you decide what does not belong. Regex is a **prior**, not the
verdict — except formatted SSN / Luhn-valid card numbers, which fail closed
even if the small model shrugs.

## Setup

Clone this repo, then install deps. Ollama must be running locally
(`qwen2.5-coder:7b` is the 9400 default; it fits an 8 GB GPU).

```bash
pip install -r requirements.txt
```

## Run

Point at the dump you were given (do not copy it into git):

```bash
python -m burling.run --intake "/path/to/handover"
```

Safe first smoke — inventory + regex only, no model:

```bash
python -m burling.run --intake "/path/to/handover" --priors-only
```

Resume / drip overnight (Bet 6):

```bash
python -m burling.run --pass 1 --limit 20
python -m burling.run --pass 2 --limit 20
python -m burling.run --report
```

## Outputs (`burling/output/`)

| File | Role |
|---|---|
| `ledger.json` | Source of truth. Redacted priors, tags, recommendations. |
| `queue.json` | File list + status. |
| `DOCUMENT-MAP.md` | Pass 1 tags grouped so you can see the dump. |
| `DELETE-CANDIDATES.md` | Pass 2 files to remove by hand. |
| `REVIEW-QUEUE.md` | Extract failures + model `review` + not-yet-scanned. |
| `SUMMARY.md` | Counts. |

The ledger stores **redacted** samples (`***-**-6789`), never the raw SSN.

## Best practices this encodes

- **Local only.** Non-localhost model URLs are refused.
- **One file, one call.** No shared chat history, so a 400-file run does not drift.
- **Full text, never truncate.** Long files are chunked with overlap, then merged.
- **Fail closed on SSN/card.** Code overrides a model `keep`.
- **Human deletes.** Automation that removes files will eventually delete the wrong one.
- **Do not commit the dump or the output.** Both are gitignored.

## Tests

```bash
python -m unittest burling.tests.test_priors burling.tests.test_queue
```
