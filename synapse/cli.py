# synapse/cli.py
import os
import subprocess
import sys
import time

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from .orchestrator import Orchestrator
from typing import Optional

app = typer.Typer()
console = Console()

# mock cost tracking for now
MODEL_COSTS = {"gpt-4": 0.03, "gpt-3.5-turbo": 0.002, "mock": 0.0}


def format_duration(seconds: float) -> str:
    """Format duration in seconds to readable string."""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    return f"{seconds:.1f}s"


def calculate_cost(model: str, tokens: int = 0) -> float:
    """Calculate cost based on model and token usage."""
    # For now, return 0 or mock cost based on model
    # In real implementation, track actual token usage
    return MODEL_COSTS.get(model, 0.0) * (tokens / 1000) if tokens > 0 else 0.001


@app.command()
def run(
    workflow: str = typer.Argument(..., help="Path to workflow YAML file"),
    prompt: str = typer.Option(..., "--prompt", "-p", help="Initial prompt/input"),
    ui: bool = typer.Option(False, "--ui", "-u", help="Start dashboard UI server"),
    port: int = typer.Option(8000, "--port", help="Port for dashboard UI"),
):
    """
    Run a Synapse workflow.

    Example:
        synapse run pipeline.yaml --prompt "research neural rendering"
        synapse run pipeline.yaml --prompt "research neural rendering" --ui
    """

    # check if workflow file exists
    if not os.path.exists(workflow):
        console.print(f"[red]Error:[/red] workflow file not found: {workflow}")
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
                status_text = f"retry #{attempts-1} failed ({result.get('error_type', 'error')}), retry #{attempts} success"
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
):
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
