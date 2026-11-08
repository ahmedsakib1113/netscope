from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "dashboard.py"


def test_empty_dashboard_gives_start_instructions(tmp_path, monkeypatch):
    path = tmp_path / "missing.sqlite3"
    monkeypatch.setenv("NETSCOPE_DB", str(path))
    app = AppTest.from_file(str(APP)).run(timeout=20)
    assert not app.exception
    assert "No measurements yet" in app.info[0].value
    assert not path.exists()  # Dashboard never creates a fake or empty database.


def test_real_database_to_cards_and_interface_selection(recorded_store, monkeypatch):
    store, _ = recorded_store
    monkeypatch.setenv("NETSCOPE_DB", str(store.path))
    app = AppTest.from_file(str(APP)).run(timeout=20)
    assert not app.exception
    assert [m.value for m in app.metric] == ["4.00 Mbps", "2.00 Mbps", "20.00 ms", "25.00 %"]
    assert app.selectbox[1].value == "Wi-Fi"
    app.toggle[0].set_value(False).run(timeout=20)
    app.selectbox[2].select(5).run(timeout=20)
    assert not app.exception
    assert app.metric[0].value == "4.00 Mbps"
