# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-17

### Added

- Two-pass local review harness (queue → tag → keep/review/delete-candidate).
- Deterministic PII priors (formatted SSN, Luhn cards) with redacted ledger samples.
- Local-only Ollama client; non-localhost model URLs are refused.
- Synthetic `tiny-dump` fixture and GitHub Actions CI.

[0.1.0]: https://github.com/mbufkin/burling/releases/tag/v0.1.0
