#!/usr/bin/env bash
# Launch the AI Opportunity Finder.
set -euo pipefail
cd "$(dirname "$0")"

# Load .env if present (optional)
if [ -f .env ]; then
  set -a; source .env; set +a
fi

exec streamlit run app.py "$@"
