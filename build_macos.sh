#!/usr/bin/env bash
# Builds "PII Scrub.app" into dist/. Run on macOS only - PyInstaller cannot
# cross-compile, so the Windows .exe must be built on Windows.
set -euo pipefail
cd "$(dirname "$0")"
VENV="${VENV:-.venv}"

"$VENV/bin/python" -c "import en_core_web_lg" || {
  echo "en_core_web_lg missing: $VENV/bin/python -m spacy download en_core_web_lg" >&2
  exit 1
}
"$VENV/bin/python" -m PyInstaller --noconfirm --clean piiscrub.spec
echo "Built: $(pwd)/dist/PII Scrub.app"
