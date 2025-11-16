# Synapse Flow Summary

## What is Synapse?

Synapse is a **Kubernetes-like orchestration system for AI agents**. It provides:
- **Declarative workflows** via YAML definitions
- **Agent lifecycle management** (instantiation, execution, retries)
- **Observability** through SQLite-backed tracing
- **Dashboard** for real-time monitoring

---

## Complete Flow: From Command to Completion

### 1. **User Command**
```bash
python -m synapse.cli run examples/research.yml --prompt "neural rendering"
```

### 2. **CLI Processing** (`synapse/cli.py`)
- Validates workflow file exists
- Creates `Orchestrator(workflow_path)`
- Calls `orch.run(prompt)`
- Displays results

### 3. **Orchestrator Initialization** (`synapse/orchestrator.py`)
- Loads YAML workflow via `yaml_loader.load_workflow()`
- Creates `TraceStore()` instance
- Initializes SQLite database (`synapse_traces.db`)
- Generates unique `run_id` (UUID)
- Records run in `runs` table

### 4. **Agent Instantiation** (`synapse/orchestrator.py`)
- Parses workflow["nodes"]
- For each node:
  - Extracts: `name`, `impl`, `model`, `retries`
  - Resolves `impl` → function via `_resolve_impl()`
  - Creates `Agent(name, func, model, retries)`
  - Stores in `self.agents[name]`

### 5. **Workflow Execution Loop** (`synapse/orchestrator.py`)
- Initializes context: `{"input": prompt}`
- Sets current node: `workflow["start"]`
- **WHILE current is not None:**
  - Records context snapshot (version++)
  - Gets agent: `self.agents[current]`
  - Executes agent: `agent.run(context, tracer)`
  - Updates context: `context["last_output"] = out`
  - Moves to next node: `current = node["next"]`
- Records final context snapshot
- Returns: `{"run_id": ..., "final_context": ...}`

### 6. **Agent Execution** (`synapse/agent.py`)
- **WHILE attempt <= retries:**
  - **TRY:**
    - Calls `self.func(context)`
    - Records success in `tracer.record_node()`
    - Returns output
  - **EXCEPT Exception:**
    - Records error in `tracer.record_error()`
    - Stores exception: `last_exc = e`
    - Backoff: `sleep(min(1 * attempt, 3))`
    - Retries (if attempts left)
- **If retries exhausted:** RAISE last_exc

### 7. **Integration Functions** (`synapse/integrations.py`)
- `builtin_research(context)` → Returns `{"papers": [...], "meta": {...}}`
- `builtin_summarize(context)` → Returns `{"summary": "..."}`
- `echo_agent(context)` → Returns `{"echo": "..."}`

### 8. **Tracing** (`synapse/trace.py`)
- Records runs in `runs` table
- Records nodes in `nodes` table (success/error)
- Records contexts in `contexts` table (version snapshots)
- All stored in SQLite database

### 9. **Dashboard** (`dashboard/backend_app.py`)
- FastAPI server on port 8080
- REST API endpoints:
  - `GET /api/runs` → List all runs
  - `GET /api/nodes/{run_id}` → Get nodes for a run
  - `GET /api/contexts/{run_id}` → Get context versions for a run
- Frontend (`dashboard/templates/index.html`):
  - Displays runs, nodes, inputs/outputs, errors
  - Auto-refreshes every 3 seconds

---

## Data Flow: Context Evolution

### Initial Context
```json
{
  "input": "neural rendering"
}
```

### After Researcher Agent
```json
{
  "input": "neural rendering",
  "last_output": {
    "papers": [
      {"title": "Advances in neural rendering #1", "abstract": "..."},
      {"title": "Advances in neural rendering #2", "abstract": "..."},
      {"title": "Advances in neural rendering #3", "abstract": "..."}
    ],
    "meta": {"source": "mock", "topic": "neural rendering"}
  }
}
```

### After Summarizer Agent
```json
{
  "input": "neural rendering",
  "last_output": {
    "summary": "High-level summary: Advances in neural rendering #1 ; Advances in neural rendering #2 ; Advances in neural rendering #3"
  }
}
```

---

## Key Concepts

### 1. **Workflow Definition (YAML)**
- `start`: Starting node name
- `nodes`: Dictionary of node definitions
  - `impl`: Function name (builtin_* or custom)
  - `model`: Model label (mock|local|openai)
  - `retries`: Number of retries on failure
  - `next`: Next node name (null = end)

### 2. **Agent Abstraction**
- `name`: Agent identifier
- `func`: Callable function `(context) -> output`
- `model`: Model label (for future use)
- `retries`: Retry count on failure
- `timeout_s`: Timeout in seconds (for future use)

### 3. **Context Passing**
- Agents communicate via shared `context` dictionary
- Previous agent output stored in `context["last_output"]`
- Context is immutable between agents (snapshots recorded)
- Allows agents to access both initial input and intermediate results

### 4. **Tracing & Observability**
- **Runs**: High-level execution records
- **Nodes**: Individual agent execution records (success/error)
- **Contexts**: Context version snapshots (before each agent)

### 5. **Error Handling**
- Retry logic with exponential backoff
- Error recording in TraceStore
- Exception propagation to Orchestrator
- Workflow stops on unrecoverable errors

---

## Example Workflow: Research → Summarize

### Workflow YAML
```yaml
start: researcher
nodes:
  researcher:
    impl: builtin_research
    model: mock
    retries: 1
    next: summarizer
  summarizer:
    impl: builtin_summarize
    model: mock
    retries: 1
    next: null
```

### Execution Steps

1. **Researcher Agent**
   - Input: `{"input": "neural rendering"}`
   - Function: `builtin_research()`
   - Output: `{"papers": [...], "meta": {...}}`
   - Duration: ~0.8s

2. **Summarizer Agent**
   - Input: `{"input": "...", "last_output": {"papers": [...], ...}}`
   - Function: `builtin_summarize()`
   - Output: `{"summary": "High-level summary: ..."}`
   - Duration: ~0.6s

3. **Final Context**
   - `{"input": "...", "last_output": {"summary": "..."}}`

---

## Dashboard Usage

### Starting Dashboard
```bash
python -m synapse.cli serve_dashboard
# or
uvicorn dashboard.backend_app:app --reload
```

### Viewing Traces
1. Open http://127.0.0.1:8080
2. Dashboard shows:
   - List of recent runs
   - Nodes for each run
   - Input/output for each node
   - Errors (if any)
   - Duration and attempt counts
3. Auto-refreshes every 3 seconds

---

## Future Enhancements (Not Yet Implemented)

1. **Custom Agent Functions**: Support for `run: path/to/script.py` in YAML
2. **Parallel Execution**: Multiple agents running concurrently
3. **Conditionals**: Branching based on agent output
4. **Loops**: Iterative execution
5. **Model Adapters**: Actual OpenAI/Claude/local LLM integration
6. **Distributed Execution**: Agents running on different machines
7. **Resource Management**: CPU/memory limits per agent
8. **Health Checks**: Agent health monitoring
9. **Rolling Updates**: Update workflows without downtime
10. **Service Discovery**: Agents discovering each other dynamically

---

## File Structure

```
synapse/
├── synapse/
│   ├── __init__.py          # Package initialization
│   ├── cli.py               # CLI entry point
│   ├── orchestrator.py      # Workflow orchestration
│   ├── agent.py             # Agent abstraction
│   ├── trace.py             # SQLite tracing
│   ├── integrations.py      # Built-in agent functions
│   └── yaml_loader.py       # YAML workflow loader
├── dashboard/
│   ├── backend_app.py       # FastAPI backend
│   └── templates/
│       └── index.html       # Dashboard UI
├── examples/
│   └── research.yml         # Example workflow
├── scripts/
│   └── run_local.sh         # Local execution script
├── synapse_traces.db        # SQLite database (generated)
├── ARCHITECTURE.md          # Detailed architecture documentation
├── FLOW_DIAGRAM.md          # Visual flow diagrams
├── FLOW_SUMMARY.md          # This file
└── README.md                # Project documentation
```

---

## Summary

Synapse provides a **declarative, YAML-based orchestration system** for AI agents, similar to how Kubernetes manages containers. It handles:

- **Workflow definition** via YAML
- **Agent lifecycle** (instantiation, execution, retries)
- **Context management** (passing data between agents)
- **Observability** (tracing, error logging, dashboard)
- **Error handling** (retries, backoff, error propagation)

The architecture is designed to be **extensible** and **observable**, making it easy to debug and monitor multi-agent workflows.
