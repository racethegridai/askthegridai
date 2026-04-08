#!/usr/bin/env bash
# PitWall AI — start the backend
# Run this from the pitwall-backend/ directory

set -e
cd "$(dirname "$0")"

# Create virtualenv on first run
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python -m venv .venv
fi

# Activate
source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate

# Install / upgrade dependencies
pip install -q -r requirements.txt

echo ""
echo "======================================"
echo "  PitWall AI Backend"
echo "  http://localhost:8001"
echo "  SSE stream: http://localhost:8001/events"
echo "  State:      http://localhost:8001/api/state"
echo "======================================"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8001 --reload
