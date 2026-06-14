#!/usr/bin/env bash
set -e

# Directory of the script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=== Setup OpenCode Go Router ==="

# Create venv if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv and install requirements
echo "Activating virtual environment and installing dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn httpx

echo "======================================"
echo "Starting OpenCode Go Router on http://127.0.0.1:8080..."
echo "Press Ctrl+C to stop the server."
echo "======================================"

python router.py
