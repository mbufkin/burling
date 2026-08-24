#!/usr/bin/env bash
# Pass C: L1 graph checks + L2 group-at-a-time placement audit.
# Does not re-tag or restitch. Resume skips chunks with status=done.
# Best practice: one group, then its children; fat groups split at 12 files.
set -euo pipefail
cd /home/lenovo/burling
PY=/home/lenovo/burling/.venv/bin/python
CFG=/home/lenovo/cte-manager-run/config.yaml
LOG=/home/lenovo/cte-manager-run/run.log
export PYTHONUNBUFFERED=1
exec >>"$LOG" 2>&1

echo "==== AUDIT START $(date -Iseconds) ===="
curl -sS http://127.0.0.1:8080/health || echo "WARN: nemotron health failed"
"$PY" -m burling.run --config "$CFG" --audit
echo "==== AUDIT DONE $(date -Iseconds) ===="
echo "Open: /home/lenovo/cte-manager-run/output/AUDIT.md"
