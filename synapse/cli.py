# synapse/cli.py
import os
import subprocess
import sys
import time
from pathlib import Path

import typer
import uvicorn
from rich.console import Console

from .orchestrator import Orchestrator

app = typer.Typer()
console = Console()

# mock cost tracking for now
MODEL_COSTS = {"gpt-4": 0.03, "gpt-3.5-turbo": 0.002, "mock": 0.0}


def format_duration(seconds: float) -> str:
    """Format duration in seconds to readable string."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    return f"{seconds:.1f}s"


def calculate_cost(model: str, tokens: int = 0) -> float:
    """Calculate cost based on model and token usage."""
    # For now, return 0 or mock cost based on model
    # In real implementation, track actual token usage
    return MODEL_COSTS.get(model, 0.0) * (tokens / 1000) if tokens > 0 else 0.001


def create_demo_agent(agent_path: Path, agent_name: str, agent_code: str) -> None:
    """Create a demo agent file with the given code."""
    agent_path.write_text(agent_code)
    console.print(f"[green]✓[/green] Created {agent_name}")


@app.command()
def init() -> None:
    """
    Initialize a new Synapse project with demo agents.

    Creates an agents/ directory with summarize.py and classify.py demo
    agents.
    """
    console.print("[cyan]Initializing Synapse project...[/cyan]\n")

    # Create agents directory
    agents_dir = Path("agents")
    agents_dir.mkdir(exist_ok=True)
    console.print(f"[green]✓[/green] Created {agents_dir}/ directory")

    # Demo agent: summarize.py
    summarize_code = '''# agents/summarize.py
"""
Summarize Agent

This agent takes text input and generates a concise summary.
"""

def run(context: dict) -> dict:
    """
    Summarize agent function.

    Args:
        context: Dictionary with 'input' key containing text to summarize

    Returns:
        Dictionary with 'summary' key containing the summarized text
    """
    text = context.get("input", "")

    # Simulate summarization (in real implementation, this would call an LLM)
    if len(text) > 100:
        summary = text[:100] + "..." if len(text) > 100 else text
        summary = f"Summary: {summary}"
    else:
        summary = f"Summary: {text}" if text else "No input provided"

    return {
        "summary": summary,
        "meta": {
            "original_length": len(text),
            "summary_length": len(summary),
            "source": "summarize_agent"
        }
    }
'''

    # Demo agent: classify.py
    classify_code = '''# agents/classify.py
"""
Classify Agent

This agent categorizes text input into predefined categories.
"""

def run(context: dict) -> dict:
    """
    Classify agent function.

    Args:
        context: Dictionary with 'input' key containing text to classify

    Returns:
        Dictionary with 'category' and 'confidence' keys
    """
    text = context.get("input", "")

    # Simple keyword-based classification (in real implementation, use LLM)
    categories = {
        "technology": ["code", "software", "computer", "algorithm", "data"],
        "business": ["market", "revenue", "profit", "customer", "strategy"],
        "science": ["research", "experiment", "study", "analysis", "theory"],
        "general": []  # fallback category
    }

    text_lower = text.lower()
    best_category = "general"
    max_matches = 0

    for category, keywords in categories.items():
        if category == "general":
            continue
        matches = sum(1 for keyword in keywords if keyword in text_lower)
        if matches > max_matches:
            max_matches = matches
            best_category = category

    confidence = (
        min(0.9, 0.3 + (max_matches * 0.2)) if max_matches > 0 else 0.1
    )

    return {
        "category": best_category,
        "confidence": confidence,
        "meta": {
            "text_length": len(text),
            "keyword_matches": max_matches,
            "source": "classify_agent"
        }
    }
'''

    # Create demo agent files
    create_demo_agent(agents_dir / "summarize.py", "summarize.py", summarize_code)
    create_demo_agent(agents_dir / "classify.py", "classify.py", classify_code)

    # Create example workflow
    workflow_code = """# workflow.yaml
workflow:
  name: demo-pipeline
  agents:
    - name: SummarizeAgent
      run: agents/summarize.py
      retries: 2
      model: gpt-4
      description: "Summarizes input text"
      timeout: 30

    - name: ClassifyAgent
      run: agents/classify.py
      retries: 1
      model: gpt-4
      description: "Classifies the summarized text"
      timeout: 30
      depends_on: SummarizeAgent
"""

    workflow_path = Path("workflow.yaml")
    workflow_path.write_text(workflow_code)
    console.print("[green]✓[/green] Created workflow.yaml")

    console.print(
        "\n[bold green]✓ Synapse project " "initialized successfully![/bold green]"
    )
    console.print("\n[cyan]Next steps:[/cyan]")
    console.print(
        "1. Try running: [yellow]synapse run workflow.yaml --prompt "
        '"Your text here"[/yellow]'
    )
    console.print("2. Start dashboard: [yellow]synapse serve[/yellow]")
    console.print(
        "3. Check the [yellow]agents/[/yellow] " "directory to modify the demo agents"
    )


@app.command()
def run(
    workflow: str = typer.Argument(..., help="Path to workflow YAML file"),
    prompt: str = typer.Option(..., "--prompt", "-p", help="Initial prompt/input"),
    ui: bool = typer.Option(False, "--ui", "-u", help="Start dashboard UI server"),
    port: int = typer.Option(8000, "--port", help="Port for dashboard UI"),
) -> None:
    """
    Run a Synapse workflow.

    Example:
        synapse run pipeline.yaml --prompt "research neural rendering"
        synapse run pipeline.yaml --prompt "research neural rendering" --ui
    """

    # check if workflow file exists
    if not os.path.exists(workflow):
        console.print(
            f"[red]Error:[/red] workflow \
        file not found: {workflow}"
        )
        raise typer.Exit(1)

    # start dashboard if requested
    dashboard_process = None

    if ui:
        console.print(f"[cyan]Starting dashboard on http://localhost:{port}...[/cyan]")
        dashboard_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "synapse.dashboard.backend_app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(2)  # give server time to start
        console.print(
            f"[green]✓[/green] Dashboard running at http://localhost:{port}\n"
        )

    try:
        # initialize orchestrator
        orch = Orchestrator(workflow)

        # run workflow
        console.print(f"[cyan]Running workflow: {workflow}[/cyan]\n")

        res = orch.run(prompt)

        # get execution results from orchestrator
        execution_results = orch.get_execution_results()

        # display results
        console.print("\n[bold]Execution Results:[/bold]\n")

        total_cost = 0.0

        for result in execution_results:
            agent_name = result["agent_name"]
            status = result["status"]
            duration = result["duration"]
            attempts = result["attempts"]
            model = result["model"]

            # calculate cost -- mock for now
            cost = calculate_cost(model)
            total_cost += cost

            # format status
            if status == "success":
                icon = "[green]✅[/green]"
                status_text = "success"
            elif status == "retry_success":
                icon = "[yellow]✅[/yellow]"
                status_text = (
                    f"retry #{attempts - 1} failed "
                    f"({result.get('error_type', 'error')}), "
                    f"retry #{attempts} success"
                )
            else:
                icon = "[red]❌[/red]"
                status_text = "failed"

            # format output line
            duration_str = format_duration(duration)
            console.print(f"{icon} {agent_name}: {status_text} ({duration_str})")

        console.print(f"\n[bold]💰 Total cost:[/bold] ${total_cost:.3f}")
        console.print(f"\n[green]Run complete.[/green] run_id={res['run_id']}")

        if ui:
            console.print(f"\n[cyan]Dashboard:[/cyan] http://localhost:{port}")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)
    finally:
        # Clean up dashboard process
        if dashboard_process:
            dashboard_process.terminate()
            dashboard_process.wait()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
    port: int = typer.Option(8080, "--port", help="Port to bind to"),
) -> None:
    """
    Launch the Synapse dashboard server.

    Example:
        synapse serve
        synapse server --port 3000
    """
    console.print(f"[cyan]Starting Synapse dashboard on http://{host}:{port}...[/cyan]")
    uvicorn.run("synapse.dashboard.backend_app:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    app()
