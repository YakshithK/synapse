# synapse/cli.py
import functools
import json
import os
import select
import sys
import termios
import threading
import tty
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import typer
import uvicorn
from rich.console import Console

from .orchestrator import Orchestrator

app = typer.Typer()
console = Console()

# mock cost tracking for now
MODEL_COSTS = {"gpt-4": 0.03, "gpt-3.5-turbo": 0.002, "mock": 0.0}


PROJECT_CONFIG_FILE = ".synapse/config.json"


def getch(
    timeout: float = 0.1,
) -> Optional[str]:  # Reduced timeout for more responsive log updates
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if rlist:
            ch = sys.stdin.read(1)
            if ch == "\x03":  # Ctrl+C
                raise KeyboardInterrupt()
            return ch
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


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


def is_initialized() -> bool:
    """Check if the project is initialized by looking for the config file."""
    return Path(PROJECT_CONFIG_FILE).exists()


def ensure_initialized() -> None:
    """Ensure the project is intiialized, or exit with an error."""
    if not is_initialized():
        console.print(
            "[red]Error:[/red] Project not initialized. \
            Please run 'synapse init' first."
        )
        raise typer.Exit(1)


@app.command()
def init() -> None:
    """
    Initialize a new Synapse project with demo agents.

    Creates an agents/ directory with summarize.py and classify.py demo
    agents.
    """
    if is_initialized():
        console.print("[yellow]Project is already initialized.[/yellow]")
        raise typer.Exit(1)

    console.print("[cyan]Initializing Synapse project...[/cyan]\n")

    # Create .synapse dir
    config_dir = Path(".synapse")
    config_dir.mkdir(exist_ok=True)

    # Create config file
    config = {"version": "1.0", "initialized_at": datetime.now().isoformat()}

    Path(PROJECT_CONFIG_FILE).write_text(json.dumps(config, indent=2))

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


def requires_init(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to ensure the project is initialized before running a command."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        ensure_initialized()
        return func(*args, **kwargs)

    return wrapper


@app.command()
@requires_init
def run(
    workflow: str = typer.Argument(..., help="Path to workflow YAML file"),
    prompt: str = typer.Option(..., "--prompt", "-p", help="Initial prompt/input"),
) -> None:
    """
    Run a Synapse workflow.

    Example:
        synapse run pipeline.yaml --prompt "research neural rendering"
    """

    # check if workflow file exists
    if not os.path.exists(workflow):
        console.print(
            f"[red]Error:[/red] workflow \
        file not found: {workflow}"
        )
        raise typer.Exit(1)

    try:
        # initialize orchestrator
        orch = Orchestrator(workflow)

        # run workflow
        console.print("[cyan]Starting workflow execution...[/cyan]")
        console.print(f"[dim]Workflow: {workflow}[/dim]")
        console.print(f"[dim]Run ID: {orch.run_id}[/dim]\n")
        console.print("[green]✓[/green] Your process is running in the background.")
        console.print(
            "\n[yellow]💡 Tip:[/yellow] Type [cyan]synapse logs[/cyan] to see "
            "real-time execution logs"
        )
        console.print(
            "[dim]The workflow will continue running in the background.[/dim]\n"
        )

        def run_workflow() -> None:
            try:
                # Run the workflow (result is captured via orchestrator state)
                orch.run(prompt)

                # Save execution results to a file for logs command
                execution_results = orch.get_execution_results()

                # Create logs directory if it doesn't exist
                logs_dir = Path(".synapse/logs")
                logs_dir.mkdir(parents=True, exist_ok=True)

                # Save run details
                run_data = {
                    "run_id": orch.run_id,
                    "workflow": workflow,
                    "prompt": prompt,
                    "start_time": datetime.now().isoformat(),
                    "status": "running",
                    "results": execution_results,
                }

                run_file = logs_dir / f"run_{orch.run_id}.json"
                run_file.write_text(json.dumps(run_data, indent=2))

                # Update status when complete
                run_data["status"] = "completed"
                run_data["end_time"] = datetime.now().isoformat()
                run_file.write_text(json.dumps(run_data, indent=2))

            except Exception as e:
                # Save error information
                error_data = {
                    "run_id": orch.run_id,
                    "workflow": workflow,
                    "prompt": prompt,
                    "start_time": datetime.now().isoformat(),
                    "status": "failed",
                    "error": str(e),
                }

                logs_dir = Path(".synapse/logs")
                logs_dir.mkdir(parents=True, exist_ok=True)
                run_file = logs_dir / f"run_{orch.run_id}.json"
                run_file.write_text(json.dumps(error_data, indent=2))

        # Start the workflow in a background thread
        thread = threading.Thread(target=run_workflow)
        thread.start()

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command()
@requires_init
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


@app.command()
@requires_init
def logs(
    follow: bool = typer.Option(
        True, "--follow", "-f", help="Follow logs in real-time"
    ),
    run_id: str = typer.Option(None, "--run-id", "-r", help="Specific run ID to view"),
) -> None:
    """
    View Synapse workflow execution logs.

    Shows real-time execution logs for running and completed workflows.

    Examples:
        synapse logs                    # Show latest logs
        synapse logs --follow           # Follow logs in real-time
        synapse logs --run-id abc123    # Show logs for specific run
    """

    logs_dir = Path(".synapse/logs")

    if not logs_dir.exists():
        console.print(
            "[yellow]No logs found. Run a workflow first " "with 'synapse run'[/yellow]"
        )
        raise typer.Exit(1)

    # Find log files
    log_files = list(logs_dir.glob("run_*.json"))

    if not log_files:
        console.print("[yellow]No log files found. Run a workflow first.[/yellow]")
        raise typer.Exit(1)

    # Filter by run_id if specified
    if run_id:
        log_files = [f for f in log_files if f.name == f"run_{run_id}.json"]
        if not log_files:
            console.print(f"[red]No logs found for run ID: {run_id}[/red]")
            raise typer.Exit(1)

    # Sort by modification time (newest first)
    log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    def display_log_file(log_file: Path, show_header: bool = True) -> None:
        try:
            data = json.loads(log_file.read_text())

            if show_header:
                console.print(f"\n[bold cyan]Run ID:[/bold cyan] {data['run_id']}")
                console.print(f"[dim]Workflow:[/dim] {data['workflow']}")
                if "start_time" in data:
                    start_time = datetime.fromisoformat(data["start_time"])
                    console.print(
                        (
                            f"[dim]Started:[/dim] "
                            f"{start_time.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                    )
                if "prompt" in data:
                    prompt = data["prompt"]
                    if len(prompt) > 50:
                        prompt = prompt[:47] + "..."
                    console.print(f"[dim]Prompt:[/dim] '{prompt}'")
                console.print()

            # Display status
            status = data.get("status", "unknown")
            if status == "running":
                status_icon = "[yellow]🔄[/yellow]"
                status_text = "Running"
            elif status == "completed":
                status_icon = "[green]✅[/green]"
                status_text = "Completed"
            elif status == "failed":
                status_icon = "[red]❌[/red]"
                status_text = "Failed"
            else:
                status_icon = "[dim]❓[/dim]"
                status_text = status.capitalize()

            console.print(f"{status_icon} Status: {status_text}")

            # Display results if available
            if "results" in data and data["results"]:
                console.print("\n[bold]Execution Results:[/bold]")
                total_cost = 0.0

                for result in data["results"]:
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
                    console.print(
                        f"  {icon} {agent_name}: {status_text} ({duration_str})"
                    )

                console.print(f"\n[bold]💰 Total cost:[/bold] ${total_cost:.3f}")

            # Display error if failed
            if "error" in data:
                console.print(f"\n[red]Error:[/red] {data['error']}")

            # Show end time if available
            if "end_time" in data:
                end_time = datetime.fromisoformat(data["end_time"])
                console.print(
                    (
                        f"\n[dim]Ended:[/dim] "
                        f"{end_time.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                )

        except Exception as e:
            console.print(
                f"[red]Error reading log file {log_file.name}:[/red] {str(e)}"
            )

    # Display the most recent log (or specific run if requested)
    display_log_file(log_files[0])

    # Follow mode - keep updating
    if follow and not run_id:
        console.print("\n[dim]Following logs... Press Ctrl+C to exit[/dim]")
        last_mtime = log_files[0].stat().st_mtime

        try:
            while True:
                getch(timeout=0.1)

                # Check for new logs or updates
                current_log_files = list(logs_dir.glob("run_*.json"))
                current_log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

                if current_log_files:
                    current_mtime = current_log_files[0].stat().st_mtime

                    # If there's a newer log or the current log was updated
                    if (
                        current_mtime > last_mtime
                        or current_log_files[0] != log_files[0]
                    ):
                        console.print("\n[dim]--- Updated ---[/dim]\n")
                        display_log_file(current_log_files[0])
                        last_mtime = current_mtime
                        log_files[0] = current_log_files[0]

                        # Stop following if completed
                        try:
                            data = json.loads(current_log_files[0].read_text())
                            if data.get("status") in ["completed", "failed"]:
                                console.print(
                                    (
                                        f"\n[dim]Workflow {data['status']}. "
                                        "Stopping follow...[/dim]"
                                    )
                                )
                                break
                        except Exception:
                            pass
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped following logs[/dim]")


if __name__ == "__main__":
    app()
