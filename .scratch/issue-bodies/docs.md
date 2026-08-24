## Problem
docs/*.md are excellent engineering records but written for the author ("the CTE-manager dump", "the 3515-tag stitch", "gb10"). A stranger installing from README has no end-to-end path from "my folder of files" to "organized output + topic map".

## Tasks
1. Write docs/tutorial.md: one synthetic folder (reuse burling/tests/fixtures/sort-sample/), every CLI step from intake to organized tree to HTML map, with expected outputs at each step.
2. Link it as "Start here" from README.md.
3. Add a short glossary (gb10, walk, stitch, RALP, unmapped, main/sub/detail) — either in the tutorial or docs/glossary.md.
4. Audit README claims against reality: every flag shown must exist in run.py --help.

## Acceptance
- A reader with Python 3.10+ and Ollama can follow the tutorial without reading any other doc, using only committed fixtures.
