"""Command line entry point for a collector with explicit, bounded settings."""

import argparse
import logging
import math
from pathlib import Path
import signal
from threading import Event

from netscope.bandwidth import read_counters
from netscope.collector import collect
from netscope.probes import validate_target
from netscope.storage import DEFAULT_DB, Store


def positive_number(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Must be a finite positive number")
    return number


def main():
    parser = argparse.ArgumentParser(description="NetScope Windows network collector")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("interfaces", help="List interface names and link state")
    run = sub.add_parser("collect", help="Collect until Ctrl+C or --duration seconds")
    run.add_argument("--db", type=Path, default=DEFAULT_DB)
    run.add_argument("--target", default="1.1.1.1", help="Numeric IPv4/IPv6 probe target")
    run.add_argument("--interval", type=positive_number, default=2)
    run.add_argument("--probe-interval", type=positive_number, default=10)
    run.add_argument("--count", type=int, choices=range(1, 21), default=4)
    run.add_argument("--timeout-ms", type=int, default=1000)
    run.add_argument("--duration", type=positive_number)
    run.add_argument("--interface", help="Exact interface name; default: all non-loopback interfaces")
    args = parser.parse_args()
    if args.command == "interfaces":
        for name, value in sorted(read_counters().items()):
            print(f"{name}: {'up' if value.is_up else 'down'}")
        return
    try:
        args.target = validate_target(args.target)
    except ValueError as exc:
        parser.error(str(exc))
    if args.interval < 0.5 or args.probe_interval < 1:
        parser.error("Sample interval must be >=0.5s and probe interval >=1s")
    if not 100 <= args.timeout_ms <= 5000:
        parser.error("--timeout-ms must be between 100 and 5000")
    if args.interface and args.interface not in read_counters():
        parser.error("Interface not found. Run 'netscope interfaces' to list available names.")
    stop = Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    try:
        collect(Store(args.db), target=args.target, interval=args.interval,
                probe_interval=args.probe_interval, count=args.count, timeout_ms=args.timeout_ms,
                duration=args.duration, interface=args.interface, stop=stop)
    except (RuntimeError, OSError) as exc:
        parser.exit(1, f"NetScope: {exc}\n")


if __name__ == "__main__":
    main()
