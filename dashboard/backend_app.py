# dashboard/backend_app.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import sqlite3, json, os
from fastapi.templating import Jinja2Templates
from fastapi import Request

DB = os.path.join(os.getcwd(), "synapse_traces.db")
app = FastAPI()
templates = Jinja2Templates(directory=os.path.join(os.getcwd(), "dashboard", "templates"))

@app.get("/api/runs")
def runs(limit: int = 50):
    if not os.path.exists(DB):
        return []
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT run_id, started_at, workflow FROM runs ORDER BY started_at DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    out = [{"run_id": r[0], "started_at": r[1], "workflow": r[2]} for r in rows]
    return out

@app.get("/api/nodes/{run_id}")
def nodes(run_id: str):
    if not os.path.exists(DB):
        raise HTTPException(status_code=404, detail="DB not found")
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT id, agent_id, name, input_json, output_json, duration, attempt, error, ts, model FROM nodes WHERE run_id=? ORDER BY ts ASC", (run_id,))
    rows = cur.fetchall()
    out = []
    for r in rows:
        out.append({
            "id": r[0],
            "agent_id": r[1],
            "name": r[2],
            "input": json.loads(r[3]) if r[3] else {},
            "output": json.loads(r[4]) if r[4] else {},
            "duration": r[5],
            "attempt": r[6],
            "error": json.loads(r[7]) if r[7] else None,
            "ts": r[8],
            "model": r[9],
        })
    return out

@app.get("/api/contexts/{run_id}")
def contexts(run_id: str):
    if not os.path.exists(DB):
        raise HTTPException(status_code=404, detail="DB not found")
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT version, node_name, ctx_json, ts FROM contexts WHERE run_id=? ORDER BY version ASC", (run_id,))
    rows = cur.fetchall()
    out = [{"version": r[0], "node": r[1], "ctx": json.loads(r[2]), "ts": r[3]} for r in rows]
    return out

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    # simple UI served from template
    return templates.TemplateResponse("index.html", {"request": request})
