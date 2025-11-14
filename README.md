# Synapse

**Kubernetes-like orchestration system for AI agents**

[![PyPI version](https://badge.fury.io/py/synapse-ai.svg)](https://badge.fury.io/py/synapse-ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/pypi/pyversions/synapse-ai.svg)](https://pypi.org/project/synapse-ai/)

Synapse is a powerful framework for orchestrating AI agents with Kubernetes-like semantics. It provides a simple YAML-based workflow definition and a rich CLI for managing agent-based applications.

## Features

- 🚀 **Kubernetes-inspired** agent orchestration
- 📊 **Built-in observability** with a web dashboard
- ⚡ **Fast execution** with parallel agent processing
- 🔄 **Dependency management** between agents
- 📝 **YAML-based** workflow definitions
- 🔍 **Tracing and logging** for debugging
- 🎨 **Rich CLI** with beautiful output

## Installation

Install from PyPI:

```bash
pip install agent-synapse
```

## Quick Start

1. Create a workflow file `my_workflow.yaml`:

```yaml
name: Research Workflow
schema_version: "2.0"

description: >
  A sample workflow that demonstrates Synapse's capabilities
  for orchestrating AI agents in a research pipeline.

agents:
  - name: researcher
    description: Researches a given topic
    model: gpt-4
    run: research_agent.py
    inputs:
      - topic: str
    outputs:
      - research_summary: str

  - name: writer
    description: Writes a blog post based on research
    model: gpt-4
    run: writer_agent.py
    depends_on: [researcher]
    inputs:
      - research: !ref researcher.outputs.research_summary
    outputs:
      - blog_post: str
```

2. Run the workflow:

```bash
synapse run my_workflow.yaml --prompt "neural rendering"
```

3. View the dashboard (optional):

```bash
synapse serve
# Open http://localhost:8080 in your browser
```

## Documentation

For detailed documentation, please visit the [Synapse Documentation](https://github.com/YakshithK/synapse#readme).

### Key Concepts

- **Agents**: Independent units of work that process inputs and produce outputs
- **Workflows**: YAML files that define the agent graph and their dependencies
- **Traces**: Detailed execution logs stored in `synapse_traces.db`
- **Dashboard**: Web UI for monitoring and debugging agent executions

## Examples

Check out the [examples](./examples) directory for sample workflows and agent implementations.

## Development

1. Clone the repository:

```bash
git clone https://github.com/YakshithK/synapse.git
cd synapse
```

2. Set up a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

3. Run tests:

```bash
pytest
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For support, please [open an issue](https://github.com/YakshithK/synapse/issues) on GitHub.