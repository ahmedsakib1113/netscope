"""Measurement types; missing observations are represented by None, never zero."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Counter:
    received: int
    sent: int
    is_up: bool


@dataclass(frozen=True)
class InterfaceSample:
    timestamp: float
    interface: str
    is_up: bool
    bytes_received: int
    bytes_sent: int
    elapsed_seconds: float | None
    download_mbps: float | None
    upload_mbps: float | None
    quality: str


@dataclass(frozen=True)
class ProbeBatch:
    timestamp: float
    target: str
    sent: int
    received: int
    min_ms: float | None
    mean_ms: float | None
    max_ms: float | None
    statuses: str
    error: str | None = None

    @property
    def loss_percent(self) -> float | None:
        if self.error or not self.sent:
            return None
        return 100.0 * (self.sent - self.received) / self.sent
