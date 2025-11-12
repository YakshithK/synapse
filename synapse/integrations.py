# synapse/integrations.py
"""
This file containes simple adapters / builtin implementations
We intentionally keep models mocked for demo. Please replace
with OpenAI calls or Llama binding later.
"""

import time, random

def builtin_research(context):
    """
    pretend to fetc paper: output list of 'paper' dicts
    """
    topic = context.get("input") or context.get("topic") or "unknown"
    # simulate latency
    time.sleep(0.8)
    papers = [
        {"title": f"Advances in {topic} #{i}", "abstract": f"Abstract about {topic} part {i}"} for i in range(1, 4)
    ]
    return {"papers": papers, "meta": {"source": "mock", "topic": topic}}

def builtin_summarize(context):
    """
    summarizer: consumes context['last_output'] or context['papers']
    """
    time.sleep(0.6)
    papers = context.get("last_output", {}).get("papers") or context.get("papers") or []
    summary = " ; ".join([p["title"] for p in papers])
    return {"summary": f"High-level summary: {summary}"}

def echo_agent(context):
    time.sleep(0.2)
    return {"echo": context.get("input", "no input")}

#model adapter placeholder: unify signature
def call_model(model_label: str, prompt: str):
    """
    Very small deterministic mocked 'model call'.
    Replace with actual OpenAI/Claude/local llm adapter.
    """
    time.sleep(0.3)

    #deterministic pseudo-output
    return f"[{model_label}] response to: {prompt}"