# Contributing

Thanks for looking. Burling is a local-first handover clerk. The bar for a
change is: tests pass without a GPU, and personal files never enter git.

## Development setup

Python 3.10+ and a local clone:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

A local LLM is only required for pass 1 / pass 2 / walk. Regex work uses
`--priors-only`. Do not add a test that needs Ollama, llama.cpp, or a real
handover dump.

## Tests

Same two commands as CI:

```bash
python -m unittest discover -s burling/tests -p "test_*.py"
python -m burling.run --priors-only --intake burling/tests/fixtures/tiny-dump
```

Walk and maintain tests inject stub choosers. If you change coerce, rehome,
or the default `--intake` path, extend those tests.

## Pull requests

1. Branch from `main`.
2. Keep the diff about one thing.
3. If you change PII detection, add a unit test with **synthetic** identifiers
   (the SSA example `123-45-6789` is fine; a real SSN is not).
4. Fill in the PR template.

Please do **not** commit:

- Anything under `intake/`, `corpus/`, or `output/` except the placeholders
- `rclone.conf`, `.env`, or a filled-in `config.yaml`
- Machine YAMLs with local model paths (`config.cte-manager-*.yaml`, gb10)
- Screenshots or logs that show real names, emails, or account numbers

## Code of conduct

Participation is covered by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Security

Vulnerability reports go through [SECURITY.md](SECURITY.md), not the public
issue tracker.
