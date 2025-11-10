import typer
from .orchestrator import Orchestrator

app = typer.Typer()

@app.command()
def run(workflow: str, prompt: str):
    orch = Orchestrator(workflow)
    res = orch.run(prompt)
    print("Done. last output:", res.get('last_output'))

if __name__=="__main__":
    app()