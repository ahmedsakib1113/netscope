"""Small display calculations shared by the dashboard and tests."""


def weighted_loss(probes: list[dict]) -> float | None:
    valid = [p for p in probes if not p["error"] and p["sent"] > 0]
    sent = sum(p["sent"] for p in valid)
    received = sum(p["received"] for p in valid)
    return 100 * (sent - received) / sent if sent else None


def collector_state(session: dict, latest_timestamp: float, now: float) -> str:
    if session["ended_at"] is not None:
        return "Stopped"
    if now - latest_timestamp > max(10, session["sample_interval"] * 3):
        return "Stale"
    return "Live"
