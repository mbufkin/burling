# Handover review summary

**Documents in queue:** 28
**Extract failed (human must open):** 1
**Regex SSN hits:** 0
**Regex address hits:** 7

PII scan is a **suggestion / focus list**, not a verdict. Regex flags identifier-shaped
hits; the model only suggests personal leftover vs work record so you know where to look.
Work files with PII (student immunization, travel) stay on `PII-MAP.md` and are **not**
delete instructions.

## Pass 2 suggestions (human confirms)

| Suggestion | Count |
|---|---|
| delete_candidate (personal) — focus item | 0 |
| review — focus item | 0 |
| keep (work) | 27 |
| pending | 1 |

## Pass 1 tag map

| Tag | Documents |
|---|---|
| curriculum_admin | 26 |
| work_email_or_memo | 18 |
| curriculum_pacing | 11 |
| curriculum_lesson | 10 |
| curriculum_assessment | 5 |
| student_record | 2 |

The harness never deletes files. Use these lists to focus review; confirm
`DELETE-CANDIDATES.md` yourself, then move or delete by hand if you agree.
