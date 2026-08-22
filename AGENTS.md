# Agent notes

This repository reviews folders that may contain personal data.

- Never read, copy, or commit `intake/`, `corpus/`, or `output/` except the
  gitignored placeholders and `burling/tests/fixtures/tiny-dump/`.
- Never point the model client at a non-localhost URL.
- Never add an auto-delete path.
- Run `python -m unittest discover -s burling/tests -p "test_*.py"` after
  changing priors, queue, or reports.
- Everyday organize is `--walk` (locked series, then reuse/invent; maintain later). `--layers` is the previous test: `docs/file-plan-layers.md`.
- Staged taxonomy spike (main → combine → sub → detail) and why names-only over-merges: `docs/taxonomy-spike.md`. NVIDIA NIM proxy is 20news / `policy.public_corpus` only.
