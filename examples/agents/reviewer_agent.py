# examples/agents/analysis_agent.py
def run(context: dict) -> dict:
    """Analysis agent - placeholder."""
    last_output = context.get("last_output", {})
    papers = last_output.get("papers", [])
    
    return {
        "analysis": f"Analyzed {len(papers)} papers",
        "summary": "Analysis complete"
    }