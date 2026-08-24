#!/usr/bin/env bash
# Recover unread files (OCR + zip), re-tag with the natural prompt, restitch.
# Best practice: do not re-run Pass 1/2 PII — those already finished.
# Identity stays on rel_path so an OCR recover updates the same ledger row.
set -euo pipefail
cd /home/lenovo/burling
PY=/home/lenovo/burling/.venv/bin/python
CFG=/home/lenovo/cte-manager-run/config.yaml
LOG=/home/lenovo/cte-manager-run/run.log
export PYTHONUNBUFFERED=1
exec >>"$LOG" 2>&1

echo "==== RECOVER+RETAG START $(date -Iseconds) ===="
"$PY" -c "import pymupdf, rapidocr_onnxruntime; print('ocr stack ok', pymupdf.__version__)"
curl -sS http://127.0.0.1:8080/health || echo "WARN: nemotron health failed"

echo "1/3 rebuild queue (OCR scans, unpack zips)"
"$PY" -m burling.run --config "$CFG" --intake /home/lenovo/cte-manager-intake --priors-only

echo "2/3 Pass A rich tags (force, natural prompt — not a handover story)"
"$PY" -m burling.run --config "$CFG" --tags --tags-force --resume

echo "3/3 Pass B stitch + two-way browse graph"
"$PY" -m burling.run --config "$CFG" --stitch

echo "==== DONE $(date -Iseconds) ===="
echo "Open: /home/lenovo/cte-manager-run/output/topic-map.html"
