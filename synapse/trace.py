# synapse/trace.py
import sqlite3, json, time, os
from typing import Optional

DB_PATH = os.path.join(os.getcwd(), "synapse_traces.db")

class TraceStore:
    """
    Very small sqlite-backed tracer.
    Tables:
        - runs(run_id, started_at, workflow_name)
        - nodes(id, run_id, agent_id, name, input_json, output_json, duration, attempt, error, ts, model)
        - contexts(run_id, version, node_name, ctx_json, ts)
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()
        self.current_run_id = None

    def _init_db(self):
        c = self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, started_at REAL, workflow TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                agent_id TEXT,
                name TEXT,
                input_json TEXT,
                output_json TEXT,
                duration REAL,
                attempt INTEGER,
                error TEXT,
                ts REAL,
                model TEXT
            )""")
        c.execute("""CREATE TABLE IF NOT EXISTS contexts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                version INTEGER,
                node_name TEXT,
                ctx_json TEXT,
                ts REAL
            )""")
        self.conn.commit()

    def start_run(self, run_id: str, workflow: str):
        self.current_run_id = run_id
        c = self.conn.cursor()
        c.execute("INSERT OR REPLACE INTO runs (run_id, started_at, workflow) VALUES (?,?,?)",
                  (run_id, time.time(), workflow))
        self.conn.commit()

    def record_node(self, run_id, agent_id, name, input_ctx, output, duration, attempt, model):
        c = self.conn.cursor()
        c.execute("""INSERT INTO nodes (run_id, agent_id, name, input_json, output_json, duration, attempt, error, ts, model)
                     VALUES (?,?,?,?,?,?,?,?,?,?)""",
                  (run_id, agent_id, name, json.dumps(input_ctx), json.dumps(output), float(duration), int(attempt), None, time.time(), model))
        self.conn.commit()

    def record_error(self, run_id, agent_id, name, error, stack, duration, attempt, model):
        c = self.conn.cursor()
        err_obj = {"error": error, "stack": stack}
        c.execute("""INSERT INTO nodes (run_id, agent_id, name, input_json, output_json, duration, attempt, error, ts, model)
                     VALUES (?,?,?,?,?,?,?,?,?,?)""",
                  (run_id, agent_id, name, json.dumps({}), json.dumps({}), float(duration), int(attempt), json.dumps(err_obj), time.time(), model))
        self.conn.commit()

    def record_context_version(self, run_id, version, node_name, ctx):
        c = self.conn.cursor()
        c.execute("INSERT INTO contexts (run_id, version, node_name, ctx_json, ts) VALUES (?,?,?,?,?)",
                  (run_id, int(version), node_name, json.dumps(ctx), time.time()))
        self.conn.commit()

    def fetch_runs(self, limit=50):
        c = self.conn.cursor()
        c.execute("SELECT run_id, started_at, workflow FROM runs ORDER BY started_at DESC LIMIT ?", (limit,))
        return [{"run_id": r[0], "started_at": r[1], "workflow": r[2]} for r in c.fetchall()]

    def fetch_nodes(self, run_id, limit=500):
        c = self.conn.cursor()
        c.execute("SELECT id, agent_id, name, input_json, output_json, duration, attempt, error, ts, model FROM nodes WHERE run_id=? ORDER BY ts ASC LIMIT ?", (run_id, limit))
        out = []
        for r in c.fetchall():
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

    def fetch_contexts(self, run_id):
        c = self.conn.cursor()
        c.execute("SELECT version, node_name, ctx_json, ts FROM contexts WHERE run_id=? ORDER BY version ASC", (run_id,))
        return [{"version": r[0], "node": r[1], "ctx": json.loads(r[2]), "ts": r[3]} for r in c.fetchall()]