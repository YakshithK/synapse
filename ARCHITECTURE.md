# Synapse Architecture & Flow Documentation

## Overview
Synapse is a **Kubernetes-like orchestration system for AI agents**. It provides:
- **Workflow orchestration** via YAML definitions
- **Agent lifecycle management** with retries and error handling
- **Observability** through SQLite-backed tracing
- **Dashboard** for real-time monitoring

---

## Architecture Components

### 1. **Core Components**

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI (synapse/cli.py)                    │
│  - Entry point: `python -m synapse.cli run <workflow.yml>`  │
│  - Dashboard server: `serve_dashboard`                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Orchestrator (synapse/orchestrator.py)         │
│  - Loads YAML workflow                                       │
│  - Instantiates agents                                       │
│  - Manages execution flow                                    │
│  - Tracks context versions                                   │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Agent      │  │  TraceStore  │  │ YAML Loader  │
│ (agent.py)   │  │  (trace.py)  │  │(yaml_loader) │
└──────────────┘  └──────────────┘  └──────────────┘
        │                │
        │                ▼
        │        ┌──────────────┐
        │        │  SQLite DB   │
        │        │(traces.db)   │
        │        └──────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│   Integrations (integrations.py)        │
│   - builtin_research                    │
│   - builtin_summarize                   │
│   - echo_agent                          │
└─────────────────────────────────────────┘
```

### 2. **Dashboard Components**

```
┌─────────────────────────────────────────────────────────────┐
│           Dashboard Backend (dashboard/backend_app.py)      │
│  - FastAPI server                                           │
│  - REST API: /api/runs, /api/nodes/{run_id}                │
│  - Reads from SQLite DB                                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│        Dashboard Frontend (dashboard/templates/index.html)  │
│  - HTML/JS UI                                               │
│  - Auto-refreshes every 3s                                  │
│  - Shows runs, nodes, inputs/outputs, errors                │
└─────────────────────────────────────────────────────────────┘
```

---

## Detailed Flow: Workflow Execution

### Phase 1: Initialization

```
1. CLI receives command:
   python -m synapse.cli run examples/research.yml --prompt "neural rendering"

2. CLI validates workflow file exists
   ├─ If not: raises typer.Exit
   └─ If yes: Creates Orchestrator(workflow_path)

3. Orchestrator.__init__():
   ├─ Loads YAML via yaml_loader.load_workflow()
   │  └─ Validates: must have "start" and "nodes" keys
   ├─ Creates TraceStore() instance
   │  └─ Initializes SQLite DB (synapse_traces.db)
   │     └─ Creates tables: runs, nodes, contexts
   └─ Initializes empty agents dictionary
```

### Phase 2: Agent Instantiation

```
4. Orchestrator.run(initial_input) called:
   ├─ Generates unique run_id (UUID)
   ├─ Calls trace.start_run(run_id, workflow_path)
   │  └─ Records run in SQLite: runs table
   ├─ Sets trace.current_run_id = run_id
   └─ Calls _instantiate_agents()

5. _instantiate_agents():
   For each node in workflow["nodes"]:
   ├─ Extracts: name, impl, model, retries
   ├─ Calls _resolve_impl(impl_name)
   │  └─ Maps impl name → function:
   │     ├─ "builtin_research" → builtin_research()
   │     ├─ "builtin_summarize" → builtin_summarize()
   │     └─ "echo" → echo_agent()
   └─ Creates Agent(name, func, model, retries)
      └─ Stores in self.agents[name]
```

**Example Workflow (research.yml):**
```yaml
start: researcher
nodes:
  researcher:
    impl: builtin_research
    model: mock
    retries: 1
    next: summarizer
  summarizer:
    impl: builtin_summarize  # Note: YAML shows "run: summarize_agent.py" but code uses "impl"
    model: mock
    retries: 1
    next: null
```

### Phase 3: Workflow Execution Loop

```
6. Orchestrator execution loop:
   ├─ context = {"input": initial_input}  # e.g., {"input": "neural rendering"}
   ├─ version = 0
   └─ current = workflow["start"]  # "researcher"

   WHILE current is not None:
   
   a. Get agent: agent = self.agents[current]
   
   b. Record context snapshot:
      ├─ version += 1
      └─ trace.record_context_version(run_id, version, current, context)
         └─ Stores in SQLite: contexts table
   
   c. Execute agent:
      └─ out = agent.run(context, tracer=self.trace)
   
   d. Update context:
      └─ context["last_output"] = out
   
   e. Determine next node:
      └─ nxt = workflow["nodes"][current]["next"]
   
   f. Continue or break:
      ├─ If nxt is None: break (workflow complete)
      └─ Else: current = nxt (continue to next node)

7. Final context recording:
   ├─ version += 1
   └─ trace.record_context_version(run_id, version, "end", context)
```

### Phase 4: Agent Execution (Detailed)

```
agent.run(context, tracer):
├─ attempt = 0
├─ last_exc = None
└─ WHILE attempt <= retries:
   
   a. attempt += 1
   b. start_time = time.time()
   
   c. TRY:
      ├─ out = self.func(context)  # Call agent function
      ├─ duration = time.time() - start_time
      ├─ tracer.record_node(...)
      │  └─ Stores in SQLite: nodes table
      │     ├─ run_id, agent_id, name
      │     ├─ input_json (context), output_json (out)
      │     ├─ duration, attempt, model
      │     └─ error = None (success)
      └─ RETURN out
   
   d. EXCEPT Exception as e:
      ├─ duration = time.time() - start_time
      ├─ err = traceback.format_exc()
      ├─ tracer.record_error(...)
      │  └─ Stores in SQLite: nodes table
      │     └─ error = {"error": str(e), "stack": err}
      ├─ last_exc = e
      ├─ Backoff: time.sleep(min(1 * attempt, 3))
      └─ Continue loop (retry)
   
   e. If all retries exhausted:
      └─ RAISE last_exc (propagates to orchestrator)
```

### Phase 5: Data Flow Between Agents

```
Agent 1 (researcher):
├─ Input context: {"input": "neural rendering"}
├─ Function: builtin_research(context)
│  ├─ Extracts: topic = context.get("input")  # "neural rendering"
│  ├─ Simulates latency: time.sleep(0.8)
│  └─ Returns: {"papers": [...], "meta": {...}}
└─ Output stored in: context["last_output"]

Agent 2 (summarizer):
├─ Input context: 
│  {
│    "input": "neural rendering",
│    "last_output": {"papers": [...], "meta": {...}}
│  }
├─ Function: builtin_summarize(context)
│  ├─ Extracts: papers = context.get("last_output", {}).get("papers")
│  ├─ Simulates latency: time.sleep(0.6)
│  └─ Returns: {"summary": "High-level summary: ..."}
└─ Output stored in: context["last_output"] (overwrites previous)

Final context:
{
  "input": "neural rendering",
  "last_output": {"summary": "High-level summary: ..."}
}
```

---

## Data Models

### 1. **Workflow YAML Schema**
```yaml
start: <node_name>          # Starting node
nodes:
  <node_name>:
    impl: <function_name>   # Function to call (builtin_* or custom)
    model: <model_label>    # mock|local|openai (for future use)
    retries: <int>          # Number of retries on failure
    next: <node_name>|null  # Next node in chain (null = end)
```

### 2. **Context Object**
```python
context = {
    "input": str,              # Initial input
    "last_output": dict|str,   # Output from previous agent
    # ... any additional keys added by agents
}
```

### 3. **SQLite Schema**

**runs table:**
- `run_id` (TEXT PRIMARY KEY)
- `started_at` (REAL - timestamp)
- `workflow` (TEXT - workflow file path)

**nodes table:**
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `run_id` (TEXT)
- `agent_id` (TEXT - UUID of agent instance)
- `name` (TEXT - agent name)
- `input_json` (TEXT - JSON string of input context)
- `output_json` (TEXT - JSON string of output)
- `duration` (REAL - seconds)
- `attempt` (INTEGER)
- `error` (TEXT - JSON string of error object or NULL)
- `ts` (REAL - timestamp)
- `model` (TEXT - model label)

**contexts table:**
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `run_id` (TEXT)
- `version` (INTEGER - context version number)
- `node_name` (TEXT - node name or "end")
- `ctx_json` (TEXT - JSON string of context)
- `ts` (REAL - timestamp)

---

## Observability & Tracing

### Trace Recording Points

1. **Run Start**: When `orchestrator.run()` is called
   - Recorded in `runs` table

2. **Context Snapshots**: Before each agent execution
   - Recorded in `contexts` table
   - Version number increments
   - Allows tracking context evolution

3. **Node Execution**: After each agent attempt
   - Recorded in `nodes` table
   - Success: `error = NULL`, `output_json` contains result
   - Failure: `error` contains error details, `output_json = {}`

4. **Run End**: After workflow completes
   - Final context snapshot recorded in `contexts` table
   - `node_name = "end"`

### Dashboard Flow

```
1. User opens http://127.0.0.1:8080
   └─ Frontend loads index.html

2. Frontend JavaScript:
   ├─ Calls GET /api/runs
   │  └─ Backend queries: SELECT * FROM runs ORDER BY started_at DESC
   ├─ Displays list of runs (run_id, timestamp, workflow)
   └─ Auto-refreshes every 3 seconds

3. User clicks on a run:
   ├─ Calls GET /api/nodes/{run_id}
   │  └─ Backend queries: SELECT * FROM nodes WHERE run_id = ? ORDER BY ts ASC
   ├─ Displays nodes with:
   │  ├─ Name, model, duration, attempt
   │  ├─ Error (if any)
   │  ├─ Input (expandable)
   │  └─ Output (expandable)
   └─ Can also call GET /api/contexts/{run_id} to see context evolution
```

---

## Error Handling & Retries

### Retry Logic

```
Agent.retries = N means:
- Maximum attempts = N + 1
- If attempt 1 fails → retry (attempt 2)
- If attempt 2 fails → retry (attempt 3)
- ...
- If attempt N+1 fails → raise exception

Backoff strategy:
- Linear backoff: sleep(min(1 * attempt, 3))
- Example: attempt 1 → sleep(1s), attempt 2 → sleep(2s), attempt 3+ → sleep(3s)
```

### Error Propagation

```
1. Agent function raises exception
   └─ Caught in agent.run()

2. Error recorded in TraceStore
   └─ Stored in nodes table with error details

3. Retry logic:
   ├─ If retries left: sleep + retry
   └─ If no retries left: raise last_exc

4. Exception propagates to Orchestrator
   └─ Workflow execution stops
   └─ Final context snapshot still recorded (if possible)
```

---

## Key Design Patterns

### 1. **Kubernetes-like Concepts**

- **Workflows = Pods**: YAML-defined execution units
- **Agents = Containers**: Isolated execution units
- **Orchestrator = Kubelet**: Manages agent lifecycle
- **TraceStore = Logging/Monitoring**: Observability layer
- **Dashboard = kubectl/dashboard**: Management UI

### 2. **Context Passing**

- Agents communicate via shared `context` dictionary
- Previous agent output stored in `context["last_output"]`
- Context is immutable between agents (snapshots recorded)
- Allows agents to access both initial input and intermediate results

### 3. **Function Resolution**

- Built-in functions: Hard-coded mapping in `_resolve_impl()`
- Future: Support for custom functions via import paths
- Current: Only builtin_research, builtin_summarize, echo_agent

### 4. **Sequential Execution**

- Current: Linear chain (node → next → next → null)
- Future: Could support parallel execution, conditionals, loops

---

## Example Execution Trace

### Input
```bash
python -m synapse.cli run examples/research.yml --prompt "neural rendering"
```

### Execution Steps

1. **Run Initialization**
   - run_id: `abc-123-def-456`
   - workflow: `examples/research.yml`
   - Recorded in `runs` table

2. **Context Version 1** (before researcher)
   - context: `{"input": "neural rendering"}`
   - Recorded in `contexts` table

3. **Agent: researcher**
   - Input: `{"input": "neural rendering"}`
   - Function: `builtin_research()`
   - Duration: ~0.8s
   - Output: `{"papers": [...], "meta": {...}}`
   - Recorded in `nodes` table

4. **Context Version 2** (before summarizer)
   - context: `{"input": "neural rendering", "last_output": {"papers": [...], "meta": {...}}}`
   - Recorded in `contexts` table

5. **Agent: summarizer**
   - Input: `{"input": "neural rendering", "last_output": {"papers": [...], "meta": {...}}}`
   - Function: `builtin_summarize()`
   - Duration: ~0.6s
   - Output: `{"summary": "High-level summary: ..."}`
   - Recorded in `nodes` table

6. **Context Version 3** (end)
   - context: `{"input": "neural rendering", "last_output": {"summary": "..."}}`
   - Recorded in `contexts` table

7. **Result**
   - Returns: `{"run_id": "abc-123-def-456", "final_context": {...}}`
   - CLI displays: Run complete message

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

