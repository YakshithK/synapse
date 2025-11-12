# synapse/orchestrator.py
import uuid, time
from .yaml_loader import load_workflow
from .trace import TraceStore
from .integrations import builtin_research, builtin_summarize, echo_agent
from .agent import Agent

class Orchestrator:
    def __init__(self, workflow_path: str):
        self.workflow_path = workflow_path
        self.workflow = load_workflow(workflow_path)
        self.trace = TraceStore()
        self.run_id = None
        self.agents = {}

    def _resolve_impl(self, impl_name):
        # wire builtin implementations
        if impl_name == "builtin_research":
            return builtin_research
        if impl_name == "builtin_summarize":
            return builtin_summarize
        if impl_name == "echo":
            return echo_agent
        # default fallback
        return echo_agent

    def _instantiate_agents(self):
        nodes = self.workflow.get("nodes", {})
        for name, node in nodes.items():
            impl = node.get("impl", "echo")
            func = self._resolve_impl(impl)
            model = node.get("model", "mock")
            retries = int(node.get("retries", 1))
            self.agents[name] = Agent(name=name, func=func, model=model, retries=retries)

    def run(self, initial_input: str):
        # start run 
        self.run_id = str(uuid.uuid4())
        self.trace.start_run(self.run_id, workflow=self.workflow_path)
        self.trace.current_run_id = self.run_id
        self._instantiate_agents()

        context = {"input": initial_input}
        version = 0

        current = self.workflow.get("start")

        while current:
            agent = self.agents.get(current)
            #record pre-node context snapshot

            version += 1
            self.trace.record_context_version(self.run_id, version, current, context)

            out = agent.run(context, tracer=self.trace)

            context["last_output"] = out

            nxt = self.workflow.get("nodes", {}).get(current, {}).get("next")

            if not nxt:
                break
            current = nxt

        version += 1
        self.trace.record_context_version(self.run_id, version, "end", context)
        return {"run_id": self.run_id, "final_context": context}