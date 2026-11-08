import { summarize, selectWindow } from "./demo-metrics.mjs";

const $ = id => document.getElementById(id);
const number = (value, digits = 2) => Number.isFinite(value) ? value.toFixed(digits) : "—";
const ns = "http://www.w3.org/2000/svg";

function chart(target, samples, series, suffix) {
  const width = 900, height = 270, left = 50, right = 20, top = 20, bottom = 35;
  const values = samples.flatMap(s => series.map(k => s[k.key])).filter(Number.isFinite);
  const maximum = Math.max(1, ...values) * 1.15;
  const start = samples[0]?.seconds ?? 0;
  const end = samples.at(-1)?.seconds ?? 1;
  const x = t => left + (t - start) / Math.max(1, end - start) * (width - left - right);
  const y = v => height - bottom - v / maximum * (height - top - bottom);
  const parts = [];
  for (let i = 0; i <= 4; i++) {
    const value = maximum * i / 4;
    parts.push(`<line x1="${left}" x2="${width-right}" y1="${y(value)}" y2="${y(value)}" stroke="#243042"/><text x="${left-10}" y="${y(value)+4}" text-anchor="end">${value.toFixed(maximum < 10 ? 1 : 0)}</text>`);
  }
  for (let i = 0; i <= 4; i++) {
    const t = start + (end-start)*i/4;
    parts.push(`<text x="${x(t)}" y="${height-10}" text-anchor="middle">${t.toFixed(0)}s</text>`);
  }
  for (const item of series) {
    let drawing = false, path = "";
    for (const sample of samples) {
      if (!Number.isFinite(sample[item.key])) { drawing = false; continue; }
      path += `${drawing ? "L" : "M"}${x(sample.seconds)},${y(sample[item.key])} `;
      drawing = true;
    }
    parts.push(`<path d="${path}" fill="none" stroke="${item.color}" stroke-width="2.5" stroke-linejoin="round"/>`);
    for (const sample of samples) {
      const value = sample[item.key];
      if (!Number.isFinite(value)) continue;
      parts.push(`<circle cx="${x(sample.seconds)}" cy="${y(value)}" r="4" fill="${item.color}"><title>${item.name}: ${value.toFixed(2)} ${suffix} at ${sample.seconds.toFixed(1)}s</title></circle>`);
    }
  }
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", series.map(s => s.name).join(" and ") + " over the selected recorded interval");
  svg.innerHTML = parts.join("");
  $(target).replaceChildren(svg);
}

async function main() {
  const response = await fetch("./demo.json");
  if (!response.ok) throw new Error(`Recorded session unavailable (HTTP ${response.status})`);
  const data = await response.json();
  $("capture-date").textContent = new Date(data.started_at_utc).toLocaleString("en-GB", { timeZone: "UTC", dateStyle: "medium", timeStyle: "short" }) + " UTC";
  $("duration").textContent = `${data.duration_seconds.toFixed(0)} seconds`;
  $("sample-count").textContent = data.samples.length;
  const render = () => {
    const selected = selectWindow(data, $("window").value);
    const values = summarize(selected.samples, selected.probes);
    $("download").textContent = number(values.latest?.download_mbps);
    $("upload").textContent = number(values.latest?.upload_mbps);
    $("latency").textContent = number(values.meanRtt);
    $("loss").textContent = number(values.loss);
    $("replies").textContent = `${values.received}/${values.sent} replies in selected interval`;
    $("peak").textContent = `${number(values.peakDown)} Mbps peak observed download`;
    $("selected").textContent = `${values.samples} observations · ${selected.start.toFixed(0)}–${selected.end.toFixed(0)} seconds into recording`;
    chart("traffic-chart", selected.samples, [{key:"download_mbps",name:"Download",color:"#45dfb0"},{key:"upload_mbps",name:"Upload",color:"#79a9ff"}], "Mbps");
    chart("latency-chart", selected.probes.filter(p => !p.measurement_error), [{key:"mean_ms",name:"Batch mean RTT",color:"#a5adff"}], "ms");
    const body = $("observations");
    body.replaceChildren();
    for (const row of [...selected.samples].reverse()) {
      const tr = document.createElement("tr");
      for (const value of [`${row.seconds.toFixed(1)}s`, number(row.download_mbps), number(row.upload_mbps), row.quality]) {
        const td = document.createElement("td"); td.textContent = value; tr.append(td);
      }
      body.append(tr);
    }
  };
  $("window").addEventListener("change", render);
  render();
  $("loading").hidden = true;
  $("dashboard").hidden = false;
}

main().catch(error => {
  $("loading").textContent = `${error.message}. You can still view the original dashboard screenshots below.`;
  $("loading").setAttribute("role", "alert");
});
