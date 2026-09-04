#!/usr/bin/env sh
set -eu

python -m pip install --upgrade pip pip-audit
python -m pip_audit -r "$(dirname "$0")/../requirements.txt"
