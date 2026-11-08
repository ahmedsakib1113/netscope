"""Windows ICMP via .NET Ping, returning JSON independent of OS display language."""

import ipaddress
import json
import os
import statistics
import subprocess
import time

from netscope.models import ProbeBatch


def validate_target(target: str) -> str:
    # Numeric IPs keep execution bounded and avoid DNS latency being mistaken for RTT.
    address = ipaddress.ip_address(target)
    if address.is_unspecified or address.is_multicast or "%" in target:
        raise ValueError("Use a unicast IPv4 or IPv6 address without a scope identifier.")
    return str(address)


def summarize(timestamp: float, target: str, rows: list[dict]) -> ProbeBatch:
    errors = [str(row.get("error")) for row in rows if row.get("error")]
    completed = [row for row in rows if not row.get("error")]
    times = [float(row["ms"]) for row in completed if row["status"] == "Success"]
    return ProbeBatch(
        timestamp, target, len(completed), len(times),
        min(times) if times else None,
        statistics.mean(times) if times else None,
        max(times) if times else None,
        ", ".join(sorted({str(row.get("status", "Error")) for row in rows})),
        "; ".join(errors) if errors else ("No probe results" if not rows else None),
    )


def probe(target: str, count: int = 4, timeout_ms: int = 1000) -> ProbeBatch:
    target = validate_target(target)
    if not 1 <= count <= 20 or not 100 <= timeout_ms <= 5000:
        raise ValueError("Probe count must be 1–20 and timeout 100–5000 ms.")
    if os.name != "nt":
        return ProbeBatch(time.time(), target, 0, 0, None, None, None, "Error",
                          "Live ICMP collection currently requires Windows.")
    # Only validated IP/numeric values are interpolated; no shell=True or parsed ping text.
    script = r"""
$ErrorActionPreference = 'Stop'
$pinger = New-Object System.Net.NetworkInformation.Ping
try {
    $rows = @(for ($i = 0; $i -lt __COUNT__; $i++) {
        try {
            $reply = $pinger.Send([System.Net.IPAddress]::Parse('__TARGET__'), __TIMEOUT__)
            [pscustomobject]@{status=$reply.Status.ToString(); ms=$reply.RoundtripTime; error=$null}
        } catch {
            [pscustomobject]@{status='Error'; ms=$null; error=$_.Exception.GetBaseException().Message}
        }
        if ($i -lt (__COUNT__ - 1)) { Start-Sleep -Milliseconds 200 }
    })
    ConvertTo-Json -InputObject $rows -Compress
} finally { $pinger.Dispose() }
"""
    script = script.replace("__COUNT__", str(count)).replace("__TARGET__", target)
    script = script.replace("__TIMEOUT__", str(timeout_ms))
    executable = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                              "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    try:
        result = subprocess.run(
            [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=count * (timeout_ms / 1000 + 0.2) + 10,
            check=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        rows = json.loads(result.stdout.strip().lstrip("\ufeff"))
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list) or len(rows) != count:
            raise ValueError("Incomplete probe batch")
        return summarize(time.time(), target, rows)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
        return ProbeBatch(time.time(), target, 0, 0, None, None, None, "Error",
                          f"{type(exc).__name__}: ICMP probe could not complete")
