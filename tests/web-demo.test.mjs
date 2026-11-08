import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { summarize, selectWindow } from "../docs/demo-metrics.mjs";

test("missing baselines stay missing, errors are excluded, replies weight RTT", () => {
  const result = summarize([{download_mbps:null,upload_mbps:null}], [
    {sent:4,received:4,mean_ms:10},
    {sent:4,received:2,mean_ms:40},
    {sent:4,received:0,mean_ms:null,measurement_error:1},
  ]);
  assert.equal(result.latest,null);
  assert.equal(result.peakDown,null);
  assert.equal(result.loss,25);
  assert.equal(result.meanRtt,20);
  assert.equal(result.measurementErrors,1);
  assert.equal(summarize([],[]).loss,null);
});

test("window selection includes its boundary and only completed in-window probes", () => {
  const selected = selectWindow({samples:[{seconds:1},{seconds:20},{seconds:30}],probes:[{seconds:19},{seconds:20},{seconds:31}]},10);
  assert.deepEqual(selected.samples.map(s=>s.seconds),[20,30]);
  assert.deepEqual(selected.probes.map(p=>p.seconds),[20]);
});

test("the published recording contains real samples and reconciled requests", async () => {
  const data = JSON.parse(await readFile(new URL("../docs/demo.json",import.meta.url),"utf8"));
  const result = summarize(data.samples,data.probes);
  assert.equal(data.mode,"recorded");
  assert.ok(result.validSamples > 0);
  assert.ok(result.sent > 0);
  assert.ok(result.received <= result.sent);
  assert.ok(data.samples.some(s=>s.download_mbps===null));
  const full = selectWindow(data,"all");
  assert.equal(full.samples.length,data.samples.length);
});
