# Handover review summary

**Documents in queue:** 871
**Extract failed (human must open):** 61
**Regex SSN hits:** 33
**Regex address hits:** 214

PII scan is a **suggestion / focus list**, not a verdict. Regex flags identifier-shaped
hits; the model only suggests personal leftover vs work record so you know where to look.
Work files with PII (student immunization, travel) stay on `PII-MAP.md` and are **not**
delete instructions.

## Pass 2 suggestions (human confirms)

| Suggestion | Count |
|---|---|
| delete_candidate (personal) — focus item | 0 |
| review — focus item | 0 |
| keep (work) | 7 |
| pending | 864 |

## Pass 1 tag map

| Tag | Documents |
|---|---|
| curriculum_admin | 7 |
| work_email_or_memo | 6 |
| curriculum_lesson | 1 |
| curriculum_pacing | 1 |
| student_record | 1 |

The harness never deletes files. Use these lists to focus review; confirm
`DELETE-CANDIDATES.md` yourself, then move or delete by hand if you agree.
