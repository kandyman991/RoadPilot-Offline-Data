import "./style.css";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { Map as MapLibreMap, Marker, NavigationControl, addProtocol, setWorkerUrl } from "maplibre-gl";
import type { Feature, FeatureCollection, Geometry } from "geojson";
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
  geometry: Geometry;
};
type RoutePlanResult = {
  elapsedMs: number;
  geometry: Geometry;
  response: {
    trip?: {
      summary?: {
        length?: number;
        time?: number;
        has_toll?: boolean;
        has_highway?: boolean;
        has_ferry?: boolean;
      };
      legs?: Array<{
        maneuvers?: Array<{
          instruction?: string;
          verbal_pre_transition_instruction?: string;
          length?: number;
          time?: number;
        }>;
      }>;
      status?: number;
      status_message?: string;
      units?: string;
    };
  };
};
type ExpansionResult = {
  elapsedMs: number;
  featureCount: number;
  geojson: FeatureCollection;
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
  primaryGeometry: Geometry;
  bufferGeometry: Geometry;
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
        <h2>Valhalla route planner</h2>
        <div class="field">
          <label for="routeCosting">Costing</label>
          <select id="routeCosting">
            <option value="motorcycle">Motorcycle</option>
            <option value="auto">Auto</option>
            <option value="bicycle">Bicycle</option>
            <option value="pedestrian">Pedestrian</option>
          </select>
        </div>
        <div class="coord-grid">
          <div class="field"><label for="routeStartLat">Start lat</label><input id="routeStartLat" type="number" step="0.000001" /></div>
          <div class="field"><label for="routeStartLng">Start lng</label><input id="routeStartLng" type="number" step="0.000001" /></div>
          <div class="field"><label for="routeEndLat">End lat</label><input id="routeEndLat" type="number" step="0.000001" /></div>
          <div class="field"><label for="routeEndLng">End lng</label><input id="routeEndLng" type="number" step="0.000001" /></div>
        </div>
        <div class="actions">
          <button id="pickRouteStartBtn" class="btn" type="button">Pick start</button>
          <button id="pickRouteEndBtn" class="btn" type="button">Pick end</button>
          <button id="runRouteBtn" class="btn primary" type="button">Route</button>
        </div>
        <div class="field inline-field">
          <label><input id="routeExpansionToggle" type="checkbox" /> Show search expansion</label>
        </div>
        <details class="route-options">
          <summary>Costing options</summary>
          <div class="field">
            <label for="routeUseHighways">Use highways <span id="routeUseHighwaysValue">1.0</span></label>
            <input id="routeUseHighways" type="range" min="0" max="1" step="0.1" value="1" />
          </div>
          <div class="field">
            <label for="routeUseTolls">Use tolls <span id="routeUseTollsValue">1.0</span></label>
            <input id="routeUseTolls" type="range" min="0" max="1" step="0.1" value="1" />
          </div>
          <div class="field">
            <label for="routeUseFerry">Use ferries <span id="routeUseFerryValue">1.0</span></label>
            <input id="routeUseFerry" type="range" min="0" max="1" step="0.1" value="1" />
          </div>
        </details>
        <div id="routeSummary" class="empty">Build/select a graph, then choose start and destination.</div>
        <div id="routeManeuvers" class="maneuver-list"></div>
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
const routeCosting = document.querySelector<HTMLSelectElement>("#routeCosting")!;
const routeStartLat = document.querySelector<HTMLInputElement>("#routeStartLat")!;
const routeStartLng = document.querySelector<HTMLInputElement>("#routeStartLng")!;
const routeEndLat = document.querySelector<HTMLInputElement>("#routeEndLat")!;
const routeEndLng = document.querySelector<HTMLInputElement>("#routeEndLng")!;
const pickRouteStartBtn = document.querySelector<HTMLButtonElement>("#pickRouteStartBtn")!;
const pickRouteEndBtn = document.querySelector<HTMLButtonElement>("#pickRouteEndBtn")!;
const runRouteBtn = document.querySelector<HTMLButtonElement>("#runRouteBtn")!;
const routeExpansionToggle = document.querySelector<HTMLInputElement>("#routeExpansionToggle")!;
const routeUseHighways = document.querySelector<HTMLInputElement>("#routeUseHighways")!;
const routeUseTolls = document.querySelector<HTMLInputElement>("#routeUseTolls")!;
const routeUseFerry = document.querySelector<HTMLInputElement>("#routeUseFerry")!;
const routeUseHighwaysValue = document.querySelector<HTMLSpanElement>("#routeUseHighwaysValue")!;
const routeUseTollsValue = document.querySelector<HTMLSpanElement>("#routeUseTollsValue")!;
const routeUseFerryValue = document.querySelector<HTMLSpanElement>("#routeUseFerryValue")!;
const routeSummary = document.querySelector<HTMLDivElement>("#routeSummary")!;
const routeManeuvers = document.querySelector<HTMLDivElement>("#routeManeuvers")!;
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
let routePickMode: "start" | "end" | null = null;
let routeStartMarker: Marker | null = null;
let routeEndMarker: Marker | null = null;
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

const map = new MapLibreMap({
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
    data: { type: "Feature", properties: {}, geometry: preview.primaryGeometry } as Feature,
  });
  map.addSource("rp-editor-buffer", {
    type: "geojson",
    data: { type: "Feature", properties: {}, geometry: preview.bufferGeometry } as Feature,
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
    } as FeatureCollection,
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

const routeSourceId = "roadpilot-route";
const routeLayerId = "roadpilot-route-line";
const expansionSourceId = "roadpilot-expansion";
const expansionLayerId = "roadpilot-expansion-line";

function removeRouteLayers(): void {
  if (map.getLayer(expansionLayerId)) map.removeLayer(expansionLayerId);
  if (map.getSource(expansionSourceId)) map.removeSource(expansionSourceId);
  if (map.getLayer(routeLayerId)) map.removeLayer(routeLayerId);
  if (map.getSource(routeSourceId)) map.removeSource(routeSourceId);
}

function showRouteGeometry(geometry: Geometry): void {
  if (map.getLayer(routeLayerId)) map.removeLayer(routeLayerId);
  if (map.getSource(routeSourceId)) map.removeSource(routeSourceId);
  map.addSource(routeSourceId, {
    type: "geojson",
    data: { type: "Feature", properties: {}, geometry } as Feature,
  });
  map.addLayer({
    id: routeLayerId,
    type: "line",
    source: routeSourceId,
    paint: {
      "line-color": "#276fbf",
      "line-width": ["interpolate", ["linear"], ["zoom"], 6, 4, 14, 7],
      "line-opacity": 0.95,
    },
  });
  const line = geometry.type === "LineString" ? geometry.coordinates : [];
  if (line.length >= 2) {
    const lngs = line.map(point => Number(point[0]));
    const lats = line.map(point => Number(point[1]));
    map.fitBounds(
      [[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]],
      { padding: 70, duration: 400 },
    );
  }
}

function showExpansion(expansion: FeatureCollection): void {
  if (map.getLayer(expansionLayerId)) map.removeLayer(expansionLayerId);
  if (map.getSource(expansionSourceId)) map.removeSource(expansionSourceId);
  map.addSource(expansionSourceId, { type: "geojson", data: expansion });
  map.addLayer({
    id: expansionLayerId,
    type: "line",
    source: expansionSourceId,
    paint: {
      "line-color": "#d68c45",
      "line-width": ["interpolate", ["linear"], ["zoom"], 6, 1, 14, 2],
      "line-opacity": 0.45,
    },
  }, routeLayerId);
}

function routeCoordinate(field: HTMLInputElement, label: string, min: number, max: number): number {
  const value = Number(field.value);
  if (!Number.isFinite(value) || value < min || value > max) {
    throw new Error(`${label} is invalid.`);
  }
  return value;
}

function routeCostingOptions(): Record<string, unknown> {
  const costing = routeCosting.value;
  if (costing !== "motorcycle" && costing !== "auto") return {};
  return {
    [costing]: {
      use_highways: Number(routeUseHighways.value),
      use_tolls: Number(routeUseTolls.value),
      use_ferry: Number(routeUseFerry.value),
    },
  };
}

function formatDuration(seconds: number | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return "—";
  const rounded = Math.round(seconds);
  const hours = Math.floor(rounded / 3600);
  const minutes = Math.floor((rounded % 3600) / 60);
  const secs = rounded % 60;
  return hours > 0 ? `${hours}h ${minutes}m` : minutes > 0 ? `${minutes}m ${secs}s` : `${secs}s`;
}

function setRoutePoint(kind: "start" | "end", lat: number, lng: number): void {
  const latField = kind === "start" ? routeStartLat : routeEndLat;
  const lngField = kind === "start" ? routeStartLng : routeEndLng;
  latField.value = lat.toFixed(6);
  lngField.value = lng.toFixed(6);
  const current = kind === "start" ? routeStartMarker : routeEndMarker;
  current?.remove();
  const marker = new Marker({ color: kind === "start" ? "#2d8a5c" : "#b94b4b" })
    .setLngLat([lng, lat])
    .addTo(map);
  if (kind === "start") routeStartMarker = marker;
  else routeEndMarker = marker;
}

function renderRouteResult(result: RoutePlanResult, expansion?: ExpansionResult): void {
  const trip = result.response.trip;
  const summary = trip?.summary;
  routeSummary.className = "kv";
  routeSummary.innerHTML = `
    <dt>Graph</dt><dd>${activeRegion?.id ?? "—"}</dd>
    <dt>Costing</dt><dd>${routeCosting.value}</dd>
    <dt>Distance</dt><dd>${summary?.length == null ? "—" : summary.length.toFixed(2) + " km"}</dd>
    <dt>Duration</dt><dd>${formatDuration(summary?.time)}</dd>
    <dt>Valhalla time</dt><dd>${result.elapsedMs} ms</dd>
    <dt>Highway</dt><dd>${summary?.has_highway ? "yes" : "no"}</dd>
    <dt>Toll</dt><dd>${summary?.has_toll ? "yes" : "no"}</dd>
    <dt>Ferry</dt><dd>${summary?.has_ferry ? "yes" : "no"}</dd>
    ${expansion ? `<dt>Expanded edges</dt><dd>${expansion.featureCount} in ${expansion.elapsedMs} ms</dd>` : ""}
  `;
  const maneuvers = trip?.legs?.flatMap(leg => leg.maneuvers ?? []) ?? [];
  routeManeuvers.innerHTML = maneuvers.slice(0, 80).map((maneuver, index) => {
    const instruction = maneuver.instruction || maneuver.verbal_pre_transition_instruction || "Maneuver";
    const meta = [
      maneuver.length == null ? null : `${maneuver.length.toFixed(2)} km`,
      maneuver.time == null ? null : formatDuration(maneuver.time),
    ].filter(Boolean).join(" • ");
    return `<div class="maneuver-row"><b>${index + 1}. ${instruction}</b><span>${meta}</span></div>`;
  }).join("");
}

async function runStandardRoute(): Promise<void> {
  if (!activeRegion) {
    routeSummary.className = "bad";
    routeSummary.textContent = "Select a region first.";
    return;
  }
  runRouteBtn.disabled = true;
  routeSummary.className = "empty";
  routeSummary.textContent = "Calculating standard Valhalla route…";
  routeManeuvers.innerHTML = "";
  try {
    const payload = {
      regionId: activeRegion.id,
      startLat: routeCoordinate(routeStartLat, "Start latitude", -90, 90),
      startLng: routeCoordinate(routeStartLng, "Start longitude", -180, 180),
      endLat: routeCoordinate(routeEndLat, "End latitude", -90, 90),
      endLng: routeCoordinate(routeEndLng, "End longitude", -180, 180),
      costing: routeCosting.value,
      costingOptions: routeCostingOptions(),
    };
    removeRouteLayers();
    const result = await invoke<RoutePlanResult>("plan_route", payload);
    showRouteGeometry(result.geometry);
    let expansion: ExpansionResult | undefined;
    if (routeExpansionToggle.checked) {
      expansion = await invoke<ExpansionResult>("route_expansion", payload);
      showExpansion(expansion.geojson);
    }
    renderRouteResult(result, expansion);
  } catch (error) {
    routeSummary.className = "bad";
    routeSummary.textContent = `Route failed: ${String(error)}`;
    appendLog(`Valhalla route failed: ${String(error)}`);
  } finally {
    runRouteBtn.disabled = false;
  }
}

function syncRouteSlider(input: HTMLInputElement, label: HTMLSpanElement): void {
  const update = () => label.textContent = Number(input.value).toFixed(1);
  input.addEventListener("input", update);
  update();
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
  removeRouteLayers();
  routeStartMarker?.remove();
  routeEndMarker?.remove();
  routeStartMarker = null;
  routeEndMarker = null;
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
    const groups = new globalThis.Map<string, GeofabrikCatalogItem[]>();
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
  const existingRouting = (existing["routing"] ?? {}) as Record<string, unknown>;
  const existingRoutes = Array.isArray(existingRouting.validationRoutes)
    ? existingRouting.validationRoutes as Array<Record<string, unknown>>
    : [];
  const firstBorderIndex = existingRoutes.findIndex(route => route.kind === "border");
  const routeName = editorRouteName.value.trim() || "border-smoke-test";
  const editedBorderRoute = {
    name: routeName,
    kind: "border",
    costing: "motorcycle",
    start: { lat: startLat, lng: startLng },
    end: { lat: endLat, lng: endLng },
  };
  const validationRoutes = existingRoutes.map(route => structuredClone(route));
  if (firstBorderIndex >= 0) validationRoutes[firstBorderIndex] = editedBorderRoute;
  else validationRoutes.push(editedBorderRoute);

  const config: Record<string, unknown> = {
    ...existing,
    schemaVersion: 1,
    id: regionId,
    name,
    routing: {
      ...existingRouting,
      enabled: true,
      expectedValhallaVersion: String(existingRouting.expectedValhallaVersion ?? "3.6.3"),
      borderBufferKm: editorPreview.borderBufferKm,
      buildConcurrency: Number(existingRouting.buildConcurrency ?? 12),
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
      validationRoutes,
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

pickRouteStartBtn.addEventListener("click", () => {
  routePickMode = "start";
  pickRouteStartBtn.textContent = "Click map…";
  pickRouteEndBtn.textContent = "Pick end";
});
pickRouteEndBtn.addEventListener("click", () => {
  routePickMode = "end";
  pickRouteEndBtn.textContent = "Click map…";
  pickRouteStartBtn.textContent = "Pick start";
});
runRouteBtn.addEventListener("click", runStandardRoute);
syncRouteSlider(routeUseHighways, routeUseHighwaysValue);
syncRouteSlider(routeUseTolls, routeUseTollsValue);
syncRouteSlider(routeUseFerry, routeUseFerryValue);

graphLayerBtn.addEventListener("click", () => {
  if (!activeRegion) return;
  if (graphVisible) removeGraphLayer();
  else addGraphLayer(activeRegion);
});
fitBtn.addEventListener("click", fitActiveRegion);

map.on("click", (event) => {
  lastMapClick = { lat: event.lngLat.lat, lng: event.lngLat.lng };
  locateBtn.disabled = !activeRegion;
  if (routePickMode) {
    setRoutePoint(routePickMode, event.lngLat.lat, event.lngLat.lng);
    routePickMode = null;
    pickRouteStartBtn.textContent = "Pick start";
    pickRouteEndBtn.textContent = "Pick end";
    return;
  }
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
