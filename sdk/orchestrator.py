from .agent import Agent
from .trace import Trace
from .yaml_loader import load_workflow

class Orchestrator:
    def __init__(self, workflow_file):
        self.workflow = load_workflow(workflow_file)
        self.trace = Trace()
        self.agents = self._instantiate_agents()

    def _instantiate_agents(self):
        agents = {}
        for name, node in self.workflow['nodes'].items():
            func = self._load_func(node.get('impl', 'builtin'))
            agents[name] = Agent(name, func, model=node.get('model', 'gpt-4'), retries=node.get('retries', 1))
        return agents
    
    def run(self, initial_input):
        context = {'input': initial_input}
        # simplistic sequential runner based on YAML next pointers
        current = self.workflow['start']
        while current: 
            agent = self.agents[current]
            out = agent.run(context, self.trace)
            # apply simple memory sync
            context.update({'last_output': out})
            current = self.workflow['nodes'][current].get('next')

        return context
