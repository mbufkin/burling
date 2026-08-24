# Audit plan (group-at-a-time)

Work order is the browse tree: parent, then children, then unassigned.
Fat groups (>12 files) are split into chunks. That split is a **workaround** — a later granular node is the real fix.

**Chunks:** 68
**L1 findings:** 25

## L1 graph

- `fat-branch` `budget-tracker` — Budget Tracking has 52 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `career-clusters` — Career Clusters has 64 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `classroom-management` — Classroom Management has 50 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `curriculum-and-instruction` — Curriculum & Instruction has 256 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `events-and-showcase` — Events & Showcase has 86 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `finance-and-grants` — Finance & Grants has 114 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `health-and-compliance` — Health & Compliance has 136 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `lab-results` — Lab Results & Reports has 41 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `needs-review` — Needs review has 404 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `procurement-and-vendors` — Procurement & Vendors has 104 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `professional-development` — Professional Development has 154 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `reporting-cycles` — Reporting Cycles has 49 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `school-entry-compliance` — School Entry Compliance has 75 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `session-attendance` — Session Tracking has 45 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `student-pathways-and-wbl` — Student Pathways & WBL has 153 files (≥40). Audit will chunk; consider a granular split.
- `scope-drift` `advisory-council` — 16 child files are not also on parent student-pathways-and-wbl (scope-inclusion proxy)
- `scope-drift` `agreements-dallasisd-org` — 11 child files are not also on parent procurement-and-vendors (scope-inclusion proxy)
- `scope-drift` `budget-tracker` — 23 child files are not also on parent finance-and-grants (scope-inclusion proxy)
- `scope-drift` `classroom-management` — 22 child files are not also on parent curriculum-and-instruction (scope-inclusion proxy)
- `scope-drift` `eif-pathful-training` — 10 child files are not also on parent professional-development (scope-inclusion proxy)
- `scope-drift` `middle-school-cte` — 12 child files are not also on parent student-pathways-and-wbl (scope-inclusion proxy)
- `scope-drift` `reporting-cycles` — 32 child files are not also on parent events-and-showcase (scope-inclusion proxy)
- `scope-drift` `school-entry-compliance` — 35 child files are not also on parent health-and-compliance (scope-inclusion proxy)
- `scope-drift` `session-attendance` — 38 child files are not also on parent events-and-showcase (scope-inclusion proxy)
- `unassigned` `__unassigned__` — 260 files have no region_ids

## Work order

| # | Group | Files | Chunks | Why split |
|---|---|---|---|---|
| 1 | Curriculum & Instruction (`curriculum-and-instruction`) | 41 | 4 | >12 files; split so the model can finish JSON |
| 2 | Career Clusters (`career-clusters`) | 38 | 4 | >12 files; split so the model can finish JSON |
| 3 | Classroom Management (`classroom-management`) | 37 | 4 | >12 files; split so the model can finish JSON |
| 4 | Curriculum Alignment (`curriculum-alignment`) | 20 | 2 | >12 files; split so the model can finish JSON |
| 5 | Events & Showcase (`events-and-showcase`) | 3 | 1 | fits in one call |
| 6 | Reporting Cycles (`reporting-cycles`) | 20 | 2 | >12 files; split so the model can finish JSON |
| 7 | Session Tracking (`session-attendance`) | 12 | 1 | fits in one call |
| 8 | Finance & Grants (`finance-and-grants`) | 9 | 1 | fits in one call |
| 9 | Budget Tracking (`budget-tracker`) | 50 | 5 | >12 files; split so the model can finish JSON |
| 10 | Reimbursements & Travel (`reimbursement-voucher`) | 18 | 2 | >12 files; split so the model can finish JSON |
| 11 | Health & Compliance (`health-and-compliance`) | 7 | 1 | fits in one call |
| 12 | Lab Results & Reports (`lab-results`) | 37 | 4 | >12 files; split so the model can finish JSON |
| 13 | School Entry Compliance (`school-entry-compliance`) | 17 | 2 | >12 files; split so the model can finish JSON |
| 14 | Procurement & Vendors (`procurement-and-vendors`) | 4 | 1 | fits in one call |
| 15 | District Agreements (`agreements-dallasisd-org`) | 29 | 3 | >12 files; split so the model can finish JSON |
| 16 | Quote Management (`quote-2025`) | 12 | 1 | fits in one call |
| 17 | Professional Development (`professional-development`) | 2 | 1 | fits in one call |
| 18 | EIF & Pathful Training (`eif-pathful-training`) | 17 | 2 | >12 files; split so the model can finish JSON |
| 19 | Advisory Councils (`advisory-council`) | 30 | 3 | >12 files; split so the model can finish JSON |
| 20 | Middle School CTE (`middle-school-cte`) | 5 | 1 | fits in one call |
| 21 | Needs review (`needs-review`) | 2 | 1 | fits in one call |
| 22 | Unassigned (`__unassigned__`) | 260 | 22 | >12 files; split so the model can finish JSON |
