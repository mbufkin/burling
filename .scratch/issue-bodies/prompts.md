## Problem
classify_map.py _system_prompt hardcodes "Dallas ISD CTE working documents" while --ralp advertises "Works on any --intake folder" (docs/ralp-loop.md: corpus-agnostic, "no district seed labels"). The domain bleed contradicts the project's own spec and limits OSS usefulness.

## Tasks
1. Move domain-specific prompt text (audience description, handoff_note framing) into config.yaml keys with generic defaults.
2. classify_map.py reads the prompt fragments from cfg; no district/school references remain in code.
3. Keep the existing governed-vocabulary mechanism unchanged — only the prose becomes configurable.

## Acceptance
- grep -ri "dallas\|disd\|cte" burling/*.py returns no hits outside tests/fixtures and docs/.
- Existing classify/map tests pass with a config that supplies equivalent fragment text.
