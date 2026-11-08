"""Versioned SQLite storage with short writes and read-only dashboard connections."""

from contextlib import contextmanager
from dataclasses import astuple
from pathlib import Path
import sqlite3
import time
import uuid

from netscope.models import InterfaceSample, ProbeBatch


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "netscope.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    started_at REAL NOT NULL,
    ended_at REAL,
    target TEXT NOT NULL,
    sample_interval REAL NOT NULL,
    probe_interval REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS interface_samples (
    session_id TEXT NOT NULL REFERENCES sessions(id),
    timestamp REAL NOT NULL,
    interface TEXT NOT NULL,
    is_up INTEGER NOT NULL,
    bytes_received INTEGER NOT NULL,
    bytes_sent INTEGER NOT NULL,
    elapsed_seconds REAL,
    download_mbps REAL,
    upload_mbps REAL,
    quality TEXT NOT NULL,
    PRIMARY KEY (session_id, timestamp, interface)
);
CREATE TABLE IF NOT EXISTS probe_batches (
    session_id TEXT NOT NULL REFERENCES sessions(id),
    timestamp REAL NOT NULL,
    target TEXT NOT NULL,
    sent INTEGER NOT NULL,
    received INTEGER NOT NULL CHECK (received <= sent),
    min_ms REAL,
    mean_ms REAL,
    max_ms REAL,
    statuses TEXT NOT NULL,
    error TEXT,
    loss_percent REAL,
    PRIMARY KEY (session_id, timestamp)
);
CREATE INDEX IF NOT EXISTS samples_lookup ON interface_samples(session_id, interface, timestamp);
"""


class Store:
    def __init__(self, path: Path | str = DEFAULT_DB):
        self.path = Path(path).resolve()

    @contextmanager
    def connect(self, *, readonly: bool = False):
        if readonly:
            conn = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=5)
        else:
            conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            if not readonly:
                conn.commit()
        except BaseException:
            if not readonly:
                conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise RuntimeError(f"Unsupported database schema version {version}")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            conn.execute("PRAGMA user_version=1")

    def start_session(self, target: str, interval: float, probe_interval: float) -> str:
        session = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute("INSERT INTO sessions VALUES (?, ?, NULL, ?, ?, ?)",
                         (session, time.time(), target, interval, probe_interval))
        return session

    def finish_session(self, session: str):
        with self.connect() as conn:
            conn.execute("UPDATE sessions SET ended_at=? WHERE id=?", (time.time(), session))

    def save_samples(self, session: str, samples: list[InterfaceSample]):
        with self.connect() as conn:
            conn.executemany("INSERT INTO interface_samples VALUES (?,?,?,?,?,?,?,?,?,?)",
                             [(session, *astuple(sample)) for sample in samples])

    def save_probe(self, session: str, batch: ProbeBatch):
        with self.connect() as conn:
            conn.execute("INSERT INTO probe_batches VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (session, *astuple(batch), batch.loss_percent))

    def sessions(self) -> list[dict]:
        with self.connect(readonly=True) as conn:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT 30")]

    def interfaces(self, session: str) -> list[str]:
        with self.connect(readonly=True) as conn:
            return [row[0] for row in conn.execute(
                "SELECT DISTINCT interface FROM interface_samples WHERE session_id=? ORDER BY interface",
                (session,))]

    def history(self, session: str, interface: str, minutes: int) -> tuple[list[dict], list[dict]]:
        with self.connect(readonly=True) as conn:
            end = conn.execute(
                "SELECT MAX(timestamp) FROM interface_samples WHERE session_id=?", (session,)
            ).fetchone()[0] or time.time()
            start = end - minutes * 60
            samples = [dict(row) for row in conn.execute(
                "SELECT * FROM (SELECT * FROM interface_samples WHERE session_id=? "
                "AND interface=? AND timestamp>=? ORDER BY timestamp DESC LIMIT 5000) "
                "ORDER BY timestamp", (session, interface, start))]
            probes = [dict(row) for row in conn.execute(
                "SELECT * FROM (SELECT * FROM probe_batches WHERE session_id=? AND timestamp>=? "
                "ORDER BY timestamp DESC LIMIT 1000) ORDER BY timestamp", (session, start))]
        return samples, probes
