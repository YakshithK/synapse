#!/usr/bin/env bash
# Make executable: chmod +x scripts/run_local.sh
source .venv/bin/activate
# Start dashboard server
echo "Starting dashboard on http://127.0.0.1:8080 ..."
uvicorn dashboard.backend_app:app --reload &

# Give the server a moment
sleep 1

# Run example workflow
echo "Running example workflow..."
# Line 13: Update path
python3 -m synapse.cli run examples/workflows/research.yml --prompt "neural rendering"
echo "Done. Open dashboard at http://127.0.0.1:8080 to view traces."
