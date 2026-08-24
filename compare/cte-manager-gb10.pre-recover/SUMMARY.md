# Handover review summary

**Documents in queue:** 670
**Extract failed (human must open):** 258
**Regex SSN hits:** 20
**Regex address hits:** 136

PII scan is a **suggestion / focus list**, not a verdict. Regex flags identifier-shaped
hits; the model only suggests personal leftover vs work record so you know where to look.
Work files with PII (student immunization, travel) stay on `PII-MAP.md` and are **not**
delete instructions.

## Pass 2 suggestions (human confirms)

| Suggestion | Count |
|---|---|
| delete_candidate (personal) — focus item | 22 |
| review — focus item | 0 |
| keep (work) | 390 |
| pending | 258 |

## Pass 1 tag map

| Tag | Documents |
|---|---|
| curriculum_admin | 323 |
| work_email_or_memo | 203 |
| curriculum_lesson | 102 |
| student_record | 102 |
| curriculum_pacing | 100 |
| curriculum_assessment | 49 |
| medical | 48 |
| credentials_secrets | 18 |
| employee_hr | 15 |
| personal_photo_or_media | 13 |
| personal_correspondence | 10 |
| tax_financial | 8 |
| unknown | 2 |
| identity_document | 1 |

The harness never deletes files. Use these lists to focus review; confirm
`DELETE-CANDIDATES.md` yourself, then move or delete by hand if you agree.
