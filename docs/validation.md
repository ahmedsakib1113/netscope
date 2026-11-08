# Validation

Verified locally on **6 November 2026** with Windows, Python 3.12.7 and the exact dependency versions in `requirements-lock.txt`. Automated tests use deterministic fixtures and remain distinct from live observations. GitHub Actions is provided but has not been run remotely.

## Automated checks

```text
python -m pytest -q
30 passed in 3.70s

python -m pip check
No broken requirements found.
```

The tests exercise actual storage and Streamlit app rendering with controlled counter/probe inputs. They cover counter reset/reconnect behavior, elapsed-time calculations, zero versus missing values, ICMP aggregation, validation, permission errors, weighted loss, SQL persistence/isolation, read-only connections, OS collector locking, clean shutdown and dashboard controls.

The restricted development environment blocks Windows local sockets. Streamlit's AppTest harness initially stalled while creating an asyncio socket pair; the same suite completed with local socket permission. No application workaround or test skip was added for this environment restriction.

## Live Windows capture

Run: `python -m netscope collect --duration 60`, default settings, from **11:39:14 to 11:40:14 Malaysia time (UTC+8)**, equivalent to 03:39:14–03:40:14 UTC.

| Observation | Result |
| --- | --- |
| Interfaces recorded separately | 6, including Wi-Fi and a VPN adapter |
| Wi-Fi observations | 29, including the initial baseline |
| Observed Wi-Fi download range | 1.66–55.61 Mbps over valid sample intervals |
| Target | `1.1.1.1`, following Windows routing |
| Probe batches | 6 × 4 echo requests |
| Successful echo replies | 24 of 24 |
| Observed probe loss | 0% for this short recording |
| Batch mean RTT range | 37.75–62.00 ms |
| SQLite integrity check | `ok` |
| Foreign-key violations | 0 |
| Session closed at bounded stop | Yes |

These are observations from one short session, not a performance guarantee. The presence of a VPN means the probe route need not match the Wi-Fi adapter's physical path. No traffic-generation load test or speed test was performed.

A separate earlier restricted run saved real interface counters but returned `Access is denied` for ICMP. Those probe batches have missing loss/RTT estimates and explicit errors rather than fabricated loss values. Both recordings remain in the ignored local database for inspection.

## Browser → data → displayed result

| Boundary | Evidence |
| --- | --- |
| Dashboard server | Local `/_stcore/health` returned `ok` |
| SQLite → cards | Last saved Wi-Fi rates displayed as 5.01 Mbps down / 0.20 Mbps up; last batch RTT 38.25 ms; window loss 0.00% |
| SQLite → charts | Browser rendered traffic, six RTT values and six 0% loss points |
| Historical status | Stopped session explicitly displayed as historical, with probe age |
| History controls | Automated interface/history-window checks and browser recorded-data tab |
| CSV export | Browser download produced 29 Wi-Fi rows; checked against stored values |
| Browser console | No captured error-level messages |

Screenshots: [overview](dashboard-overview.png), [charts](dashboard-charts.png). The temporary preview server and bounded collector were stopped after verification. Reopen them using the launch files or README commands.

## Remaining boundaries

Live collection currently targets Windows; other platforms receive an explicit unsupported ICMP measurement error. Retention, background-service installation, anomaly detection and switch telemetry remain future work. The public GitHub Pages preview explores a recorded session; the full Streamlit dashboard and Windows collector run locally using the README instructions.
