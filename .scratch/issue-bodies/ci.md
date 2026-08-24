## Problem
CI runs unit tests and CodeQL but has no lint, type-check, or formatting gate — table stakes for a top-tier Python project.

## Tasks
1. Add ruff (lint + format check) and mypy config to pyproject.toml. Start lenient (non-strict mypy) so existing code passes without mass rewrites.
2. Add a CI job (or steps in the existing test job) running both.
3. Fix or noqa the violations it surfaces — prefer fixing.
4. Add [dev] extras entries for both tools.

## Acceptance
- ruff check . and mypy burling pass locally and in CI on a clean checkout.
- CONTRIBUTING.md "Tests" section mentions the new commands.

Depends on #49 landing first.
