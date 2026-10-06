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
type GeofabrikCatalogItem = {
  id: string;
  name: string;
  parent: string | null;
  pbfUrl: string;
  polygonUrl: string;
  countryId: string | null;
  countryName: string | null;
  bounds: { minLat: number; maxLat: number; minLng: number; maxLng: number };
};
type RegionPreviewSource = {
  id: string;
  name: string;
  pbfUrl: string;
  polygonUrl: string;
  primary: boolean;
  intersectionArea: number;
  geometry: GeoJSON.Geometry;
};
type RegionPreview = {
  geofabrikId: string;
  name: string;
  countryId: string | null;
  countryName: string | null;
  pbfUrl: string;
  polygonUrl: string;
  borderBufferKm: number;
  bounds: { minLat: number; maxLat: number; minLng: number; maxLng: number };
  primaryGeometry: GeoJSON.Geometry;
  bufferGeometry: GeoJSON.Geometry;
  sources: RegionPreviewSource[];
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
        <h2>Region configuration</h2>
        <div class="actions">
          <button id="newRegionBtn" class="btn" type="button">New region</button>
          <button id="editRegionBtn" class="btn" type="button" disabled>Edit selected</button>
        </div>
        <p>Graph Studio keeps editable region definitions in your local workspace and seeds them from the production repository.</p>
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
      <section id="regionEditorSection" class="section" hidden>
        <h2>Region editor</h2>
        <div class="field">
          <label for="editorRoadpilotId">RoadPilot region id</label>
          <input id="editorRoadpilotId" autocomplete="off" placeholder="geofabrik-austria" />
        </div>
        <div class="field">
          <label for="editorName">Display name</label>
          <input id="editorName" autocomplete="off" />
        </div>
        <div class="field">
          <label for="editorGeofabrik">Geofabrik extract</label>
          <select id="editorGeofabrik"></select>
        </div>
        <div class="field">
          <label for="editorBuffer">Border buffer (km)</label>
          <input id="editorBuffer" type="number" min="1" max="100" step="1" value="25" />
        </div>
        <div class="actions">
          <button id="previewRegionBtn" class="btn" type="button">Preview + discover sources</button>
          <button id="refreshCatalogBtn" class="btn" type="button">Refresh catalog</button>
        </div>
        <div id="regionPreviewSummary" class="empty" style="margin-top:8px">Choose a Geofabrik extract and preview it.</div>
        <div id="regionSourceList" class="source-list"></div>

        <h2 style="margin-top:16px">Border validation route</h2>
        <div class="field">
          <label for="editorRouteName">Test name</label>
          <input id="editorRouteName" value="border-smoke-test" autocomplete="off" />
        </div>
        <div class="coord-grid">
          <div class="field"><label for="editorStartLat">Start lat</label><input id="editorStartLat" type="number" step="0.000001" /></div>
          <div class="field"><label for="editorStartLng">Start lng</label><input id="editorStartLng" type="number" step="0.000001" /></div>
          <div class="field"><label for="editorEndLat">End lat</label><input id="editorEndLat" type="number" step="0.000001" /></div>
          <div class="field"><label for="editorEndLng">End lng</label><input id="editorEndLng" type="number" step="0.000001" /></div>
        </div>
        <p>Exactly one endpoint must be inside the nominal Geofabrik region. You can copy coordinates from the map inspector.</p>
        <div class="actions">
          <button id="saveRegionBtn" class="btn primary" type="button" disabled>Save region</button>
          <button id="closeRegionEditorBtn" class="btn" type="button">Close</button>
        </div>
      </section>
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
const newRegionBtn = document.querySelector<HTMLButtonElement>("#newRegionBtn")!;
const editRegionBtn = document.querySelector<HTMLButtonElement>("#editRegionBtn")!;
const regionEditorSection = document.querySelector<HTMLElement>("#regionEditorSection")!;
const editorRoadpilotId = document.querySelector<HTMLInputElement>("#editorRoadpilotId")!;
const editorName = document.querySelector<HTMLInputElement>("#editorName")!;
const editorGeofabrik = document.querySelector<HTMLSelectElement>("#editorGeofabrik")!;
const editorBuffer = document.querySelector<HTMLInputElement>("#editorBuffer")!;
const previewRegionBtn = document.querySelector<HTMLButtonElement>("#previewRegionBtn")!;
const refreshCatalogBtn = document.querySelector<HTMLButtonElement>("#refreshCatalogBtn")!;
const regionPreviewSummary = document.querySelector<HTMLDivElement>("#regionPreviewSummary")!;
const regionSourceList = document.querySelector<HTMLDivElement>("#regionSourceList")!;
const editorRouteName = document.querySelector<HTMLInputElement>("#editorRouteName")!;
const editorStartLat = document.querySelector<HTMLInputElement>("#editorStartLat")!;
const editorStartLng = document.querySelector<HTMLInputElement>("#editorStartLng")!;
const editorEndLat = document.querySelector<HTMLInputElement>("#editorEndLat")!;
const editorEndLng = document.querySelector<HTMLInputElement>("#editorEndLng")!;
const saveRegionBtn = document.querySelector<HTMLButtonElement>("#saveRegionBtn")!;
const closeRegionEditorBtn = document.querySelector<HTMLButtonElement>("#closeRegionEditorBtn")!;
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
let geofabrikCatalog: GeofabrikCatalogItem[] = [];
let editorPreview: RegionPreview | null = null;
let editorExistingConfig: Record<string, unknown> | null = null;
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

const editorOverlaySourceIds = ["rp-editor-primary", "rp-editor-buffer", "rp-editor-sources"];
const editorOverlayLayerIds = ["rp-editor-primary-fill", "rp-editor-primary-line", "rp-editor-buffer-fill", "rp-editor-buffer-line", "rp-editor-sources-line"];

function removeEditorOverlays(): void {
  for (const id of editorOverlayLayerIds) if (map.getLayer(id)) map.removeLayer(id);
  for (const id of editorOverlaySourceIds) if (map.getSource(id)) map.removeSource(id);
}

function showEditorPreview(preview: RegionPreview): void {
  removeEditorOverlays();
  map.addSource("rp-editor-primary", {
    type: "geojson",
    data: { type: "Feature", properties: {}, geometry: preview.primaryGeometry } as GeoJSON.Feature,
  });
  map.addSource("rp-editor-buffer", {
    type: "geojson",
    data: { type: "Feature", properties: {}, geometry: preview.bufferGeometry } as GeoJSON.Feature,
  });
  map.addSource("rp-editor-sources", {
    type: "geojson",
    data: {
      type: "FeatureCollection",
      features: preview.sources.map(source => ({
        type: "Feature",
        properties: { id: source.id, primary: source.primary },
        geometry: source.geometry,
      })),
    } as GeoJSON.FeatureCollection,
  });
  map.addLayer({ id: "rp-editor-sources-line", type: "line", source: "rp-editor-sources", paint: { "line-color": "#6b7f93", "line-width": 1, "line-opacity": 0.5 } });
  map.addLayer({ id: "rp-editor-buffer-fill", type: "fill", source: "rp-editor-buffer", paint: { "fill-color": "#4f9bd8", "fill-opacity": 0.08 } });
  map.addLayer({ id: "rp-editor-buffer-line", type: "line", source: "rp-editor-buffer", paint: { "line-color": "#4f9bd8", "line-width": 2, "line-dasharray": [3, 2] } });
  map.addLayer({ id: "rp-editor-primary-fill", type: "fill", source: "rp-editor-primary", paint: { "fill-color": "#e66a52", "fill-opacity": 0.08 } });
  map.addLayer({ id: "rp-editor-primary-line", type: "line", source: "rp-editor-primary", paint: { "line-color": "#e66a52", "line-width": 2 } });
  map.fitBounds(
    [[preview.bounds.minLng, preview.bounds.minLat], [preview.bounds.maxLng, preview.bounds.maxLat]],
    { padding: 60, duration: 450 },
  );
}

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
  editRegionBtn.disabled = false;
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

async function loadGeofabrikCatalog(refresh = false): Promise<void> {
  editorGeofabrik.disabled = true;
  editorGeofabrik.innerHTML = '<option value="">Loading Geofabrik catalog…</option>';
  try {
    geofabrikCatalog = await invoke<GeofabrikCatalogItem[]>("geofabrik_catalog", { refresh });
    const groups = new Map<string, GeofabrikCatalogItem[]>();
    for (const item of geofabrikCatalog) {
      const country = item.countryName || "Other";
      const list = groups.get(country) ?? [];
      list.push(item);
      groups.set(country, list);
    }
    editorGeofabrik.innerHTML = '<option value="">Choose extract…</option>';
    for (const country of [...groups.keys()].sort()) {
      const group = document.createElement("optgroup");
      group.label = country;
      for (const item of groups.get(country) ?? []) {
        const option = document.createElement("option");
        option.value = item.id;
        option.textContent = `${item.name} (${item.id})`;
        group.appendChild(option);
      }
      editorGeofabrik.appendChild(group);
    }
  } catch (error) {
    editorGeofabrik.innerHTML = '<option value="">Catalog unavailable</option>';
    appendLog(`Geofabrik catalog error: ${String(error)}`);
  } finally {
    editorGeofabrik.disabled = false;
  }
}

function resetRegionEditor(): void {
  editorExistingConfig = null;
  editorPreview = null;
  editorRoadpilotId.value = "";
  editorRoadpilotId.disabled = false;
  editorName.value = "";
  editorGeofabrik.value = "";
  editorBuffer.value = "25";
  editorRouteName.value = "border-smoke-test";
  editorStartLat.value = "";
  editorStartLng.value = "";
  editorEndLat.value = "";
  editorEndLng.value = "";
  regionPreviewSummary.textContent = "Choose a Geofabrik extract and preview it.";
  regionSourceList.innerHTML = "";
  saveRegionBtn.disabled = true;
  removeEditorOverlays();
}

function openRegionEditor(): void {
  regionEditorSection.hidden = false;
  regionEditorSection.scrollIntoView({ block: "start" });
}

function closeRegionEditor(): void {
  regionEditorSection.hidden = true;
  removeEditorOverlays();
}

async function previewEditorRegion(refresh = false): Promise<void> {
  const geofabrikId = editorGeofabrik.value;
  const bufferKm = Number(editorBuffer.value);
  if (!geofabrikId) {
    regionPreviewSummary.textContent = "Choose a Geofabrik extract first.";
    return;
  }
  previewRegionBtn.disabled = true;
  saveRegionBtn.disabled = true;
  regionPreviewSummary.textContent = "Discovering exact polygon and neighboring source extracts…";
  try {
    const preview = await invoke<RegionPreview>("preview_region", { geofabrikId, bufferKm, refresh });
    editorPreview = preview;
    if (!editorName.value.trim()) editorName.value = preview.name;
    if (!editorRoadpilotId.value.trim()) {
      editorRoadpilotId.value = geofabrikId.replaceAll("/", "-");
    }
    regionPreviewSummary.innerHTML =
      `<span class="ok">Preview ready</span> • ${preview.sources.length} source extract${preview.sources.length === 1 ? "" : "s"} intersect the ${preview.borderBufferKm} km buffer.`;
    regionSourceList.innerHTML = preview.sources.map(source =>
      `<div class="source-row"><span>${source.primary ? "PRIMARY" : "NEIGHBOR"}</span><b>${source.name}</b><small>${source.id}</small></div>`
    ).join("");
    showEditorPreview(preview);
    saveRegionBtn.disabled = false;
  } catch (error) {
    editorPreview = null;
    regionPreviewSummary.innerHTML = `<span class="bad">Preview failed:</span> ${String(error)}`;
    regionSourceList.innerHTML = "";
    removeEditorOverlays();
  } finally {
    previewRegionBtn.disabled = false;
  }
}

function numberField(field: HTMLInputElement, label: string): number {
  const value = Number(field.value);
  if (!Number.isFinite(value)) throw new Error(`${label} is required.`);
  return value;
}

function configFromEditor(): Record<string, unknown> {
  if (!editorPreview) throw new Error("Preview the region before saving.");
  const regionId = editorRoadpilotId.value.trim();
  if (!/^[a-z0-9][a-z0-9-]*$/.test(regionId)) {
    throw new Error("RoadPilot region id must contain only lowercase letters, numbers and hyphens.");
  }
  const name = editorName.value.trim();
  if (!name) throw new Error("Display name is required.");

  const startLat = numberField(editorStartLat, "Start latitude");
  const startLng = numberField(editorStartLng, "Start longitude");
  const endLat = numberField(editorEndLat, "End latitude");
  const endLng = numberField(editorEndLng, "End longitude");
  const existing = editorExistingConfig ? structuredClone(editorExistingConfig) : {};
  const existingOverture = existing["overture"];
  const routeName = editorRouteName.value.trim() || "border-smoke-test";
  const config: Record<string, unknown> = {
    ...existing,
    schemaVersion: 1,
    id: regionId,
    name,
    routing: {
      enabled: true,
      expectedValhallaVersion: "3.6.3",
      borderBufferKm: editorPreview.borderBufferKm,
      buildConcurrency: 12,
      coverage: editorPreview.bounds,
      source: {
        primaryGeofabrikId: editorPreview.geofabrikId,
        polygonUrl: editorPreview.polygonUrl,
        pbfs: editorPreview.sources.map(source => ({ id: source.id, url: source.pbfUrl })),
      },
      package: {
        fileNameTemplate: `${regionId}-routing-{version}.tar`,
        manifestFileNameTemplate: `${regionId}-routing-{version}-manifest.json`,
      },
      validationRoutes: [{
        name: routeName,
        kind: "border",
        costing: "motorcycle",
        start: { lat: startLat, lng: startLng },
        end: { lat: endLat, lng: endLng },
      }],
    },
  };
  if (existingOverture) config["overture"] = existingOverture;
  return config;
}

newRegionBtn.addEventListener("click", async () => {
  resetRegionEditor();
  openRegionEditor();
  if (!geofabrikCatalog.length) await loadGeofabrikCatalog(false);
});

editRegionBtn.addEventListener("click", async () => {
  if (!activeRegion) return;
  resetRegionEditor();
  openRegionEditor();
  try {
    if (!geofabrikCatalog.length) await loadGeofabrikCatalog(false);
    const config = await invoke<Record<string, unknown>>("load_region_config", { regionId: activeRegion.id });
    editorExistingConfig = config;
    editorRoadpilotId.value = String(config.id ?? activeRegion.id);
    editorRoadpilotId.disabled = true;
    editorName.value = String(config.name ?? activeRegion.name);
    const routing = (config.routing ?? {}) as Record<string, unknown>;
    const source = (routing.source ?? {}) as Record<string, unknown>;
    editorGeofabrik.value = String(source.primaryGeofabrikId ?? "");
    editorBuffer.value = String(routing.borderBufferKm ?? activeRegion.border_buffer_km);
    const routes = Array.isArray(routing.validationRoutes) ? routing.validationRoutes as Array<Record<string, unknown>> : [];
    const borderRoute = routes.find(route => route.kind === "border");
    if (borderRoute) {
      editorRouteName.value = String(borderRoute.name ?? "border-smoke-test");
      const start = (borderRoute.start ?? {}) as Record<string, unknown>;
      const end = (borderRoute.end ?? {}) as Record<string, unknown>;
      editorStartLat.value = String(start.lat ?? "");
      editorStartLng.value = String(start.lng ?? "");
      editorEndLat.value = String(end.lat ?? "");
      editorEndLng.value = String(end.lng ?? "");
    }
    await previewEditorRegion(false);
  } catch (error) {
    regionPreviewSummary.innerHTML = `<span class="bad">Could not load region:</span> ${String(error)}`;
  }
});

previewRegionBtn.addEventListener("click", () => previewEditorRegion(false));
refreshCatalogBtn.addEventListener("click", async () => {
  await loadGeofabrikCatalog(true);
  appendLog("Geofabrik catalog refreshed.");
});
closeRegionEditorBtn.addEventListener("click", closeRegionEditor);

saveRegionBtn.addEventListener("click", async () => {
  saveRegionBtn.disabled = true;
  try {
    const config = configFromEditor();
    const saved = await invoke<Record<string, unknown>>("save_region_config", { config, refreshGeometry: false });
    appendLog(`Saved and validated region config: ${String(saved.id)}`);
    await refreshRegions();
    const savedRegion = regions.find(region => region.id === String(saved.id));
    if (savedRegion) setActiveRegion(savedRegion);
    closeRegionEditor();
  } catch (error) {
    regionPreviewSummary.innerHTML = `<span class="bad">Save rejected:</span> ${String(error)}`;
  } finally {
    saveRegionBtn.disabled = editorPreview == null;
  }
});

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

async function bootstrap(): Promise<void> {
  await listen<{ line: string }>("graph-studio://build-log", event => appendLog(event.payload.line));
  await listen<BuildStatus>("graph-studio://build-status", event => {
    renderBuildStatus(event.payload);
    if (!event.payload.running) refreshBuilds().catch(() => {});
  });

  await Promise.all([
    refreshRegions(),
    refreshToolchain(),
    refreshBuildStatus(),
    refreshBuilds(),
    refreshStats(),
  ]);
  setInterval(refreshStats, 3000);
  setInterval(refreshBuildStatus, 2500);
}

bootstrap().catch(error => appendLog(`Startup error: ${String(error)}`));
