# synapse/dependancy_graph.py
from collections import defaultdict, deque
from typing import Any, Dict, List, Set


class DependencyGraph:
    """
    Manages agent dependencies and execution order.
    """

    def __init__(self, agents: List[Dict[str, Any]]):
        self.agents = agents
        self.graph = self._build_graph()
        self.reverse_graph = self._build_reverse_graph()

    def _build_graph(self) -> Dict[str, Set[str]]:
        """Build dependency graph: agent -> set of dependencies."""
        graph = defaultdict(set)
        agent_names = {agent["name"] for agent in self.agents}

        for agent in self.agents:
            name = agent["name"]
            depends_on = agent.get("depends_on", [])

            # handle both str and list
            if isinstance(depends_on, str):
                depends_on = [depends_on]
            elif depends_on is None:
                depends_on = []

            # validate dependencies exist
            for dep in depends_on:
                if dep not in agent_names:
                    raise ValueError(
                        f"Agent '{name}' depends on '{dep}' which doesn't exist"
                    )
                graph[name].add(dep)

        return dict(graph)

    def _build_reverse_graph(self) -> Dict[str, Set[str]]:
        """Build reverse graph: agent -> set of dependents."""
        reverse = defaultdict(set)
        for agent, deps in self.graph.items():
            for dep in deps:
                reverse[dep].add(agent)
        return dict(reverse)

    def get_execution_order(self) -> List[str]:
        """
        Get topological sort of agents for execution order.

        Returns:
            List of agent names in execution order
        """

        # Kahn's algorithm for topological sort
        in_degree = defaultdict(int)
        for agent in self.agents:
            in_degree[agent["name"]] = len(self.graph.get(agent["name"], set()))

        queue = deque(
            [agent["name"] for agent in self.agents if in_degree[agent["name"]] == 0]
        )
        result = []

        while queue:
            agent_name = queue.popleft()
            result.append(agent_name)

            # update in degree of dependents
            for dependent in self.reverse_graph.get(agent_name, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # check for cycles
        if len(result) != len(self.agents):
            raise ValueError("Circular dependency detected in agent graph")

        return result

    def validate_cycles(self) -> bool:
        """Check for circular dependencies."""
        try:
            self.get_execution_order()
            return True
        except ValueError:
            return False

    def get_parallel_groups(self) -> List[List[str]]:
        """
        Get group of agents that can run in parallel.

        Returns:
            List of groups, where each group can run in parallel
        """

        execution_order = self.get_execution_order()
        groups = []
        completed: Set[str] = set()

        while len(completed) < len(execution_order):
            # find agents with all dependencies completed
            ready = []
            for agent_name in execution_order:
                if agent_name not in completed:
                    deps = self.graph.get(agent_name, set())
                    if deps.issubset(completed):
                        ready.append(agent_name)

            if not ready:
                # should not happen if graph is valid
                break

            groups.append(ready)
            completed.update(ready)

        return groups
