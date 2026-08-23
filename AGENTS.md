# Agent notes

This repository reviews folders that may contain personal data.

- Never read, copy, or commit `intake/`, `corpus/`, or `output/` except the
  gitignored placeholders and `burling/tests/fixtures/tiny-dump/`.
- Never point the model client at a non-localhost URL.
- Never add an auto-delete path.
- Run `python -m unittest discover -s burling/tests -p "test_*.py"` after
  changing priors, queue, or reports.
- Walk organize (locked main, then reuse / invent / combine; combine rehomes): `docs/file-plan-layers.md`.
