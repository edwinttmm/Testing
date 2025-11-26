#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."
python3 -m venv _pyusb_tmp
source _pyusb_tmp/bin/activate
pip install --no-input pyusb
pip wheel pyusb -w wheelhouse
PYUSB_WHEEL=$(ls wheelhouse/pyusb-*.whl | head -n 1)
deactivate
rm -rf _pyusb_tmp
if [[ -f "$PYUSB_WHEEL" ]]; then
  pip install --find-links=wheelhouse $(basename "$PYUSB_WHEEL")
else
  echo "PyUSB wheel not found" >&2
  exit 1
fi
rm -rf wheelhouse
