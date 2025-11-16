# synapse/trace.py
import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

DB_PATH = os.path.join(os.getcwd(), "synapse_traces.db")


class TraceStore:
    """
    Very small sqlite-backed tracer.
    Tables:
        - runs(run_id, started_at, workflow_name)
        - nodes(id, run_id, agent_id, name, input_json,
                output_json, duration, attempt, error, ts, model, metadata)
        - contexts(run_id, version, node_name, ctx_json, ts)
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or DB_PATH
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()
        self.current_run_id: Optional[str] = None

    def _init_db(self) -> None:
        c = self.conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY,
                started_at REAL, workflow TEXT)"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS nodes (
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
                model TEXT,
                metadata TEXT
            )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS contexts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                version INTEGER,
                node_name TEXT,
                ctx_json TEXT,
                ts REAL
            )"""
        )
        self.conn.commit()

        # Migrate existing database: add metadata column if it doesn't exist
        self._migrate_db()

    def _migrate_db(self) -> None:
        """Migrate database schema to add metadata column if it doesn't exist."""
        c = self.conn.cursor()

        # Check if metadata column exists in nodes table
        try:
            c.execute("PRAGMA table_info(nodes)")
            columns = [row[1] for row in c.fetchall()]

            if "metadata" not in columns:
                # Add metadata column
                c.execute("ALTER TABLE nodes ADD COLUMN metadata TEXT")
                self.conn.commit()
        except Exception:
            """
            If table doesn't exist or other error, that's okay,
            it will be created with the correct schema
            """
            pass

    def start_run(self, run_id: str, workflow: str) -> None:
        self.current_run_id = run_id
        c = self.conn.cursor()
        c.execute(
            """INSERT OR REPLACE INTO runs (run_id, started_at, workflow)
            VALUES (?,?,?)""",
            (run_id, time.time(), workflow),
        )
        self.conn.commit()

    def record_node(
        self,
        run_id: str,
        agent_id: str,
        name: str,
        input_ctx: Dict[str, Any],
        output: Dict[str, Any],
        duration: float,
        attempt: int,
        model: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        c = self.conn.cursor()
        metadata_json = json.dumps(metadata) if metadata else None
        c.execute(
            """INSERT INTO nodes (run_id, agent_id, name, input_json, output_json,
                    duration, attempt, error, ts, model, metadata)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run_id,
                agent_id,
                name,
                json.dumps(input_ctx),
                json.dumps(output),
                float(duration),
                int(attempt),
                None,
                time.time(),
                model,
                metadata_json,
            ),
        )
        self.conn.commit()

    def record_error(
        self,
        run_id: str,
        agent_id: str,
        name: str,
        error: str,
        stack: str,
        duration: float,
        attempt: int,
        model: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        c = self.conn.cursor()
        err_obj = {"error": error, "stack": stack}
        metadata_json = json.dumps(metadata) if metadata else None
        c.execute(
            """INSERT INTO nodes (run_id, agent_id, name, input_json, output_json,
                    duration, attempt, error, ts, model, metadata)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run_id,
                agent_id,
                name,
                json.dumps({}),
                json.dumps({}),
                float(duration),
                int(attempt),
                json.dumps(err_obj),
                time.time(),
                model,
                metadata_json,
            ),
        )
        self.conn.commit()

    def record_context_version(
        self, run_id: str, version: int, node_name: str, ctx: Dict[str, Any]
    ) -> None:
        c = self.conn.cursor()
        c.execute(
            """INSERT INTO contexts (run_id, version,
            node_name, ctx_json, ts) VALUES (?,?,?,?,?)""",
            (run_id, int(version), node_name, json.dumps(ctx), time.time()),
        )
        self.conn.commit()

    def fetch_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        c = self.conn.cursor()
        c.execute(
            """SELECT run_id, started_at,
            workflow FROM runs ORDER BY started_at DESC LIMIT ?""",
            (limit,),
        )
        return [
            {"run_id": r[0], "started_at": r[1], "workflow": r[2]} for r in c.fetchall()
        ]

    def fetch_nodes(self, run_id: str, limit: int = 500) -> List[Dict[str, Any]]:
        c = self.conn.cursor()
        # Check if metadata column exists to handle both old and new schemas
        try:
            c.execute("PRAGMA table_info(nodes)")
            columns = [row[1] for row in c.fetchall()]
            has_metadata = "metadata" in columns

            if has_metadata:
                c.execute(
                    """SELECT id, agent_id, name, input_json,
                    output_json, duration, attempt, error, ts, model, metadata
                    FROM nodes WHERE run_id=? ORDER BY ts ASC LIMIT ?""",
                    (run_id, limit),
                )
            else:
                c.execute(
                    """SELECT id, agent_id, name, input_json,
                    output_json, duration, attempt, error, ts, model
                    FROM nodes WHERE run_id=? ORDER BY ts ASC LIMIT ?""",
                    (run_id, limit),
                )

            out = []
            for r in c.fetchall():
                node = {
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
                }
                if has_metadata:
                    node["metadata"] = json.loads(r[10]) if r[10] else None
                else:
                    node["metadata"] = None
                out.append(node)
            return out
        except Exception:
            # Fallback to old schema if error occurs
            c.execute(
                """SELECT id, agent_id, name, input_json, output_json,
                duration, attempt, error, ts, model FROM nodes
                WHERE run_id=? ORDER BY ts ASC LIMIT ?""",
                (run_id, limit),
            )
            out = []
            for r in c.fetchall():
                out.append(
                    {
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
                        "metadata": None,
                    }
                )
            return out

    def fetch_contexts(self, run_id: str) -> List[Dict[str, Any]]:
        c = self.conn.cursor()
        c.execute(
            """SELECT version, node_name, ctx_json, ts
            FROM contexts WHERE run_id=? ORDER BY version ASC""",
            (run_id,),
        )
        return [
            {"version": r[0], "node": r[1], "ctx": json.loads(r[2]), "ts": r[3]}
            for r in c.fetchall()
        ]
