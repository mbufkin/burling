# One file per call

Type: grilling
Status: resolved
Blocked by:

## Question

Audit today sends up to 12 files as path + 280-character summaries. If every model call must see extracted text, is an audit/revise call **exactly one file** (group walk is only the work order), or still a small group with each file’s text attached?

This also decides whether “12 files / chunk” survives in the spec.

## Recommended (research, 2026-08-20)

**A.** Exactly one file per audit/revise call. Full extracted text, chunk-then-merge if long, fresh window. Group walk is only the work order. 12-file blurbs go. 12 full texts in one window (B) is the Lost-in-the-Middle failure. Blurb batches (C) are how Agriculture dissolved.

Trail: [docs/fresh-window-bet.md](../../../docs/fresh-window-bet.md).

## Answer

**A.** Locked 2026-08-20. Audit and revise: exactly one file, full extracted text, chunk-then-merge if long, fresh window. Group walk is only the work order. 12-file batches do not survive.
