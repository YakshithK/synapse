# Synapse Flow Diagram

## High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER COMMAND                                   │
│  python -m synapse.cli run examples/research.yml --prompt "neural..."  │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLI (cli.py)                                   │
│  • Validates workflow file exists                                        │
│  • Creates Orchestrator(workflow_path)                                   │
│  • Calls orch.run(prompt)                                                │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR (orchestrator.py)                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 1. INITIALIZATION                                                │   │
│  │    • Load YAML via yaml_loader.load_workflow()                   │   │
│  │    • Create TraceStore()                                         │   │
│  │    • Initialize SQLite DB (runs, nodes, contexts tables)         │   │
│  │    • Generate run_id (UUID)                                      │   │
│  │    • Record run in TraceStore                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 2. AGENT INSTANTIATION                                            │   │
│  │    • Parse workflow["nodes"]                                      │   │
│  │    • For each node:                                               │   │
│  │      - Resolve impl → function (_resolve_impl)                    │   │
│  │      - Create Agent(name, func, model, retries)                   │   │
│  │      - Store in self.agents[name]                                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 3. WORKFLOW EXECUTION LOOP                                        │   │
│  │    • context = {"input": prompt}                                  │   │
│  │    • current = workflow["start"]                                  │   │
│  │    • WHILE current is not None:                                   │   │
│  │      a. Record context snapshot (version++)                       │   │
│  │      b. Get agent = self.agents[current]                          │   │
│  │      c. Execute agent.run(context, tracer)                        │   │
│  │      d. Update context["last_output"] = out                       │   │
│  │      e. Move to next node: current = node["next"]                 │   │
│  │    • Record final context snapshot                                │   │
│  │    • Return {"run_id": ..., "final_context": ...}                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        AGENT (agent.py)                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ agent.run(context, tracer)                                       │   │
│  │  • attempt = 0                                                   │   │
│  │  • WHILE attempt <= retries:                                     │   │
│  │    a. attempt += 1                                               │   │
│  │    b. TRY:                                                       │   │
│  │       - Call self.func(context)                                  │   │
│  │       - Record success in tracer.record_node()                   │   │
│  │       - RETURN output                                            │   │
│  │    c. EXCEPT Exception:                                          │   │
│  │       - Record error in tracer.record_error()                    │   │
│  │       - last_exc = e                                             │   │
│  │       - Backoff: sleep(min(1 * attempt, 3))                      │   │
│  │    d. If retries exhausted: RAISE last_exc                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    INTEGRATIONS (integrations.py)                        │
│  • builtin_research(context) → {"papers": [...], "meta": {...}}         │
│  • builtin_summarize(context) → {"summary": "..."}                      │
│  • echo_agent(context) → {"echo": "..."}                                │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      TRACESTORE (trace.py)                               │
│  • record_node() → INSERT INTO nodes (success)                          │
│  • record_error() → INSERT INTO nodes (error)                           │
│  • record_context_version() → INSERT INTO contexts                      │
│  • start_run() → INSERT INTO runs                                       │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    SQLITE DATABASE (synapse_traces.db)                   │
│  • runs table: run_id, started_at, workflow                             │
│  • nodes table: run_id, agent_id, name, input_json, output_json, ...    │
│  • contexts table: run_id, version, node_name, ctx_json, ts             │
└─────────────────────────────────────────────────────────────────────────┘
```

## Detailed Agent Execution Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT EXECUTION (Detailed)                            │
└─────────────────────────────────────────────────────────────────────────┘

agent.run(context, tracer)
│
├─► attempt = 0
├─► last_exc = None
│
└─► WHILE attempt <= retries:
    │
    ├─► attempt += 1
    ├─► start_time = time.time()
    │
    ├─► TRY:
    │   │
    │   ├─► out = self.func(context)
    │   │   │
    │   │   └─► Function Execution:
    │   │       ├─► builtin_research(context)
    │   │       │   ├─► topic = context.get("input")
    │   │       │   ├─► time.sleep(0.8)  # Simulate latency
    │   │       │   ├─► papers = [...]
    │   │       │   └─► return {"papers": papers, "meta": {...}}
    │   │       │
    │   │       └─► builtin_summarize(context)
    │   │           ├─► papers = context.get("last_output", {}).get("papers")
    │   │           ├─► time.sleep(0.6)  # Simulate latency
    │   │           ├─► summary = " ; ".join([p["title"] for p in papers])
    │   │           └─► return {"summary": f"High-level summary: {summary}"}
    │   │
    │   ├─► duration = time.time() - start_time
    │   │
    │   ├─► tracer.record_node(
    │   │       run_id, agent_id, name,
    │   │       input_ctx, output,
    │   │       duration, attempt, model
    │   │   )
    │   │   └─► INSERT INTO nodes (success)
    │   │
    │   └─► RETURN out
    │
    └─► EXCEPT Exception as e:
        │
        ├─► duration = time.time() - start_time
        ├─► err = traceback.format_exc()
        │
        ├─► tracer.record_error(
        │       run_id, agent_id, name,
        │       error, stack,
        │       duration, attempt, model
        │   )
        │   └─► INSERT INTO nodes (error)
        │
        ├─► last_exc = e
        │
        ├─► Backoff: time.sleep(min(1 * attempt, 3))
        │   └─► attempt 1 → sleep(1s)
        │   └─► attempt 2 → sleep(2s)
        │   └─► attempt 3+ → sleep(3s)
        │
        └─► Continue loop (retry)

└─► If all retries exhausted:
    └─► RAISE last_exc
```

## Context Flow Between Agents

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      CONTEXT EVOLUTION                                   │
└─────────────────────────────────────────────────────────────────────────┘

INITIAL CONTEXT
┌─────────────────────────────────┐
│ {                               │
│   "input": "neural rendering"   │
│ }                               │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CONTEXT VERSION 1 (before researcher)                                   │
│  ┌─────────────────────────────────┐                                    │
│  │ {                               │                                    │
│  │   "input": "neural rendering"   │                                    │
│  │ }                               │                                    │
│  └─────────────────────────────────┘                                    │
│  Recorded in contexts table (version=1, node_name="researcher")         │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  AGENT: researcher                                                       │
│  • Input: {"input": "neural rendering"}                                 │
│  • Function: builtin_research()                                         │
│  • Output: {"papers": [...], "meta": {...}}                             │
│  Recorded in nodes table (success)                                      │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CONTEXT UPDATE                                                          │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │ {                                                             │     │
│  │   "input": "neural rendering",                                │     │
│  │   "last_output": {                                            │     │
│  │     "papers": [                                               │     │
│  │       {"title": "Advances in neural rendering #1", ...},      │     │
│  │       {"title": "Advances in neural rendering #2", ...},      │     │
│  │       {"title": "Advances in neural rendering #3", ...}       │     │
│  │     ],                                                         │     │
│  │     "meta": {"source": "mock", "topic": "neural rendering"}   │     │
│  │   }                                                            │     │
│  │ }                                                             │     │
│  └───────────────────────────────────────────────────────────────┘     │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CONTEXT VERSION 2 (before summarizer)                                   │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │ {                                                             │     │
│  │   "input": "neural rendering",                                │     │
│  │   "last_output": {"papers": [...], "meta": {...}}            │     │
│  │ }                                                             │     │
│  └───────────────────────────────────────────────────────────────┘     │
│  Recorded in contexts table (version=2, node_name="summarizer")         │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  AGENT: summarizer                                                       │
│  • Input: {"input": "...", "last_output": {"papers": [...], ...}}      │
│  • Function: builtin_summarize()                                        │
│  • Extracts: papers = context.get("last_output", {}).get("papers")     │
│  • Output: {"summary": "High-level summary: ..."}                      │
│  Recorded in nodes table (success)                                      │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CONTEXT UPDATE                                                          │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │ {                                                             │     │
│  │   "input": "neural rendering",                                │     │
│  │   "last_output": {                                            │     │
│  │     "summary": "High-level summary: ..."                      │     │
│  │   }                                                            │     │
│  │ }                                                             │     │
│  └───────────────────────────────────────────────────────────────┘     │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  CONTEXT VERSION 3 (end)                                                 │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │ {                                                             │     │
│  │   "input": "neural rendering",                                │     │
│  │   "last_output": {"summary": "High-level summary: ..."}      │     │
│  │ }                                                             │     │
│  └───────────────────────────────────────────────────────────────┘     │
│  Recorded in contexts table (version=3, node_name="end")                │
└─────────────────────────────────────────────────────────────────────────┘
```

## Dashboard Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DASHBOARD FLOW                                    │
└─────────────────────────────────────────────────────────────────────────┘

USER BROWSER
┌─────────────────────────────────┐
│ http://127.0.0.1:8080           │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  DASHBOARD FRONTEND (index.html)                                         │
│  • HTML/JS UI                                                            │
│  • Auto-refresh every 3 seconds                                          │
│  • Displays runs, nodes, inputs/outputs, errors                          │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  DASHBOARD BACKEND (backend_app.py)                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ GET /api/runs                                                    │   │
│  │   • Query: SELECT * FROM runs ORDER BY started_at DESC          │   │
│  │   • Returns: [{run_id, started_at, workflow}, ...]              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ GET /api/nodes/{run_id}                                          │   │
│  │   • Query: SELECT * FROM nodes WHERE run_id=? ORDER BY ts ASC   │   │
│  │   • Returns: [{id, agent_id, name, input, output, ...}, ...]    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ GET /api/contexts/{run_id}                                       │   │
│  │   • Query: SELECT * FROM contexts WHERE run_id=? ORDER BY ...   │   │
│  │   • Returns: [{version, node, ctx, ts}, ...]                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    SQLITE DATABASE (synapse_traces.db)                   │
│  • runs table                                                            │
│  • nodes table                                                           │
│  • contexts table                                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

## Workflow Definition Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    WORKFLOW DEFINITION (research.yml)                    │
└─────────────────────────────────────────────────────────────────────────┘

YAML FILE
┌─────────────────────────────────┐
│ start: researcher               │
│ nodes:                          │
│   researcher:                   │
│     impl: builtin_research      │
│     model: mock                 │
│     retries: 1                  │
│     next: summarizer            │
│   summarizer:                   │
│     impl: builtin_summarize     │
│     model: mock                 │
│     retries: 1                  │
│     next: null                  │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  YAML LOADER (yaml_loader.py)                                            │
│  • Load YAML file                                                        │
│  • Validate: must have "start" and "nodes"                               │
│  • Return: workflow dictionary                                           │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  ORCHESTRATOR._instantiate_agents()                                      │
│  • Parse workflow["nodes"]                                               │
│  • For each node:                                                        │
│    - Extract: name, impl, model, retries                                 │
│    - Resolve impl → function:                                            │
│      • "builtin_research" → builtin_research()                           │
│      • "builtin_summarize" → builtin_summarize()                         │
│      • "echo" → echo_agent()                                             │
│    - Create Agent(name, func, model, retries)                            │
│    - Store in self.agents[name]                                          │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  AGENT INSTANCES                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ self.agents = {                                                  │   │
│  │   "researcher": Agent(                                           │   │
│  │     name="researcher",                                           │   │
│  │     func=builtin_research,                                       │   │
│  │     model="mock",                                                │   │
│  │     retries=1                                                    │   │
│  │   ),                                                             │   │
│  │   "summarizer": Agent(                                           │   │
│  │     name="summarizer",                                           │   │
│  │     func=builtin_summarize,                                      │   │
│  │     model="mock",                                                │   │
│  │     retries=1                                                    │   │
│  │   )                                                              │   │
│  │ }                                                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      ERROR HANDLING FLOW                                 │
└─────────────────────────────────────────────────────────────────────────┘

AGENT EXECUTION
┌─────────────────────────────────┐
│ agent.run(context, tracer)      │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  ATTEMPT 1                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ TRY: self.func(context)                                         │   │
│  │   └─► Exception raised                                          │   │
│  │                                                                 │   │
│  │ EXCEPT Exception as e:                                          │   │
│  │   ├─► tracer.record_error(...)                                 │   │
│  │   │   └─► INSERT INTO nodes (error)                            │   │
│  │   ├─► last_exc = e                                             │   │
│  │   ├─► Backoff: sleep(1s)                                       │   │
│  │   └─► Continue loop (retry)                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  ATTEMPT 2                                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ TRY: self.func(context)                                         │   │
│  │   └─► Exception raised                                          │   │
│  │                                                                 │   │
│  │ EXCEPT Exception as e:                                          │   │
│  │   ├─► tracer.record_error(...)                                 │   │
│  │   │   └─► INSERT INTO nodes (error)                            │   │
│  │   ├─► last_exc = e                                             │   │
│  │   ├─► Backoff: sleep(2s)                                       │   │
│  │   └─► Continue loop (retry)                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  RETRIES EXHAUSTED                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ attempt > retries:                                              │   │
│  │   └─► RAISE last_exc                                           │   │
│  │                                                                 │   │
│  │ Exception propagates to Orchestrator:                           │   │
│  │   └─► Workflow execution stops                                 │   │
│  │   └─► Final context snapshot still recorded (if possible)      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

