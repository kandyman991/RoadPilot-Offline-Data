import "./style.css";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { Map as MapLibreMap, Marker, NavigationControl, addProtocol, setWorkerUrl } from "maplibre-gl";
import { PMTiles } from "pmtiles";
import type { RangeResponse, Source as PMTilesSource } from "pmtiles";
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
  graph_index_path: string | null;
  graph_tile_fingerprint: string | null;
  internal_fingerprint: string | null;
  boundary_fingerprints: Record<string, string>;
};
type VisualBuildArtifact = {
  region_id: string;
  version: string;
  built_at_utc: string;
  artifact_file: string;
  size_bytes: number;
  sha256: string;
  tile_count: number;
  min_zoom: number;
  max_zoom: number;
  bounds: { minLat?: number; maxLat?: number; minLng?: number; maxLng?: number };
  source_fingerprint: string;
  profile_fingerprint: string;
  manifest_path: string;
  layers: string[];
  road_index_file: string | null;
  major_road_count: number;
  border_road_count: number;
  missing_road_count: number;
};

type PublicationKind = "ROUTING" | "VISUAL";
type PublicationTarget = {
  artifactKind: PublicationKind;
  region_id: string;
  version: string;
  sha256: string;
  manifest_path: string;
};

type R2CredentialStatus = {
  configured: boolean;
  accountId: string | null;
  bucket: string | null;
  accessKeySuffix: string | null;
  endpointUrl: string | null;
};
type PublicationStatus = {
  running: boolean;
  regionId: string | null;
  packageVersion: string | null;
  stage: string;
  currentKey: string | null;
  bytesTransferred: number;
  totalBytes: number;
  lastError: string | null;
};
type PublishedLatest = {
  schema: string;
  version: number;
  artifactKind: string;
  regionId: string;
  packageVersion: string;
  releaseKey: string;
  releaseSha256: string;
  builtAtUtc: string;
};
type PublishedRelease = {
  key: string;
  sha256: string | null;
  artifactKind: string;
  regionId: string;
  packageVersion: string;
  builtAtUtc: string;
};
type R2RegionPublicationStatus = {
  schema: string;
  version: number;
  regionId: string;
  namespace: string;
  latestKey: string;
  latest: PublishedLatest | null;
  releases: PublishedRelease[];
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
type HandoffSnap = {
  regionId: string;
  input: { lat: number; lng: number };
  correlated: { lat: number; lng: number };
  wayId: number | string | null;
  percentAlong: number | null;
  distanceMeters: number | null;
  heading: number | null;
  linearReference: string | null;
  edgeId: unknown;
  edge: unknown;
  edgeInfo: unknown;
  graph: {
    regionId: string;
    packageVersion: string;
    builtAtUtc: string;
    graphFingerprint: string;
  };
};
type HandoffValidation = {
  passed: boolean;
  regionA: string;
  regionB: string;
  graphA: Record<string, unknown>;
  graphB: Record<string, unknown>;
  probes: Record<string, {
    passed?: boolean;
    elapsedMs?: number;
    error?: string;
    summary?: Record<string, unknown>;
  }>;
};
type HandoffOverride = {
  id: string;
  source: string;
  status: "VALID" | "STALE" | string;
  createdAtEpochMs: number;
  regionA: string;
  regionB: string;
  graphFingerprintA?: string;
  graphFingerprintB?: string;
  snapA: HandoffSnap;
  snapB: HandoffSnap;
  validation?: HandoffValidation;
};
type HandoffArtifactItem = {
  kind: "candidate" | "accepted" | "learned" | "manual";
  id: string | null;
  status: string;
  validationState?: string | null;
  fromRegionId: string;
  toRegionId: string;
  from: { lat: number; lng: number };
  to: { lat: number; lng: number };
  modes: string[];
  evidence: string[];
  separationMeters?: number | null;
  artifactPath: string;
};
type ConnectorAnchor = {
  id: string;
  candidateId: string;
  frontierRoadId: string;
  stableWayId: number;
  neighborRegionId: string;
  sourcePairId: string;
  graphAnchor: {
    coordinate: { lat: number; lng: number };
    graphId: number;
    wayId: number | null;
    percentAlong: number | null;
  };
  roles: {
    MOTORCYCLE: string[];
    CAR: string[];
  };
};
type ConnectorMatrixCell = {
  fromAnchorId: string;
  toAnchorId: string;
  status: "REACHABLE" | "UNREACHABLE" | "INCONCLUSIVE" | string;
  distanceKm: number | null;
  timeSeconds: number | null;
  matrixDistanceKm: number | null;
  matrixTimeSeconds: number | null;
  error: string | null;
};
type ConnectorMatrixMode = {
  entryAnchorIds: string[];
  exitAnchorIds: string[];
  candidatePairCount: number;
  reachableCount: number;
  unreachableCount: number;
  inconclusiveCount: number;
  cells: ConnectorMatrixCell[];
};
type ConnectorMatrixInspection = {
  regionId: string;
  status: "CURRENT" | "STALE" | "MISSING" | string;
  refreshAction: string;
  currentGraph: Record<string, unknown>;
  recognizedInventories: number;
  recognizedMatrices: number;
  searchDirectories: string[];
  inventory: null | {
    artifactPath: string;
    sha256: string;
    current: boolean;
    graph: Record<string, unknown>;
    anchorCount: number;
    sourceConnectivity: Array<Record<string, unknown>>;
    boundaryChecks: Array<{
      neighborPrimaryGeofabrikId: string;
      boundBoundaryFingerprint: string | null;
      currentBoundaryFingerprint: string | null;
      matches: boolean;
    }>;
    anchors: ConnectorAnchor[];
  };
  matrix: null | {
    artifactPath: string;
    current: boolean;
    graph: Record<string, unknown>;
    sourceInventorySha256: string | null;
    sourceAnchorCount: number | null;
    sourceInventoryPresent: boolean;
    sourceInventoryCurrent: boolean;
    anchorCountMatches: boolean;
    modes: {
      MOTORCYCLE?: ConnectorMatrixMode;
      CAR?: ConnectorMatrixMode;
    };
  };
};

type BorderRoadDiffMetrics = {
  commonWays: number;
  aOnlyWays: number;
  bOnlyWays: number;
  loadedEdgesA: number;
  loadedEdgesB: number;
  unidentifiedA: number;
  unidentifiedB: number;
};
type BuildIndexDiff = {
  regionId: string;
  versionA: string;
  versionB: string;
  graphTileFingerprintA: string | null;
  graphTileFingerprintB: string | null;
  internalFingerprintA: string | null;
  internalFingerprintB: string | null;
  counts: {
    addedTiles: number;
    removedTiles: number;
    changedTiles: number;
    internalChangedTiles: number;
    boundaryChangedTiles: number;
  };
  boundaries: Array<{
    sourceId: string;
    oldFingerprint: string | null;
    newFingerprint: string | null;
    requiresRefresh: boolean;
    changedTiles: number;
  }>;
  changedBoundaryTiles: FeatureCollection;
};

type BorderDiagnosticsExport = {
  jsonPath: string;
  markdownPath: string;
  report: unknown;
};
type HandoffArtifactInspection = {
  regionA: string;
  regionB: string;
  graphA: Record<string, unknown>;
  graphB: Record<string, unknown>;
  recognizedArtifactFiles: number;
  searchDirectories: string[];
  items: HandoffArtifactItem[];
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
        <p>Builds run sequentially. Each selected region produces its routing pack and, when enabled, an independently versioned visual PMTiles pack using shared cached source data.</p>
      </section>
      <section class="section">
        <h2>R2 publication</h2>
        <div id="r2CredentialSummary" class="empty">R2 credentials are not configured.</div>
        <details class="route-options" style="margin-top:8px">
          <summary>Credentials</summary>
          <div class="field">
            <label for="r2AccountId">Cloudflare account ID</label>
            <input id="r2AccountId" autocomplete="off" />
          </div>
          <div class="field">
            <label for="r2Bucket">R2 bucket</label>
            <input id="r2Bucket" autocomplete="off" />
          </div>
          <div class="field">
            <label for="r2AccessKey">Access key ID</label>
            <input id="r2AccessKey" type="password" autocomplete="off" placeholder="Leave blank to keep saved key" />
          </div>
          <div class="field">
            <label for="r2SecretKey">Secret access key</label>
            <input id="r2SecretKey" type="password" autocomplete="off" placeholder="Leave blank to keep saved secret" />
          </div>
          <div class="field">
            <label for="r2Endpoint">Custom endpoint (optional)</label>
            <input id="r2Endpoint" autocomplete="off" placeholder="https://…" />
          </div>
          <div class="actions">
            <button id="saveR2CredentialsBtn" class="btn primary" type="button">Save locally</button>
            <button id="testR2CredentialsBtn" class="btn" type="button">Test</button>
            <button id="clearR2CredentialsBtn" class="btn danger" type="button">Clear</button>
          </div>
          <p>Secrets are stored only in Graph Studio app data with private file permissions. They are never written to the repository or publication artifacts.</p>
        </details>
        <div class="field">
          <label for="publicationKind">Artifact</label>
          <select id="publicationKind">
            <option value="ROUTING">Routing graph</option>
            <option value="VISUAL">Visual PMTiles</option>
          </select>
        </div>
        <div class="field">
          <label for="publishBuildSelect">Local validated build</label>
          <select id="publishBuildSelect"></select>
        </div>
        <div class="actions">
          <button id="refreshPublicationBtn" class="btn" type="button">Refresh R2</button>
          <button id="publishBuildBtn" class="btn primary" type="button" disabled>Publish selected</button>
        </div>
        <div id="publicationVersionSummary" class="empty" style="margin-top:8px">Choose a local build.</div>
        <div id="publicationProgress" class="publication-progress"><div></div></div>
        <div id="publicationProgressText" class="status-line">Publication idle.</div>
        <div class="status-title" style="margin-top:10px">Published history</div>
        <div id="publicationHistory" class="empty">No region selected.</div>
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
        <h2>Visual map inspector</h2>
        <div class="field">
          <label for="visualBuildSelect">RoadPilot visual build</label>
          <select id="visualBuildSelect"></select>
        </div>
        <div class="actions">
          <button id="loadVisualBuildBtn" class="btn primary" type="button" disabled>Load exact PMTiles</button>
          <button id="fitVisualBuildBtn" class="btn" type="button" disabled>Fit visual</button>
        </div>
        <div id="visualBuildSummary" class="empty" style="margin-top:8px">No retained visual build selected.</div>

        <details class="route-options" open style="margin-top:10px">
          <summary>Map layers</summary>
          <div id="mapLayerToggles" class="layer-toggle-grid">
            <label><input type="checkbox" data-layer-toggle="offlineVisual" checked /> RoadPilot offline visual</label>
            <label><input type="checkbox" data-layer-toggle="onlineReference" checked /> Online reference</label>
            <label><input type="checkbox" data-layer-toggle="graphEdges" checked /> Valhalla edges</label>
            <label><input type="checkbox" data-layer-toggle="graphNodes" checked /> Valhalla nodes</label>
            <label><input type="checkbox" data-layer-toggle="shortcuts" checked /> Shortcuts</label>
            <label><input type="checkbox" data-layer-toggle="restrictions" checked /> Access restrictions</label>
            <label><input type="checkbox" data-layer-toggle="borderBuffer" checked /> Border buffer</label>
            <label><input type="checkbox" data-layer-toggle="graphA" checked /> Graph A</label>
            <label><input type="checkbox" data-layer-toggle="graphB" checked /> Graph B</label>
            <label><input type="checkbox" data-layer-toggle="route" checked /> Calculated route</label>
            <label><input type="checkbox" data-layer-toggle="expansion" checked /> Route-search expansion</label>
            <label><input type="checkbox" data-layer-toggle="handoffs" checked /> Candidate / learned / manual handoffs</label>
          </div>
        </details>

        <h2 style="margin-top:16px">Visual build comparison</h2>
        <div class="coord-grid">
          <div class="field"><label for="visualCompareA">Visual A</label><select id="visualCompareA"></select></div>
          <div class="field"><label for="visualCompareB">Visual B</label><select id="visualCompareB"></select></div>
        </div>
        <div class="actions">
          <button id="compareVisualBuildsBtn" class="btn" type="button" disabled>Compare visible roads</button>
        </div>
        <div id="visualComparisonSummary" class="empty">Choose two visual builds of the same region.</div>
        <div class="border-diff-legend" style="margin-top:8px">
          <span><i class="legend-common"></i>Unchanged</span>
          <span><i class="legend-a"></i>Removed / A only</span>
          <span><i class="legend-b"></i>Added / B only</span>
          <span><i class="artifact-candidate"></i>Changed</span>
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
        <h2>Border inspector</h2>
        <div class="coord-grid">
          <div class="field">
            <label for="borderRegionA">Graph A</label>
            <select id="borderRegionA"></select>
          </div>
          <div class="field">
            <label for="borderRegionB">Graph B</label>
            <select id="borderRegionB"></select>
          </div>
        </div>
        <div class="actions">
          <button id="loadBorderPairBtn" class="btn" type="button">Load A/B overlay</button>
          <button id="pickHandoffABtn" class="btn" type="button">Pick A edge</button>
          <button id="pickHandoffBBtn" class="btn" type="button">Pick B edge</button>
        </div>
        <div class="handoff-grid">
          <div class="handoff-card">
            <strong>Graph A snap</strong>
            <div id="handoffASummary" class="empty">Not selected.</div>
          </div>
          <div class="handoff-card">
            <strong>Graph B snap</strong>
            <div id="handoffBSummary" class="empty">Not selected.</div>
          </div>
        </div>
        <div class="actions" style="margin-top:8px">
          <button id="validateHandoffBtn" class="btn" type="button" disabled>Validate crossing</button>
          <button id="saveHandoffBtn" class="btn primary" type="button" disabled>Save manual override</button>
          <button id="clearHandoffBtn" class="btn" type="button">Clear</button>
        </div>
        <div id="handoffValidationSummary" class="empty" style="margin-top:8px">No manual crossing selected.</div>
        <div id="handoffProbeList" class="probe-list"></div>
        <h2 style="margin-top:16px">Road overlap</h2>
        <div class="border-diff-legend">
          <span><i class="legend-common"></i>Common OSM way</span>
          <span><i class="legend-a"></i>A only</span>
          <span><i class="legend-b"></i>B only</span>
        </div>
        <div class="actions" style="margin-top:8px">
          <button id="refreshBorderDiffBtn" class="btn" type="button" disabled>Refresh road diff</button>
        </div>
        <div id="borderDiffSummary" class="empty">Load a graph pair to compare border roads.</div>
        <h2 style="margin-top:16px">Handoff layers</h2>
        <div class="handoff-artifact-legend">
          <span><i class="artifact-candidate"></i>Candidate</span>
          <span><i class="artifact-accepted"></i>Accepted / bound</span>
          <span><i class="artifact-learned"></i>Learned F8 proof</span>
          <span><i class="artifact-manual"></i>Manual</span>
        </div>
        <div class="actions" style="margin-top:8px">
          <button id="refreshHandoffArtifactsBtn" class="btn" type="button" disabled>Refresh handoffs</button>
        </div>
        <div id="handoffArtifactSummary" class="empty">Load a graph pair to inspect handoff artifacts.</div>
        <div id="handoffArtifactList" class="artifact-list"></div>
        <h2 style="margin-top:16px">Regional connector matrix</h2>
        <div class="coord-grid">
          <div class="field">
            <label for="connectorRegion">Region</label>
            <select id="connectorRegion"></select>
          </div>
          <div class="field">
            <label for="connectorMode">Mode</label>
            <select id="connectorMode">
              <option value="MOTORCYCLE">Motorcycle</option>
              <option value="CAR">Car</option>
            </select>
          </div>
        </div>
        <div class="connector-matrix-legend">
          <span><i class="connector-reachable"></i>Reachable</span>
          <span><i class="connector-unreachable"></i>Unreachable</span>
          <span><i class="connector-inconclusive"></i>Inconclusive</span>
          <span><i class="connector-anchor"></i>Anchor</span>
        </div>
        <div class="actions" style="margin-top:8px">
          <button id="refreshConnectorMatrixBtn" class="btn" type="button" disabled>Inspect matrix</button>
        </div>
        <div id="connectorMatrixSummary" class="empty">Choose a locally built region to inspect its connector inventory and matrix.</div>
        <div id="connectorMatrixList" class="artifact-list"></div>
        <div class="actions" style="margin-top:10px">
          <button id="exportBorderDiagnosticsBtn" class="btn" type="button" disabled>Export diagnostics</button>
        </div>
        <div id="borderReportSummary" class="empty" style="margin-top:8px">No diagnostics report exported.</div>
        <h2 style="margin-top:16px">Saved manual overrides</h2>
        <div id="handoffOverrideList" class="empty">No manual overrides.</div>
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
const r2CredentialSummary = document.querySelector<HTMLDivElement>("#r2CredentialSummary")!;
const r2AccountId = document.querySelector<HTMLInputElement>("#r2AccountId")!;
const r2Bucket = document.querySelector<HTMLInputElement>("#r2Bucket")!;
const r2AccessKey = document.querySelector<HTMLInputElement>("#r2AccessKey")!;
const r2SecretKey = document.querySelector<HTMLInputElement>("#r2SecretKey")!;
const r2Endpoint = document.querySelector<HTMLInputElement>("#r2Endpoint")!;
const saveR2CredentialsBtn = document.querySelector<HTMLButtonElement>("#saveR2CredentialsBtn")!;
const testR2CredentialsBtn = document.querySelector<HTMLButtonElement>("#testR2CredentialsBtn")!;
const clearR2CredentialsBtn = document.querySelector<HTMLButtonElement>("#clearR2CredentialsBtn")!;
const publicationKind = document.querySelector<HTMLSelectElement>("#publicationKind")!;
const publishBuildSelect = document.querySelector<HTMLSelectElement>("#publishBuildSelect")!;
const refreshPublicationBtn = document.querySelector<HTMLButtonElement>("#refreshPublicationBtn")!;
const publishBuildBtn = document.querySelector<HTMLButtonElement>("#publishBuildBtn")!;
const publicationVersionSummary = document.querySelector<HTMLDivElement>("#publicationVersionSummary")!;
const publicationProgress = document.querySelector<HTMLDivElement>("#publicationProgress")!;
const publicationProgressText = document.querySelector<HTMLDivElement>("#publicationProgressText")!;
const publicationHistory = document.querySelector<HTMLDivElement>("#publicationHistory")!;
const visualBuildSelect = document.querySelector<HTMLSelectElement>("#visualBuildSelect")!;
const loadVisualBuildBtn = document.querySelector<HTMLButtonElement>("#loadVisualBuildBtn")!;
const fitVisualBuildBtn = document.querySelector<HTMLButtonElement>("#fitVisualBuildBtn")!;
const visualBuildSummary = document.querySelector<HTMLDivElement>("#visualBuildSummary")!;
const mapLayerToggles = document.querySelector<HTMLDivElement>("#mapLayerToggles")!;
const visualCompareA = document.querySelector<HTMLSelectElement>("#visualCompareA")!;
const visualCompareB = document.querySelector<HTMLSelectElement>("#visualCompareB")!;
const compareVisualBuildsBtn = document.querySelector<HTMLButtonElement>("#compareVisualBuildsBtn")!;
const visualComparisonSummary = document.querySelector<HTMLDivElement>("#visualComparisonSummary")!;
const graphLayerBtn = document.querySelector<HTMLButtonElement>("#graphLayerBtn")!;
const fitBtn = document.querySelector<HTMLButtonElement>("#fitBtn")!;
const locateBtn = document.querySelector<HTMLButtonElement>("#locateBtn")!;
const borderRegionA = document.querySelector<HTMLSelectElement>("#borderRegionA")!;
const borderRegionB = document.querySelector<HTMLSelectElement>("#borderRegionB")!;
const loadBorderPairBtn = document.querySelector<HTMLButtonElement>("#loadBorderPairBtn")!;
const pickHandoffABtn = document.querySelector<HTMLButtonElement>("#pickHandoffABtn")!;
const pickHandoffBBtn = document.querySelector<HTMLButtonElement>("#pickHandoffBBtn")!;
const handoffASummary = document.querySelector<HTMLDivElement>("#handoffASummary")!;
const handoffBSummary = document.querySelector<HTMLDivElement>("#handoffBSummary")!;
const validateHandoffBtn = document.querySelector<HTMLButtonElement>("#validateHandoffBtn")!;
const saveHandoffBtn = document.querySelector<HTMLButtonElement>("#saveHandoffBtn")!;
const clearHandoffBtn = document.querySelector<HTMLButtonElement>("#clearHandoffBtn")!;
const handoffValidationSummary = document.querySelector<HTMLDivElement>("#handoffValidationSummary")!;
const handoffProbeList = document.querySelector<HTMLDivElement>("#handoffProbeList")!;
const handoffOverrideList = document.querySelector<HTMLDivElement>("#handoffOverrideList")!;
const refreshBorderDiffBtn = document.querySelector<HTMLButtonElement>("#refreshBorderDiffBtn")!;
const borderDiffSummary = document.querySelector<HTMLDivElement>("#borderDiffSummary")!;
const refreshHandoffArtifactsBtn = document.querySelector<HTMLButtonElement>("#refreshHandoffArtifactsBtn")!;
const handoffArtifactSummary = document.querySelector<HTMLDivElement>("#handoffArtifactSummary")!;
const handoffArtifactList = document.querySelector<HTMLDivElement>("#handoffArtifactList")!;
const connectorRegion = document.querySelector<HTMLSelectElement>("#connectorRegion")!;
const connectorMode = document.querySelector<HTMLSelectElement>("#connectorMode")!;
const refreshConnectorMatrixBtn = document.querySelector<HTMLButtonElement>("#refreshConnectorMatrixBtn")!;
const connectorMatrixSummary = document.querySelector<HTMLDivElement>("#connectorMatrixSummary")!;
const connectorMatrixList = document.querySelector<HTMLDivElement>("#connectorMatrixList")!;
const exportBorderDiagnosticsBtn = document.querySelector<HTMLButtonElement>("#exportBorderDiagnosticsBtn")!;
const borderReportSummary = document.querySelector<HTMLDivElement>("#borderReportSummary")!;
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
let visualArtifacts: VisualBuildArtifact[] = [];
let geofabrikCatalog: GeofabrikCatalogItem[] = [];
let editorPreview: RegionPreview | null = null;
let editorExistingConfig: Record<string, unknown> | null = null;
let activeRegion: RegionSummary | null = null;
let graphVisible = false;
let activeVisualBuild: VisualBuildArtifact | null = null;
let referenceLayerIds: string[] = [];
let lastBorderDiffMetrics: BorderRoadDiffMetrics | null = null;
let handoffPickMode: "A" | "B" | null = null;
let editingHandoffId: string | null = null;
let handoffSnapA: HandoffSnap | null = null;
let handoffSnapB: HandoffSnap | null = null;
let handoffValidation: HandoffValidation | null = null;
let connectorInspection: ConnectorMatrixInspection | null = null;
let r2Credentials: R2CredentialStatus | null = null;
let remotePublication: R2RegionPublicationStatus | null = null;
let currentPublicationStatus: PublicationStatus | null = null;
let toolchainReady = false;
let handoffMarkerA: Marker | null = null;
let handoffMarkerB: Marker | null = null;
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

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function activePublicationKind(): PublicationKind {
  return publicationKind.value === "VISUAL" ? "VISUAL" : "ROUTING";
}

function publicationPrefix(): "routing" | "visual" {
  return activePublicationKind() === "VISUAL" ? "visual" : "routing";
}

function publicationTargets(): PublicationTarget[] {
  if (activePublicationKind() === "VISUAL") {
    return visualArtifacts.map(item => ({
      artifactKind: "VISUAL",
      region_id: item.region_id,
      version: item.version,
      sha256: item.sha256,
      manifest_path: item.manifest_path,
    }));
  }
  return artifacts.map(item => ({
    artifactKind: "ROUTING",
    region_id: item.region_id,
    version: item.version,
    sha256: item.sha256,
    manifest_path: item.manifest_path,
  }));
}

function selectedPublicationBuild(): PublicationTarget | null {
  const manifestPath = publishBuildSelect.value;
  return publicationTargets().find(item => item.manifest_path === manifestPath) ?? null;
}

function renderPublicationBuildSelector(): void {
  const previous = publishBuildSelect.value;
  const kind = activePublicationKind();
  const targets = publicationTargets();
  publishBuildSelect.innerHTML = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = targets.length
    ? `Choose ${kind === "VISUAL" ? "visual" : "routing"} build…`
    : `No retained ${kind === "VISUAL" ? "visual" : "routing"} builds`;
  publishBuildSelect.appendChild(empty);
  for (const item of targets) {
    const option = document.createElement("option");
    option.value = item.manifest_path;
    option.textContent = `${item.region_id} • ${item.version}`;
    publishBuildSelect.appendChild(option);
  }
  if ([...publishBuildSelect.options].some(option => option.value === previous)) {
    publishBuildSelect.value = previous;
  }
  remotePublication = null;
  renderPublicationRemoteStatus();
  updatePublicationControls();
}

function updatePublicationControls(): void {
  const hasBuild = selectedPublicationBuild() != null;
  const configured = r2Credentials?.configured === true;
  const running = currentPublicationStatus?.running === true;
  publicationKind.disabled = running;
  publishBuildSelect.disabled = running;
  publishBuildBtn.disabled = !hasBuild || !configured || running;
  refreshPublicationBtn.disabled = !hasBuild || !configured || running;
  testR2CredentialsBtn.disabled = !configured || running;
  saveR2CredentialsBtn.disabled = running;
  clearR2CredentialsBtn.disabled = !configured || running;
}

function renderR2CredentialStatus(status: R2CredentialStatus): void {
  r2Credentials = status;
  r2CredentialSummary.className = status.configured ? "kv" : "empty";
  if (!status.configured) {
    r2CredentialSummary.textContent = "R2 credentials are not configured.";
  } else {
    r2CredentialSummary.innerHTML = `
      <dt>Account</dt><dd>${escapeHtml(status.accountId)}</dd>
      <dt>Bucket</dt><dd>${escapeHtml(status.bucket)}</dd>
      <dt>Access key</dt><dd>••••${escapeHtml(status.accessKeySuffix)}</dd>
      <dt>Endpoint</dt><dd>${escapeHtml(status.endpointUrl || "Cloudflare R2 default")}</dd>
    `;
    if (!r2AccountId.value) r2AccountId.value = status.accountId ?? "";
    if (!r2Bucket.value) r2Bucket.value = status.bucket ?? "";
    if (!r2Endpoint.value) r2Endpoint.value = status.endpointUrl ?? "";
  }
  r2AccessKey.value = "";
  r2SecretKey.value = "";
  updatePublicationControls();
}

async function refreshR2CredentialStatus(): Promise<void> {
  try {
    renderR2CredentialStatus(await invoke<R2CredentialStatus>("r2_credential_status"));
  } catch (error) {
    r2Credentials = null;
    r2CredentialSummary.className = "bad";
    r2CredentialSummary.textContent = `Could not read local R2 credential state: ${String(error)}`;
    updatePublicationControls();
  }
}

function renderPublicationStatus(status: PublicationStatus): void {
  const wasRunning = currentPublicationStatus?.running === true;
  currentPublicationStatus = status;
  const percent = status.totalBytes > 0
    ? Math.max(0, Math.min(100, status.bytesTransferred / status.totalBytes * 100))
    : 0;
  const bar = publicationProgress.firstElementChild as HTMLDivElement | null;
  if (bar) bar.style.width = `${percent.toFixed(1)}%`;
  publicationProgress.classList.toggle("active", status.running && status.totalBytes > 0);
  if (status.lastError) {
    publicationProgressText.className = "status-line bad";
    publicationProgressText.textContent = status.lastError;
  } else if (status.running) {
    publicationProgressText.className = "status-line";
    const transfer = status.totalBytes > 0
      ? ` • ${bytes(status.bytesTransferred)} / ${bytes(status.totalBytes)}`
      : "";
    publicationProgressText.textContent =
      `${status.stage}${status.currentKey ? ` • ${status.currentKey}` : ""}${transfer}`;
  } else {
    publicationProgressText.className = "status-line";
    publicationProgressText.textContent = status.stage || "Publication idle.";
  }
  updatePublicationControls();
  if (wasRunning && !status.running && !status.lastError) {
    void refreshR2Publication();
  }
}

async function refreshPublicationStatus(): Promise<void> {
  try {
    renderPublicationStatus(await invoke<PublicationStatus>("publication_status"));
  } catch { /* keep last state */ }
}

function renderPublicationRemoteStatus(): void {
  const local = selectedPublicationBuild();
  const remote = remotePublication;
  publicationHistory.innerHTML = "";
  if (!local) {
    publicationVersionSummary.className = "empty";
    publicationVersionSummary.textContent = "Choose a local build.";
    publicationHistory.className = "empty";
    publicationHistory.textContent = "No region selected.";
    updatePublicationControls();
    return;
  }

  const latest = remote?.latest ?? null;
  const state = !latest
    ? "NOT PUBLISHED"
    : latest.artifactKind !== local.artifactKind
      ? "WRONG ARTIFACT"
      : latest.packageVersion === local.version
        ? "CURRENT"
        : "DIFFERENT";
  const stateClass = state === "CURRENT" ? "ok" : state === "WRONG ARTIFACT" ? "bad" : "warn";
  publicationVersionSummary.className = "kv";
  publicationVersionSummary.innerHTML = `
    <dt>Artifact</dt><dd>${escapeHtml(local.artifactKind)}</dd>
    <dt>Namespace</dt><dd>${escapeHtml(publicationPrefix())}/${escapeHtml(local.region_id)}</dd>
    <dt>Region</dt><dd>${escapeHtml(local.region_id)}</dd>
    <dt>Local</dt><dd>${escapeHtml(local.version)}</dd>
    <dt>R2 latest</dt><dd>${escapeHtml(latest?.packageVersion ?? "none")}</dd>
    <dt>Status</dt><dd class="${stateClass}">${state}</dd>
    <dt>Local SHA</dt><dd>${escapeHtml(local.sha256)}</dd>
    <dt>Latest release</dt><dd>${escapeHtml(latest?.releaseKey ?? "—")}</dd>
  `;

  const releases = remote?.releases ?? [];
  if (!releases.length) {
    publicationHistory.className = "empty";
    publicationHistory.textContent = "No immutable releases published for this region.";
  } else {
    publicationHistory.className = "publication-history";
    for (const release of releases) {
      const row = document.createElement("div");
      row.className = "publication-release-row";
      const info = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = release.packageVersion;
      const meta = document.createElement("small");
      const isLatest = latest?.releaseKey === release.key;
      meta.textContent = `${release.builtAtUtc} • ${isLatest ? "LATEST • " : ""}${release.sha256?.slice(0, 18) ?? "no SHA"}…`;
      info.append(title, meta);
      const action = document.createElement("button");
      action.className = "btn";
      action.type = "button";
      action.textContent = isLatest ? "Current" : "Roll back";
      action.disabled = isLatest || currentPublicationStatus?.running === true;
      action.addEventListener("click", async () => {
        action.disabled = true;
        publicationProgressText.className = "status-line";
        publicationProgressText.textContent = `Verifying and activating ${release.packageVersion}…`;
        try {
          await invoke("activate_r2_release", { releaseKey: release.key });
          appendLog(`R2 latest rolled back to ${local.region_id} • ${release.packageVersion}`);
          await refreshR2Publication();
        } catch (error) {
          publicationProgressText.className = "status-line bad";
          publicationProgressText.textContent = `Rollback failed: ${String(error)}`;
        } finally {
          action.disabled = false;
        }
      });
      row.append(info, action);
      publicationHistory.appendChild(row);
    }
  }
  updatePublicationControls();
}

async function refreshR2Publication(): Promise<void> {
  const local = selectedPublicationBuild();
  remotePublication = null;
  if (!local) {
    renderPublicationRemoteStatus();
    return;
  }
  if (!r2Credentials?.configured) {
    publicationVersionSummary.className = "warn";
    publicationVersionSummary.textContent = "Configure R2 credentials to compare local and published versions.";
    publicationHistory.className = "empty";
    publicationHistory.textContent = "R2 not configured.";
    updatePublicationControls();
    return;
  }
  publicationVersionSummary.className = "empty";
  publicationVersionSummary.textContent = "Reading latest.json and immutable release history…";
  try {
    remotePublication = await invoke<R2RegionPublicationStatus>("r2_region_publication_status", {
      regionId: local.region_id,
      prefix: publicationPrefix(),
    });
    renderPublicationRemoteStatus();
  } catch (error) {
    publicationVersionSummary.className = "bad";
    publicationVersionSummary.textContent = `R2 inspection failed: ${String(error)}`;
    publicationHistory.className = "empty";
    publicationHistory.textContent = "Could not read published history.";
  }
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

const buildGraphManifests = new globalThis.Map<string, string>();
addProtocol("roadpilot-build-graph", async (request) => {
  const raw = request.url.replace("roadpilot-build-graph://", "");
  const match = raw.match(/^([^/]+)\/(\d+)\/(\d+)\/(\d+)\.mvt$/);
  if (!match) throw new Error("Invalid retained-build graph tile URL");
  const [, buildKey, z, x, y] = match;
  const manifestPath = buildGraphManifests.get(buildKey);
  if (!manifestPath) throw new Error(`Unknown retained build key: ${buildKey}`);
  const data = await invoke<number[]>("graph_tile_for_build", {
    manifestPath,
    z: Number(z),
    x: Number(x),
    y: Number(y),
  });
  return { data: new Uint8Array(data).buffer };
});

class TauriPmtilesSource implements PMTilesSource {
  constructor(
    private readonly manifestPath: string,
    private readonly key: string,
  ) {}

  getKey(): string {
    return this.key;
  }

  async getBytes(
    offset: number,
    length: number,
    signal?: AbortSignal,
  ): Promise<RangeResponse> {
    signal?.throwIfAborted();
    const data = await invoke<number[]>("visual_archive_range", {
      manifestPath: this.manifestPath,
      offset,
      length,
    });
    signal?.throwIfAborted();
    return { data: new Uint8Array(data).buffer };
  }
}

const visualArchives = new globalThis.Map<string, PMTiles>();

function visualArchiveKey(build: VisualBuildArtifact): string {
  return build.sha256;
}

function ensureVisualArchive(build: VisualBuildArtifact): PMTiles {
  const key = visualArchiveKey(build);
  const existing = visualArchives.get(key);
  if (existing) return existing;
  const source = new TauriPmtilesSource(
    build.manifest_path,
    `roadpilot-local-pmtiles:${key}`,
  );
  const archive = new PMTiles(source);
  visualArchives.set(key, archive);
  return archive;
}

addProtocol("roadpilot-visual", async (request) => {
  const raw = request.url.replace("roadpilot-visual://", "");
  const match = raw.match(/^([0-9a-f]{64})\/(\d+)\/(\d+)\/(\d+)\.mvt$/);
  if (!match) throw new Error("Invalid RoadPilot visual tile URL");
  const [, key, z, x, y] = match;
  const archive = visualArchives.get(key);
  if (!archive) throw new Error(`Unknown retained visual archive: ${key}`);
  const tile = await archive.getZxy(Number(z), Number(x), Number(y));
  return { data: tile?.data ?? new ArrayBuffer(0) };
});

const map = new MapLibreMap({
  container: "map",
  style: "https://tiles.openfreemap.org/styles/bright",
  center: [11.8, 46.2],
  zoom: 6.2,
});
map.addControl(new NavigationControl({ showCompass: true }), "bottom-right");

const visualSourceId = "roadpilot-offline-visual";
const visualLayerIds = [
  "rp-visual-water",
  "rp-visual-waterway",
  "rp-visual-boundary",
  "rp-visual-roads",
  "rp-visual-road-labels",
  "rp-visual-places",
  "rp-visual-mountains",
];

function setLayerVisibility(ids: string[], visible: boolean): void {
  for (const id of ids) {
    if (map.getLayer(id)) {
      map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    }
  }
}

function layerToggleChecked(name: string): boolean {
  const input = mapLayerToggles.querySelector<HTMLInputElement>(
    `input[data-layer-toggle="${name}"]`,
  );
  return input?.checked !== false;
}

function applyMapLayerToggles(): void {
  setLayerVisibility(visualLayerIds, layerToggleChecked("offlineVisual"));
  setLayerVisibility(referenceLayerIds, layerToggleChecked("onlineReference"));
  setLayerVisibility(["rp-graph-edges"], layerToggleChecked("graphEdges"));
  setLayerVisibility(["rp-graph-nodes"], layerToggleChecked("graphNodes"));
  setLayerVisibility(["rp-graph-shortcuts"], layerToggleChecked("shortcuts"));
  setLayerVisibility(["rp-graph-restrictions"], layerToggleChecked("restrictions"));
  setLayerVisibility(
    ["rp-editor-buffer-fill", "rp-editor-buffer-line"],
    layerToggleChecked("borderBuffer"),
  );
  setLayerVisibility(["roadpilot-border-a-edges"], layerToggleChecked("graphA"));
  setLayerVisibility(["roadpilot-border-b-edges"], layerToggleChecked("graphB"));
  setLayerVisibility(["roadpilot-route-line"], layerToggleChecked("route"));
  setLayerVisibility(["roadpilot-expansion-line"], layerToggleChecked("expansion"));
  setLayerVisibility(
    [
      "roadpilot-handoff-candidate",
      "roadpilot-handoff-accepted",
      "roadpilot-handoff-learned",
      "roadpilot-handoff-manual",
      "roadpilot-handoff-endpoints",
    ],
    layerToggleChecked("handoffs"),
  );
}

mapLayerToggles.querySelectorAll<HTMLInputElement>("input[data-layer-toggle]").forEach(input => {
  input.addEventListener("change", applyMapLayerToggles);
});

map.on("load", () => {
  referenceLayerIds = (map.getStyle().layers ?? []).map(layer => layer.id);
  applyMapLayerToggles();
});

function removeVisualBuildLayer(): void {
  for (const id of visualLayerIds) if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource(visualSourceId)) map.removeSource(visualSourceId);
  activeVisualBuild = null;
}

function addVisualBuildLayer(build: VisualBuildArtifact): void {
  removeVisualBuildLayer();
  ensureVisualArchive(build);
  map.addSource(visualSourceId, {
    type: "vector",
    tiles: [
      `roadpilot-visual://${visualArchiveKey(build)}/{z}/{x}/{y}.mvt`,
    ],
    minzoom: build.min_zoom,
    maxzoom: build.max_zoom,
  });

  map.addLayer({
    id: "rp-visual-water",
    type: "fill",
    source: visualSourceId,
    "source-layer": "water",
    paint: { "fill-color": "#7fb5d8", "fill-opacity": 0.72 },
  });
  map.addLayer({
    id: "rp-visual-waterway",
    type: "line",
    source: visualSourceId,
    "source-layer": "waterway",
    paint: {
      "line-color": "#6ca8cf",
      "line-width": ["interpolate", ["linear"], ["zoom"], 7, 0.7, 14, 2.2],
      "line-opacity": 0.9,
    },
  });
  map.addLayer({
    id: "rp-visual-boundary",
    type: "line",
    source: visualSourceId,
    "source-layer": "boundary",
    paint: {
      "line-color": "#8b78a9",
      "line-width": ["interpolate", ["linear"], ["zoom"], 4, 0.7, 12, 1.8],
      "line-dasharray": [3, 2],
      "line-opacity": 0.8,
    },
  });
  map.addLayer({
    id: "rp-visual-roads",
    type: "line",
    source: visualSourceId,
    "source-layer": "transportation",
    paint: {
      "line-color": [
        "match",
        ["get", "class"],
        "motorway", "#e7a04a",
        "trunk", "#e5b35a",
        "primary", "#f2d07a",
        "secondary", "#ded6bc",
        "#b9bec4",
      ],
      "line-width": [
        "interpolate",
        ["linear"],
        ["zoom"],
        5, 0.6,
        9, 1.3,
        14, 4.2,
      ],
      "line-opacity": 0.95,
    },
  });
  map.addLayer({
    id: "rp-visual-road-labels",
    type: "symbol",
    source: visualSourceId,
    "source-layer": "transportation_name",
    minzoom: 7,
    layout: {
      "symbol-placement": "line",
      "text-field": ["coalesce", ["get", "name"], ["get", "ref"]],
      "text-size": ["interpolate", ["linear"], ["zoom"], 7, 9, 14, 12],
      "text-max-angle": 30,
    },
    paint: {
      "text-color": "#37404a",
      "text-halo-color": "#f7f3e8",
      "text-halo-width": 1.2,
    },
  });
  map.addLayer({
    id: "rp-visual-places",
    type: "symbol",
    source: visualSourceId,
    "source-layer": "place",
    layout: {
      "text-field": ["coalesce", ["get", "name"], ["get", "name_en"]],
      "text-size": [
        "match",
        ["get", "class"],
        "city", 15,
        "town", 12,
        10,
      ],
      "text-offset": [0, 0.5],
    },
    paint: {
      "text-color": "#27313a",
      "text-halo-color": "#f7f3e8",
      "text-halo-width": 1.3,
    },
  });
  map.addLayer({
    id: "rp-visual-mountains",
    type: "symbol",
    source: visualSourceId,
    "source-layer": "mountain_peak",
    minzoom: 9,
    layout: {
      "text-field": [
        "case",
        ["has", "ele"],
        ["concat", ["coalesce", ["get", "name"], ""], " ", ["to-string", ["get", "ele"]], " m"],
        ["coalesce", ["get", "name"], ""],
      ],
      "text-size": 10,
      "text-offset": [0, 0.8],
    },
    paint: {
      "text-color": "#665b52",
      "text-halo-color": "#f7f3e8",
      "text-halo-width": 1,
    },
  });
  activeVisualBuild = build;
  applyMapLayerToggles();
}

function fitVisualBuild(build: VisualBuildArtifact): void {
  const b = build.bounds;
  if (
    Number.isFinite(b.minLng) && Number.isFinite(b.minLat)
    && Number.isFinite(b.maxLng) && Number.isFinite(b.maxLat)
  ) {
    map.fitBounds(
      [[Number(b.minLng), Number(b.minLat)], [Number(b.maxLng), Number(b.maxLat)]],
      { padding: 48, duration: 450 },
    );
  }
}

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
  applyMapLayerToggles();
}

const borderSourceA = "roadpilot-border-a";
const borderSourceB = "roadpilot-border-b";
const borderLayerA = "roadpilot-border-a-edges";
const borderLayerB = "roadpilot-border-b-edges";
const borderDiffSource = "roadpilot-border-road-diff";
const borderDiffCommonLayer = "roadpilot-border-common";
const borderDiffAOnlyLayer = "roadpilot-border-a-only";
const borderDiffBOnlyLayer = "roadpilot-border-b-only";
const buildDiffSource = "roadpilot-build-boundary-diff";
const buildDiffFillLayer = "roadpilot-build-boundary-diff-fill";
const buildDiffLineLayer = "roadpilot-build-boundary-diff-line";
const buildRoadSourceA = "roadpilot-build-road-a";
const buildRoadSourceB = "roadpilot-build-road-b";
const buildRoadHiddenLayerA = "roadpilot-build-road-a-hidden";
const buildRoadHiddenLayerB = "roadpilot-build-road-b-hidden";
const buildRoadDiffSource = "roadpilot-build-road-diff";
const buildRoadAddedLayer = "roadpilot-build-road-added";
const buildRoadRemovedLayer = "roadpilot-build-road-removed";
const buildRoadChangedLayer = "roadpilot-build-road-changed";
let buildComparisonGeneration = 0;

function removeBuildRoadDiff(): void {
  for (const id of [
    buildRoadAddedLayer,
    buildRoadRemovedLayer,
    buildRoadChangedLayer,
    buildRoadHiddenLayerA,
    buildRoadHiddenLayerB,
  ]) {
    if (map.getLayer(id)) map.removeLayer(id);
  }
  for (const id of [buildRoadDiffSource, buildRoadSourceA, buildRoadSourceB]) {
    if (map.getSource(id)) map.removeSource(id);
  }
  buildGraphManifests.delete("a");
  buildGraphManifests.delete("b");
}

function removeBuildDiffOverlay(): void {
  removeBuildRoadDiff();
  for (const id of [buildDiffFillLayer, buildDiffLineLayer]) {
    if (map.getLayer(id)) map.removeLayer(id);
  }
  if (map.getSource(buildDiffSource)) map.removeSource(buildDiffSource);
}

function showBuildDiffOverlay(collection: FeatureCollection): void {
  removeBuildDiffOverlay();
  if (!collection.features.length) return;
  map.addSource(buildDiffSource, { type: "geojson", data: collection });
  map.addLayer({
    id: buildDiffFillLayer,
    type: "fill",
    source: buildDiffSource,
    paint: {
      "fill-color": [
        "match", ["get", "status"],
        "added", "#42c58a",
        "removed", "#e35d5b",
        "#f2a93b",
      ],
      "fill-opacity": 0.18,
    },
  });
  map.addLayer({
    id: buildDiffLineLayer,
    type: "line",
    source: buildDiffSource,
    paint: {
      "line-color": [
        "match", ["get", "status"],
        "added", "#42c58a",
        "removed", "#e35d5b",
        "#f2a93b",
      ],
      "line-width": 2.2,
      "line-opacity": 0.9,
    },
  });
  const bounds = collection.features
    .map(feature => feature.geometry)
    .filter((geometry): geometry is Extract<Geometry, { type: "Polygon" }> => geometry.type === "Polygon")
    .flatMap(geometry => geometry.coordinates[0])
    .reduce<{ minLng: number; minLat: number; maxLng: number; maxLat: number } | null>((acc, coordinate) => {
      const [lng, lat] = coordinate;
      if (!acc) return { minLng: lng, minLat: lat, maxLng: lng, maxLat: lat };
      acc.minLng = Math.min(acc.minLng, lng);
      acc.minLat = Math.min(acc.minLat, lat);
      acc.maxLng = Math.max(acc.maxLng, lng);
      acc.maxLat = Math.max(acc.maxLat, lat);
      return acc;
    }, null);
  if (bounds) {
    map.fitBounds([[bounds.minLng, bounds.minLat], [bounds.maxLng, bounds.maxLat]], { padding: 70, duration: 450 });
  }
}

type RoadFeature = {
  type: "Feature";
  geometry: Geometry;
  properties?: Record<string, unknown> | null;
};

type RoadAggregate = {
  features: RoadFeature[];
  attributeSignatures: Set<string>;
  geometrySignatures: Set<string>;
};

const buildRoadComparableProperties = [
  "use",
  "country_crossing",
  "access_forward",
  "access_backward",
  "length",
  "speed_forward",
  "speed_backward",
  "speed_limit",
  "tunnel",
  "bridge",
  "roundabout",
  "destination_only",
  "unpaved",
  "surface",
  "ramp",
  "not_thru",
  "layer",
] as const;

function normalizedNumber(value: number): number {
  return Math.round(value * 1_000_000) / 1_000_000;
}

function canonicalLineCoordinates(coordinates: number[][]): string {
  const normalized = coordinates.map(([lng, lat]) => [normalizedNumber(lng), normalizedNumber(lat)]);
  const forward = JSON.stringify(normalized);
  const reverse = JSON.stringify([...normalized].reverse());
  return forward < reverse ? forward : reverse;
}

function geometrySignature(geometry: Geometry): string {
  if (geometry.type === "LineString") {
    return "LineString:" + canonicalLineCoordinates(geometry.coordinates as number[][]);
  }
  if (geometry.type === "MultiLineString") {
    const parts = (geometry.coordinates as number[][][]).map(canonicalLineCoordinates).sort();
    return "MultiLineString:" + JSON.stringify(parts);
  }
  return JSON.stringify(geometry);
}

function geometryBounds(geometry: Geometry): [number, number, number, number] | null {
  const points: number[][] = [];
  const collect = (value: unknown): void => {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && typeof value[0] === "number" && typeof value[1] === "number") {
      points.push([value[0], value[1]]);
      return;
    }
    for (const item of value) collect(item);
  };
  if ("coordinates" in geometry) collect(geometry.coordinates);
  if (!points.length) return null;
  let minLng = points[0][0], maxLng = points[0][0];
  let minLat = points[0][1], maxLat = points[0][1];
  for (const [lng, lat] of points.slice(1)) {
    minLng = Math.min(minLng, lng);
    maxLng = Math.max(maxLng, lng);
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
  }
  return [minLng, minLat, maxLng, maxLat];
}

function boundaryTileBounds(collection: FeatureCollection): Array<[number, number, number, number]> {
  return collection.features
    .map(feature => geometryBounds(feature.geometry as Geometry))
    .filter((value): value is [number, number, number, number] => value != null);
}

function boundsIntersect(a: [number, number, number, number], b: [number, number, number, number]): boolean {
  return a[0] <= b[2] && a[2] >= b[0] && a[1] <= b[3] && a[3] >= b[1];
}

function featureTouchesChangedBoundary(
  geometry: Geometry,
  changedBounds: Array<[number, number, number, number]>,
): boolean {
  const bounds = geometryBounds(geometry);
  return bounds != null && changedBounds.some(candidate => boundsIntersect(bounds, candidate));
}

function roadAttributeSignature(properties: Record<string, unknown> | null | undefined): string {
  return JSON.stringify(buildRoadComparableProperties.map(key => [key, properties?.[key] ?? null]));
}

function aggregateRoadWays(
  features: ReturnType<typeof map.querySourceFeatures>,
  changedBounds: Array<[number, number, number, number]>,
): globalThis.Map<string, RoadAggregate> {
  const ways = new globalThis.Map<string, RoadAggregate>();
  for (const raw of features) {
    const feature = raw as unknown as RoadFeature;
    const osmId = edgeOsmId(feature);
    if (!osmId || !featureTouchesChangedBoundary(feature.geometry, changedBounds)) continue;
    let aggregate = ways.get(osmId);
    if (!aggregate) {
      aggregate = { features: [], attributeSignatures: new Set<string>(), geometrySignatures: new Set<string>() };
      ways.set(osmId, aggregate);
    }
    aggregate.features.push(feature);
    aggregate.attributeSignatures.add(roadAttributeSignature(feature.properties));
    aggregate.geometrySignatures.add(geometrySignature(feature.geometry));
  }
  return ways;
}

function aggregateSignature(aggregate: RoadAggregate): string {
  return JSON.stringify({
    attributes: [...aggregate.attributeSignatures].sort(),
    geometries: [...aggregate.geometrySignatures].sort(),
  });
}

function renderBuildRoadDiffCollection(collection: FeatureCollection): void {
  for (const id of [buildRoadAddedLayer, buildRoadRemovedLayer, buildRoadChangedLayer]) {
    if (map.getLayer(id)) map.removeLayer(id);
  }
  if (map.getSource(buildRoadDiffSource)) map.removeSource(buildRoadDiffSource);
  if (!collection.features.length) return;
  map.addSource(buildRoadDiffSource, { type: "geojson", data: collection });
  map.addLayer({
    id: buildRoadAddedLayer, type: "line", source: buildRoadDiffSource,
    filter: ["==", ["get", "classification"], "added"],
    paint: { "line-color": "#42c58a", "line-width": 4, "line-opacity": 0.95 },
  });
  map.addLayer({
    id: buildRoadRemovedLayer, type: "line", source: buildRoadDiffSource,
    filter: ["==", ["get", "classification"], "removed"],
    paint: { "line-color": "#e35d5b", "line-width": 4, "line-opacity": 0.95 },
  });
  map.addLayer({
    id: buildRoadChangedLayer, type: "line", source: buildRoadDiffSource,
    filter: ["==", ["get", "classification"], "changed"],
    paint: { "line-color": "#f2a93b", "line-width": 4.6, "line-opacity": 0.98 },
  });
}

function classifyBuildRoads(diff: BuildIndexDiff, generation: number): void {
  if (generation !== buildComparisonGeneration) return;
  const changedBounds = boundaryTileBounds(diff.changedBoundaryTiles);
  if (!changedBounds.length) return;
  const featuresA = map.querySourceFeatures(buildRoadSourceA, { sourceLayer: "edges" });
  const featuresB = map.querySourceFeatures(buildRoadSourceB, { sourceLayer: "edges" });
  const summary = document.querySelector<HTMLElement>("#buildRoadDiffSummary");
  if (!featuresA.length && !featuresB.length) {
    if (summary) summary.textContent = "no retained edge features loaded for the changed boundary window";
    return;
  }
  const waysA = aggregateRoadWays(featuresA, changedBounds);
  const waysB = aggregateRoadWays(featuresB, changedBounds);
  const ids = new Set([...waysA.keys(), ...waysB.keys()]);
  let added = 0, removed = 0, changed = 0, unchanged = 0;
  const output: Feature[] = [];
  const seen = new Set<string>();
  const emit = (aggregate: RoadAggregate, classification: "added" | "removed" | "changed", side: "A" | "B", osmId: string): void => {
    for (const feature of aggregate.features) {
      const key = classification + ":" + side + ":" + osmId + ":" + geometrySignature(feature.geometry);
      if (seen.has(key)) continue;
      seen.add(key);
      output.push({
        type: "Feature", geometry: feature.geometry,
        properties: { ...(feature.properties ?? {}), classification, source_build: side, osm_id: osmId },
      });
    }
  };
  for (const osmId of ids) {
    const a = waysA.get(osmId);
    const b = waysB.get(osmId);
    if (!a && b) { added += 1; emit(b, "added", "B", osmId); continue; }
    if (a && !b) { removed += 1; emit(a, "removed", "A", osmId); continue; }
    if (!a || !b) continue;
    if (aggregateSignature(a) !== aggregateSignature(b)) {
      changed += 1;
      emit(b, "changed", "B", osmId);
    } else {
      unchanged += 1;
    }
  }
  renderBuildRoadDiffCollection({ type: "FeatureCollection", features: output });
  if (summary) {
    const stateClass = added || removed || changed ? "warn" : "ok";
    summary.innerHTML =
      "<span class=\"" + stateClass + "\">" +
      added + " added / " + removed + " removed / " + changed + " changed / " + unchanged + " unchanged OSM ways</span>" +
      "<small> (" + featuresA.length + " A edges / " + featuresB.length + " B edges loaded)</small>";
  }
}

function loadBuildRoadComparison(a: BuildArtifact, b: BuildArtifact, diff: BuildIndexDiff, generation: number): void {
  if (!diff.changedBoundaryTiles.features.length) return;
  buildGraphManifests.set("a", a.manifest_path);
  buildGraphManifests.set("b", b.manifest_path);
  map.addSource(buildRoadSourceA, {
    type: "vector", tiles: ["roadpilot-build-graph://a/{z}/{x}/{y}.mvt"], minzoom: 5, maxzoom: 18,
  });
  map.addSource(buildRoadSourceB, {
    type: "vector", tiles: ["roadpilot-build-graph://b/{z}/{x}/{y}.mvt"], minzoom: 5, maxzoom: 18,
  });
  map.addLayer({
    id: buildRoadHiddenLayerA, type: "line", source: buildRoadSourceA, "source-layer": "edges",
    paint: { "line-opacity": 0.01, "line-width": 0.5 },
  });
  map.addLayer({
    id: buildRoadHiddenLayerB, type: "line", source: buildRoadSourceB, "source-layer": "edges",
    paint: { "line-opacity": 0.01, "line-width": 0.5 },
  });
  map.once("idle", () => classifyBuildRoads(diff, generation));
}

function removeBorderRoadDiff(): void {
  lastBorderDiffMetrics = null;
  for (const id of [borderDiffCommonLayer, borderDiffAOnlyLayer, borderDiffBOnlyLayer]) {
    if (map.getLayer(id)) map.removeLayer(id);
  }
  if (map.getSource(borderDiffSource)) map.removeSource(borderDiffSource);
  borderDiffSummary.className = "empty";
  borderDiffSummary.textContent = "Load a graph pair to compare border roads.";
}

function removeBorderPairLayers(): void {
  removeBorderRoadDiff();
  removeHandoffArtifactOverlay();
  for (const id of [borderLayerA, borderLayerB]) if (map.getLayer(id)) map.removeLayer(id);
  for (const id of [borderSourceA, borderSourceB]) if (map.getSource(id)) map.removeSource(id);
  refreshBorderDiffBtn.disabled = true;
  exportBorderDiagnosticsBtn.disabled = true;
  borderReportSummary.className = "empty";
  borderReportSummary.textContent = "No diagnostics report exported.";
}

function edgeOsmId(feature: { properties?: Record<string, unknown> | null }): string | null {
  const value = feature.properties?.osm_id;
  if (value == null || value === "") return null;
  return String(value);
}

function borderDiffFeatureKey(osmId: string, geometry: Geometry, side: string): string {
  return `${side}:${osmId}:${JSON.stringify(geometry)}`;
}

function refreshBorderRoadDiff(): void {
  if (!map.getSource(borderSourceA) || !map.getSource(borderSourceB)) return;

  const featuresA = map.querySourceFeatures(borderSourceA, { sourceLayer: "edges" });
  const featuresB = map.querySourceFeatures(borderSourceB, { sourceLayer: "edges" });
  if (!featuresA.length && !featuresB.length) {
    lastBorderDiffMetrics = null;
    borderDiffSummary.className = "empty";
    borderDiffSummary.textContent = "Graph tiles are still loading. Move/zoom the map or refresh again.";
    return;
  }

  const idsA = new Set<string>();
  const idsB = new Set<string>();
  let unidentifiedA = 0;
  let unidentifiedB = 0;
  for (const feature of featuresA) {
    const id = edgeOsmId(feature);
    if (id) idsA.add(id);
    else unidentifiedA += 1;
  }
  for (const feature of featuresB) {
    const id = edgeOsmId(feature);
    if (id) idsB.add(id);
    else unidentifiedB += 1;
  }

  const common = new Set([...idsA].filter(id => idsB.has(id)));
  const aOnly = new Set([...idsA].filter(id => !idsB.has(id)));
  const bOnly = new Set([...idsB].filter(id => !idsA.has(id)));

  const output: Feature[] = [];
  const seen = new Set<string>();
  const addFeatures = (
    features: typeof featuresA,
    allowed: Set<string>,
    classification: "common" | "a-only" | "b-only",
    side: "A" | "B",
  ) => {
    for (const feature of features) {
      const osmId = edgeOsmId(feature);
      if (!osmId || !allowed.has(osmId)) continue;
      const key = borderDiffFeatureKey(osmId, feature.geometry as Geometry, side);
      if (seen.has(key)) continue;
      seen.add(key);
      output.push({
        type: "Feature",
        geometry: feature.geometry as Geometry,
        properties: {
          classification,
          side,
          osm_id: osmId,
        },
      });
    }
  };

  // Draw common roads once using Graph A's geometry. Independent graphs may split the same
  // OSM way differently, but shared OSM identity is the stable evidence we care about here.
  addFeatures(featuresA, common, "common", "A");
  addFeatures(featuresA, aOnly, "a-only", "A");
  addFeatures(featuresB, bOnly, "b-only", "B");

  const collection: FeatureCollection = { type: "FeatureCollection", features: output };
  const existing = map.getSource(borderDiffSource) as { setData?: (data: FeatureCollection) => void } | undefined;
  if (existing?.setData) {
    existing.setData(collection);
  } else {
    map.addSource(borderDiffSource, { type: "geojson", data: collection });
    map.addLayer({
      id: borderDiffCommonLayer,
      type: "line",
      source: borderDiffSource,
      filter: ["==", ["get", "classification"], "common"],
      paint: { "line-color": "#42c58a", "line-width": 4.2, "line-opacity": 0.92 },
    });
    map.addLayer({
      id: borderDiffAOnlyLayer,
      type: "line",
      source: borderDiffSource,
      filter: ["==", ["get", "classification"], "a-only"],
      paint: { "line-color": "#e35d5b", "line-width": 3.2, "line-opacity": 0.9 },
    });
    map.addLayer({
      id: borderDiffBOnlyLayer,
      type: "line",
      source: borderDiffSource,
      filter: ["==", ["get", "classification"], "b-only"],
      paint: { "line-color": "#4b9ee8", "line-width": 3.2, "line-opacity": 0.9 },
    });
  }

  lastBorderDiffMetrics = {
    commonWays: common.size,
    aOnlyWays: aOnly.size,
    bOnlyWays: bOnly.size,
    loadedEdgesA: featuresA.length,
    loadedEdgesB: featuresB.length,
    unidentifiedA,
    unidentifiedB,
  };

  borderDiffSummary.className = "kv";
  borderDiffSummary.innerHTML = `
    <dt>Common OSM ways</dt><dd>${common.size}</dd>
    <dt>Graph A only</dt><dd>${aOnly.size}</dd>
    <dt>Graph B only</dt><dd>${bOnly.size}</dd>
    <dt>Loaded A edges</dt><dd>${featuresA.length}</dd>
    <dt>Loaded B edges</dt><dd>${featuresB.length}</dd>
    <dt>No OSM id</dt><dd>A ${unidentifiedA} / B ${unidentifiedB}</dd>
  `;
}

function scheduleBorderRoadDiff(): void {
  if (!map.getSource(borderSourceA) || !map.getSource(borderSourceB)) return;
  window.setTimeout(() => {
    try {
      refreshBorderRoadDiff();
    } catch (error) {
      borderDiffSummary.className = "bad";
      borderDiffSummary.textContent = `Road diff failed: ${String(error)}`;
    }
  }, 120);
}

function showBorderPairLayers(regionA: string, regionB: string): void {
  removeBorderPairLayers();
  map.addSource(borderSourceA, {
    type: "vector",
    tiles: [`roadpilot-graph://${encodeURIComponent(regionA)}/{z}/{x}/{y}.mvt`],
    minzoom: 5,
    maxzoom: 18,
  });
  map.addSource(borderSourceB, {
    type: "vector",
    tiles: [`roadpilot-graph://${encodeURIComponent(regionB)}/{z}/{x}/{y}.mvt`],
    minzoom: 5,
    maxzoom: 18,
  });
  map.addLayer({
    id: borderLayerA,
    type: "line",
    source: borderSourceA,
    "source-layer": "edges",
    paint: { "line-color": "#e35d5b", "line-width": 1.4, "line-opacity": 0.22 },
  });
  map.addLayer({
    id: borderLayerB,
    type: "line",
    source: borderSourceB,
    "source-layer": "edges",
    paint: { "line-color": "#4b9ee8", "line-width": 1.4, "line-opacity": 0.22 },
  });
  refreshBorderDiffBtn.disabled = false;
  refreshHandoffArtifactsBtn.disabled = false;
  exportBorderDiagnosticsBtn.disabled = false;
  borderDiffSummary.className = "empty";
  borderDiffSummary.textContent = "Loading OSM way identities from both graph tile sets…";
  applyMapLayerToggles();
  map.once("idle", scheduleBorderRoadDiff);
  refreshHandoffArtifactOverlay().catch(error => appendLog(String(error)));
}

function clearHandoffSelection(removeLayers = false): void {
  editingHandoffId = null;
  handoffSnapA = null;
  handoffSnapB = null;
  handoffValidation = null;
  handoffPickMode = null;
  handoffMarkerA?.remove();
  handoffMarkerB?.remove();
  handoffMarkerA = null;
  handoffMarkerB = null;
  handoffASummary.className = "empty";
  handoffASummary.textContent = "Not selected.";
  handoffBSummary.className = "empty";
  handoffBSummary.textContent = "Not selected.";
  handoffValidationSummary.className = "empty";
  handoffValidationSummary.textContent = "No manual crossing selected.";
  handoffProbeList.innerHTML = "";
  validateHandoffBtn.disabled = true;
  saveHandoffBtn.disabled = true;
  pickHandoffABtn.textContent = "Pick A edge";
  pickHandoffBBtn.textContent = "Pick B edge";
  if (removeLayers) removeBorderPairLayers();
}

function handoffSnapSummary(snap: HandoffSnap): string {
  const edgeId = snap.edgeId == null ? "—" : JSON.stringify(snap.edgeId);
  return `
    <div class="kv">
      <dt>Region</dt><dd>${snap.regionId}</dd>
      <dt>Correlated</dt><dd>${snap.correlated.lat.toFixed(6)}, ${snap.correlated.lng.toFixed(6)}</dd>
      <dt>OSM way</dt><dd>${snap.wayId ?? "—"}</dd>
      <dt>Percent</dt><dd>${snap.percentAlong == null ? "—" : snap.percentAlong.toFixed(5)}</dd>
      <dt>Edge id</dt><dd>${edgeId}</dd>
      <dt>Graph</dt><dd>${snap.graph.packageVersion ?? "—"}</dd>
    </div>
  `;
}

function renderHandoffValidation(validation: HandoffValidation): void {
  handoffValidationSummary.className = validation.passed ? "ok" : "bad";
  handoffValidationSummary.textContent = validation.passed
    ? "VALID — both graphs proved the manual crossing in both directions for motorcycle and auto."
    : "FAILED — one or more Valhalla proofs failed. The override cannot be saved as VALID.";
  handoffProbeList.innerHTML = Object.entries(validation.probes).map(([name, result]) => {
    const passed = result.passed === true;
    const detail = passed
      ? `${result.elapsedMs ?? "—"} ms`
      : result.error || "No route";
    return `<div class="probe-row"><span class="${passed ? "ok" : "bad"}">${passed ? "✓" : "✗"}</span><b>${name}</b><small>${detail}</small></div>`;
  }).join("");
  saveHandoffBtn.disabled = !validation.passed;
}

function uniqueBuiltRegions(): string[] {
  return [...new Set(artifacts.map(item => item.region_id))].sort();
}

function renderBorderRegionSelectors(): void {
  const currentA = borderRegionA.value;
  const currentB = borderRegionB.value;
  const currentConnector = connectorRegion.value || activeRegion?.id || "";
  const options = uniqueBuiltRegions().map(id => `<option value="${id}">${id}</option>`).join("");
  borderRegionA.innerHTML = `<option value="">Choose A…</option>${options}`;
  borderRegionB.innerHTML = `<option value="">Choose B…</option>${options}`;
  connectorRegion.innerHTML = `<option value="">Choose region…</option>${options}`;
  if ([...borderRegionA.options].some(option => option.value === currentA)) borderRegionA.value = currentA;
  if ([...borderRegionB.options].some(option => option.value === currentB)) borderRegionB.value = currentB;
  if ([...connectorRegion.options].some(option => option.value === currentConnector)) connectorRegion.value = currentConnector;
  refreshConnectorMatrixBtn.disabled = !connectorRegion.value;
}

async function refreshHandoffOverrides(): Promise<void> {
  try {
    const overrides = await invoke<HandoffOverride[]>("list_handoff_overrides");
    if (!overrides.length) {
      handoffOverrideList.className = "empty";
      handoffOverrideList.textContent = "No manual overrides.";
      return;
    }
    handoffOverrideList.className = "";
    handoffOverrideList.innerHTML = "";
    for (const item of overrides) {
      const row = document.createElement("div");
      row.className = "handoff-override-row";
      const statusClass = item.status === "VALID" ? "ok" : "warn";
      row.innerHTML = `
        <div><b>${item.regionA} ↔ ${item.regionB}</b><span class="${statusClass}">${item.status}</span></div>
        <small>${item.id}</small>
      `;
      const actions = document.createElement("div");
      actions.className = "actions";
      const load = document.createElement("button");
      load.className = "btn";
      load.type = "button";
      load.textContent = "Inspect";
      load.addEventListener("click", () => {
        editingHandoffId = item.id;
        borderRegionA.value = item.regionA;
        borderRegionB.value = item.regionB;
        handoffSnapA = item.snapA;
        handoffSnapB = item.snapB;
        handoffValidation = item.validation ?? null;
        showBorderPairLayers(item.regionA, item.regionB);
        handoffASummary.className = "";
        handoffASummary.innerHTML = handoffSnapSummary(item.snapA);
        handoffBSummary.className = "";
        handoffBSummary.innerHTML = handoffSnapSummary(item.snapB);
        if (item.validation) renderHandoffValidation(item.validation);
        handoffMarkerA?.remove();
        handoffMarkerB?.remove();
        handoffMarkerA = new Marker({ color: "#e35d5b" }).setLngLat([item.snapA.correlated.lng, item.snapA.correlated.lat]).addTo(map);
        handoffMarkerB = new Marker({ color: "#4b9ee8" }).setLngLat([item.snapB.correlated.lng, item.snapB.correlated.lat]).addTo(map);
        validateHandoffBtn.disabled = false;
        saveHandoffBtn.disabled = item.status !== "VALID";
      });
      const remove = document.createElement("button");
      remove.className = "btn danger";
      remove.type = "button";
      remove.textContent = "Delete";
      remove.addEventListener("click", async () => {
        try {
          await invoke("delete_handoff_override", {
            regionA: item.regionA,
            regionB: item.regionB,
            overrideId: item.id,
          });
          await refreshHandoffOverrides();
          if (borderRegionA.value && borderRegionB.value) {
            await refreshHandoffArtifactOverlay();
          }
        } catch (error) {
          appendLog(`Delete manual handoff failed: ${String(error)}`);
        }
      });
      actions.append(load, remove);
      row.appendChild(actions);
      handoffOverrideList.appendChild(row);
    }
  } catch (error) {
    handoffOverrideList.className = "bad";
    handoffOverrideList.textContent = `Could not load manual overrides: ${String(error)}`;
  }
}

async function snapHandoff(kind: "A" | "B", lat: number, lng: number): Promise<void> {
  const regionId = kind === "A" ? borderRegionA.value : borderRegionB.value;
  if (!regionId) {
    appendLog(`Choose Graph ${kind} before selecting a handoff edge.`);
    return;
  }
  const summary = kind === "A" ? handoffASummary : handoffBSummary;
  summary.className = "empty";
  summary.textContent = "Snapping to Valhalla directed edge…";
  try {
    const snap = await invoke<HandoffSnap>("snap_handoff_point", { regionId, lat, lng });
    const marker = new Marker({ color: kind === "A" ? "#e35d5b" : "#4b9ee8" })
      .setLngLat([snap.correlated.lng, snap.correlated.lat])
      .addTo(map);
    if (kind === "A") {
      handoffMarkerA?.remove();
      handoffMarkerA = marker;
      handoffSnapA = snap;
      handoffASummary.className = "";
      handoffASummary.innerHTML = handoffSnapSummary(snap);
    } else {
      handoffMarkerB?.remove();
      handoffMarkerB = marker;
      handoffSnapB = snap;
      handoffBSummary.className = "";
      handoffBSummary.innerHTML = handoffSnapSummary(snap);
    }
    handoffValidation = null;
    handoffValidationSummary.className = "empty";
    handoffValidationSummary.textContent = "Manual points changed — validation required.";
    handoffProbeList.innerHTML = "";
    validateHandoffBtn.disabled = !(handoffSnapA && handoffSnapB);
    saveHandoffBtn.disabled = true;
  } catch (error) {
    summary.className = "bad";
    summary.textContent = `Snap failed: ${String(error)}`;
  }
}

const handoffArtifactSource = "roadpilot-handoff-artifacts";
const handoffArtifactLayers = [
  "roadpilot-handoff-candidate",
  "roadpilot-handoff-accepted",
  "roadpilot-handoff-learned",
  "roadpilot-handoff-manual",
  "roadpilot-handoff-endpoints",
];

function removeHandoffArtifactOverlay(): void {
  for (const id of handoffArtifactLayers) if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource(handoffArtifactSource)) map.removeSource(handoffArtifactSource);
  handoffArtifactSummary.className = "empty";
  handoffArtifactSummary.textContent = "Load a graph pair to inspect handoff artifacts.";
  handoffArtifactList.innerHTML = "";
  refreshHandoffArtifactsBtn.disabled = true;
}

function artifactLineFeature(item: HandoffArtifactItem): Feature {
  return {
    type: "Feature",
    geometry: {
      type: "LineString",
      coordinates: [
        [item.from.lng, item.from.lat],
        [item.to.lng, item.to.lat],
      ],
    },
    properties: {
      kind: item.kind,
      id: item.id ?? "",
      status: item.status,
      fromRegionId: item.fromRegionId,
      toRegionId: item.toRegionId,
      modes: item.modes.join(","),
      evidence: item.evidence.join(","),
      artifactPath: item.artifactPath,
      active: item.status === "CURRENT" || item.status === "VALID",
      geometryRole: "link",
    },
  };
}

function artifactPointFeatures(item: HandoffArtifactItem): Feature[] {
  return [
    {
      type: "Feature",
      geometry: { type: "Point", coordinates: [item.from.lng, item.from.lat] },
      properties: {
        kind: item.kind,
        status: item.status,
        id: item.id ?? "",
        regionId: item.fromRegionId,
        endpoint: "from",
        active: item.status === "CURRENT" || item.status === "VALID",
        geometryRole: "endpoint",
      },
    },
    {
      type: "Feature",
      geometry: { type: "Point", coordinates: [item.to.lng, item.to.lat] },
      properties: {
        kind: item.kind,
        status: item.status,
        id: item.id ?? "",
        regionId: item.toRegionId,
        endpoint: "to",
        active: item.status === "CURRENT" || item.status === "VALID",
        geometryRole: "endpoint",
      },
    },
  ];
}

function renderHandoffArtifactOverlay(result: HandoffArtifactInspection): void {
  const features: Feature[] = [];
  for (const item of result.items) {
    features.push(artifactLineFeature(item), ...artifactPointFeatures(item));
  }
  const collection: FeatureCollection = { type: "FeatureCollection", features };

  const existing = map.getSource(handoffArtifactSource) as { setData?: (data: FeatureCollection) => void } | undefined;
  if (existing?.setData) {
    existing.setData(collection);
  } else {
    map.addSource(handoffArtifactSource, { type: "geojson", data: collection });

    const addLine = (id: string, kind: HandoffArtifactItem["kind"], color: string, dash?: number[]) => {
      map.addLayer({
        id,
        type: "line",
        source: handoffArtifactSource,
        filter: ["all",
          ["==", ["get", "geometryRole"], "link"],
          ["==", ["get", "kind"], kind],
        ],
        paint: {
          "line-color": color,
          "line-width": ["case", ["==", ["get", "active"], true], 4.2, 2.6],
          "line-opacity": ["case", ["==", ["get", "active"], true], 0.95, 0.38],
          ...(dash ? { "line-dasharray": dash } : {}),
        },
      });
    };

    addLine("roadpilot-handoff-candidate", "candidate", "#f0a44b", [2, 2]);
    addLine("roadpilot-handoff-accepted", "accepted", "#2fbd71");
    addLine("roadpilot-handoff-learned", "learned", "#9d72e8", [4, 1.5]);
    addLine("roadpilot-handoff-manual", "manual", "#ee5aa7");

    map.addLayer({
      id: "roadpilot-handoff-endpoints",
      type: "circle",
      source: handoffArtifactSource,
      filter: ["==", ["get", "geometryRole"], "endpoint"],
      paint: {
        "circle-radius": ["case", ["==", ["get", "active"], true], 5, 3.5],
        "circle-color": [
          "match",
          ["get", "kind"],
          "candidate", "#f0a44b",
          "accepted", "#2fbd71",
          "learned", "#9d72e8",
          "manual", "#ee5aa7",
          "#ffffff",
        ],
        "circle-opacity": ["case", ["==", ["get", "active"], true], 0.95, 0.4],
        "circle-stroke-color": "#111820",
        "circle-stroke-width": 1,
      },
    });
  }

  const counts = new Map<string, number>();
  for (const item of result.items) {
    const key = `${item.kind}:${item.status}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const count = (kind: string, status: string) => counts.get(`${kind}:${status}`) ?? 0;
  handoffArtifactSummary.className = "kv";
  handoffArtifactSummary.innerHTML = `
    <dt>Generated candidates</dt><dd>${count("candidate", "CURRENT")} current / ${count("candidate", "STALE")} stale</dd>
    <dt>Validated runtime</dt><dd>${count("accepted", "CURRENT")} current / ${count("accepted", "STALE")} stale</dd>
    <dt>Learned proofs</dt><dd>${count("learned", "CURRENT")} current / ${count("learned", "STALE")} stale</dd>
    <dt>Manual</dt><dd>${count("manual", "VALID")} valid / ${count("manual", "STALE")} stale</dd>
    <dt>Artifact files</dt><dd>${result.recognizedArtifactFiles}</dd>
  `;

  handoffArtifactList.innerHTML = result.items.slice(0, 100).map(item => {
    const statusClass = item.status === "CURRENT" || item.status === "VALID" ? "ok" : "warn";
    const modes = item.modes.length ? item.modes.join(", ") : "—";
    const evidence = item.evidence.length ? item.evidence.join(", ") : "—";
    const validation = item.validationState ?? "LEGACY";
    return `
      <div class="artifact-row">
        <div><b>${item.kind.toUpperCase()} ${item.id ?? ""}</b><span class="${statusClass}">${item.status}</span></div>
        <small>${item.fromRegionId} → ${item.toRegionId} • ${validation} • ${modes}</small>
        <small>${evidence}</small>
      </div>
    `;
  }).join("");
  if (!result.items.length) {
    handoffArtifactList.innerHTML = `
      <div class="empty">
        No generated/validated/learned/manual connectivity artifacts found for this pair.
        Artifact imports are scanned under:<br>
        ${result.searchDirectories.map(path => `<code>${path}</code>`).join("<br>")}
      </div>
    `;
  }
  applyMapLayerToggles();
}

async function refreshHandoffArtifactOverlay(): Promise<void> {
  const regionA = borderRegionA.value;
  const regionB = borderRegionB.value;
  if (!regionA || !regionB || regionA === regionB) return;
  refreshHandoffArtifactsBtn.disabled = true;
  handoffArtifactSummary.className = "empty";
  handoffArtifactSummary.textContent = "Reading fingerprint-bound handoff artifacts…";
  try {
    const result = await invoke<HandoffArtifactInspection>("inspect_handoff_artifacts", {
      regionA,
      regionB,
    });
    renderHandoffArtifactOverlay(result);
  } catch (error) {
    handoffArtifactSummary.className = "bad";
    handoffArtifactSummary.textContent = `Handoff artifact inspection failed: ${String(error)}`;
  } finally {
    refreshHandoffArtifactsBtn.disabled = false;
  }
}

const connectorMatrixSource = "roadpilot-connector-matrix";
const connectorMatrixLayers = [
  "roadpilot-connector-reachable",
  "roadpilot-connector-unreachable",
  "roadpilot-connector-inconclusive",
  "roadpilot-connector-anchors",
];

function removeConnectorMatrixOverlay(): void {
  for (const id of connectorMatrixLayers) if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource(connectorMatrixSource)) map.removeSource(connectorMatrixSource);
}

function connectorStatusClass(status: string): string {
  if (status === "CURRENT" || status === "REACHABLE" || status === "NONE") return "ok";
  if (status === "MISSING" || status.includes("BUILD") || status.includes("REBUILD") || status === "INCONCLUSIVE") return "warn";
  return "bad";
}

function renderConnectorMatrix(result: ConnectorMatrixInspection): void {
  connectorInspection = result;
  removeConnectorMatrixOverlay();
  const modeName = connectorMode.value as "MOTORCYCLE" | "CAR";
  const inventory = result.inventory;
  const matrix = result.matrix;
  const mode = matrix?.modes?.[modeName];
  const anchors = inventory?.anchors ?? [];
  const anchorById = new globalThis.Map(anchors.map(anchor => [anchor.id, anchor]));
  const features: Feature[] = [];

  for (const anchor of anchors) {
    const roles = anchor.roles?.[modeName] ?? [];
    if (!roles.length) continue;
    features.push({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [anchor.graphAnchor.coordinate.lng, anchor.graphAnchor.coordinate.lat],
      },
      properties: {
        geometryRole: "anchor",
        id: anchor.id,
        candidateId: anchor.candidateId,
        neighborRegionId: anchor.neighborRegionId,
        roles: roles.join(","),
      },
    });
  }

  const allCells = mode?.cells ?? [];
  const renderCells = allCells.slice(0, 500);
  for (const cell of renderCells) {
    const from = anchorById.get(cell.fromAnchorId);
    const to = anchorById.get(cell.toAnchorId);
    if (!from || !to) continue;
    features.push({
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: [
          [from.graphAnchor.coordinate.lng, from.graphAnchor.coordinate.lat],
          [to.graphAnchor.coordinate.lng, to.graphAnchor.coordinate.lat],
        ],
      },
      properties: {
        geometryRole: "cell",
        status: cell.status,
        fromAnchorId: cell.fromAnchorId,
        toAnchorId: cell.toAnchorId,
        distanceKm: cell.distanceKm,
        timeSeconds: cell.timeSeconds,
      },
    });
  }

  if (features.length) {
    const collection: FeatureCollection = { type: "FeatureCollection", features };
    map.addSource(connectorMatrixSource, { type: "geojson", data: collection });
    for (const [id, status, color, opacity, dash] of [
      ["roadpilot-connector-reachable", "REACHABLE", "#2fbd71", 0.78, null],
      ["roadpilot-connector-unreachable", "UNREACHABLE", "#e35d5b", 0.22, [2, 2]],
      ["roadpilot-connector-inconclusive", "INCONCLUSIVE", "#f0a44b", 0.55, [4, 2]],
    ] as Array<[string, string, string, number, number[] | null]>) {
      map.addLayer({
        id,
        type: "line",
        source: connectorMatrixSource,
        filter: ["all", ["==", ["get", "geometryRole"], "cell"], ["==", ["get", "status"], status]],
        paint: {
          "line-color": color,
          "line-width": status === "REACHABLE" ? 3.2 : 2,
          "line-opacity": opacity,
          ...(dash ? { "line-dasharray": dash } : {}),
        },
      });
    }
    map.addLayer({
      id: "roadpilot-connector-anchors",
      type: "circle",
      source: connectorMatrixSource,
      filter: ["==", ["get", "geometryRole"], "anchor"],
      paint: {
        "circle-radius": 5,
        "circle-color": [
          "case",
          ["==", ["get", "roles"], "ENTRY,EXIT"], "#9d72e8",
          ["==", ["get", "roles"], "ENTRY"], "#4b9ee8",
          "#ee5aa7",
        ],
        "circle-stroke-color": "#111820",
        "circle-stroke-width": 1.2,
      },
    });
  }

  const statusClass = connectorStatusClass(result.status);
  const matrixStatus = matrix ? (matrix.current ? "CURRENT" : "STALE") : "MISSING";
  const inventoryStatus = inventory ? (inventory.current ? "CURRENT" : "STALE") : "MISSING";
  connectorMatrixSummary.className = "kv";
  connectorMatrixSummary.innerHTML = `
    <dt>Overall</dt><dd class="${statusClass}">${result.status}</dd>
    <dt>Refresh action</dt><dd class="${connectorStatusClass(result.refreshAction)}">${result.refreshAction}</dd>
    <dt>Inventory</dt><dd class="${connectorStatusClass(inventoryStatus)}">${inventoryStatus} • ${inventory?.anchorCount ?? 0} anchors</dd>
    <dt>Inventory file</dt><dd>${inventory?.artifactPath ?? "—"}</dd>
    <dt>Matrix</dt><dd class="${connectorStatusClass(matrixStatus)}">${matrixStatus}</dd>
    <dt>Matrix file</dt><dd>${matrix?.artifactPath ?? "—"}</dd>
    <dt>Inventory binding</dt><dd class="${matrix?.sourceInventoryPresent && matrix?.sourceInventoryCurrent && matrix?.anchorCountMatches ? "ok" : "warn"}">${matrix ? (matrix.sourceInventoryPresent && matrix.sourceInventoryCurrent && matrix.anchorCountMatches ? "exact/current" : "stale or missing") : "—"}</dd>
    <dt>${modeName}</dt><dd>${mode ? `${mode.reachableCount} reachable / ${mode.unreachableCount} unreachable / ${mode.inconclusiveCount} inconclusive` : "no mode matrix"}</dd>
    <dt>Overlay</dt><dd>${Math.min(allCells.length, 500)} / ${allCells.length} cells rendered</dd>
  `;

  const boundaryRows = (inventory?.boundaryChecks ?? []).map(check => {
    const state = check.matches ? "CURRENT" : "STALE";
    return `
      <div class="artifact-row">
        <div><b>BOUNDARY ${check.neighborPrimaryGeofabrikId}</b><span class="${connectorStatusClass(state)}">${state}</span></div>
        <small>${check.currentBoundaryFingerprint ?? "missing current fingerprint"}</small>
      </div>
    `;
  }).join("");

  const cellRows = allCells.slice(0, 200).map(cell => {
    const metric = cell.status === "REACHABLE"
      ? `${cell.distanceKm?.toFixed(2) ?? "—"} km • ${cell.timeSeconds?.toFixed(0) ?? "—"} s`
      : cell.error || "no usable connector traversal";
    return `
      <div class="artifact-row">
        <div><b>${cell.fromAnchorId} → ${cell.toAnchorId}</b><span class="${connectorStatusClass(cell.status)}">${cell.status}</span></div>
        <small>${metric}</small>
      </div>
    `;
  }).join("");

  connectorMatrixList.innerHTML = boundaryRows + cellRows;
  if (!inventory && !matrix) {
    connectorMatrixList.innerHTML = `
      <div class="empty">
        No connector inventory or matrix found for ${result.regionId}. Searched:<br>
        ${result.searchDirectories.map(path => `<code>${path}</code>`).join("<br>")}
      </div>
    `;
  } else if (!boundaryRows && !cellRows) {
    connectorMatrixList.innerHTML = '<div class="empty">No boundary checks or matrix cells to display.</div>';
  }
}

async function refreshConnectorMatrix(): Promise<void> {
  const regionId = connectorRegion.value;
  if (!regionId) return;
  refreshConnectorMatrixBtn.disabled = true;
  connectorMatrixSummary.className = "empty";
  connectorMatrixSummary.textContent = "Reading connector inventory, weights and freshness…";
  try {
    const result = await invoke<ConnectorMatrixInspection>("inspect_region_connector_matrix", { regionId });
    renderConnectorMatrix(result);
  } catch (error) {
    connectorInspection = null;
    removeConnectorMatrixOverlay();
    connectorMatrixSummary.className = "bad";
    connectorMatrixSummary.textContent = `Connector matrix inspection failed: ${String(error)}`;
    connectorMatrixList.innerHTML = "";
  } finally {
    refreshConnectorMatrixBtn.disabled = false;
  }
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
  applyMapLayerToggles();
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
  applyMapLayerToggles();
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
  applyMapLayerToggles();
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
  if ([...connectorRegion.options].some(option => option.value === region.id)) {
    connectorRegion.value = region.id;
    refreshConnectorMatrixBtn.disabled = false;
  }
  fitActiveRegion();
  renderRegions();
  renderVisualBuildSelectors();
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
  const existingVisual = (existing["visual"] ?? {}) as Record<string, unknown>;
  const existingVisualValidation = (existingVisual.validation ?? {}) as Record<string, unknown>;
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
    visual: {
      ...existingVisual,
      enabled: true,
      source: {
        primaryGeofabrikId: editorPreview.geofabrikId,
        url: editorPreview.pbfUrl,
        polygonUrl: editorPreview.polygonUrl,
      },
      buildThreads: Number(existingVisual.buildThreads ?? 4),
      package: {
        fileNameTemplate: `${regionId}-visual-{version}.pmtiles`,
        manifestFileNameTemplate: `${regionId}-visual-{version}-manifest.json`,
        roadIndexFileNameTemplate: `${regionId}-visual-{version}-road-index.json`,
      },
      validation: {
        ...existingVisualValidation,
        majorRoadClasses: Array.isArray(existingVisualValidation.majorRoadClasses)
          ? existingVisualValidation.majorRoadClasses
          : ["motorway", "trunk", "primary", "secondary"],
        borderToleranceMeters: Number(existingVisualValidation.borderToleranceMeters ?? 75),
      },
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
  toolchainReady = status.ready;
  buildBtn.disabled = !toolchainReady;
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
  buildBtn.disabled = status.running || !toolchainReady;
}

async function refreshBuildStatus(): Promise<void> {
  renderBuildStatus(await invoke<BuildStatus>("build_status"));
}

function selectedVisualBuild(): VisualBuildArtifact | null {
  const manifestPath = visualBuildSelect.value;
  return visualArtifacts.find(item => item.manifest_path === manifestPath) ?? null;
}

function visualBuildOption(build: VisualBuildArtifact, index: number): string {
  return `<option value="${index}">${escapeHtml(build.region_id)} • ${escapeHtml(build.version)}</option>`;
}

function renderVisualBuildSelectors(): void {
  const selectedManifest = visualBuildSelect.value;
  const previousA = visualCompareA.value;
  const previousB = visualCompareB.value;

  visualBuildSelect.innerHTML = '<option value="">Choose visual build…</option>';
  for (const build of visualArtifacts) {
    const option = document.createElement("option");
    option.value = build.manifest_path;
    option.textContent = `${build.region_id} • ${build.version}`;
    visualBuildSelect.appendChild(option);
  }
  if ([...visualBuildSelect.options].some(option => option.value === selectedManifest)) {
    visualBuildSelect.value = selectedManifest;
  } else if (activeRegion) {
    const newest = visualArtifacts.find(item => item.region_id === activeRegion?.id);
    if (newest) visualBuildSelect.value = newest.manifest_path;
  }

  const options = visualArtifacts.map(visualBuildOption).join("");
  visualCompareA.innerHTML = `<option value="">Choose A…</option>${options}`;
  visualCompareB.innerHTML = `<option value="">Choose B…</option>${options}`;
  if ([...visualCompareA.options].some(option => option.value === previousA)) visualCompareA.value = previousA;
  if ([...visualCompareB.options].some(option => option.value === previousB)) visualCompareB.value = previousB;

  const build = selectedVisualBuild();
  loadVisualBuildBtn.disabled = build == null;
  fitVisualBuildBtn.disabled = build == null;
  compareVisualBuildsBtn.disabled = !(visualCompareA.value && visualCompareB.value);
  renderVisualBuildSummary(build);
}

function renderVisualBuildSummary(build: VisualBuildArtifact | null): void {
  if (!build) {
    visualBuildSummary.className = "empty";
    visualBuildSummary.textContent = "No retained visual build selected.";
    return;
  }
  const b = build.bounds;
  visualBuildSummary.className = "kv";
  visualBuildSummary.innerHTML = `
    <dt>Region / version</dt><dd>${escapeHtml(build.region_id)} • ${escapeHtml(build.version)}</dd>
    <dt>Artifact</dt><dd>${escapeHtml(build.artifact_file)}</dd>
    <dt>Size</dt><dd>${bytes(build.size_bytes)}</dd>
    <dt>Tiles</dt><dd>${build.tile_count}</dd>
    <dt>Zoom</dt><dd>${build.min_zoom}–${build.max_zoom}</dd>
    <dt>Coverage</dt><dd>${Number(b.minLat ?? 0).toFixed(4)}, ${Number(b.minLng ?? 0).toFixed(4)} → ${Number(b.maxLat ?? 0).toFixed(4)}, ${Number(b.maxLng ?? 0).toFixed(4)}</dd>
    <dt>SHA-256</dt><dd><code>${escapeHtml(build.sha256)}</code></dd>
    <dt>Source fingerprint</dt><dd><code>${escapeHtml(build.source_fingerprint)}</code></dd>
    <dt>Profile fingerprint</dt><dd><code>${escapeHtml(build.profile_fingerprint)}</code></dd>
    <dt>Layers</dt><dd>${build.layers.map(escapeHtml).join(", ")}</dd>
    <dt>Major / border roads</dt><dd>${build.major_road_count} / ${build.border_road_count}</dd>
    <dt>Missing required roads</dt><dd class="${build.missing_road_count ? "bad" : "ok"}">${build.missing_road_count}</dd>
  `;
}

async function refreshVisualBuilds(): Promise<void> {
  visualArtifacts = await invoke<VisualBuildArtifact[]>("list_visual_builds");
  renderVisualBuildSelectors();
  if (activePublicationKind() === "VISUAL") renderPublicationBuildSelector();
}

const visualCompareSourceA = "roadpilot-visual-compare-a";
const visualCompareSourceB = "roadpilot-visual-compare-b";
const visualCompareHiddenA = "roadpilot-visual-compare-a-hidden";
const visualCompareHiddenB = "roadpilot-visual-compare-b-hidden";
const visualDiffSource = "roadpilot-visual-road-diff";
const visualDiffLayers = [
  "roadpilot-visual-diff-unchanged",
  "roadpilot-visual-diff-removed",
  "roadpilot-visual-diff-added",
  "roadpilot-visual-diff-changed",
];

function removeVisualComparison(): void {
  for (const id of visualDiffLayers) if (map.getLayer(id)) map.removeLayer(id);
  for (const id of [visualCompareHiddenA, visualCompareHiddenB]) if (map.getLayer(id)) map.removeLayer(id);
  for (const id of [visualDiffSource, visualCompareSourceA, visualCompareSourceB]) {
    if (map.getSource(id)) map.removeSource(id);
  }
}

function visualFeatureId(feature: { id?: string | number | undefined }): string | null {
  if (feature.id == null) return null;
  const value = String(feature.id);
  return value && value !== "0" ? value : null;
}

function stableVisualRoadProperties(properties: Record<string, unknown> | null | undefined): string {
  const keys = ["class", "subclass", "name", "name_en", "ref", "surface", "oneway", "bridge", "tunnel", "layer"];
  const value: Record<string, unknown> = {};
  for (const key of keys) {
    const item = properties?.[key];
    if (item !== undefined && item !== null && item !== "") value[key] = item;
  }
  return JSON.stringify(value);
}

function visualRoadGroups(features: ReturnType<typeof map.querySourceFeatures>): Map<string, {
  signatures: Set<string>;
  features: typeof features;
}> {
  const groups = new Map<string, { signatures: Set<string>; features: typeof features }>();
  for (const feature of features) {
    const id = visualFeatureId(feature);
    if (!id) continue;
    let group = groups.get(id);
    if (!group) {
      group = { signatures: new Set<string>(), features: [] };
      groups.set(id, group);
    }
    const signature = `${stableVisualRoadProperties(feature.properties)}|${JSON.stringify(feature.geometry)}`;
    group.signatures.add(signature);
    if (!group.features.some(existing => JSON.stringify(existing.geometry) === JSON.stringify(feature.geometry))) {
      group.features.push(feature);
    }
  }
  return groups;
}

function addVisualDiffFeatures(
  output: Feature[],
  groups: Map<string, { signatures: Set<string>; features: ReturnType<typeof map.querySourceFeatures> }>,
  ids: Set<string>,
  classification: "unchanged" | "removed" | "added" | "changed",
): void {
  const seen = new Set<string>();
  for (const id of ids) {
    const group = groups.get(id);
    if (!group) continue;
    for (const feature of group.features) {
      const geometry = feature.geometry as Geometry;
      const key = `${id}:${JSON.stringify(geometry)}`;
      if (seen.has(key)) continue;
      seen.add(key);
      output.push({
        type: "Feature",
        geometry,
        properties: {
          osm_id: id,
          classification,
          ...feature.properties,
        },
      });
    }
  }
}

function classifyVisualRoadComparison(a: VisualBuildArtifact, b: VisualBuildArtifact): void {
  const featuresA = map.querySourceFeatures(visualCompareSourceA, { sourceLayer: "transportation" });
  const featuresB = map.querySourceFeatures(visualCompareSourceB, { sourceLayer: "transportation" });
  if (!featuresA.length && !featuresB.length) {
    visualComparisonSummary.className = "empty";
    visualComparisonSummary.textContent = "Visual tiles are still loading. Move/zoom the map or compare again.";
    return;
  }

  const groupsA = visualRoadGroups(featuresA);
  const groupsB = visualRoadGroups(featuresB);
  const idsA = new Set(groupsA.keys());
  const idsB = new Set(groupsB.keys());
  const unchanged = new Set<string>();
  const changed = new Set<string>();
  const removed = new Set([...idsA].filter(id => !idsB.has(id)));
  const added = new Set([...idsB].filter(id => !idsA.has(id)));
  for (const id of idsA) {
    const ga = groupsA.get(id);
    const gb = groupsB.get(id);
    if (!ga || !gb) continue;
    const aSignatures = [...ga.signatures].sort().join("\n");
    const bSignatures = [...gb.signatures].sort().join("\n");
    (aSignatures === bSignatures ? unchanged : changed).add(id);
  }

  const output: Feature[] = [];
  addVisualDiffFeatures(output, groupsA, unchanged, "unchanged");
  addVisualDiffFeatures(output, groupsA, removed, "removed");
  addVisualDiffFeatures(output, groupsB, added, "added");
  addVisualDiffFeatures(output, groupsB, changed, "changed");

  map.addSource(visualDiffSource, {
    type: "geojson",
    data: { type: "FeatureCollection", features: output } as FeatureCollection,
  });
  for (const [id, classification, color, width, opacity] of [
    ["roadpilot-visual-diff-unchanged", "unchanged", "#42c58a", 2.4, 0.5],
    ["roadpilot-visual-diff-removed", "removed", "#e35d5b", 4.0, 0.95],
    ["roadpilot-visual-diff-added", "added", "#4b9ee8", 4.0, 0.95],
    ["roadpilot-visual-diff-changed", "changed", "#d99a3e", 4.5, 0.95],
  ] as const) {
    map.addLayer({
      id,
      type: "line",
      source: visualDiffSource,
      filter: ["==", ["get", "classification"], classification],
      paint: { "line-color": color, "line-width": width, "line-opacity": opacity },
    });
  }

  visualComparisonSummary.className = "kv";
  visualComparisonSummary.innerHTML = `
    <dt>Versions</dt><dd>${escapeHtml(a.version)} → ${escapeHtml(b.version)}</dd>
    <dt>Visible unchanged roads</dt><dd class="ok">${unchanged.size}</dd>
    <dt>Visible removed roads</dt><dd class="${removed.size ? "warn" : "ok"}">${removed.size}</dd>
    <dt>Visible added roads</dt><dd class="${added.size ? "warn" : "ok"}">${added.size}</dd>
    <dt>Visible changed roads</dt><dd class="${changed.size ? "warn" : "ok"}">${changed.size}</dd>
    <dt>Scope</dt><dd>currently loaded map tiles / viewport</dd>
    <dt>Package SHA changed</dt><dd class="${a.sha256 === b.sha256 ? "ok" : "warn"}">${a.sha256 === b.sha256 ? "no" : "yes"}</dd>
  `;
}

function compareVisualBuilds(): void {
  removeVisualComparison();
  const a = visualArtifacts[Number(visualCompareA.value)];
  const b = visualArtifacts[Number(visualCompareB.value)];
  if (!a || !b) return;
  if (a.region_id !== b.region_id) {
    visualComparisonSummary.className = "bad";
    visualComparisonSummary.textContent = "Visual builds must be from the same region.";
    return;
  }
  ensureVisualArchive(a);
  ensureVisualArchive(b);
  map.addSource(visualCompareSourceA, {
    type: "vector",
    tiles: [`roadpilot-visual://${visualArchiveKey(a)}/{z}/{x}/{y}.mvt`],
    minzoom: a.min_zoom,
    maxzoom: a.max_zoom,
  });
  map.addSource(visualCompareSourceB, {
    type: "vector",
    tiles: [`roadpilot-visual://${visualArchiveKey(b)}/{z}/{x}/{y}.mvt`],
    minzoom: b.min_zoom,
    maxzoom: b.max_zoom,
  });
  map.addLayer({
    id: visualCompareHiddenA,
    type: "line",
    source: visualCompareSourceA,
    "source-layer": "transportation",
    paint: { "line-opacity": 0.001, "line-width": 0.5 },
  });
  map.addLayer({
    id: visualCompareHiddenB,
    type: "line",
    source: visualCompareSourceB,
    "source-layer": "transportation",
    paint: { "line-opacity": 0.001, "line-width": 0.5 },
  });
  visualComparisonSummary.className = "empty";
  visualComparisonSummary.textContent = "Loading exact PMTiles road features from both builds…";
  map.once("idle", () => classifyVisualRoadComparison(a, b));
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
      meta.textContent = `${bytes(item.size_bytes)} • ${item.tile_count} tiles • ${item.sha256.slice(0, 10)}…${item.graph_index_path ? " • indexed" : ""}`;
      card.append(strong, meta);
      buildsHost.appendChild(card);
    }
  }
  renderCompareSelectors();
  renderBorderRegionSelectors();
  renderPublicationBuildSelector();
}

function renderCompareSelectors(): void {
  const currentA = compareA.value;
  const currentB = compareB.value;
  const options = artifacts.map((a, i) => `<option value="${i}">${a.region_id} • ${a.version}</option>`).join("");
  compareA.innerHTML = `<option value="">Choose…</option>${options}`;
  compareB.innerHTML = `<option value="">Choose…</option>${options}`;
  compareA.value = currentA;
  compareB.value = currentB;
  void renderComparison();
}

async function renderComparison(): Promise<void> {
  const generation = ++buildComparisonGeneration;
  removeBuildDiffOverlay();
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
  const basic = `
    <dt>Version</dt><dd>${a.version} → ${b.version}</dd>
    <dt>Size change</dt><dd>${sizeDelta >= 0 ? "+" : ""}${bytes(Math.abs(sizeDelta))} ${sizeDelta < 0 ? "smaller" : "larger"}</dd>
    <dt>Tile change</dt><dd>${tileDelta >= 0 ? "+" : ""}${tileDelta}</dd>
    <dt>Same package</dt><dd class="${a.sha256 === b.sha256 ? "ok" : "warn"}">${a.sha256 === b.sha256 ? "yes" : "no"}</dd>
  `;
  comparison.className = "kv";
  if (!a.graph_index_path || !b.graph_index_path) {
    comparison.innerHTML = basic + `
      <dt>Graph index</dt><dd class="warn">unavailable — rebuild both versions with the current Graph Studio</dd>
    `;
    return;
  }
  comparison.innerHTML = basic + `<dt>Graph diff</dt><dd>Reading deterministic tile indexes…</dd>`;
  try {
    const diff = await invoke<BuildIndexDiff>("compare_build_indexes", {
      manifestPathA: a.manifest_path,
      manifestPathB: b.manifest_path,
    });
    if (generation !== buildComparisonGeneration) return;
    const graphChanged = diff.graphTileFingerprintA !== diff.graphTileFingerprintB;
    const internalChanged = diff.internalFingerprintA !== diff.internalFingerprintB;
    const refreshBoundaries = diff.boundaries.filter(item => item.requiresRefresh);
    const boundaryRows = diff.boundaries.length
      ? diff.boundaries.map(item =>
          `<div class="source-row"><span>${item.requiresRefresh ? "REFRESH" : "UNCHANGED"}</span><b>${item.sourceId}</b><small>${item.changedTiles} changed tiles</small></div>`
        ).join("")
      : `<div class="empty">No neighboring boundary fingerprints were recorded.</div>`;
    comparison.innerHTML = basic + `
      <dt>Graph tiles changed</dt><dd class="${graphChanged ? "warn" : "ok"}">${graphChanged ? "yes" : "no"}</dd>
      <dt>Added / removed / modified</dt><dd>${diff.counts.addedTiles} / ${diff.counts.removedTiles} / ${diff.counts.changedTiles}</dd>
      <dt>Internal-only changed tiles</dt><dd class="${internalChanged ? "warn" : "ok"}">${diff.counts.internalChangedTiles}</dd>
      <dt>Boundary changed tiles</dt><dd class="${diff.counts.boundaryChangedTiles ? "warn" : "ok"}">${diff.counts.boundaryChangedTiles}</dd>
      <dt>Neighbor metadata refresh</dt><dd class="${refreshBoundaries.length ? "warn" : "ok"}">${refreshBoundaries.length ? refreshBoundaries.map(item => item.sourceId).join(", ") : "none"}</dd>
      <dt>Boundary fingerprints</dt><dd>${boundaryRows}</dd>
      <dt>Road-level boundary diff</dt><dd id="buildRoadDiffSummary">${diff.changedBoundaryTiles.features.length ? "loading retained Build A/B roads…" : "no changed boundary tiles"}</dd>
    `;
    showBuildDiffOverlay(diff.changedBoundaryTiles);
    if (diff.changedBoundaryTiles.features.length) {
      loadBuildRoadComparison(a, b, diff, generation);
    }
  } catch (error) {
    comparison.innerHTML = basic + `<dt>Graph diff</dt><dd class="bad">${String(error)}</dd>`;
  }
}
compareA.addEventListener("change", () => { void renderComparison(); });
compareB.addEventListener("change", () => { void renderComparison(); });

visualBuildSelect.addEventListener("change", () => {
  const build = selectedVisualBuild();
  loadVisualBuildBtn.disabled = build == null;
  fitVisualBuildBtn.disabled = build == null;
  renderVisualBuildSummary(build);
});
loadVisualBuildBtn.addEventListener("click", () => {
  const build = selectedVisualBuild();
  if (!build) return;
  try {
    addVisualBuildLayer(build);
    fitVisualBuild(build);
    appendLog(`Loaded exact visual PMTiles: ${build.region_id} • ${build.version}`);
  } catch (error) {
    visualBuildSummary.className = "bad";
    visualBuildSummary.textContent = `Could not load visual PMTiles: ${String(error)}`;
  }
});
fitVisualBuildBtn.addEventListener("click", () => {
  const build = selectedVisualBuild();
  if (build) fitVisualBuild(build);
});
visualCompareA.addEventListener("change", () => {
  compareVisualBuildsBtn.disabled = !(visualCompareA.value && visualCompareB.value);
});
visualCompareB.addEventListener("change", () => {
  compareVisualBuildsBtn.disabled = !(visualCompareA.value && visualCompareB.value);
});
compareVisualBuildsBtn.addEventListener("click", compareVisualBuilds);

saveR2CredentialsBtn.addEventListener("click", async () => {
  saveR2CredentialsBtn.disabled = true;
  r2CredentialSummary.className = "empty";
  r2CredentialSummary.textContent = "Saving private local R2 credentials…";
  try {
    const status = await invoke<R2CredentialStatus>("save_r2_credentials", {
      accountId: r2AccountId.value.trim(),
      bucket: r2Bucket.value.trim(),
      accessKeyId: r2AccessKey.value,
      secretAccessKey: r2SecretKey.value,
      endpointUrl: r2Endpoint.value.trim() || null,
    });
    renderR2CredentialStatus(status);
    appendLog(`Saved local R2 configuration for bucket ${status.bucket ?? "unknown"}.`);
    await refreshR2Publication();
  } catch (error) {
    r2CredentialSummary.className = "bad";
    r2CredentialSummary.textContent = `R2 credential save failed: ${String(error)}`;
  } finally {
    updatePublicationControls();
  }
});

testR2CredentialsBtn.addEventListener("click", async () => {
  testR2CredentialsBtn.disabled = true;
  r2CredentialSummary.className = "empty";
  r2CredentialSummary.textContent = "Testing R2 bucket access without writing objects…";
  try {
    const result = await invoke<Record<string, unknown>>("test_r2_credentials");
    await refreshR2CredentialStatus();
    r2CredentialSummary.className = "kv";
    r2CredentialSummary.innerHTML += `
      <dt>Connection</dt><dd class="ok">OK</dd>
      <dt>Sample keys</dt><dd>${escapeHtml(result.keyCountSample ?? 0)}</dd>
    `;
    appendLog("R2 credential test succeeded.");
    await refreshR2Publication();
  } catch (error) {
    r2CredentialSummary.className = "bad";
    r2CredentialSummary.textContent = `R2 test failed: ${String(error)}`;
  } finally {
    updatePublicationControls();
  }
});

clearR2CredentialsBtn.addEventListener("click", async () => {
  clearR2CredentialsBtn.disabled = true;
  try {
    renderR2CredentialStatus(await invoke<R2CredentialStatus>("clear_r2_credentials"));
    r2AccountId.value = "";
    r2Bucket.value = "";
    r2Endpoint.value = "";
    remotePublication = null;
    renderPublicationRemoteStatus();
    appendLog("Cleared Graph Studio's local R2 credentials.");
  } catch (error) {
    r2CredentialSummary.className = "bad";
    r2CredentialSummary.textContent = `Could not clear R2 credentials: ${String(error)}`;
  } finally {
    updatePublicationControls();
  }
});

publicationKind.addEventListener("change", () => {
  remotePublication = null;
  renderPublicationBuildSelector();
});

publishBuildSelect.addEventListener("change", () => {
  remotePublication = null;
  renderPublicationRemoteStatus();
  void refreshR2Publication();
});

refreshPublicationBtn.addEventListener("click", () => {
  void refreshR2Publication();
});

publishBuildBtn.addEventListener("click", async () => {
  const build = selectedPublicationBuild();
  if (!build) return;
  publishBuildBtn.disabled = true;
  publicationProgressText.className = "status-line";
  publicationProgressText.textContent =
    `Starting validated ${build.artifactKind.toLowerCase()} publication for ${build.region_id} • ${build.version}…`;
  try {
    await invoke("start_r2_publication", {
      manifestPath: build.manifest_path,
      artifactKind: build.artifactKind,
    });
    await refreshPublicationStatus();
    appendLog(
      `R2 ${build.artifactKind} publication started: ${build.region_id} • ${build.version}`,
    );
  } catch (error) {
    publicationProgressText.className = "status-line bad";
    publicationProgressText.textContent = `Could not start R2 publication: ${String(error)}`;
  } finally {
    updatePublicationControls();
  }
});

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

loadBorderPairBtn.addEventListener("click", () => {
  const a = borderRegionA.value;
  const b = borderRegionB.value;
  if (!a || !b || a === b) {
    handoffValidationSummary.className = "bad";
    handoffValidationSummary.textContent = "Choose two different locally built regions.";
    return;
  }
  clearHandoffSelection(false);
  showBorderPairLayers(a, b);
  handoffValidationSummary.className = "empty";
  handoffValidationSummary.textContent = `Overlay loaded: A=${a}, B=${b}. Road diff uses stable OSM way identity.`;
});

refreshBorderDiffBtn.addEventListener("click", scheduleBorderRoadDiff);
refreshHandoffArtifactsBtn.addEventListener("click", () => refreshHandoffArtifactOverlay());
refreshConnectorMatrixBtn.addEventListener("click", () => refreshConnectorMatrix());
connectorMode.addEventListener("change", () => {
  if (connectorInspection) renderConnectorMatrix(connectorInspection);
});
connectorRegion.addEventListener("change", () => {
  connectorInspection = null;
  removeConnectorMatrixOverlay();
  connectorMatrixList.innerHTML = "";
  connectorMatrixSummary.className = "empty";
  connectorMatrixSummary.textContent = connectorRegion.value
    ? "Inspect this region to load connector inventory and matrix freshness."
    : "Choose a locally built region to inspect its connector inventory and matrix.";
  refreshConnectorMatrixBtn.disabled = !connectorRegion.value;
});
exportBorderDiagnosticsBtn.addEventListener("click", async () => {
  const regionA = borderRegionA.value;
  const regionB = borderRegionB.value;
  if (!regionA || !regionB || regionA === regionB) return;
  exportBorderDiagnosticsBtn.disabled = true;
  borderReportSummary.className = "empty";
  borderReportSummary.textContent = "Writing JSON and Markdown diagnostics…";
  try {
    const result = await invoke<BorderDiagnosticsExport>("export_border_diagnostics", {
      regionA,
      regionB,
      roadDiff: lastBorderDiffMetrics,
      selectedValidation: handoffValidation,
    });
    borderReportSummary.className = "ok report-path";
    borderReportSummary.textContent = `Saved Markdown: ${result.markdownPath}\nSaved JSON: ${result.jsonPath}`;
    appendLog(`Border diagnostics saved: ${result.markdownPath}`);
  } catch (error) {
    borderReportSummary.className = "bad";
    borderReportSummary.textContent = `Diagnostics export failed: ${String(error)}`;
  } finally {
    exportBorderDiagnosticsBtn.disabled = false;
  }
});
map.on("moveend", scheduleBorderRoadDiff);

pickHandoffABtn.addEventListener("click", () => {
  if (!borderRegionA.value) {
    handoffValidationSummary.className = "bad";
    handoffValidationSummary.textContent = "Choose Graph A first.";
    return;
  }
  handoffPickMode = "A";
  pickHandoffABtn.textContent = "Click map…";
  pickHandoffBBtn.textContent = "Pick B edge";
});
pickHandoffBBtn.addEventListener("click", () => {
  if (!borderRegionB.value) {
    handoffValidationSummary.className = "bad";
    handoffValidationSummary.textContent = "Choose Graph B first.";
    return;
  }
  handoffPickMode = "B";
  pickHandoffBBtn.textContent = "Click map…";
  pickHandoffABtn.textContent = "Pick A edge";
});

validateHandoffBtn.addEventListener("click", async () => {
  if (!handoffSnapA || !handoffSnapB) return;
  validateHandoffBtn.disabled = true;
  saveHandoffBtn.disabled = true;
  handoffValidationSummary.className = "empty";
  handoffValidationSummary.textContent = "Running two-graph motorcycle/auto direction proofs…";
  try {
    const validation = await invoke<HandoffValidation>("validate_handoff_override", {
      regionA: borderRegionA.value,
      regionB: borderRegionB.value,
      snapA: handoffSnapA,
      snapB: handoffSnapB,
    });
    handoffValidation = validation;
    renderHandoffValidation(validation);
  } catch (error) {
    handoffValidation = null;
    handoffValidationSummary.className = "bad";
    handoffValidationSummary.textContent = `Validation failed: ${String(error)}`;
  } finally {
    validateHandoffBtn.disabled = !(handoffSnapA && handoffSnapB);
  }
});

saveHandoffBtn.addEventListener("click", async () => {
  if (!handoffSnapA || !handoffSnapB || !handoffValidation?.passed) return;
  saveHandoffBtn.disabled = true;
  try {
    const saved = await invoke<HandoffOverride>("save_handoff_override", {
      regionA: borderRegionA.value,
      regionB: borderRegionB.value,
      snapA: handoffSnapA,
      snapB: handoffSnapB,
      overrideId: editingHandoffId,
    });
    editingHandoffId = saved.id;
    appendLog(`Saved VALID manual handoff: ${borderRegionA.value} ↔ ${borderRegionB.value}`);
    await refreshHandoffOverrides();
    await refreshHandoffArtifactOverlay();
  } catch (error) {
    handoffValidationSummary.className = "bad";
    handoffValidationSummary.textContent = `Save rejected: ${String(error)}`;
  } finally {
    saveHandoffBtn.disabled = !handoffValidation?.passed;
  }
});

clearHandoffBtn.addEventListener("click", () => clearHandoffSelection(false));
borderRegionA.addEventListener("change", () => clearHandoffSelection(true));
borderRegionB.addEventListener("change", () => clearHandoffSelection(true));

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
  if (handoffPickMode) {
    const mode = handoffPickMode;
    handoffPickMode = null;
    pickHandoffABtn.textContent = "Pick A edge";
    pickHandoffBBtn.textContent = "Pick B edge";
    snapHandoff(mode, event.lngLat.lat, event.lngLat.lng).catch(error => appendLog(String(error)));
    return;
  }
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
    if (!event.payload.running) {
      refreshBuilds().catch(() => {});
      refreshVisualBuilds().catch(() => {});
    }
  });
  await listen<PublicationStatus>("graph-studio://publication-status", event => {
    renderPublicationStatus(event.payload);
  });
  await listen<Record<string, unknown>>("graph-studio://publication-event", event => {
    const kind = String(event.payload.event ?? "");
    if (kind && kind !== "UPLOAD_PROGRESS") {
      appendLog(`R2 ${kind}: ${String(event.payload.key ?? event.payload.releaseKey ?? "")}`);
    }
  });

  await Promise.all([
    refreshRegions(),
    refreshToolchain(),
    refreshBuildStatus(),
    refreshBuilds(),
    refreshVisualBuilds(),
    refreshHandoffOverrides(),
    refreshStats(),
    refreshR2CredentialStatus(),
    refreshPublicationStatus(),
  ]);
  setInterval(refreshStats, 3000);
  setInterval(refreshBuildStatus, 2500);
  setInterval(refreshPublicationStatus, 2500);
}

bootstrap().catch(error => appendLog(`Startup error: ${String(error)}`));
