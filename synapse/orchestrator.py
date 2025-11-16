# synapse/orchestrator.py
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from .agent import Agent
from .agent_loader import AgentLoader
from .dependency_graph import DependencyGraph
from .trace import TraceStore
from .yaml_loader import load_workflow


class Orchestrator:
    def __init__(self, workflow_path: str):
        self.workflow_path = workflow_path
        self.workflow = load_workflow(workflow_path)
        self.trace = TraceStore()
        self.run_id: Optional[str] = None
        self.agents: Dict[str, Agent] = {}
        self.agent_loader = AgentLoader(agent_dir=self.workflow.get("workflow_dir"))
        self.execution_order: Optional[List[str]] = None

        # Backward compatibility: check if old schema
        self.use_new_schema = self.workflow.get("schema_version") == "2.0"

    def _resolve_agent_function(
        self, agent_config: Dict[str, Any]
    ) -> Tuple[Callable[..., Any], Dict[str, Any]]:
        """
        Resolve agent function from configuration.

        Supports:
        - New schema: 'run' key with Python file path
        - Old schema: 'impl' key with builtin name
        """
        if self.use_new_schema:
            # New schema: load from file
            agent_file = agent_config.get("run")
            if not agent_file:
                raise ValueError(
                    f"Agent {agent_config.get('name')} must have 'run' key"
                )

            try:
                agent_data = self.agent_loader.load_agent(agent_file)
                return agent_data["func"], agent_data["metadata"]
            except Exception as e:
                raise ValueError(f"Failed to load agent {agent_file}: {str(e)}")
        else:
            # Old schema: use builtin
            from .integrations import builtin_research, builtin_summarize, echo_agent

            impl_name = agent_config.get("impl", "echo")
            impl_map = {
                "builtin_research": builtin_research,
                "builtin_summarize": builtin_summarize,
                "echo": echo_agent,
            }

            func = impl_map.get(impl_name, echo_agent)
            metadata = {"name": impl_name, "type": "builtin"}

            return func, metadata

    def _instantiate_agents(self) -> None:
        """Instantiate agents from workflow configuration."""
        if self.use_new_schema:
            # New schema: use dependency graph
            agents_config = self.workflow.get("agents", [])

            # Build dependency graph
            self.dependency_graph = DependencyGraph(agents_config)

            # Validate no cycles
            if not self.dependency_graph.validate_cycles():
                raise ValueError("Circular dependency detected in agent graph")

            # Get execution order
            execution_order = self.dependency_graph.get_execution_order()

            # Instantiate agents
            for agent_config in agents_config:
                name = agent_config["name"]
                func, metadata = self._resolve_agent_function(agent_config)
                model = agent_config.get("model", "mock")
                retries = int(agent_config.get("retries", 1))
                timeout = float(agent_config.get("timeout", 30.0))

                self.agents[name] = Agent(
                    name=name,
                    func=func,
                    model=model,
                    retries=retries,
                    timeout_s=timeout,
                    metadata=metadata,
                )

            self.execution_order = execution_order
        else:
            # Old schema: sequential execution
            nodes = self.workflow.get("nodes", {})
            for name, node in nodes.items():
                agent_config = {"name": name, **node}
                func, metadata = self._resolve_agent_function(agent_config)
                model = node.get("model", "mock")
                retries = int(node.get("retries", 1))

                self.agents[name] = Agent(
                    name=name,
                    func=func,
                    model=model,
                    retries=retries,
                    metadata=metadata,
                )

            # Old schema: use 'start' and 'next' for execution order
            self.execution_order = None
            self.start_node = self.workflow.get("start")

    def run(self, initial_input: str) -> Dict[str, Any]:
        """Run workflow with initial input."""
        # Start run
        self.run_id = str(uuid.uuid4())
        workflow_name = self.workflow.get("workflow_name", "unnamed")
        self.trace.start_run(self.run_id, workflow=workflow_name)
        self.trace.current_run_id = self.run_id
        self._instantiate_agents()
        self.execution_results = []

        context = {"input": initial_input}
        version = 0

        if self.use_new_schema:
            # New schema: execute based on dependency order
            if self.execution_order is None:
                raise ValueError("Execution order not initialized for new schema")
            for agent_name in self.execution_order:
                agent = self.agents.get(agent_name)
                if not agent:
                    raise ValueError(f"Agent {agent_name} not found")

                version += 1
                self.trace.record_context_version(
                    self.run_id, version, agent_name, context
                )

                # Track execution
                agent_start = time.time()
                attempts = 0

                try:
                    out = agent.run(context, tracer=self.trace)
                    agent_duration = time.time() - agent_start
                    attempts = 1

                    # get attempts from trace
                    nodes = self.trace.fetch_nodes(self.run_id)
                    agent_nodes = [n for n in nodes if n["name"] == agent_name]

                    if agent_nodes:
                        attempts = max([n["attempt"] for n in agent_nodes])

                    self.execution_results.append(
                        {
                            "agent_name": agent_name,
                            "status": "retry_success" if attempts > 1 else "success",
                            "duration": agent_duration,
                            "attempts": attempts,
                            "model": agent.model,
                            "error_type": None,
                        }
                    )

                    context["last_output"] = out

                except Exception as e:
                    agent_duration = time.time() - agent_start
                    attempts = 1

                    # get attempts from trace
                    nodes = self.trace.fetch_nodes(self.run_id)
                    agent_nodes = [n for n in nodes if n["name"] == agent_name]
                    if agent_nodes:
                        attempts = max([n["attempt"] for n in agent_nodes])

                    self.execution_results.append(
                        {
                            "agent_name": agent_name,
                            "status": "failed",
                            "duration": agent_duration,
                            "attempts": attempts,
                            "model": agent.model,
                            "error_type": type(e).__name__,
                        }
                    )
                    raise

        else:
            # Old schema: sequential execution
            current = self.start_node
            while current:
                agent = self.agents.get(current)
                if not agent:
                    raise ValueError(f"Agent {current} not found")

                version += 1
                self.trace.record_context_version(
                    self.run_id, version, current, context
                )

                out = agent.run(context, tracer=self.trace)
                context["last_output"] = out

                nxt = self.workflow.get("nodes", {}).get(current, {}).get("next")
                if not nxt:
                    break
                current = nxt

        version += 1
        self.trace.record_context_version(self.run_id, version, "end", context)
        return {"run_id": self.run_id, "final_context": context}

    def get_execution_results(self) -> List[Dict[str, Any]]:
        """Get execution results for CLI display."""
        return self.execution_results
