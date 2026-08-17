# Prior art — Burling is not a new idea

We paused before scaling the Drive scan. The two-axis design (Python finds PII, model decides personal vs work) already exists in several mature systems. Steal from them instead of inventing.

## What already exists

### 1. eDiscovery TAR (Grossman & Cormack, 2011)

Loom already cited this (`docs/BETS.md` Bet 9). Lawyers do **not** ask one question. They code **relevance** and **privilege** as separate passes. A document can be relevant *and* privileged.

Our analogue:

| TAR | Burling |
|---|---|
| Contains the topic? | Contains PII? (Python) |
| Privileged / withhold? | Personal leftover vs work record? (model) |
| Human QC on a sample | You confirm delete candidates |

Grossman & Cormack also showed exhaustive human review is **not** a gold standard. Measure recall/precision on a coded sample. Do not assume the 7B is right because JSON parsed.

TAR 1.0 trains on a **seed set** of human-coded docs, then ranks the rest. We have not done that. We are asking the 7B to invent the policy from a prompt. That is weaker than “here are 20 files you already judged.”

### 2. Microsoft Purview: SITs + trainable classifiers

Enterprise DLP already splits the same two jobs:

- **Sensitive Information Types** = regex / checksum / keywords (SSN, card, bank).
- **Trainable classifiers** = “this *looks like* a tax return / contract / source code.”

Purview’s own guidance: use **both**. A spreadsheet with a 16-digit SKU is not a financial statement. A financial training manual is not a W-2. Label only when **type AND identifier** match.

That is exactly: immunization + SSN → work, keep, still on the PII map. TurboTax + SSN → personal, delete-candidate.

### 3. Microsoft Presidio (open-source PII)

The standard Python PII engine. Regex + NER + **checksum** + **context words** + confidence scores.

SSN lessons they already paid for:

- Invalidate area `000`, `666`, `9xx` (SSA never issued).
- Drop known sample SSNs (`123-45-6789`, `078-05-1120`) so tests and ads do not flood the queue.
- Boost confidence when nearby words are `SSN`, `social security`, `TIN`.
- Regex-only SSN has noisy false positives; Presidio’s FAQ says tune thresholds, do not treat every 9-digit blob as real.

We rolled a thinner regex. Fine for a prototype. For 1,100 files, borrow Presidio’s US_SSN recognizer rather than keep inventing.

Presidio also has **image** redaction. It does not read pixels itself — **OCR first**, then regex. Scanned W-2s with no text layer are invisible to us today.

### 4. Google Sensitive Data Protection (DLP)

Same split: classify infoTypes, then redact. For images/PDFs it runs **OCR before** classification. Storage scans write findings to a table (our ledger). Likelihood scores, not booleans.

### 5. FERPA / school data class

Student immunization, TB, transcripts **with SSN** are still **education records**. The correct action is **keep and protect**, not delete. Deleting them because they contain PII would be the wrong compliance move. District travel with DOB is work HR, not a leftover tax packet.

WNC and similar school classification guides put student SSN, DOB, and even parent W-2s (financial aid) under FERPA restricted data — retain under policy, do not treat as “personal junk.”

### 6. Cloakbox (this owner’s other repo)

Fail-closed. Do not let the model roam raw identifiers. Tokenize / redact in the ledger. Detection miss = leak if you skip the deterministic layer. We already follow that: regex first, redacted samples only.

### 7. Local “shoebox” classifiers

Paperless-ngx + Tesseract + a local Qwen is a common 2025–2026 hobby pipeline for tax/medical/personal *type* labels. They classify **form type**. They usually do **not** ask “district work vs employee’s private life.” That second question is our actual gap — and Purview’s classifier layer, not Presidio’s.

## What to steal (priority order)

1. **Two labels, never one.** `pii_kinds[]` from Python. `custody: personal | work | unclear` from the model. Delete only if custody=personal. PII map lists both.
2. **Do not model every file.** TAR culls. Python on all ~1,151. Model only: PII hits, tax/mortgage filenames, extract failures, and a random sample for QC. Overnight 7B on every PDF is the tokens-are-expensive instinct inverted into waste.
3. **Presidio SSN rules** (invalid areas, sample SSNs, context boost) instead of homemade regex only.
4. **OCR on image PDFs** (ocrmypdf / Tesseract) before regex. Tax scans are the miss mode we should fear most.
5. **Document fingerprints** for W-2 / 1040 / 1099 templates (Purview). Filename + layout beat a 7B guessing a scan.
6. **Seed set + metrics.** You code 20–30 files (personal vs work). Report precision/recall. Grossman: if you do not measure, you are guessing.
7. **FERPA keep-path.** Student health / immunization / TB stay `keep` even with SSN; they still appear on `PII-MAP.md` so they are not lost in the dump.
8. **Goldens.** Loom’s intake goldens: synthetic W-2, synthetic immunization roster, travel form, clean lesson plan. CI the policy, not just JSON parse.

## What not to copy

- Cloud DLP / Purview as the scanner — this dump has student health and tax. Local only.
- “Has SSN ⇒ delete.” That is the mistake Presidio/Purview exist to prevent, and it would eat FERPA records.
- Trusting 7B JSON parse as proof of correctness. Parse ≠ custody.
