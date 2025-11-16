# examples/agents/research_agent.py
"""
Research Agent

This agent researches topics and returns papers.
"""


def run(context: dict) -> dict:
    """
    Research agent function.

    Args:
        context: Dictionary with 'input' key containing research topic

    Returns:
        Dictionary with 'papers' key containing list of papers
    """
    topic = context.get("input", "")

    # Simulate research (in real implementation, this would call an API)
    papers = [
        {
            "title": f"Advances in {topic} #1",
            "abstract": f"Abstract about {topic} part 1",
        },
        {
            "title": f"Advances in {topic} #2",
            "abstract": f"Abstract about {topic} part 2",
        },
        {
            "title": f"Advances in {topic} #3",
            "abstract": f"Abstract about {topic} part 3",
        },
    ]

    return {
        "papers": papers,
        "meta": {"topic": topic, "count": len(papers), "source": "research_agent"},
    }
