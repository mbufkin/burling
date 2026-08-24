# Audit plan (group-at-a-time)

Work order is the browse tree: parent, then children, then unassigned.
Fat groups (>12 files) are split into chunks. That split is a **workaround** — a later granular node is the real fix.

**Chunks:** 83
**L1 findings:** 32

## L1 graph

- `empty-node` `receipts-payments` — Receipts and Payments has no assigned files
- `empty-node` `session-attendance` — Session Attendance & Records has no assigned files
- `empty-node` `student-records` — Student Records & Affiliation has no assigned files
- `empty-node` `tax-documents` — Tax & Financial Documents has no assigned files
- `fat-branch` `academic-programs` — academic-programs has 196 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `career-exploration` — Career Exploration has 73 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `conference-travel` — Conference Travel & Authorization has 60 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `cte-summer-program` — CTE Summer Programs has 153 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `curriculum` — Curriculum & Materials has 58 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `events-and-conferences` — events-and-conferences has 290 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `financial-administration` — financial-administration has 215 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `health-compliance` — health-compliance has 272 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `industry-certifications` — Industry Certifications has 40 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `needs-review` — Needs review has 773 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `procurement-compliance` — Procurement & Vendor Compliance has 272 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `professional-development` — Professional Development has 166 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `program-planning` — Program Planning & Planning has 65 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `purchasing-operations` — Purchasing Operations has 77 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `student-services` — student-services has 180 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `summer-pd` — Summer Professional Development has 103 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `tb-screening` — Tuberculosis Screening has 50 files (≥40). Audit will chunk; consider a granular split.
- `fat-branch` `workforce-pathways` — Workforce Development & Career Pathways has 271 files (≥40). Audit will chunk; consider a granular split.
- `scope-drift` `career-exploration` — 46 child files are not also on parent workforce-pathways (scope-inclusion proxy)
- `scope-drift` `conference-travel` — 29 child files are not also on parent events-and-conferences (scope-inclusion proxy)
- `scope-drift` `cte-summer-program` — 122 child files are not also on parent professional-development (scope-inclusion proxy)
- `scope-drift` `ctso-activities` — 3 child files are not also on parent events-and-conferences (scope-inclusion proxy)
- `scope-drift` `curriculum` — 41 child files are not also on parent academic-programs (scope-inclusion proxy)
- `scope-drift` `industry-certifications` — 14 child files are not also on parent workforce-pathways (scope-inclusion proxy)
- `scope-drift` `program-planning` — 32 child files are not also on parent academic-programs (scope-inclusion proxy)
- `scope-drift` `purchasing-operations` — 21 child files are not also on parent procurement-compliance (scope-inclusion proxy)
- `scope-drift` `summer-pd` — 69 child files are not also on parent professional-development (scope-inclusion proxy)
- `unassigned` `__unassigned__` — 62 files have no region_ids

## Work order

| # | Group | Files | Chunks | Why split |
|---|---|---|---|---|
| 1 | academic-programs (`academic-programs`) | 60 | 5 | >12 files; split so the model can finish JSON |
| 2 | Curriculum & Materials (`curriculum`) | 15 | 2 | >12 files; split so the model can finish JSON |
| 3 | Program Planning & Planning (`program-planning`) | 32 | 3 | >12 files; split so the model can finish JSON |
| 4 | events-and-conferences (`events-and-conferences`) | 91 | 8 | >12 files; split so the model can finish JSON |
| 5 | Conference Travel & Authorization (`conference-travel`) | 59 | 5 | >12 files; split so the model can finish JSON |
| 6 | CTSO Activities & Fundraising (`ctso-activities`) | 8 | 1 | fits in one call |
| 7 | financial-administration (`financial-administration`) | 86 | 8 | >12 files; split so the model can finish JSON |
| 8 | health-compliance (`health-compliance`) | 41 | 4 | >12 files; split so the model can finish JSON |
| 9 | Immunization Records (`immunization`) | 12 | 1 | fits in one call |
| 10 | Lab Results & Medical Testing (`lab-results`) | 3 | 1 | fits in one call |
| 11 | Tuberculosis Screening (`tb-screening`) | 47 | 4 | >12 files; split so the model can finish JSON |
| 12 | Procurement & Vendor Compliance (`procurement-compliance`) | 15 | 2 | >12 files; split so the model can finish JSON |
| 13 | Purchasing Operations (`purchasing-operations`) | 48 | 4 | >12 files; split so the model can finish JSON |
| 14 | Vendor Approval & Compliance (`vendor-management`) | 15 | 2 | >12 files; split so the model can finish JSON |
| 15 | Professional Development (`professional-development`) | 18 | 2 | >12 files; split so the model can finish JSON |
| 16 | CTE Summer Programs (`cte-summer-program`) | 129 | 11 | >12 files; split so the model can finish JSON |
| 17 | Summer Professional Development (`summer-pd`) | 21 | 2 | >12 files; split so the model can finish JSON |
| 18 | student-services (`student-services`) | 4 | 1 | fits in one call |
| 19 | Workforce Development & Career Pathways (`workforce-pathways`) | 4 | 1 | fits in one call |
| 20 | Career Exploration (`career-exploration`) | 73 | 7 | >12 files; split so the model can finish JSON |
| 21 | Industry Certifications (`industry-certifications`) | 20 | 2 | >12 files; split so the model can finish JSON |
| 22 | Needs review (`needs-review`) | 8 | 1 | fits in one call |
| 23 | Unassigned (`__unassigned__`) | 62 | 6 | >12 files; split so the model can finish JSON |
