# synapse/yaml_loader.py
import yaml
from typing import Dict, Any

def load_workflow(path: str) -> Dict[str, Any]:
    """
    Read YAML workflow. Minimal expected schema:
    start: node_name
    nodes:
        node_name:
            impl: builtin_name or path.to.func (not yet supported)
            model: mock|local|openai
            retries: int
            next: other_node_name or null
    """

    with open(path, "r", encoding="utf8") as f:
        doc = yaml.safe_load(f)

    assert "start" in doc and "nodes" in doc, "workflow must have 'start' and 'nodes'"
    return doc