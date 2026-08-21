# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Staged taxonomy spike (`--spike`): main → combine → sub → detail → review
  on public 20 Newsgroups text. Findings and citations (TnT-LLM / ClusterLLM /
  Chain-of-Layer) are in `docs/taxonomy-spike.md`.
- Layered file plan, census combine, and walk organize CLIs (`--layers`,
  `--census`, `--walk`). Spec: `docs/file-plan-layers.md`.
- Fail-closed extract for password-locked PDFs so one Drive `(SECURED)` file
  cannot stall a run. Filename-only stub when the body cannot be read.
- NVIDIA NIM proxy allowed only with `policy.public_corpus` (20news). Workplace
  intake is refused.

## [0.1.0] - 2026-08-17

### Added

- Two-pass local review harness (queue → tag → keep/review/delete-candidate).
- Deterministic PII priors (formatted SSN, Luhn cards) with redacted ledger samples.
- Local-only Ollama client; non-localhost model URLs are refused.
- Synthetic `tiny-dump` fixture and GitHub Actions CI.

[0.1.0]: https://github.com/mbufkin/burling/releases/tag/v0.1.0
