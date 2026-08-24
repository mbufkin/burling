# RALP log

Organize → audit → apply → revise mixed groups → audit again.
The 30B writes decision rules and splits. Code applies and stops.

**Stop:** `flags-rose`
**Rounds:** 3

| Round | Flags | Flag rate | Applied | Skipped | Revise |
|---|---|---|---|---|---|
| 1 | 7 | 39% | 7 | 0 | agriculture, environment, sports-facility, sports-league, transport-rail |
| 2 | 5 | 28% | 5 | 0 | agriculture, agriculture-environment, agriculture-soil-irrigation, rail-operations, waste-management |
| 3 | 7 | 39% | 0 | 0 | — |

## Notes

- R1: agriculture: split → 2 children
- R1: environment: split → 3 children
- R1: sports-facility: dissolved → sports (dropped 0 children)
- R1: sports-league: split → 2 children
- R1: transport-rail: split → 2 children
- R2: air-quality: folded 1 file(s) → environment
- R2: waste-management: folded 1 file(s) → environment
- R2: wetland-ecology: folded 1 file(s) → environment
- R2: sports-league-standings: folded 1 file(s) → sports-league
- R2: sports-league-scheduling: folded 1 file(s) → sports-league
- R2: rail-operations: folded 1 file(s) → transport-rail
- R2: harbor-operations: folded 1 file(s) → transport-rail
- R2: agriculture: dissolved → needs-review (dropped 2 children)
- R2: agriculture-environment: missing
- R2: agriculture-soil-irrigation: missing
- R2: rail-operations: missing
- R2: waste-management: missing
- R3: skipped apply: flag rate rose 28% → 39%
