#!/usr/bin/env bash
# Build a standalone binary (and macOS .app) of lifegen-save-editor.
#
# Prereq: run inside a venv that has the dev dependencies installed:
#     python3 -m venv .venv
#     .venv/bin/pip install -r requirements.txt -r packaging/requirements-build.txt
#
# Output:
#     dist/lifegen-save-editor/             — portable directory
#     dist/lifegen-save-editor.app          — macOS app bundle (macOS only)
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/pyinstaller" ]; then
    echo "PyInstaller missing in .venv. Install with:"
    echo "  .venv/bin/pip install -r packaging/requirements-build.txt"
    exit 1
fi

rm -rf build dist
.venv/bin/pyinstaller --clean --noconfirm packaging/lifegen-save-editor.spec
echo
echo "Built:"
ls -la dist/
