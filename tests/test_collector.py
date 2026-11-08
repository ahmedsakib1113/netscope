from threading import Event

from netscope import collector
from netscope.models import Counter, ProbeBatch
from netscope.storage import Store


def test_collection_persists_and_closes_session(tmp_path, monkeypatch):
    ticks = iter([0, 0, 0, 0, 0.6, 0.6, 0.6, 1.2])
    monkeypatch.setattr(collector.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(collector, "read_counters", lambda: {"Wi-Fi": Counter(100, 200, True)})
    monkeypatch.setattr(collector, "probe", lambda *a: ProbeBatch(1000, "1.1.1.1", 1, 1, 2, 2, 2, "Success"))
    store = Store(tmp_path / "collector.sqlite3")
    session = collector.collect(store, target="1.1.1.1", duration=1, interval=0.5)
    samples, probes = store.history(session, "Wi-Fi", 60)
    assert len(samples) == 2
    assert samples[0]["quality"] == "baseline"
    assert samples[1]["download_mbps"] == 0
    # Probe timestamp is synthetic, so query it without the time window.
    with store.connect(readonly=True) as conn:
        assert conn.execute("SELECT COUNT(*) FROM probe_batches").fetchone()[0] >= 1
    assert store.sessions()[0]["ended_at"] is not None


def test_stop_signal_still_finalizes_session(tmp_path):
    stop = Event()
    stop.set()
    store = Store(tmp_path / "stop.sqlite3")
    collector.collect(store, target="1.1.1.1", stop=stop)
    assert store.sessions()[0]["ended_at"] is not None
