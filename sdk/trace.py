import sqlite3, json, time

class Trace:
    def __init__(self, db="traces.db"):
        self.conn = sqlite3.connect(db, check_same_thread=False)
        self._init()
    def _init(self):
        c = self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXIST nodes (id TEXT, name TEXT, input TEXT, output TEXT, duration REAL, attempt INT, ts REAL)""")
        self.conn.commit()
    def record(self, id, name, input_ctx, output, duration, attempt):
        c = self.conn.cursor()
        c.execute("INSERT INTO nodes VALUES (?,?,?,?,?,?,?)", (id, name, json.dumps(input_ctx), json.dumps(output), duration, attempt, time.time()))
        self.conn.commit()
    def record_error(self, id, name, error, attempt):
        self.record(id, name, {"error": error}, {"error": error},0,attempt)