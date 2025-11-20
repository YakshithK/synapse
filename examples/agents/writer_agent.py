# examples/agents/analysis_agent.py

import time


def run(context: dict) -> dict:
    """Analysis agent - placeholder."""
    last_output = context.get("last_output", {})
    papers = last_output.get("papers", [])

    time.sleep(3)

    return {
        "analysis": f"Analyzed {len(papers)} papers",
        "summary": "Analysis complete",
    }
