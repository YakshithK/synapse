# synapse/yaml_loader.py
import yaml
from typing import Dict, Any, Optional
import os

def load_workflow(path: str) -> Dict[str, Any]:
    """
    Load workflow YAML, supporting both old and new schemas.
    
    New schema:
        workflow:
            name: workflow-name
            agents:
                - name: AgentName
                  run: agent_file.py
                  depends_on: OtherAgent
                  retries: 2
                  model: gpt-4
    
    Old schema (backward compatible):
        start: node_name
        nodes:
            node_name:
                impl: builtin_name
                next: other_node
    """
    with open(path, "r", encoding="utf8") as f:
        doc = yaml.safe_load(f)
    
    # Check if new schema
    if 'workflow' in doc:
        return _load_new_schema(doc, path)
    # Old schema
    elif 'start' in doc and 'nodes' in doc:
        return _convert_old_schema(doc, path)
    else:
        raise ValueError("Invalid workflow schema: must have 'workflow' or 'start'/'nodes'")

def _load_new_schema(doc: Dict[str, Any], workflow_path: str) -> Dict[str, Any]:
    """Load new workflow schema."""
    workflow = doc.get('workflow', {})
    
    if 'agents' not in workflow:
        raise ValueError("New schema must have 'workflow.agents'")
    
    agents = workflow['agents']
    
    # Validate agents
    agent_names = [agent['name'] for agent in agents]
    if len(agent_names) != len(set(agent_names)):
        raise ValueError("Duplicate agent names found")
    
    # Determine workflow directory (for resolving agent file paths)
    workflow_dir = os.path.dirname(os.path.abspath(workflow_path))
    
    return {
        'schema_version': '2.0',
        'workflow_name': workflow.get('name', 'unnamed'),
        'agents': agents,
        'workflow_dir': workflow_dir,
        'workflow_path': workflow_path
    }

def _convert_old_schema(doc: Dict[str, Any], workflow_path: str) -> Dict[str, Any]:
    """Convert old schema to new schema format."""
    start = doc.get('start')
    nodes = doc.get('nodes', {})
    
    agents = []
    agent_names = list(nodes.keys())
    
    # Convert nodes to agents
    for name, node in nodes.items():
        agent = {
            'name': name,
            'impl': node.get('impl', 'echo'),  # Old schema uses 'impl'
            'model': node.get('model', 'mock'),
            'retries': int(node.get('retries', 1)),
        }
        
        # Convert 'next' to 'depends_on'
        next_node = node.get('next')
        if next_node:
            # In old schema, 'next' means "runs after this"
            # So the next node depends on this one
            # We need to reverse this for new schema
            pass  # This is tricky - old schema is sequential
        
        agents.append(agent)
    
    # For old schema, execution is sequential based on 'next' links
    # We'll maintain this behavior
    return {
        'schema_version': '1.0',
        'workflow_name': 'legacy',
        'agents': agents,
        'start': start,
        'nodes': nodes,  # Keep old structure for backward compatibility
        'workflow_dir': os.path.dirname(os.path.abspath(workflow_path)),
        'workflow_path': workflow_path
    }