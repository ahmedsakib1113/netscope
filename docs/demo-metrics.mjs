export function summarize(samples, probes) {
  const valid = samples.filter(s => Number.isFinite(s.download_mbps) && Number.isFinite(s.upload_mbps));
  const batches = probes.filter(p => !p.measurement_error && p.sent > 0);
  const sent = batches.reduce((n, p) => n + p.sent, 0);
  const received = batches.reduce((n, p) => n + p.received, 0);
  const replied = batches.filter(p => p.received > 0 && Number.isFinite(p.mean_ms));
  const replyCount = replied.reduce((n, p) => n + p.received, 0);
  return {
    latest: valid.at(-1) ?? null,
    peakDown: valid.length ? Math.max(...valid.map(s => s.download_mbps)) : null,
    meanRtt: replyCount ? replied.reduce((n, p) => n + p.mean_ms * p.received, 0) / replyCount : null,
    loss: sent ? 100 * (sent - received) / sent : null,
    sent, received, samples: samples.length, validSamples: valid.length,
    measurementErrors: probes.filter(p => p.measurement_error).length,
  };
}

export function selectWindow(data, duration) {
  const last = Math.max(0, ...data.samples.map(s => s.seconds));
  const start = duration === "all" ? 0 : Math.max(0, last - Number(duration));
  return {
    start, end: last,
    samples: data.samples.filter(s => s.seconds >= start),
    probes: data.probes.filter(p => p.seconds >= start && p.seconds <= last),
  };
}
