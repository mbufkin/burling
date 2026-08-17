# Security policy

Burling reviews documents that may contain personal data. Treat every intake
folder as sensitive, even when the harness redacts samples in the ledger.

## Supported versions

| Version | Supported |
| ------- | --------- |
| `main`  | Yes       |
| older   | No        |

There are no numbered releases yet. Security fixes land on `main`.

## Reporting a vulnerability

**Do not open a public issue** for a vulnerability, a leak of personal data,
or a way to send intake text to a non-localhost model.

Use GitHub private vulnerability reporting:

https://github.com/mbufkin/burling/security/advisories/new

Include:

- What you ran (`burling` version or commit)
- What you expected vs what happened
- A **synthetic** file that reproduces it (never attach a real dump)

You should hear back within 7 days. If the report is confirmed, a fix will
target `main` and be noted in `CHANGELOG.md`.

## Design constraints (not optional)

These are fail-closed rules, not preferences:

1. **Local models only.** Non-localhost LLM URLs are refused.
2. **Never auto-delete.** The harness only writes `DELETE-CANDIDATES.md`.
3. **Redact in the ledger.** Raw SSN / card numbers must not be stored in
   `output/`.
4. **Do not commit dumps.** `intake/`, `corpus/`, and `output/` are gitignored
   except placeholders.

If a change violates one of those, it is a security bug even when tests pass.

## What this tool does not guarantee

Regex and a small local model will miss identifiers. Burling is a first-pass
map, not a de-identification product. Keep the original dump offline until a
human confirms the delete list.
