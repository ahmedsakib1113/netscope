"""Independent collection: slow ICMP work never blocks bandwidth sampling."""

from concurrent.futures import ThreadPoolExecutor
import logging
from threading import Event
import time

from netscope.bandwidth import BandwidthSampler, read_counters
from netscope.locking import collector_lock
from netscope.probes import probe
from netscope.storage import Store

LOG = logging.getLogger(__name__)


def collect(store: Store, *, target: str, interval: float = 2, probe_interval: float = 10,
            count: int = 4, timeout_ms: int = 1000, duration: float | None = None,
            interface: str | None = None, stop: Event | None = None) -> str:
    stop = stop or Event()
    with collector_lock(store.path):
        store.initialize()
        session = store.start_session(target, interval, probe_interval)
        sampler = BandwidthSampler()
        start = time.monotonic()
        next_sample = start
        next_probe = start
        pending = None
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="icmp")
        LOG.info("Collection started | session=%s | target=%s", session, target)
        try:
            while not stop.is_set():
                now = time.monotonic()
                if duration is not None and now - start >= duration:
                    break
                if pending is not None and pending.done():
                    batch = pending.result()
                    store.save_probe(session, batch)
                    LOG.info("Probe | replies=%s/%s | mean_ms=%s | loss=%s | %s",
                             batch.received, batch.sent, batch.mean_ms, batch.loss_percent,
                             batch.error or batch.statuses)
                    pending = None
                if now >= next_sample:
                    counters = read_counters()
                    if interface is not None:
                        counters = {k: v for k, v in counters.items() if k == interface}
                    samples = sampler.sample(counters, time.monotonic(), time.time())
                    store.save_samples(session, samples)
                    LOG.info("Sample | interfaces=%s", len(samples))
                    next_sample = time.monotonic() + interval
                if now >= next_probe and pending is None:
                    pending = pool.submit(probe, target, count, timeout_ms)
                    next_probe = now + probe_interval
                stop.wait(0.1)
        finally:
            # Bound on shutdown: count*(timeout+spacing) + 10s for PowerShell startup.
            pool.shutdown(wait=True, cancel_futures=True)
            try:
                if pending is not None and not pending.cancelled():
                    store.save_probe(session, pending.result())
            finally:
                store.finish_session(session)
                LOG.info("Collection stopped | session=%s", session)
    return session
