"""Per-interface counter deltas using a monotonic clock, without adapter aggregation."""

from collections.abc import Mapping

import psutil

from netscope.models import Counter, InterfaceSample


def read_counters() -> dict[str, Counter]:
    stats = psutil.net_if_stats()
    # Expose resets instead of psutil's process-local wrap compensation.
    counters = psutil.net_io_counters(pernic=True, nowrap=False) or {}
    return {
        name: Counter(c.bytes_recv, c.bytes_sent, bool(stats.get(name) and stats[name].isup))
        for name, c in counters.items()
        if "loopback" not in name.lower() and name.lower() != "lo"
    }


class BandwidthSampler:
    def __init__(self) -> None:
        self.previous: dict[str, Counter] = {}
        self.previous_tick: float | None = None

    def sample(
        self, counters: Mapping[str, Counter], tick: float, timestamp: float
    ) -> list[InterfaceSample]:
        elapsed = None if self.previous_tick is None else tick - self.previous_tick
        results = []
        for name, current in sorted(counters.items()):
            previous = self.previous.get(name)
            down = up = None
            if not current.is_up:
                quality = "interface_down"
            elif previous is None or not previous.is_up:
                quality = "baseline"
            elif elapsed is None or elapsed <= 0:
                quality = "invalid_interval"
            elif current.received < previous.received or current.sent < previous.sent:
                quality = "counter_reset"
            else:
                quality = "ok"
                down = (current.received - previous.received) * 8 / elapsed / 1_000_000
                up = (current.sent - previous.sent) * 8 / elapsed / 1_000_000
            results.append(InterfaceSample(
                timestamp, name, current.is_up, current.received, current.sent,
                elapsed, down, up, quality,
            ))
        # A disappearing adapter loses its baseline; reconnects cannot bridge the gap.
        self.previous = dict(counters)
        self.previous_tick = tick
        return results
