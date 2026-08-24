# Audit plan (group-at-a-time)

Work order is the browse tree: parent, then children, then unassigned.
Fat groups (>12 files) are split into chunks. That split is a **workaround** — a later granular node is the real fix.

**Chunks:** 8
**L1 findings:** 1

## L1 graph

- `unassigned` `__unassigned__` — 3 files have no region_ids

## Work order

| # | Group | Files | Chunks | Why split |
|---|---|---|---|---|
| 1 | Environment & Ecology (`environment`) | 3 | 1 | fits in one call |
| 2 | Health & Wellness (`health`) | 3 | 1 | fits in one call |
| 3 | Personal Finance (`finance`) | 3 | 1 | fits in one call |
| 4 | Sports & Recreation (`sports`) | 2 | 1 | fits in one call |
| 5 | League & Tournament Operations (`sports-league`) | 2 | 1 | fits in one call |
| 6 | Bike Infrastructure (`transport-bike`) | 1 | 1 | fits in one call |
| 7 | Rail & Harbor Operations (`transport-rail`) | 1 | 1 | fits in one call |
| 8 | Unassigned (`__unassigned__`) | 3 | 1 | fits in one call |
