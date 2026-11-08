# Design decisions

## Independent collector and dashboard

The collector is a CLI process; Streamlit reads stored observations. Refreshes and browser sessions never start another sampler. This avoids duplicate collection on UI reruns and keeps recording independent of a browser tab. The tradeoff is two terminals rather than an integrated background service.

## Interface throughput

`psutil.net_io_counters(pernic=True, nowrap=False)` supplies raw counters. A monotonic clock measures elapsed intervals; the wall clock timestamps observations for history. The first sample and a reset/down/reappearing interface establish a baseline without a rate. This avoids negative or fabricated spikes. Counter resets that return to a larger value between polls cannot be detected reliably from counters alone.

Loopback adapters are excluded by common Windows/Linux names. Adapter records remain separate. Virtual and VPN adapters may account for the same underlying traffic; summing them would overstate throughput. The UI defaults to Wi-Fi when present but supports choosing any recorded adapter.

## Structured Windows ICMP

The approved Windows ping measurement uses the .NET `Ping` class from Windows PowerShell. JSON results avoid parsing translated `ping.exe` output. Numeric IP validation keeps target values separate from executable input; the process uses an argument list, never `shell=True`. Numeric IPs also keep DNS lookup time out of RTT measurements.

Success, timeout and unreachable responses are completed probe attempts. Invocation/permission failures are measurement errors and invalidate the batch's loss estimate. Successful RTTs determine min/mean/max. Reported loss applies to echo probes and is not a direct estimate of all application packet loss.

One background worker runs a bounded batch at a time. The main thread persists completed results, independently polls counters, and responds to Ctrl+C. Shutdown can wait for the in-flight subprocess (bounded by `count × (timeout + 0.2s) + 10s`). Missed probe periods are not queued for a burst later.

## SQLite and freshness

Schema version 1 stores `sessions`, `interface_samples` and `probe_batches`, with foreign keys and indexes for session/interface/time queries. WAL permits short writes alongside read-only dashboard queries. A per-database OS file lock prevents two collectors from writing overlapping sessions and releases on process exit, including crashes. It is a local process lock; distributed file systems are not a deployment target.

Read-only dashboard queries cap the visible history. Freshness depends on measurement timestamps, not a process-alive claim. A session with `ended_at` is stopped. An unclosed session becomes stale after the larger of ten seconds or three sample periods. Probe freshness is displayed separately because a worker may fail while interface collection continues.

The collector uses one process and one ICMP worker, not a service, container or remote server. Persistence has no automatic retention yet. A live SQLite database should be kept outside cloud-synced folders for long-term use; `--db` and `NETSCOPE_DB` support this.

## Phase boundaries

Phase 1 does not capture packets, inventory network devices, attribute application traffic, infer physical topology, calculate a speed-test capacity, or train an anomaly detector. Those require different inputs and evaluation. The project remains local; repository creation and publication are separate user decisions.
