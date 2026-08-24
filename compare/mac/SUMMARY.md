# Handover review summary

**Documents in queue:** 28
**Extract failed (human must open):** 1
**Regex SSN hits:** 0
**Regex address hits:** 7

Python tagged PII. The model only decided personal leftover vs work record.
Work files with PII (student immunization, travel) stay on `PII-MAP.md` but are not delete candidates.

## Pass 2 recommendations

| Recommendation | Count |
|---|---|
| delete_candidate (personal) | 0 |
| review | 0 |
| keep (work) | 27 |
| pending | 1 |

## Pass 1 tag map

| Tag | Documents |
|---|---|
| curriculum_admin | 27 |
| work_email_or_memo | 13 |
| curriculum_lesson | 8 |
| curriculum_pacing | 6 |
| student_record | 5 |
| curriculum_assessment | 4 |
| tax_financial | 1 |
| unknown | 1 |

Nothing in this folder is deleted by the harness. Confirm `DELETE-CANDIDATES.md`
yourself, then move or delete those files by hand.
