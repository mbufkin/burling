# Test corpus: what would let this harness prove itself?

**Question:** What does perfect test data for Burling look like, and how do we
build it?

**Ticket date:** 2026-08-23
**Sample:** everything here is synthetic and committed under
`burling/tests/fixtures/`. No real dump, ever (`CONTRIBUTING.md`, `AGENTS.md`).

Every claim below is traced to the source that owns it (`file.py` references),
not to a write-up.

---

## Answer

The perfect corpus is **three layers**, each answering a different question:

| Layer | Question it answers | Needs a model? | Committed? |
|---|---|---|---|
| 1. PII/severity matrix | Does regex detection fire *exactly* when it should? | No | Yes (plain text) |
| 2. Format gauntlet | Can extract handle every type we claim to? | No | Yes (+ a few built in-test) |
| 3. Organize drama | Does the clerk build a *good tree* — and stop when it shouldn't file? | Yes (local) | Yes (text + ground truth) |

---

## What the harness actually ingests (source of truth: `extract.py`)

Any corpus design must cover these buckets, because each is a separate code
path:

- **Text**: `.txt .text .md .markdown .csv .log .rst .json .xml .yml .yaml`
- **HTML**: `.html .htm`
- **PDF**: `.pdf` — pypdf first, then PyMuPDF text layer (CID-font recovery),
  then OCR raster (`ocr.py`: RapidOCR via `rapidocr_onnxruntime`, max 12 pages,
  results cached in `output/ocr-cache/`)
- **Images (OCR)**: `.png .jpg .jpeg .webp .tif .tiff`
- **Zips**: unpacked beside themselves; caps at 200 members / 80 MB per member /
  400 MB total; zip-slip paths refused (`_safe_zip_target`)
- **Queued but never read**: `.gif .svg .ico .heic .mp3 .mp4 .wav .mov .avi
  .gz .tar .7z .rar .exe .dll .msi .iso .dmg .pkg`
- **Skipped entirely**: `*_files` browser sidecars, `.js .css .map .woff
  .woff2`, root `README.md`/`.gitkeep`, dotfiles
- Quirk worth a fixture: `_norm_ext` strips spaces, so `file. pdf` extracts as
  a PDF

## What the priors can detect (source of truth: `priors.py`)

Detection classes, each needing one positive AND one negative fixture:

| Class | Fires on | Negative control |
|---|---|---|
| `ssn` | `\d{3}-\d{2}-\d{4}`; also bare 9 digits **near** an SSN keyword | 9-digit order number far from any keyword |
| `credit_card` | 13–19 digits passing Luhn (`luhn_ok`) | 16 digits failing Luhn |
| `email` | standard email regex | — |
| `phone` | 10-digit NA formats incl. `(214) 555-0142` | 7 digits |
| `dob` | `dob:` / `date of birth` / `born` **prefix** required | a bare date with no keyword |
| `address` | street regex (`St/Ave/Rd/Ln/Blvd/Dr/Ct/Way/Pkwy/Hwy`), `P.O. Box n`, `ST 12345` | city name alone |
| `sensitive_keyword` | social security, passport number, password, api key, private key, confidential… | innocuous memo |

Filename hints (`FILENAME_HINTS`) fire on names alone — a clean-body file named
`2023-W-2.pdf` must tag `tax_financial` without any model call.

Severity ladder (`prior_severity`): **high** = ssn/credit_card; **medium** =
dob/email/phone/address/sensitive_keyword; **low** = none. The andon stop
(walk_plan #37) halts filing on HIGH-unmapped, so the corpus needs at least one
high-severity file the clerk genuinely can't place.

---

## Layer 1 — PII/severity matrix (GPU-free, pure unit territory)

~15 small `.txt`/`.md` files, each isolating ONE behavior:

```
pii-ssn-formatted.txt      123-45-6789 (CONTRIBUTING-blessed example)        → ssn, high
pii-ssn-keyword-blob.txt   "SSN 447038211" (keyword window hit)              → ssn, high
pii-neg-order-number.txt   "order 447038211 shipped"                         → no ssn
pii-cc-luhn-valid.txt      4111 1111 1111 1111 (industry test PAN)           → credit_card, high
pii-cc-luhn-invalid.txt    4111 1111 1111 1112                               → nothing
pii-dob.txt                "Date of birth: 04/12/1988"                       → dob, medium
pii-neg-bare-date.txt      "meeting moved to 04/12/1988"                     → nothing
pii-phone-formats.txt      (214) 555-0142 · +1 214-555-0142 · 2145550142     → phone, medium
pii-address-street.txt     "3505 Mockingbird Lane"                           → address, medium
pii-address-po-box.txt     "P.O. Box 1234"                                   → address, medium
pii-address-state-zip.txt  "Dallas, TX 75201"                                → address, medium
pii-email-plus.txt         alex+signup@example.com                           → email, medium
pii-keywords-passwords.txt fake api_key/password lines                       → sensitive_keyword, medium
hint-filename-w2.txt       clean body, name carries the hint                 → tax_financial, high body? low body
```

Names use reserved/fake values: 555-01xx phones, `example.com`, SSN area
`000`/`900` (priors flags 9xx *on purpose* — see comment atop `SSN_FORMATTED`).

**Meta-test (the real prize):** after `build_queue` over this layer, assert the
ledger row for each file shows exactly the expected kinds + severity — AND
assert no raw identifier appears anywhere in `queue.json`/reports (the
redaction contract in `scan_text`). That single assertion is the project's
privacy promise turned into CI.

## Layer 2 — Format gauntlet

- One file per text extension (tiny, valid)
- `page.html` with nav/script noise to prove stripping works
- **PDF with text layer**: hand-written minimal one-page PDF (a valid PDF is
  ~800 bytes of fixed structure) — deterministic, committed
- **Scan-only PDF + one PNG**: render text to pixels once at generation time,
  commit the binaries; tests follow `test_ocr.py`'s lead and skip where the
  OCR engine/model isn't available
- **Zip, benign**: nested folders, a `.DS_Store`, an `__MACOSX/` entry —
  members become queue rows, archive doesn't double-count
- **Zip, hostile**: built *in-test* with `zipfile` (never commit attack
  archives): a `../zip-slip.txt` member (must be refused), a 201-member zip
  and an oversized member (must raise the documented errors)
- Unreadable dummies (`.gif .mp3 .exe` — 8 garbage bytes each) → queued,
  `extract_failed`, never parsed
- Quirks: `report. pdf` (spaced ext), `site_files/` sidecar folder, unicode
  filename, 6-deep nesting

## Layer 3 — Organize drama (what the 30B actually reads)

This is what "perfect" means for a *review* harness: the corpus must make the
organizer either visibly right or visibly wrong. Design:

- **~70–90 docs across all 13 approved mains** (`file_plan.WORKPLACE_MAINS`),
  ≥4 docs per main so real sub-folders emerge instead of singularities
  (audit folds children with `< 2 docs`)
- **Near-duplicate sibling pairs** (two vendor lists, two meeting notes) to
  exercise maintain/combine rehoming
- **One deliberately mixed drawer** (3 files that share a head word but not a
  topic) for the audit's revise path
- **One high-severity unplaceable** (an encrypted-looking key dump with no
  topical body) → trips the andon; plus **low-severity junk**
  (unsubscribe/me-too) that MUST still bin normally
- **Personal/life files** (soccer schedule, family recipe) → `personal`,
  proving the delete-later lane works
- **No-substance empties** → `unmapped` with reason
- **`labels.json` ground truth** next to the fixture: expected `main` (and
  where confident, expected `sub`) per file — so organize runs get scored
  like the 20news gold harness already does, not eyeballed

### Generation mechanics

One deterministic script, `tools/make_corpus.py` (seeded, no network):
writes Layers 1–3 as plain text, emits the two PDFs from embedded minimal-PDF
templates, renders the two OCR images, builds the benign zip. Run it once;
commit its output. Hostile zips stay in-test. Every fixture stays KB-scale so
clones stay light.

---

## Why not just use public corpora?

They're complementary, not sufficient (per `docs/ralp-loop.md`): 20 Newsgroups
scores clustering but has no PII, no PDFs, no zips, no andon cases;
GovDocs1 scores extraction but is huge and unlabeled for our mains. Only a
purpose-built layer 1–3 exercises the privacy contract, the format promises,
and the file-plan semantics this repo actually ships.

## Done when

- [x] `tools/make_corpus.py` lands; fixtures committed
- [x] Layer-1 assertions wired into `test_queue`-style unit tests, incl. the redaction meta-test
- [x] Format gauntlet green in CI (OCR portion skipping gracefully off-line)
- [x] Organize drama + `labels.json` scoring a scripted `--walk` run end-to-end
      (`burling/score_placements.py` + `test_organize_drama.py`; andon trip,
      operator resume, combine rehome, and accuracy 1.0 all asserted)
