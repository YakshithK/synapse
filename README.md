# Synapse - Local runtime + observability for multi-agent systems (MVP)

Quickstart:
1. create venv and install deps (see repo)
2. run `./scripts/run_local.sh`
3. open http://127.0.0.1:8080 to view traces and nodes.

This is a minimal MVP: runtime (CLI) runs YAML workflows; traces are stored in `synapse_traces.db`; dashboard reads those traces.
