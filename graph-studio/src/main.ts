import "./style.css";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { Map, NavigationControl, addProtocol, setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

setWorkerUrl(workerUrl);

type Coverage = { min_lat: number; max_lat: number; min_lng: number; max_lng: number } | null;
type RegionSummary = {
  id: string;
  name: string;
  border_buffer_km: number;
  expected_valhalla_version: string;
  source_ids: string[];
  coverage: Coverage;
};
type Tool = { name: string; available: boolean; detail: string };
type ToolchainStatus = { ready: boolean; tools: Tool[] };
type SystemStats = {
  logical_cpus: number;
  load_1m: number;
  memory_used_bytes: number;
  memory_total_bytes: number;
  disk_free_bytes: number | null;
  temperature_c: number | null;
};
type BuildStatus = {
  running: boolean;
  current_region: string | null;
  queue: string[];
  stage: string;
  started_at_epoch_ms: number | null;
  last_error: string | null;
};
type BuildArtifact = {
  region_id: string;
  version: string;
  built_at_utc: string;
  artifact_file: string;
  size_bytes: number;
  sha256: string;
  tile_count: number;
  manifest_path: string;
};

const app = document.querySelector<HTMLDivElement>("#app")!;
app.innerHTML = `
<div class="app">
  <header class="topbar">
    <div class="brand"><strong>RoadPilot Graph Studio</strong><span>map factory</span></div>
    <div id="metricCpu" class="metric">CPU <b>—</b></div>
    <div id="metricRam" class="metric">RAM <b>—</b></div>
    <div id="metricDisk" class="metric">Disk <b>—</b></div>
    <div id="metricTemp" class="metric">Temp <b>—</b></div>
    <div class="topbar-spacer"></div>
    <div id="toolchainBadge" class="metric">Toolchain <b>checking…</b></div>
  </header>

  <main class="workspace">
    <aside class="sidebar">
      <section class="section">
        <h2>Regions</h2>
        <div id="regions"></div>
      </section>
      <section class="section">
        <h2>Build</h2>
        <div class="field">
          <label for="packageVersion">Package version</label>
          <input id="packageVersion" autocomplete="off" />
        </div>
        <div class="actions">
          <button id="buildBtn" class="btn primary" type="button">Build selected</button>
          <button id="cancelBtn" class="btn danger" type="button" disabled>Cancel</button>
        </div>
        <p>Builds run sequentially and keep source/cache data in Graph Studio's local workspace.</p>
      </section>
      <section class="section">
        <h2>Toolchain</h2>
        <div id="tools" class="empty">Checking local tools…</div>
      </section>
    </aside>

    <section class="map-wrap">
      <div id="map"></div>
      <div class="map-toolbar">
        <span id="activeRegionBadge" class="map-badge">No region selected</span>
        <button id="graphLayerBtn" class="btn" type="button" disabled>Show graph</button>
        <button id="fitBtn" class="btn" type="button" disabled>Fit region</button>
      </div>
    </section>

    <aside class="inspector">
      <section class="section">
        <h2>Graph inspector</h2>
        <div id="inspectorSummary" class="empty">
          Select a built region, enable the graph layer, then click an edge or node.
        </div>
        <pre id="featureJson" class="feature-json">No graph feature selected.</pre>
        <div class="actions" style="margin-top:8px">
          <button id="locateBtn" class="btn" type="button" disabled>Deep locate</button>
        </div>
      </section>
      <section class="section">
        <h2>Build comparison</h2>
        <div class="field">
          <label for="compareA">Build A</label>
          <select id="compareA"></select>
        </div>
        <div class="field">
          <label for="compareB">Build B</label>
          <select id="compareB"></select>
        </div>
        <div id="comparison" class="empty">Choose two builds of the same region.</div>
      </section>
    </aside>
  </main>

  <footer class="console">
    <section class="console-summary">
      <div id="statusTitle" class="status-title">Idle</div>
      <div id="statusStage" class="status-line">No build running.</div>
      <div id="progress" class="progress idle"><div></div></div>
      <div id="statusQueue" class="status-line"></div>
    </section>
    <pre id="consoleLog" class="console-log">Graph Studio ready.\n</pre>
    <section class="console-side">
      <div class="status-title">Recent builds</div>
      <div id="builds" class="empty">No local builds found.</div>
    </section>
  </footer>
</div>
`;

const regionHost = document.querySelector<HTMLDivElement>("#regions")!;
const toolHost = document.querySelector<HTMLDivElement>("#tools")!;
const logHost = document.querySelector<HTMLPreElement>("#consoleLog")!;
const buildsHost = document.querySelector<HTMLDivElement>("#builds")!;
const packageVersionInput = document.querySelector<HTMLInputElement>("#packageVersion")!;
const buildBtn = document.querySelector<HTMLButtonElement>("#buildBtn")!;
const cancelBtn = document.querySelector<HTMLButtonElement>("#cancelBtn")!;
const graphLayerBtn = document.querySelector<HTMLButtonElement>("#graphLayerBtn")!;
const fitBtn = document.querySelector<HTMLButtonElement>("#fitBtn")!;
const locateBtn = document.querySelector<HTMLButtonElement>("#locateBtn")!;
const activeRegionBadge = document.querySelector<HTMLSpanElement>("#activeRegionBadge")!;
const featureJson = document.querySelector<HTMLPreElement>("#featureJson")!;
const inspectorSummary = document.querySelector<HTMLDivElement>("#inspectorSummary")!;
const compareA = document.querySelector<HTMLSelectElement>("#compareA")!;
const compareB = document.querySelector<HTMLSelectElement>("#compareB")!;
const comparison = document.querySelector<HTMLDivElement>("#comparison")!;

let regions: RegionSummary[] = [];
let artifacts: BuildArtifact[] = [];
let activeRegion: RegionSummary | null = null;
let graphVisible = false;
let lastMapClick: { lat: number; lng: number } | null = null;
const selected = new Set<string>();

function bytes(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = value;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(i >= 3 ? 1 : 0)} ${units[i]}`;
}

function defaultVersion(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}.${mm}.${dd}-1`;
}
packageVersionInput.value = defaultVersion();

function appendLog(line: string): void {
  logHost.textContent += line.endsWith("\n") ? line : line + "\n";
  const lines = logHost.textContent.split("\n");
  if (lines.length > 1200) logHost.textContent = lines.slice(-1000).join("\n");
  logHost.scrollTop = logHost.scrollHeight;
}

addProtocol("roadpilot-graph", async (request) => {
  const raw = request.url.replace("roadpilot-graph://", "");
  const match = raw.match(/^([^/]+)\/(\d+)\/(\d+)\/(\d+)\.mvt$/);
  if (!match) throw new Error("Invalid RoadPilot graph tile URL");
  const [, encodedRegion, z, x, y] = match;
  const data = await invoke<number[]>("graph_tile", {
    regionId: decodeURIComponent(encodedRegion),
    z: Number(z),
    x: Number(x),
    y: Number(y),
  });
  return { data: new Uint8Array(data).buffer };
});

const map = new Map({
  container: "map",
  style: "https://tiles.openfreemap.org/styles/bright",
  center: [11.8, 46.2],
  zoom: 6.2,
});
map.addControl(new NavigationControl({ showCompass: true }), "bottom-right");

function graphSourceId(): string { return "roadpilot-graph-source"; }
const graphLayers = ["rp-graph-edges", "rp-graph-shortcuts", "rp-graph-nodes", "rp-graph-restrictions"];

function removeGraphLayer(): void {
  for (const id of graphLayers) if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource(graphSourceId())) map.removeSource(graphSourceId());
  graphVisible = false;
  graphLayerBtn.textContent = "Show graph";
}

function addGraphLayer(region: RegionSummary): void {
  removeGraphLayer();
  map.addSource(graphSourceId(), {
    type: "vector",
    tiles: [`roadpilot-graph://${encodeURIComponent(region.id)}/{z}/{x}/{y}.mvt`],
    minzoom: 5,
    maxzoom: 18,
  });
  map.addLayer({
    id: "rp-graph-edges",
    type: "line",
    source: graphSourceId(),
    "source-layer": "edges",
    paint: { "line-color": "#ed5d47", "line-width": ["interpolate", ["linear"], ["zoom"], 6, 1, 14, 2.5] },
  });
  map.addLayer({
    id: "rp-graph-shortcuts",
    type: "line",
    source: graphSourceId(),
    "source-layer": "shortcuts",
    paint: { "line-color": "#9a62d5", "line-width": 1.3, "line-dasharray": [2, 2] },
  });
  map.addLayer({
    id: "rp-graph-nodes",
    type: "circle",
    source: graphSourceId(),
    "source-layer": "nodes",
    minzoom: 11,
    paint: { "circle-radius": 2.4, "circle-color": "#32a6c7", "circle-stroke-width": 0.6, "circle-stroke-color": "#07131b" },
  });
  map.addLayer({
    id: "rp-graph-restrictions",
    type: "circle",
    source: graphSourceId(),
    "source-layer": "access_restrictions",
    minzoom: 10,
    paint: { "circle-radius": 3, "circle-color": "#f4c95d" },
  });
  graphVisible = true;
  graphLayerBtn.textContent = "Hide graph";
}

function fitActiveRegion(): void {
  const c = activeRegion?.coverage;
  if (!c) return;
  map.fitBounds([[c.min_lng, c.min_lat], [c.max_lng, c.max_lat]], { padding: 44, duration: 450 });
}

function setActiveRegion(region: RegionSummary): void {
  activeRegion = region;
  activeRegionBadge.textContent = region.name;
  fitBtn.disabled = !region.coverage;
  graphLayerBtn.disabled = false;
  locateBtn.disabled = true;
  featureJson.textContent = "No graph feature selected.";
  inspectorSummary.textContent = `${region.id} • ${region.border_buffer_km} km border buffer • Valhalla ${region.expected_valhalla_version}`;
  removeGraphLayer();
  fitActiveRegion();
  renderRegions();
}

function renderRegions(): void {
  regionHost.innerHTML = "";
  for (const region of regions) {
    const row = document.createElement("div");
    row.className = "region-row" + (activeRegion?.id === region.id ? " active" : "");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = selected.has(region.id);
    checkbox.addEventListener("change", () => checkbox.checked ? selected.add(region.id) : selected.delete(region.id));

    const label = document.createElement("div");
    label.className = "region-name";
    label.textContent = region.name;
    const meta = document.createElement("span");
    meta.className = "region-meta";
    meta.textContent = `${region.border_buffer_km} km buffer • ${region.source_ids.length} sources`;
    label.appendChild(meta);
    label.addEventListener("click", () => setActiveRegion(region));

    const focus = document.createElement("button");
    focus.type = "button";
    focus.className = "region-focus";
    focus.title = "Inspect region";
    focus.textContent = "›";
    focus.addEventListener("click", () => setActiveRegion(region));
    row.append(checkbox, label, focus);
    regionHost.appendChild(row);
  }
}

async function refreshRegions(): Promise<void> {
  regions = await invoke<RegionSummary[]>("list_regions");
  renderRegions();
  if (!activeRegion && regions.length) setActiveRegion(regions[0]);
}

async function refreshToolchain(): Promise<void> {
  const status = await invoke<ToolchainStatus>("toolchain_status");
  const badge = document.querySelector<HTMLDivElement>("#toolchainBadge")!;
  badge.innerHTML = `Toolchain <b class="${status.ready ? "ok" : "bad"}">${status.ready ? "ready" : "incomplete"}</b>`;
  toolHost.innerHTML = "";
  for (const tool of status.tools) {
    const row = document.createElement("div");
    row.className = "tool";
    const name = document.createElement("span");
    name.textContent = tool.name;
    const state = document.createElement("span");
    state.className = tool.available ? "ok" : "bad";
    state.textContent = tool.available ? tool.detail || "found" : "missing";
    row.append(name, state);
    toolHost.appendChild(row);
  }
  buildBtn.disabled = !status.ready;
}

async function refreshStats(): Promise<void> {
  try {
    const s = await invoke<SystemStats>("system_stats");
    document.querySelector("#metricCpu b")!.textContent = `${s.logical_cpus}t / load ${s.load_1m.toFixed(1)}`;
    document.querySelector("#metricRam b")!.textContent = `${bytes(s.memory_used_bytes)} / ${bytes(s.memory_total_bytes)}`;
    document.querySelector("#metricDisk b")!.textContent = bytes(s.disk_free_bytes);
    document.querySelector("#metricTemp b")!.textContent = s.temperature_c == null ? "—" : `${s.temperature_c.toFixed(0)}°C`;
  } catch { /* keep last values */ }
}

function renderBuildStatus(status: BuildStatus): void {
  document.querySelector("#statusTitle")!.textContent = status.running
    ? `Building ${status.current_region ?? "queue"}`
    : status.last_error ? "Build failed" : "Idle";
  document.querySelector("#statusStage")!.textContent = status.last_error ?? status.stage ?? "No build running.";
  document.querySelector("#statusQueue")!.textContent = status.queue.length ? `Queue: ${status.queue.join(" → ")}` : "";
  document.querySelector("#progress")!.classList.toggle("idle", !status.running);
  cancelBtn.disabled = !status.running;
  buildBtn.disabled = status.running;
}

async function refreshBuildStatus(): Promise<void> {
  renderBuildStatus(await invoke<BuildStatus>("build_status"));
}

async function refreshBuilds(): Promise<void> {
  artifacts = await invoke<BuildArtifact[]>("list_builds");
  buildsHost.innerHTML = "";
  if (!artifacts.length) {
    buildsHost.className = "empty";
    buildsHost.textContent = "No local builds found.";
  } else {
    buildsHost.className = "";
    for (const item of artifacts.slice(0, 8)) {
      const card = document.createElement("div");
      card.className = "build-card";
      const strong = document.createElement("strong");
      strong.textContent = `${item.region_id} • ${item.version}`;
      const meta = document.createElement("span");
      meta.textContent = `${bytes(item.size_bytes)} • ${item.tile_count} tiles • ${item.sha256.slice(0, 10)}…`;
      card.append(strong, meta);
      buildsHost.appendChild(card);
    }
  }
  renderCompareSelectors();
}

function renderCompareSelectors(): void {
  const currentA = compareA.value;
  const currentB = compareB.value;
  const options = artifacts.map((a, i) => `<option value="${i}">${a.region_id} • ${a.version}</option>`).join("");
  compareA.innerHTML = `<option value="">Choose…</option>${options}`;
  compareB.innerHTML = `<option value="">Choose…</option>${options}`;
  compareA.value = currentA;
  compareB.value = currentB;
  renderComparison();
}

function renderComparison(): void {
  const ai = Number(compareA.value);
  const bi = Number(compareB.value);
  if (compareA.value === "" || compareB.value === "" || !artifacts[ai] || !artifacts[bi]) {
    comparison.className = "empty";
    comparison.textContent = "Choose two builds of the same region.";
    return;
  }
  const a = artifacts[ai], b = artifacts[bi];
  if (a.region_id !== b.region_id) {
    comparison.className = "bad";
    comparison.textContent = "Builds must be from the same region.";
    return;
  }
  const sizeDelta = b.size_bytes - a.size_bytes;
  const tileDelta = b.tile_count - a.tile_count;
  comparison.className = "kv";
  comparison.innerHTML = `
    <dt>Version</dt><dd>${a.version} → ${b.version}</dd>
    <dt>Size change</dt><dd>${sizeDelta >= 0 ? "+" : ""}${bytes(Math.abs(sizeDelta))} ${sizeDelta < 0 ? "smaller" : "larger"}</dd>
    <dt>Tile change</dt><dd>${tileDelta >= 0 ? "+" : ""}${tileDelta}</dd>
    <dt>Same graph</dt><dd class="${a.sha256 === b.sha256 ? "ok" : "warn"}">${a.sha256 === b.sha256 ? "yes" : "no"}</dd>
  `;
}
compareA.addEventListener("change", renderComparison);
compareB.addEventListener("change", renderComparison);

buildBtn.addEventListener("click", async () => {
  const queue = [...selected];
  if (!queue.length) {
    appendLog("Select at least one region.");
    return;
  }
  const version = packageVersionInput.value.trim();
  if (!/^\d{4}\.\d{2}\.\d{2}-[A-Za-z0-9._-]+$/.test(version)) {
    appendLog("Package version must look like 2026.10.06-1.");
    return;
  }
  try {
    await invoke("start_build_queue", { regionIds: queue, packageVersion: version, refreshSources: true });
    await refreshBuildStatus();
  } catch (error) {
    appendLog(`Could not start build: ${String(error)}`);
  }
});

cancelBtn.addEventListener("click", async () => {
  await invoke("cancel_build");
  appendLog("Cancellation requested.");
});

graphLayerBtn.addEventListener("click", () => {
  if (!activeRegion) return;
  if (graphVisible) removeGraphLayer();
  else addGraphLayer(activeRegion);
});
fitBtn.addEventListener("click", fitActiveRegion);

map.on("click", (event) => {
  lastMapClick = { lat: event.lngLat.lat, lng: event.lngLat.lng };
  locateBtn.disabled = !activeRegion;
  if (!graphVisible) return;
  const features = map.queryRenderedFeatures(event.point, { layers: graphLayers.filter(id => !!map.getLayer(id)) });
  if (!features.length) {
    featureJson.textContent = `No graph feature at ${event.lngLat.lat.toFixed(6)}, ${event.lngLat.lng.toFixed(6)}.`;
    return;
  }
  const f = features[0];
  const payload = {
    layer: f.layer.id,
    sourceLayer: f.sourceLayer,
    properties: f.properties,
    geometryType: f.geometry.type,
    click: lastMapClick,
  };
  featureJson.textContent = JSON.stringify(payload, null, 2);
});

locateBtn.addEventListener("click", async () => {
  if (!activeRegion || !lastMapClick) return;
  locateBtn.disabled = true;
  try {
    const result = await invoke<unknown>("inspect_locate", {
      regionId: activeRegion.id,
      lat: lastMapClick.lat,
      lng: lastMapClick.lng,
    });
    featureJson.textContent = JSON.stringify(result, null, 2);
  } catch (error) {
    featureJson.textContent = `Locate failed: ${String(error)}`;
  } finally {
    locateBtn.disabled = false;
  }
});

await listen<{ line: string }>("graph-studio://build-log", event => appendLog(event.payload.line));
await listen<BuildStatus>("graph-studio://build-status", event => {
  renderBuildStatus(event.payload);
  if (!event.payload.running) refreshBuilds().catch(() => {});
});

Promise.all([refreshRegions(), refreshToolchain(), refreshBuildStatus(), refreshBuilds(), refreshStats()])
  .catch(error => appendLog(`Startup error: ${String(error)}`));
setInterval(refreshStats, 3000);
setInterval(refreshBuildStatus, 2500);
