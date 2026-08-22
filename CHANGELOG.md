# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-08-22

### Added

- Default `--intake` path is the handover clerk: extract → pass 1 → pass 2
  leftover judge → `--walk` organize (one home on the locked workplace
  series). Maintain combines fat mixed drawers after a letter is home.
- Walk file list prefers ledger, then queue, then `tags.json`, then intake.
- Combine log stamps `from` / `into` / `merge` / `reasoning` on each fold.
- GPU-free tests for maintain coerce/rehome, stubbed `run_walk_plan`, and
  the default run calling walk instead of `map.yml`.
- Fail-closed extract for password-locked PDFs so one Drive `(SECURED)` file
  cannot stall a run. Filename-only stub when the body cannot be read.

### Changed

- CI runs unit tests on Python 3.10 and 3.12.
- README describes the clerk, not map.yml-first review.

### Experiments (not the default run)

- Staged taxonomy spike (`--spike`) on public 20 Newsgroups.
  Findings: `docs/taxonomy-spike.md`.
- `--layers`, `--census`, `--clerk`, `--ralp`, `--map` remain available.
- NVIDIA NIM proxy allowed only with `policy.public_corpus` (20news).
  Workplace intake is refused.

## [0.1.0] - 2026-08-17

### Added

- Two-pass local review harness (queue → tag → keep/review/delete-candidate).
- Deterministic PII priors (formatted SSN, Luhn cards) with redacted ledger samples.
- Local-only Ollama client; non-localhost model URLs are refused.
- Synthetic `tiny-dump` fixture and GitHub Actions CI.

[0.2.0]: https://github.com/mbufkin/burling/releases/tag/v0.2.0
[0.1.0]: https://github.com/mbufkin/burling/releases/tag/v0.1.0
