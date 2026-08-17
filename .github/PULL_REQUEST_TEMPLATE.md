## Summary

What changed, and why.

## Test plan

- [ ] `python -m unittest discover -s burling/tests -p "test_*.py"`
- [ ] `python -m burling.run --priors-only --intake burling/tests/fixtures/tiny-dump`
- [ ] No real dump, `config.yaml`, or `rclone.conf` in this PR
