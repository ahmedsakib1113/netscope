"""Export a minimal recorded session for the public portfolio preview."""
import argparse
import csv
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/netscope.sqlite3")
    parser.add_argument("--interface", default="Wi-Fi")
    args = parser.parse_args()
    with closing(sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        # Restrict the public export to the existing public probe target and
        # a completed real recording. No private router addresses are exported.
        session = connection.execute("""
            SELECT s.* FROM sessions s
            WHERE s.ended_at IS NOT NULL AND s.target = '1.1.1.1'
            AND EXISTS (SELECT 1 FROM probe_batches p WHERE p.session_id=s.id
                        AND p.error IS NULL AND p.received > 0)
            AND EXISTS (SELECT 1 FROM interface_samples i WHERE i.session_id=s.id
                        AND i.interface=? AND i.download_mbps IS NOT NULL)
            ORDER BY s.started_at DESC LIMIT 1
        """, (args.interface,)).fetchone()
        if session is None:
            raise ValueError("No completed Wi-Fi recording with successful public-target probes was found.")
        samples = [dict(row) for row in connection.execute("""
            SELECT timestamp, download_mbps, upload_mbps, quality
            FROM interface_samples WHERE session_id=? AND interface=? ORDER BY timestamp
        """, (session["id"], args.interface))]
        probes = [dict(row) for row in connection.execute("""
            SELECT timestamp,sent,received,min_ms,mean_ms,max_ms,loss_percent,
                   CASE WHEN error IS NULL THEN 0 ELSE 1 END AS measurement_error
            FROM probe_batches WHERE session_id=? ORDER BY timestamp
        """, (session["id"],))]
    started = session["started_at"]
    for row in [*samples, *probes]:
        row["seconds"] = round(row.pop("timestamp") - started, 3)
    payload = {
        "title": "Real Windows Wi-Fi capture",
        "mode": "recorded", "interface": "Wi-Fi", "target": "1.1.1.1",
        "started_at_utc": datetime.fromtimestamp(started, timezone.utc).isoformat(),
        "duration_seconds": round(session["ended_at"] - started, 3),
        "sample_interval_seconds": session["sample_interval"],
        "probe_interval_seconds": session["probe_interval"],
        "samples": samples, "probes": probes,
    }
    (ROOT / "docs/demo.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (ROOT / "docs/recorded-traffic.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=["seconds", "download_mbps", "upload_mbps", "quality"])
        writer.writeheader()
        writer.writerows(samples)
    print(f"Exported {len(samples)} real interface samples and {len(probes)} probe batches. Raw database and machine identifiers remain local.")


if __name__ == "__main__":
    main()
