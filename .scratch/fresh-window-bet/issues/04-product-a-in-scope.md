# Product A in scope

Type: grilling
Status: resolved
Blocked by:

## Question

Does “every model call” include Product A (pass 1 PII/custody tags and pass 2 leftover-vs-work), which already chunk extracted text and merge in **code**, or only Product B (tag, stitch, audit, revise)?

If Product A is in, the spec must say whether pass 1’s code merge is already the bet or whether a Lightning merge call is required.

## Recommended (research, 2026-08-20)

**A.** Product A is in scope. Pass 1 / pass 2 **calls** follow the bet (chunk-then-merge, fresh window, no handover/CTE). Merge is **code-union** of per-chunk JSON (Presidio + 800-122). A second Lightning merge (B) is extra PII use and a stuffed-context fail. Do not leave Product A out (C) — destination already said every model call.

Trail: [docs/fresh-window-bet.md](../../../docs/fresh-window-bet.md).

## Answer

**A.** Locked 2026-08-20. Product A is in. Pass 1 / pass 2 calls follow the bet. Merge is code-union of per-chunk JSON. No second Lightning merge.
