import pytest

from netscope.models import InterfaceSample, ProbeBatch
from netscope.storage import Store


@pytest.fixture
def recorded_store(tmp_path):
    store = Store(tmp_path / "test.sqlite3")
    store.initialize()
    session = store.start_session("1.1.1.1", 2, 10)
    store.save_samples(session, [
        InterfaceSample(1000, "Wi-Fi", True, 100, 200, None, None, None, "baseline"),
        InterfaceSample(1002, "Wi-Fi", True, 1_000_100, 500_200, 2, 4, 2, "ok"),
    ])
    store.save_probe(session, ProbeBatch(1002, "1.1.1.1", 4, 3, 10, 20, 30, "Success, TimedOut"))
    return store, session
