import sqlite3

import pytest

from netscope.locking import collector_lock
from netscope.storage import Store


def test_persistence_nulls_and_integrity(recorded_store):
    original, session = recorded_store
    store = Store(original.path)
    samples, probes = store.history(session, "Wi-Fi", 15)
    assert samples[0]["download_mbps"] is None
    assert samples[1]["download_mbps"] == 4
    assert probes[0]["loss_percent"] == 25
    with store.connect(readonly=True) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM sessions")


def test_sessions_and_interfaces_are_isolated(recorded_store):
    store, session = recorded_store
    other = store.start_session("127.0.0.1", 1, 10)
    assert store.interfaces(session) == ["Wi-Fi"]
    assert store.interfaces(other) == []
    assert store.history(other, "Wi-Fi", 15) == ([], [])
    # Parameterized interface lookup cannot change the SQL query.
    assert store.history(session, "' OR 1=1 --", 15)[0] == []
    store.finish_session(session)
    assert next(s for s in store.sessions() if s["id"] == session)["ended_at"] is not None


def test_single_collector_lock_releases_after_error(tmp_path):
    path = tmp_path / "lock.sqlite3"
    with pytest.raises(ValueError):
        with collector_lock(path):
            with pytest.raises(RuntimeError, match="Another collector"):
                with collector_lock(path):
                    pass
            raise ValueError("stop")
    with collector_lock(path):
        pass


def test_future_schema_is_rejected(tmp_path):
    store = Store(tmp_path / "future.sqlite3")
    with store.connect() as conn:
        conn.execute("PRAGMA user_version=99")
    with pytest.raises(RuntimeError, match="Unsupported"):
        store.initialize()
