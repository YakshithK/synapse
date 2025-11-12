# synapse/cli.py
import typer
from .orchestrator import Orchestrator
import uvicorn
import os

app = typer.Typer()

@app.command()
def run(workflow: str, prompt: str = typer.Option(..., help="initial prompt/input")):
    """
    Run a YAML workflow locally.
    Example:
      python -m synapse.cli run examples/research.yml --prompt "neural rendering"
    """
    # ensure path exists
    if not os.path.exists(workflow):
        raise typer.Exit(message=f"workflow file not found: {workflow}")
    orch = Orchestrator(workflow)
    res = orch.run(prompt)
    typer.echo(f"Run complete. run_id={res['run_id']}")
    typer.echo(f"Final context: {res['final_context']}")

@app.command()
def serve_dashboard(host: str = "127.0.0.1", port: int = 8080):
    """
    Launch the local FastAPI dashboard (thin proxy to sqlite traces)
    """
    uvicorn.run("dashboard.backend_app:app", host=host, port=port, reload=True)

if __name__ == "__main__":
    app()