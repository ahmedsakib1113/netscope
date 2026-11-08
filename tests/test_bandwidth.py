import pytest

from netscope.bandwidth import BandwidthSampler
from netscope.models import Counter


def test_actual_elapsed_time_and_units():
    sampler = BandwidthSampler()
    first = sampler.sample({"Wi-Fi": Counter(100, 200, True)}, 10, 1000)[0]
    assert first.download_mbps is None
    # 1 MB over 2.5 seconds = 3.2 decimal Mbps, independent of wall-clock changes.
    result = sampler.sample({"Wi-Fi": Counter(1_000_100, 500_200, True)}, 12.5, 900)[0]
    assert result.download_mbps == pytest.approx(3.2)
    assert result.upload_mbps == pytest.approx(1.6)
    assert result.quality == "ok"


def test_counter_reset_does_not_create_negative_rate():
    sampler = BandwidthSampler()
    sampler.sample({"Ethernet": Counter(1000, 1000, True)}, 1, 1)
    reset = sampler.sample({"Ethernet": Counter(10, 20, True)}, 2, 2)[0]
    assert reset.quality == "counter_reset"
    assert reset.download_mbps is None
    assert sampler.sample({"Ethernet": Counter(20, 30, True)}, 3, 3)[0].quality == "ok"


def test_down_and_reconnected_adapter_need_baseline():
    sampler = BandwidthSampler()
    sampler.sample({"Wi-Fi": Counter(100, 100, True)}, 1, 1)
    assert sampler.sample({"Wi-Fi": Counter(200, 200, False)}, 2, 2)[0].quality == "interface_down"
    result = sampler.sample({"Wi-Fi": Counter(300, 300, True)}, 3, 3)[0]
    assert result.quality == "baseline"
    assert result.download_mbps is None


def test_disappearance_drops_previous_baseline():
    sampler = BandwidthSampler()
    sampler.sample({"Wi-Fi": Counter(100, 100, True)}, 1, 1)
    assert sampler.sample({}, 2, 2) == []
    assert sampler.sample({"Wi-Fi": Counter(500, 500, True)}, 3, 3)[0].quality == "baseline"


def test_zero_interval_is_missing_and_idle_is_zero():
    sampler = BandwidthSampler()
    counters = {"Wi-Fi": Counter(100, 100, True)}
    sampler.sample(counters, 1, 1)
    assert sampler.sample(counters, 1, 2)[0].quality == "invalid_interval"
    idle = sampler.sample(counters, 2, 3)[0]
    assert idle.download_mbps == 0
    assert idle.quality == "ok"


def test_adapters_are_independent():
    sampler = BandwidthSampler()
    sampler.sample({"Wi-Fi": Counter(0, 0, True), "VPN": Counter(0, 0, True)}, 1, 1)
    rates = {s.interface: s.download_mbps for s in sampler.sample(
        {"Wi-Fi": Counter(1_000_000, 0, True), "VPN": Counter(500_000, 0, True)}, 2, 2)}
    assert rates == {"VPN": 4, "Wi-Fi": 8}
