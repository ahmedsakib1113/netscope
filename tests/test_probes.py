import json
from types import SimpleNamespace

import pytest

from netscope import probes


def test_mixed_replies_use_successful_rtt_only():
    result = probes.summarize(1, "1.1.1.1", [
        {"status": "Success", "ms": 0}, {"status": "TimedOut", "ms": 0},
        {"status": "Success", "ms": 20}, {"status": "DestinationHostUnreachable", "ms": 0},
    ])
    assert result.sent == 4
    assert result.received == 2
    assert result.mean_ms == 10
    assert result.min_ms == 0
    assert result.max_ms == 20
    assert result.loss_percent == 50


def test_all_timeouts_have_no_latency():
    result = probes.summarize(1, "1.1.1.1", [{"status": "TimedOut", "ms": 0} for _ in range(4)])
    assert result.mean_ms is None
    assert result.loss_percent == 100


def test_execution_error_is_not_packet_loss():
    result = probes.summarize(1, "1.1.1.1", [{"status": "Error", "error": "Permission denied"}])
    assert result.sent == 0
    assert result.loss_percent is None
    assert result.error == "Permission denied"


@pytest.mark.parametrize("target", ["example.com", "1.1.1.1; calc", "0.0.0.0", "224.0.0.1", "::", "fe80::1%3"])
def test_invalid_or_unsafe_targets(target):
    with pytest.raises(ValueError):
        probes.validate_target(target)


@pytest.mark.parametrize("target", ["1.1.1.1", "127.0.0.1", "2606:4700:4700::1111"])
def test_numeric_targets(target):
    assert probes.validate_target(target) == target


@pytest.mark.skipif(probes.os.name != "nt", reason="Windows subprocess adapter")
def test_windows_adapter_reads_structured_output(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured.update(args=args, kwargs=kwargs)
        return SimpleNamespace(stdout=json.dumps([{"status": "Success", "ms": 12, "error": None}]))

    monkeypatch.setattr(probes.subprocess, "run", fake_run)
    result = probes.probe("1.1.1.1", count=1)
    assert result.mean_ms == 12
    assert result.loss_percent == 0
    assert "shell" not in captured["kwargs"]
    assert captured["kwargs"]["timeout"] > 0


@pytest.mark.skipif(probes.os.name != "nt", reason="Windows subprocess adapter")
def test_malformed_output_becomes_measurement_error(monkeypatch):
    monkeypatch.setattr(probes.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="not JSON"))
    result = probes.probe("1.1.1.1")
    assert result.error
    assert result.loss_percent is None
