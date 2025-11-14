# Synapse

**Local runtime + observability for multi-agent systems**

This package provides a minimalist CLI for orchestrating and tracing agent workflows, designed for rapid prototyping and research.

## Features

- Runs YAML-defined multi-agent workflows locally
- Captures traces in a local SQLite DB (`synapse_traces.db`)
- Simple dashboard for visualizing agent nodes and interactions

## Quickstart

```
pip install synapse
synapse --help  # list CLI commands
```

### Development

1. Clone the repo:
   ```
   git clone https://github.com/YakshithK/synapse.git
   cd synapse
   ```

2. Create and activate a Python virtual environment:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Run locally:
   ```
   ./scripts/run_local.sh
   ```
   Then navigate to [http://127.0.0.1:8080](http://127.0.0.1:8080/) to view traces and nodes.

## Usage

See [examples](./examples) for YAML workflows and [ARCHITECTURE.md](./ARCHITECTURE.md) for design details.

## License

See [LICENSE](./LICENSE).