from netscope.analytics import collector_state, weighted_loss


def test_window_loss_weights_requests_and_excludes_errors():
    probes = [
        {"sent": 4, "received": 4, "error": None},
        {"sent": 1, "received": 0, "error": None},
        {"sent": 10, "received": 0, "error": "execution failed"},
    ]
    assert weighted_loss(probes) == 20  # Not the mean of 0% and 100%.
    assert weighted_loss([]) is None
    assert weighted_loss([probes[2]]) is None


def test_fresh_stale_and_stopped_states():
    session = {"ended_at": None, "sample_interval": 2}
    assert collector_state(session, 100, 101) == "Live"
    assert collector_state(session, 100, 200) == "Stale"
    session["ended_at"] = 101
    assert collector_state(session, 100, 101) == "Stopped"
