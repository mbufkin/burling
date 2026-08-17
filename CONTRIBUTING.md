# Contributing

Thanks for looking. Burling is a small local-first review harness. The bar
for a change is: tests pass without a GPU, and personal files never enter git.

## Development setup

Python 3.10+ and a local clone:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Ollama is only required for pass 1 / pass 2. Regex work uses `--priors-only`.

## Tests

```bash
python -m unittest discover -s burling/tests -p "test_*.py"
python -m burling.run --priors-only --intake burling/tests/fixtures/tiny-dump
```

CI runs the same commands. Do not add a test that needs a real handover dump
or a cloud API.

## Pull requests

1. Branch from `main`.
2. Keep the diff about one thing.
3. If you change PII detection, add a unit test with **synthetic** identifiers
   (the SSA example `123-45-6789` is fine; a real SSN is not).
4. Fill in the PR template.

Please do **not** commit:

- Anything under `intake/`, `corpus/`, or `output/` except the placeholders
- `rclone.conf`, `.env`, or a filled-in `config.yaml`
- Screenshots or logs that show real names, emails, or account numbers

## Code of conduct

Participation is covered by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Security

Vulnerability reports go through [SECURITY.md](SECURITY.md), not the public
issue tracker.
