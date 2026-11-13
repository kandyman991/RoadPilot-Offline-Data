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
  primary_geofabrik_id: string | null;
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

type SearchBuildArtifact = {
  region_id: string;
  version: string;
  built_at_utc: string;
  database_file: string;
  database_path: string;
  size_bytes: number;
  sha256: string;
  record_count: number;
  categorized_record_count: number;
  source_release: string;
  source_fingerprint: string;
  search_fingerprint: string;
  manifest_path: string;
  validation_passed: boolean;
};
type SearchResult = {
  id: string; title: string; address: string; latitude: number; longitude: number;
  confidence: number; freeform: string; postcode: string; locality: string; region: string; country: string;
  operatingStatus: string; basicCategory: string; taxonomyPrimary: string; taxonomyHierarchy: string[];
  taxonomyAlternates: string[]; sourceProvider: string; sourceDataset: string; sourceRecordId: string;
  sourceVersion: string; distanceMeters: number | null; score: number; scoreConfidence: number; scoreExact: number;
  scorePrefix: number; scoreContains: number; scoreBrandFirst: number; scoreTokenMatches: number; scoreCategory: number; scoreProximity: number;
};
type SearchBuildComparison = {
  placeCountA: number; placeCountB: number; placeCountDelta: number;
  categorizedPlaceCountA: number; categorizedPlaceCountB: number;
  addedCount: number; removedCount: number; changedCount: number;
  addedIds: string[]; removedIds: string[]; changedIds: string[];
  categoryDeltas: Array<{category:string;a:number;b:number;delta:number}>;
};

type LocateEdgeCandidate = {
  edge_id?: unknown;
  correlated_lat?: number;
  correlated_lon?: number;
  distance?: number;
  percent_along?: number;
  heading?: number;
  linear_reference?: string;
  edge_info?: {
    way_id?: string | number;
    names?: string[];
    shape?: string;
    [key: string]: unknown;
  };
  edge?: {
    access?: Record<string, boolean>;
    start_restriction?: Record<string, boolean>;
    end_restriction?: Record<string, boolean>;
    [key: string]: unknown;
  };
  [key: string]: unknown;
};
type LocateResult = Array<{ edges?: LocateEdgeCandidate[]; [key: string]: unknown }>;

type PublicationKind = "ROUTING" | "VISUAL" | "SEARCH";
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
  countryIsoAlpha2: string | null;
  // Geofabrik includes downloadable extracts with empty index geometry.
  // The exact .poly geometry is retrieved when opening their region editor.
  bounds: { minLat: number; maxLat: number; minLng: number; maxLng: number } | null;
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
  arrival: {
    actualStart: { lat: number; lng: number };
    actualEnd: { lat: number; lng: number };
    startOffsetMeters: number;
    endOffsetMeters: number;
    startMatched: boolean;
    destinationReached: boolean;
    maxAcceptedEndpointOffsetMeters: number;
  };
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
  countryIsoAlpha2: string | null;
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
    <div class="topbar-spacer"></div>
    <nav id="workspaceSwitcher" class="workspace-switcher" aria-label="Workspace panes" hidden>
      <button id="showRegionsPane" class="workspace-pane-btn" type="button" aria-pressed="false">Regions</button>
      <button id="showMapPane" class="workspace-pane-btn" type="button" aria-pressed="true">Map</button>
      <button id="showToolsPane" class="workspace-pane-btn" type="button" aria-pressed="false">Tools</button>
    </nav>
    <button id="toolchainBadge" class="metric toolchain-trigger" type="button" aria-label="Show toolchain details" aria-controls="toolchainDetailsPanel" aria-expanded="false">Toolchain <b>checking…</b></button>
  </header>

  <main class="workspace">
    <aside class="sidebar">
      <section class="section region-browser-section">
        <h2>Regions</h2>
        <div class="region-tabs" role="tablist" aria-label="Region browser">
          <button id="configuredRegionsTab" class="region-tab active" type="button" role="tab" aria-selected="true">Configured</button>
          <button id="catalogRegionsTab" class="region-tab" type="button" role="tab" aria-selected="false">All catalog</button>
        </div>
        <input id="regionSearch" class="region-search" type="search" autocomplete="off" placeholder="Search regions…" aria-label="Search regions" />
        <div id="regionBrowserSummary" class="region-browser-summary">Loading regions…</div>
        <div id="regions" class="region-browser"></div>
        <div class="region-tree-actions">
          <button id="newRegionBtn" class="btn" type="button">New region</button>
          <button id="editRegionBtn" class="btn" type="button" disabled>Edit selected</button>
          <button id="configureQueuedBtn" class="btn configure-queued" type="button" disabled>Configure queued regions</button>
        </div>
      </section>
    </aside>

    <div id="leftSplitter" class="pane-splitter vertical-splitter" role="separator" aria-orientation="vertical" title="Drag to resize regions pane"></div>
    <section class="map-wrap">
      <div id="map"></div>
      <div class="map-toolbar">
        <span id="activeRegionBadge" class="map-badge">No region selected</span>
        <button id="graphLayerBtn" class="btn" type="button" disabled>Show graph</button>
        <button id="fitBtn" class="btn" type="button" disabled>Fit region</button>
        <label class="map-layers-control" for="mapLayerPreset">Layers
          <select id="mapLayerPreset" aria-label="Map layer preset">
            <option value="map">Map</option><option value="routing">Routing</option><option value="borders">Borders</option><option value="all">All diagnostics</option><option value="custom" disabled>Custom</option>
          </select>
        </label>
        <button id="clearToolOverlaysBtn" class="btn" type="button" aria-label="Clear temporary map overlays" title="Remove temporary diagnostic overlays from the map; saved files and selections are unchanged">Clear</button>
      </div>
    </section>

    <div id="rightSplitter" class="pane-splitter vertical-splitter" role="separator" aria-orientation="vertical" title="Drag to resize tools pane"></div>
    <aside class="inspector">
      <div class="tool-menu-shell">
        <label for="toolMenu">Work on</label>
        <select id="toolMenu" aria-label="Graph Studio workflow">
          <option value="build">Build regions</option>
          <option value="f8">Connect regions (A → X → B)</option>
          <option value="route">Test routes</option>
          <option value="data">Map &amp; Search data</option>
          <option value="publish">Publish packages</option>
          <option value="advanced">Advanced tools…</option>
        </select>
        <button id="openToolchainBtn" class="tool-menu-diagnostics" type="button" aria-controls="toolchainDetailsPanel" aria-expanded="false" aria-label="Open toolchain diagnostics" title="Toolchain diagnostics">Tools status</button>
      </div>
      <nav id="dataWorkspaceTabs" class="workflow-subnav" aria-label="Map and Search data tools" hidden>
        <button id="dataVisualTab" type="button" class="workflow-subnav-btn" aria-pressed="true">Visual maps</button>
        <button id="dataSearchTab" type="button" class="workflow-subnav-btn" aria-pressed="false">Search / POI</button>
      </nav>
      <div id="advancedToolSelector" class="advanced-tool-selector" hidden>
        <label for="advancedToolMenu">Specialist inspector</label>
        <select id="advancedToolMenu" aria-label="Advanced Graph Studio tools">
          <option value="graph">Directed graph inspector</option>
          <option value="compare">Compare retained builds</option>
          <option value="border">Historical / manual borders</option>
        </select>
        <small>Retained diagnostic tools; historical outputs do not prove native F8 connections.</small>
      </div>
      <div id="contextToolNotice" class="context-tool-notice" hidden>
        <span id="contextToolTitle">Context tool</span>
        <button id="contextBackBtn" class="btn" type="button">Back to workflow</button>
      </div>

      <section class="section tool-panel" data-tool="build">
        <h2>Build</h2>
        <div class="field">
          <label for="packageVersion">Package version</label>
          <input id="packageVersion" autocomplete="off" />
        </div>
        <div class="actions">
          <button id="buildBtn" class="btn primary" type="button" disabled>Build selected</button>
          <button id="cancelBtn" class="btn danger" type="button" disabled>Cancel</button>
        </div>
        <div id="buildSelectionSummary" class="status-line">No regions selected.</div>
        <div id="buildPrerequisite" class="status-line" aria-live="polite">Select a region and wait for the toolchain.</div>
        <p class="status-line">Select regions on the left, choose a package version, then build. Region sources and normal Valhalla checks are automatic.</p>
        <details class="route-options">
          <summary>Advanced build options and details</summary>
          <label class="check-row"><input id="refreshSourceCheckbox" type="checkbox" />
            Force source re-download (ignore unchanged source cache)
          </label>
          <p>Source PBFs use a shared verified cache with upstream checksum checks. Each routing region is built and validated independently.</p>
          <p>Native A → X → B catalogs may be verified for private Graph Studio use separately from later Android release acceptance. Historical connector artifacts are diagnostic-only.</p>
        </details>
      </section>

      <section class="section tool-panel" data-tool="publish" hidden>
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
            <option value="SEARCH">Search / POI SQLite</option>
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

      <section id="toolchainDetailsPanel" class="section tool-panel" data-tool="toolchain" hidden>
        <h2>Toolchain &amp; system</h2>
        <div class="toolchain-metrics" aria-label="System metrics">
          <div id="metricCpu" class="metric">CPU <b>—</b></div>
          <div id="metricRam" class="metric">RAM <b>—</b></div>
          <div id="metricDisk" class="metric">Disk <b>—</b></div>
          <div id="metricTemp" class="metric">Temp <b>—</b></div>
        </div>
        <div id="tools" class="empty">Checking local tools…</div>
      </section>

      <section id="regionEditorSection" class="section tool-panel" data-tool="region" hidden>
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
        <h2 style="margin-top:16px">Search / POI region configuration</h2>
        <label class="check-row"><input id="editorSearchEnabled" type="checkbox" /> Enable independent offline Search / POI pack for this region</label>
        <div class="field"><label for="editorSearchCountry">Overture ISO alpha-2 country (from Geofabrik)</label><input id="editorSearchCountry" maxlength="2" autocomplete="off" placeholder="AT" /></div>
        <div class="field"><label for="editorSearchExpectedName">Required regression place name</label><input id="editorSearchExpectedName" autocomplete="off" placeholder="Name confirmed in Overture Places" /></div>
        <div class="field"><label for="editorSearchQuery">Required regression search query</label><input id="editorSearchQuery" autocomplete="off" placeholder="Exactly what RoadPilot should find" /></div>
        <div class="field"><label for="editorSearchAddress">Optional expected address fragments (comma-separated)</label><input id="editorSearchAddress" autocomplete="off" placeholder="city, street" /></div>
        <p>The exact Geofabrik region bounds define Search coverage for new regions; the existing Search coverage is retained on edits. Enabling Search requires one known Overture place that is verified with the Android-compatible search runtime before publication.</p>
        <div class="actions editor-pin-actions"><button id="pickEditorStartBtn" class="btn" type="button">Pick start on map</button><button id="pickEditorEndBtn" class="btn" type="button">Pick end on map</button><button id="clearEditorPinsBtn" class="btn" type="button">Clear pins</button></div>
        <p>Click Pick start/end, then click a road on the map. Drag pins to refine. This is an optional manual fallback; automatic builds find Valhalla-proved crossings.</p>
        <div class="actions">
          <button id="saveRegionBtn" class="btn primary" type="button" disabled>Save region</button>
          <button id="closeRegionEditorBtn" class="btn" type="button">Close</button>
        </div>
      </section>
      <section class="section tool-panel" data-tool="search" hidden>
        <h2>Search / POI inspector</h2>
        <details class="route-options">
          <summary>Create / import a regional Search pack</summary>
          <p>Build Search without rebuilding routing graphs or visual PMTiles. The selected region must have Search enabled and a saved deterministic validation target.</p>
          <div class="field"><label for="searchPackVersion">New immutable Search version</label><input id="searchPackVersion" autocomplete="off" placeholder="2026.11.13-1" /></div>
          <div class="field"><label for="searchLocalInput">Optional existing Overture GeoJSONSeq absolute path</label><input id="searchLocalInput" autocomplete="off" placeholder="Leave empty to download latest pinned Overture Places" /></div>
          <div class="field"><label for="searchLocalRelease">Source release (required for existing local input)</label><input id="searchLocalRelease" autocomplete="off" placeholder="YYYY-MM-DD.N" /></div>
          <div class="actions"><button id="buildSearchBtn" class="btn primary" type="button">Build Search only</button><button id="cancelSearchBtn" class="btn danger" type="button" disabled>Cancel Search build</button></div>
          <div class="field"><label for="searchImportManifest">Import validated Search manifest (absolute .json path)</label><input id="searchImportManifest" autocomplete="off" placeholder="/path/to/region-search-manifest.json" /></div>
          <div class="actions"><button id="importSearchBtn" class="btn" type="button">Validate + retain existing pack</button><button id="refreshSearchBtn" class="btn" type="button">Refresh builds</button></div>
          <div id="searchProduceStatus" class="status-line">Select a configured region to build or import. Search artifact builds are independent of Routing/Visual.</div>
        </details>
        <div class="field"><label for="searchBuildSelect">Retained search build</label><select id="searchBuildSelect"></select></div>
        <div id="searchBuildSummary" class="empty">No retained search build selected.</div>
        <div class="field"><label for="searchQuery">Name / phrase / address</label><input id="searchQuery" autocomplete="off" placeholder="SARP, hotel, Via Roma…" /></div>
        <div class="field"><label for="searchCategory">Category</label><input id="searchCategory" list="searchCategoryPresets" autocomplete="off" placeholder="gas station" /></div>
        <datalist id="searchCategoryPresets"><option value="gas station"></option><option value="restaurant"></option><option value="hotel"></option><option value="parking"></option><option value="charging station"></option><option value="hospital"></option><option value="motorcycle dealer"></option><option value="shop"></option><option value="attraction"></option></datalist>
        <label class="check-row"><input id="searchUseMapCenter" type="checkbox" checked /> Rank relative to current map center</label>
        <div class="actions"><button id="runSearchBtn" class="btn primary" type="button">Search exact DB</button><button id="clearSearchBtn" class="btn" type="button">Clear</button></div>
        <div id="searchResultsSummary" class="empty" style="margin-top:8px">Choose a retained search build.</div>
        <div id="searchResults" class="search-results"></div>

      </section>
      <section class="section tool-panel" data-tool="visual" hidden>
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

        <details class="route-options" style="margin-top:10px">
          <summary>Detailed map layers (advanced)</summary>
          <p class="status-line">Use the map toolbar to choose a preset. Individual switches create a Custom view; no routing or graph evidence is modified.</p>
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

      </section>
      <section class="section tool-panel" data-tool="graph" hidden>
        <h2>Graph inspector</h2>
        <div id="inspectorSummary" class="empty">
          Click a rendered graph feature for its MVT properties, or right-click any road for exact Valhalla locate candidates.
        </div>
        <div id="locateCandidateSummary" class="empty" style="margin-top:8px">Right-click the map to inspect directed edges from the exact selected graph.</div>
        <div class="actions" style="margin-top:8px">
          <button id="locatePrevBtn" class="btn" type="button" disabled>← Previous edge</button>
          <button id="locateNextBtn" class="btn" type="button" disabled>Next edge →</button>
          <button id="locateBtn" class="btn" type="button" disabled>Deep locate last click</button>
        </div>
        <div id="locateCandidateDetails" class="kv" style="margin-top:8px"></div>
        <pre id="featureJson" class="feature-json">No graph feature selected.</pre>
      </section>
      <section class="section tool-panel" data-tool="border" hidden>
        <h2>Border inspector</h2>
        <p class="status-line">Inspect retained graph pairs and manually validate specific directed crossings. Native F8 discovery and journey proofs are in the separate Native F8 tool.</p>
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
        <div class="border-tabs" role="tablist" aria-label="Border inspection workflow">
          <button id="borderManualTab" class="border-tab active" type="button" role="tab" aria-selected="true" aria-controls="borderManualPanel">Manual validation</button>
          <button id="borderEvidenceTab" class="border-tab" type="button" role="tab" aria-selected="false" aria-controls="borderEvidencePanel" tabindex="-1">Saved evidence</button>
        </div>
        <div id="borderManualPanel" class="border-subpanel" role="tabpanel" aria-labelledby="borderManualTab">
          <h3>Manual directed-edge crossing</h3>
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
        </div>
        <div id="borderEvidencePanel" class="border-subpanel" role="tabpanel" aria-labelledby="borderEvidenceTab" hidden>
          <p class="status-line">Read-only historical artifact review. Saved overrides remain available but do not establish native F8 parity or global journey completeness.</p>
        <h3>Historical handoff artifacts and manual evidence</h3>
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
        <div class="actions" style="margin-top:10px">
          <button id="exportBorderDiagnosticsBtn" class="btn" type="button" disabled>Export diagnostics</button>
        </div>
        <div id="borderReportSummary" class="empty" style="margin-top:8px">No diagnostics report exported.</div>
        <h3>Saved manual overrides</h3>
        <div id="handoffOverrideList" class="empty">No manual overrides.</div>
        </div>
      </section>
      <section class="section tool-panel" data-tool="f8" hidden>
        <h2>Connect regions (A → X → B)</h2>
        <p class="status-line">Build a private native catalog using Graph A final directed GraphIds and original Graph B matching directed roads at exact GPS X, preserving real branches and vehicle permissions.</p>
        <div class="coord-grid">
          <div class="field"><label for="f8RegionA">Graph A</label><select id="f8RegionA"></select></div>
          <div class="field"><label for="f8RegionB">Graph B</label><select id="f8RegionB"></select></div>
        </div>
        <div class="actions">
          <button id="f8RefreshBtn" class="btn" type="button" disabled>Check original native proof</button>
          <button id="f8BuildCatalogBtn" class="btn primary" type="button" disabled>Build private catalog</button>
          <button id="f8CancelBtn" class="btn danger" type="button" disabled>Cancel</button>
        </div>
        <div id="f8JobSummary" class="status-line" aria-live="polite">Select original Graph A and Graph B.</div>
        <div id="f8PairSummary" class="empty" aria-live="polite">Select two different retained regional graphs.</div>
        <div id="f8SampleConnections" class="artifact-list"></div>
        <details class="route-options">
          <summary>Original native evidence (advanced)</summary>
          <div class="field">
            <label for="f8EvidenceDirectory">Optional matching evidence folder</label>
            <input id="f8EvidenceDirectory" autocomplete="off" placeholder="Leave blank to search retained original native evidence" />
          </div>
          <p>If independent matching evidence already exists, it is verified and reused. Otherwise Build runs the approved original-native final-edge reader, A→exact X→B matcher, independent audit and private catalog validator. Missing original source/build prerequisites fail closed.</p>
          <p>Private catalogs are not RoadPilot Android releases; global physical-road lineage remains NOT_VERIFIED.</p>
        </details>
      </section>
      <section class="section tool-panel" data-tool="route" hidden>
        <h2>Valhalla route planner</h2>
        <p class="status-line">Test routes on one original Valhalla regional graph. A single buffered graph's cross-border route is not proof of a two-graph A → X → B connection.</p>
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
          <button id="runRouteBtn" class="btn primary" type="button" disabled>Route</button>
        </div>
        <div id="routePrerequisite" class="status-line" aria-live="polite">Select a built region and valid route coordinates.</div>
        <label class="check-row route-expansion-row"><input id="routeExpansionToggle" type="checkbox" /> <span>Show search expansion</span></label>
        <div id="expansionPlayback" class="empty" hidden>
          <label for="expansionProgress">Expansion playback <span id="expansionProgressLabel">0 / 0 edges</span></label>
          <input id="expansionProgress" type="range" min="0" max="1000" step="1" value="1000" />
          <small>Drag backward to replay Valhalla's native expansion order. The final selected route remains visible above the explored graph.</small>
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
      <section class="section tool-panel" data-tool="compare" hidden>
        <h2>Compare retained builds</h2>
        <p class="status-line">Compare immutable regional artifacts by type. Switching comparison tabs preserves the selected builds and their results.</p>
        <div class="comparison-tabs" role="tablist" aria-label="Comparison artifact type">
          <button id="compareRoutingTab" class="comparison-tab active" role="tab" type="button" aria-selected="true" aria-controls="compareRoutingPanel">Routing</button>
          <button id="compareVisualTab" class="comparison-tab" role="tab" type="button" aria-selected="false" aria-controls="compareVisualPanel" tabindex="-1">Visual</button>
          <button id="compareSearchTab" class="comparison-tab" role="tab" type="button" aria-selected="false" aria-controls="compareSearchPanel" tabindex="-1">Search</button>
        </div>
        <div id="compareRoutingPanel" class="comparison-subpanel" role="tabpanel" aria-labelledby="compareRoutingTab">
          <h3>Routing graph and boundary changes</h3>

        <div class="field">
          <label for="compareA">Build A</label>
          <select id="compareA"></select>
        </div>
        <div class="field">
          <label for="compareB">Build B</label>
          <select id="compareB"></select>
        </div>
        <div id="comparison" class="empty">Choose two builds of the same region.</div>
        </div>
        <div id="compareVisualPanel" class="comparison-subpanel" role="tabpanel" aria-labelledby="compareVisualTab" hidden>
        <h3>Visual build comparison</h3>
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
        </div>
        <div id="compareSearchPanel" class="comparison-subpanel" role="tabpanel" aria-labelledby="compareSearchTab" hidden>
          <h3>Search and POI database changes</h3>
        <div class="search-comparison-content">
          <div class="field"><label for="searchCompareA">Build A</label><select id="searchCompareA"></select></div>
          <div class="field"><label for="searchCompareB">Build B</label><select id="searchCompareB"></select></div>
          <div class="actions"><button id="compareSearchBtn" class="btn" type="button">Compare</button></div>
          <pre id="searchCompareSummary" class="feature-json">Choose two builds of the same region.</pre>
        </div>
        </div>
      </section>
    </aside>
  </main>

  <div id="consoleSplitter" class="pane-splitter horizontal-splitter" role="separator" aria-orientation="horizontal" title="Drag to resize console"></div>
  <footer class="console">
    <section class="console-summary">
      <div id="statusTitle" class="status-title">Idle</div>
      <div id="statusStage" class="status-line">No build running.</div>
      <div id="progress" class="progress idle"><div></div></div>
      <div id="statusQueue" class="status-line"></div>
      <button id="consoleToggle" type="button" class="console-toggle" aria-controls="consoleLog builds" aria-expanded="false">Show log</button>
    </section>
    <pre id="consoleLog" class="console-log">Graph Studio ready.\n</pre>
    <section class="console-side">
      <div class="status-title">Recent builds</div>
      <div id="builds" class="empty">No local builds found.</div>
    </section>
  </footer>
</div>
`;

const appRoot = document.querySelector<HTMLDivElement>(".app")!;
const regionHost = document.querySelector<HTMLDivElement>("#regions")!;
const toolMenu = document.querySelector<HTMLSelectElement>("#toolMenu")!;
const dataWorkspaceTabs = document.querySelector<HTMLElement>("#dataWorkspaceTabs")!;
const dataVisualTab = document.querySelector<HTMLButtonElement>("#dataVisualTab")!;
const dataSearchTab = document.querySelector<HTMLButtonElement>("#dataSearchTab")!;
const advancedToolSelector = document.querySelector<HTMLElement>("#advancedToolSelector")!;
const advancedToolMenu = document.querySelector<HTMLSelectElement>("#advancedToolMenu")!;
const contextToolNotice = document.querySelector<HTMLDivElement>("#contextToolNotice")!;
const contextToolTitle = document.querySelector<HTMLSpanElement>("#contextToolTitle")!;
const contextBackBtn = document.querySelector<HTMLButtonElement>("#contextBackBtn")!;
const toolchainBadge = document.querySelector<HTMLButtonElement>("#toolchainBadge")!;
const openToolchainBtn = document.querySelector<HTMLButtonElement>("#openToolchainBtn")!;
const comparisonTabs = {
  routing: document.querySelector<HTMLButtonElement>("#compareRoutingTab")!,
  visual: document.querySelector<HTMLButtonElement>("#compareVisualTab")!,
  search: document.querySelector<HTMLButtonElement>("#compareSearchTab")!,
};
const comparisonPanels = {
  routing: document.querySelector<HTMLDivElement>("#compareRoutingPanel")!,
  visual: document.querySelector<HTMLDivElement>("#compareVisualPanel")!,
  search: document.querySelector<HTMLDivElement>("#compareSearchPanel")!,
};
type ComparisonTab = "routing" | "visual" | "search";
const COMPARISON_TAB_KEY = "roadpilot.graph-studio.comparison-tab";
function activateComparisonTab(tab: ComparisonTab, remember = true): void {
  for (const key of ["routing", "visual", "search"] as const) {
    const active = key === tab;
    comparisonPanels[key].hidden = !active;
    comparisonTabs[key].classList.toggle("active", active);
    comparisonTabs[key].setAttribute("aria-selected", String(active));
    comparisonTabs[key].tabIndex = active ? 0 : -1;
  }
  if (remember) localStorage.setItem(COMPARISON_TAB_KEY, tab);
}
const previousComparisonTab = localStorage.getItem(COMPARISON_TAB_KEY);
activateComparisonTab(previousComparisonTab === "visual" || previousComparisonTab === "search" ? previousComparisonTab : "routing", false);
for (const key of ["routing", "visual", "search"] as const) {
  comparisonTabs[key].addEventListener("click", () => activateComparisonTab(key));
  comparisonTabs[key].addEventListener("keydown", event => {
    const order: ComparisonTab[] = ["routing", "visual", "search"];
    const direction = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    const destination = event.key === "Home" ? "routing" : event.key === "End" ? "search" :
      direction ? order[(order.indexOf(key) + direction + order.length) % order.length] : null;
    if (!destination) return;
    event.preventDefault();
    activateComparisonTab(destination);
    comparisonTabs[destination].focus();
  });
}
const toolPanels = [...document.querySelectorAll<HTMLElement>(".tool-panel")];
const leftSplitter = document.querySelector<HTMLDivElement>("#leftSplitter")!;
const rightSplitter = document.querySelector<HTMLDivElement>("#rightSplitter")!;
const consoleSplitter = document.querySelector<HTMLDivElement>("#consoleSplitter")!;
const workspaceSwitcher = document.querySelector<HTMLElement>("#workspaceSwitcher")!;
const workspaceButtons = {
  regions: document.querySelector<HTMLButtonElement>("#showRegionsPane")!,
  map: document.querySelector<HTMLButtonElement>("#showMapPane")!,
  tools: document.querySelector<HTMLButtonElement>("#showToolsPane")!,
};
const consoleToggle = document.querySelector<HTMLButtonElement>("#consoleToggle")!;
const configuredRegionsTab = document.querySelector<HTMLButtonElement>("#configuredRegionsTab")!;
const catalogRegionsTab = document.querySelector<HTMLButtonElement>("#catalogRegionsTab")!;
const regionSearch = document.querySelector<HTMLInputElement>("#regionSearch")!;
const regionBrowserSummary = document.querySelector<HTMLDivElement>("#regionBrowserSummary")!;
const configureQueuedBtn = document.querySelector<HTMLButtonElement>("#configureQueuedBtn")!;
const buildSelectionSummary = document.querySelector<HTMLDivElement>("#buildSelectionSummary")!;
const toolHost = document.querySelector<HTMLDivElement>("#tools")!;
const logHost = document.querySelector<HTMLPreElement>("#consoleLog")!;
const buildsHost = document.querySelector<HTMLDivElement>("#builds")!;
const packageVersionInput = document.querySelector<HTMLInputElement>("#packageVersion")!;
const refreshSourceCheckbox = document.querySelector<HTMLInputElement>("#refreshSourceCheckbox")!;
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
const pickEditorStartBtn = document.querySelector<HTMLButtonElement>("#pickEditorStartBtn")!;
const pickEditorEndBtn = document.querySelector<HTMLButtonElement>("#pickEditorEndBtn")!;
const clearEditorPinsBtn = document.querySelector<HTMLButtonElement>("#clearEditorPinsBtn")!;
const saveRegionBtn = document.querySelector<HTMLButtonElement>("#saveRegionBtn")!;
const editorSearchEnabled = document.querySelector<HTMLInputElement>("#editorSearchEnabled")!;
const editorSearchCountry = document.querySelector<HTMLInputElement>("#editorSearchCountry")!;
const editorSearchExpectedName = document.querySelector<HTMLInputElement>("#editorSearchExpectedName")!;
const editorSearchQuery = document.querySelector<HTMLInputElement>("#editorSearchQuery")!;
const editorSearchAddress = document.querySelector<HTMLInputElement>("#editorSearchAddress")!;
const closeRegionEditorBtn = document.querySelector<HTMLButtonElement>("#closeRegionEditorBtn")!;
const buildBtn = document.querySelector<HTMLButtonElement>("#buildBtn")!;
const buildPrerequisite = document.querySelector<HTMLDivElement>("#buildPrerequisite")!;
const routePrerequisite = document.querySelector<HTMLDivElement>("#routePrerequisite")!;
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
const searchPackVersion = document.querySelector<HTMLInputElement>("#searchPackVersion")!;
const searchLocalInput = document.querySelector<HTMLInputElement>("#searchLocalInput")!;
const searchLocalRelease = document.querySelector<HTMLInputElement>("#searchLocalRelease")!;
const searchImportManifest = document.querySelector<HTMLInputElement>("#searchImportManifest")!;
const buildSearchBtn = document.querySelector<HTMLButtonElement>("#buildSearchBtn")!;
const cancelSearchBtn = document.querySelector<HTMLButtonElement>("#cancelSearchBtn")!;
const importSearchBtn = document.querySelector<HTMLButtonElement>("#importSearchBtn")!;
const refreshSearchBtn = document.querySelector<HTMLButtonElement>("#refreshSearchBtn")!;
const searchProduceStatus = document.querySelector<HTMLDivElement>("#searchProduceStatus")!;
const searchBuildSelect = document.querySelector<HTMLSelectElement>("#searchBuildSelect")!;
const searchBuildSummary = document.querySelector<HTMLDivElement>("#searchBuildSummary")!;
const searchQuery = document.querySelector<HTMLInputElement>("#searchQuery")!;
const searchCategory = document.querySelector<HTMLInputElement>("#searchCategory")!;
const searchUseMapCenter = document.querySelector<HTMLInputElement>("#searchUseMapCenter")!;
const runSearchBtn = document.querySelector<HTMLButtonElement>("#runSearchBtn")!;
const clearSearchBtn = document.querySelector<HTMLButtonElement>("#clearSearchBtn")!;
const searchResultsSummary = document.querySelector<HTMLDivElement>("#searchResultsSummary")!;
const searchResults = document.querySelector<HTMLDivElement>("#searchResults")!;
const searchCompareA = document.querySelector<HTMLSelectElement>("#searchCompareA")!;
const searchCompareB = document.querySelector<HTMLSelectElement>("#searchCompareB")!;
const compareSearchBtn = document.querySelector<HTMLButtonElement>("#compareSearchBtn")!;
const searchCompareSummary = document.querySelector<HTMLPreElement>("#searchCompareSummary")!;
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
const locatePrevBtn = document.querySelector<HTMLButtonElement>("#locatePrevBtn")!;
const locateNextBtn = document.querySelector<HTMLButtonElement>("#locateNextBtn")!;
const locateCandidateSummary = document.querySelector<HTMLDivElement>("#locateCandidateSummary")!;
const locateCandidateDetails = document.querySelector<HTMLDivElement>("#locateCandidateDetails")!;
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
const refreshHandoffArtifactsBtn = document.querySelector<HTMLButtonElement>("#refreshHandoffArtifactsBtn")!;
const handoffArtifactSummary = document.querySelector<HTMLDivElement>("#handoffArtifactSummary")!;
const handoffArtifactList = document.querySelector<HTMLDivElement>("#handoffArtifactList")!;
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
const expansionPlayback = document.querySelector<HTMLDivElement>("#expansionPlayback")!;
const expansionProgress = document.querySelector<HTMLInputElement>("#expansionProgress")!;
const expansionProgressLabel = document.querySelector<HTMLSpanElement>("#expansionProgressLabel")!;
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
let searchArtifacts: SearchBuildArtifact[] = [];
let searchBuildPending = false;
let currentSearchResults: SearchResult[] = [];
let geofabrikCatalog: GeofabrikCatalogItem[] = [];
let catalogLoadError: string | null = null;
let catalogLoadPromise: Promise<void> | null = null;
let regionBrowserMode: "configured" | "catalog" = "configured";
let regionBrowserQuery = "";
let editorPreview: RegionPreview | null = null;
let editorExistingConfig: Record<string, unknown> | null = null;
let editorPickMode: "start" | "end" | null = null;
let editorStartMarker: Marker | null = null;
let editorEndMarker: Marker | null = null;
let activeRegion: RegionSummary | null = null;
let graphVisible = false;
let activeVisualBuild: VisualBuildArtifact | null = null;
let referenceLayerIds: string[] = [];
let handoffPickMode: "A" | "B" | null = null;
let editingHandoffId: string | null = null;
let handoffSnapA: HandoffSnap | null = null;
let handoffSnapB: HandoffSnap | null = null;
let handoffValidation: HandoffValidation | null = null;
let r2Credentials: R2CredentialStatus | null = null;
let remotePublication: R2RegionPublicationStatus | null = null;
let currentPublicationStatus: PublicationStatus | null = null;
let toolchainReady = false;
let latestBuildRunning = false;
let buildSubmitting = false;
let routeSubmitting = false;
let handoffMarkerA: Marker | null = null;
let handoffMarkerB: Marker | null = null;
let routePickMode: "start" | "end" | null = null;
let routeStartMarker: Marker | null = null;
let routeEndMarker: Marker | null = null;
let routeActualEndMarker: Marker | null = null;
let lastMapClick: { lat: number; lng: number } | null = null;
let currentExpansion: FeatureCollection | null = null;
let locateCandidates: LocateEdgeCandidate[] = [];
let locateCandidateIndex = 0;
const selected = new Set<string>(); // Validated, configured region IDs for building.
const pendingCatalogSelection = new Set<string>(); // Geofabrik IDs awaiting configuration.

type ToolId = "build" | "region" | "graph" | "border" | "f8" | "route" | "visual" | "search" | "compare" | "publish" | "toolchain";
type PrimaryToolId = Exclude<ToolId, "region" | "toolchain">;
const TOOL_STORAGE_KEY = "roadpilot.graph-studio.active-tool";
let activeTool: ToolId = "build";
let lastNonRegionTool: PrimaryToolId = "build";
function isToolId(value: string | null): value is ToolId {
  return ["build", "region", "graph", "border", "f8", "route", "visual", "search", "compare", "publish", "toolchain"].includes(value ?? "");
}
function isPrimaryTool(value: string | null): value is PrimaryToolId {
  return isToolId(value) && value !== "region" && value !== "toolchain";
}
function activateTool(tool: ToolId, remember = true): void {
  const contextual = tool === "region" || tool === "toolchain";
  if (!contextual) lastNonRegionTool = tool;
  activeTool = tool;
  const displayedTool = contextual ? lastNonRegionTool : tool;
  const dataGroup = displayedTool === "visual" || displayedTool === "search";
  const advancedGroup = displayedTool === "graph" || displayedTool === "border" || displayedTool === "compare";
  toolMenu.value = dataGroup ? "data" : advancedGroup ? "advanced" : displayedTool;
  dataWorkspaceTabs.hidden = contextual || !dataGroup;
  advancedToolSelector.hidden = contextual || !advancedGroup;
  dataVisualTab.setAttribute("aria-pressed", String(displayedTool === "visual"));
  dataSearchTab.setAttribute("aria-pressed", String(displayedTool === "search"));
  if (advancedGroup) advancedToolMenu.value = displayedTool;
  contextToolNotice.hidden = !contextual;
  contextToolTitle.textContent = tool === "region" ? "Region editor · opened from region tree" :
    tool === "toolchain" ? "Toolchain diagnostics · opened from header" : "";
  toolchainBadge.setAttribute("aria-expanded", String(tool === "toolchain"));
  openToolchainBtn.setAttribute("aria-expanded", String(tool === "toolchain"));
  toolchainBadge.classList.toggle("active", tool === "toolchain");
  for (const panel of toolPanels) panel.hidden = panel.dataset.tool !== tool;
  if (remember && !contextual) localStorage.setItem(TOOL_STORAGE_KEY, tool);
  if (remember && window.matchMedia("(max-width: 1100px)").matches) setCompactPane("tools");
}
const storedTool = localStorage.getItem(TOOL_STORAGE_KEY);
if (isPrimaryTool(storedTool)) activeTool = lastNonRegionTool = storedTool;
activateTool(activeTool, false);
toolMenu.addEventListener("change", () => {
  if (toolMenu.value === "data") {
    activateTool(lastNonRegionTool === "search" ? "search" : "visual");
  } else if (toolMenu.value === "advanced") {
    activateTool(["graph", "border", "compare"].includes(lastNonRegionTool)
      ? lastNonRegionTool : "graph");
  } else if (isPrimaryTool(toolMenu.value)) {
    activateTool(toolMenu.value);
  }
});
dataVisualTab.addEventListener("click", () => activateTool("visual"));
dataSearchTab.addEventListener("click", () => activateTool("search"));
advancedToolMenu.addEventListener("change", () => {
  if (isPrimaryTool(advancedToolMenu.value)) activateTool(advancedToolMenu.value);
});
contextBackBtn.addEventListener("click", () => {
  if (activeTool === "region") closeRegionEditor();
  else activateTool(lastNonRegionTool);
});
function toggleToolchainDetails(): void {
  if (activeTool === "toolchain") activateTool(lastNonRegionTool);
  else activateTool("toolchain");
}
toolchainBadge.addEventListener("click", toggleToolchainDetails);
openToolchainBtn.addEventListener("click", toggleToolchainDetails);

function bytes(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = value;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(i >= 3 ? 1 : 0)} ${units[i]}`;
}

type NativePrivateConnectionPoint = {
  sourceGraphId:number; receiverGraphIds:number[]; latitude:number; longitude:number; modes:string[];
};
type NativePrivatePairOverview = {
  pairId:string; fromVersion:string; toVersion:string;
  fromGraphFingerprint:string; toGraphFingerprint:string;
  status:"GRAPH_STUDIO_PRIVATE_READY"|"NATIVE_EVIDENCE_REQUIRED"|"READY_TO_VALIDATE_NATIVE_EVIDENCE"|"READY_TO_GENERATE_NATIVE_EVIDENCE";
  publication:string|null; sourceConnections:number; receiverIncomingRoads:number;
  sourcePhysicalRoadDirectionCompleteness:string; catalogPath:string|null;
  evidencePath:string|null; reason:string|null; samplePoints:NativePrivateConnectionPoint[];
  notForRoadPilotRuntime:true;
};
type F8JobStatus = {
  running:boolean; stage:string; lastError:string|null;
  lastResult:NativePrivatePairOverview|null;
};

type BorderSubTab = "manual" | "evidence";
const BORDER_TAB_KEY = "roadpilot.graph-studio.border.tab";
const borderTabs = {
  manual: document.querySelector<HTMLButtonElement>("#borderManualTab")!,
  evidence: document.querySelector<HTMLButtonElement>("#borderEvidenceTab")!,
};
const borderPanels = {
  manual: document.querySelector<HTMLDivElement>("#borderManualPanel")!,
  evidence: document.querySelector<HTMLDivElement>("#borderEvidencePanel")!,
};
function activateBorderTab(tab: BorderSubTab, remember = true): void {
  for (const key of ["manual", "evidence"] as const) {
    const chosen = key === tab;
    borderPanels[key].hidden = !chosen;
    borderTabs[key].classList.toggle("active", chosen);
    borderTabs[key].setAttribute("aria-selected", String(chosen));
    borderTabs[key].tabIndex = chosen ? 0 : -1;
  }
  if (remember) localStorage.setItem(BORDER_TAB_KEY, tab);
}
const savedBorderTab = localStorage.getItem(BORDER_TAB_KEY);
activateBorderTab(savedBorderTab === "evidence" ? "evidence" : "manual", false);
for (const tab of ["manual", "evidence"] as const) {
  borderTabs[tab].addEventListener("click", () => activateBorderTab(tab));
  borderTabs[tab].addEventListener("keydown", event => {
    const all: BorderSubTab[] = ["manual", "evidence"];
    const delta = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    const next = event.key === "Home" ? "manual" : event.key === "End" ? "evidence" :
      delta ? all[(all.indexOf(tab) + delta + all.length) % all.length] : null;
    if (!next) return;
    event.preventDefault(); activateBorderTab(next); borderTabs[next].focus();
  });
}

const f8RegionA = document.querySelector<HTMLSelectElement>("#f8RegionA")!;
const f8RegionB = document.querySelector<HTMLSelectElement>("#f8RegionB")!;
const f8RefreshBtn = document.querySelector<HTMLButtonElement>("#f8RefreshBtn")!;
const f8BuildCatalogBtn = document.querySelector<HTMLButtonElement>("#f8BuildCatalogBtn")!;
const f8CancelBtn = document.querySelector<HTMLButtonElement>("#f8CancelBtn")!;
const f8EvidenceDirectory = document.querySelector<HTMLInputElement>("#f8EvidenceDirectory")!;
const f8PairSummary = document.querySelector<HTMLDivElement>("#f8PairSummary")!;
const f8SampleConnections = document.querySelector<HTMLDivElement>("#f8SampleConnections")!;
const f8JobSummary = document.querySelector<HTMLDivElement>("#f8JobSummary")!;
let currentF8Pair: NativePrivatePairOverview | null = null;
let currentF8Job: F8JobStatus | null = null;
let f8PairGeneration = 0;
let f8SampleMarker: Marker | null = null;

function f8SelectedBuilds(): [BuildArtifact,BuildArtifact] | null {
  const a = artifacts.find(item => item.manifest_path === f8RegionA.value);
  const b = artifacts.find(item => item.manifest_path === f8RegionB.value);
  return a && b && a.region_id !== b.region_id ? [a,b] : null;
}
function renderF8BuildSelectors(): void {
  const previousA=f8RegionA.value, previousB=f8RegionB.value;
  for (const input of [f8RegionA, f8RegionB]) {
    const previous=input===f8RegionA ? previousA : previousB;
    input.replaceChildren(new Option(input===f8RegionA ? "Select original Graph A…" :
                                      "Select original Graph B…", ""));
    for (const item of artifacts) {
      input.add(new Option(item.region_id + " · " + item.version, item.manifest_path));
    }
    if ([...input.options].some(item=>item.value===previous)) input.value=previous;
  }
  if (!f8SelectedBuilds()) {
    // Retained builds may disappear after a refresh while a status call is
    // outstanding. Do not let that callback restore stale connections.
    ++f8PairGeneration;
    f8SampleMarker?.remove();
    f8SampleMarker=null;
    currentF8Pair=null;
    f8PairSummary.textContent="Select two different retained original regional graphs.";
    f8SampleConnections.replaceChildren();
  }
  updateF8Buttons();
}
function updateF8Buttons(): void {
  const pairValid=f8SelectedBuilds()!=null;
  const running=currentF8Job?.running === true;
  f8RegionA.disabled=running;
  f8RegionB.disabled=running;
  f8EvidenceDirectory.disabled=running;
  f8RefreshBtn.disabled=!pairValid || running;
  f8BuildCatalogBtn.disabled=!pairValid || running ||
    !["READY_TO_VALIDATE_NATIVE_EVIDENCE","READY_TO_GENERATE_NATIVE_EVIDENCE"].includes(currentF8Pair?.status ?? "");
  f8CancelBtn.disabled=!running;
}
function renderF8Overview(report:NativePrivatePairOverview):void {
  currentF8Pair=report;
  const complete=report.status==="GRAPH_STUDIO_PRIVATE_READY";
  f8PairSummary.className=complete?"kv":"empty";
  f8PairSummary.replaceChildren();
  const rows = [
    ["Pair",report.pairId],
    ["Original graph versions", report.fromVersion + " → " + report.toVersion],
    ["Native status",report.status.replaceAll("_"," ")],
    ["A final directed GraphIds",String(report.sourceConnections)],
    ["B matching directed roads",String(report.receiverIncomingRoads)],
    ["Global physical-road lineage", "NOT VERIFIED"],
    ["Android release", "NOT FOR ROADPILOT RUNTIME"],
    ["Private catalog",report.catalogPath || "Not generated"],
    ["Original evidence",report.evidencePath || "Unavailable"],
  ];
  for (const [name,value] of rows) {
    const label=document.createElement("dt");
    const content=document.createElement("dd");
    label.textContent=name;
    content.textContent=value;
    f8PairSummary.append(label,content);
  }
  if (report.reason) {
    const warning=document.createElement("p");
    warning.className="warn";
    warning.textContent=report.reason;
    f8PairSummary.appendChild(warning);
  }
  f8SampleConnections.replaceChildren();
  if(complete && report.samplePoints.length){
    const heading=document.createElement("h3");
    heading.textContent="Native directed matches at X (sample)";
    f8SampleConnections.appendChild(heading);
    for (const [index,point] of report.samplePoints.entries()) {
      const button=document.createElement("button");
      button.type="button";
      button.className="btn f8-native-sample";
      button.dataset.f8PrivateIndex=String(index);
      button.textContent="Graph A " + point.sourceGraphId + " → B " +
        point.receiverGraphIds.join(", ") + " · " + point.modes.join("/") + " · View X";
      f8SampleConnections.appendChild(button);
    }
  }
  updateF8Buttons();
}
async function refreshF8Pair():Promise<void> {
  const pair=f8SelectedBuilds();
  const generation=++f8PairGeneration;
  f8SampleMarker?.remove();
  f8SampleMarker=null;
  currentF8Pair=null;
  f8SampleConnections.replaceChildren();
  updateF8Buttons();
  if (!pair) {
    f8PairSummary.className="empty";
    f8PairSummary.textContent="Select two different original regional graph builds.";
    return;
  }
  f8PairSummary.className="empty";
  f8PairSummary.textContent="Checking native source and receiver graph fingerprints…";
  const [a,b]=pair;
  try {
    const data=await invoke<NativePrivatePairOverview>("f8_private_catalog_overview",{
      fromRegion:a.region_id,fromVersion:a.version,
      toRegion:b.region_id,toVersion:b.version,
      evidenceDirectory:f8EvidenceDirectory.value.trim()||null,
    });
    if (generation===f8PairGeneration) renderF8Overview(data);
  } catch(error){
    if (generation===f8PairGeneration){
      f8PairSummary.className="bad";
      f8PairSummary.textContent="Native pair could not be verified: "+String(error);
      updateF8Buttons();
    }
  }
}
function renderF8Job(status:F8JobStatus):void {
  const wasRunning=currentF8Job?.running===true;
  currentF8Job=status;
  f8JobSummary.className=status.lastError?"bad":"status-line";
  f8JobSummary.textContent=status.lastError ?
    "Private catalog validation failed: "+status.lastError : status.stage;
  updateF8Buttons();
  if (wasRunning && !status.running && f8SelectedBuilds()) void refreshF8Pair();
}
async function runPrivateF8Catalog():Promise<void>{
  const pair=f8SelectedBuilds();
  if (!pair || !["READY_TO_VALIDATE_NATIVE_EVIDENCE","READY_TO_GENERATE_NATIVE_EVIDENCE"].includes(currentF8Pair?.status ?? ""))return;
  const [a,b]=pair;
  try {
    await invoke("f8_start_workflow",{
      operation:"private-build",fromRegion:a.region_id,fromVersion:a.version,
      toRegion:b.region_id,toVersion:b.version,
      evidenceDirectory:f8EvidenceDirectory.value.trim()||null,
    });
    renderF8Job(await invoke<F8JobStatus>("f8_workflow_status"));
    appendLog("Private native A → X → B catalog requested: "+a.region_id+" → "+b.region_id);
  } catch(error) {
    f8JobSummary.className="bad";
    f8JobSummary.textContent="Cannot start private native catalog: "+String(error);
  }
}
f8RegionA.addEventListener("change",()=>void refreshF8Pair());
f8RegionB.addEventListener("change",()=>void refreshF8Pair());
f8EvidenceDirectory.addEventListener("change",()=>void refreshF8Pair());
f8RefreshBtn.addEventListener("click",()=>void refreshF8Pair());
f8BuildCatalogBtn.addEventListener("click",()=>void runPrivateF8Catalog());
f8CancelBtn.addEventListener("click",async()=>{
  try {
    await invoke("f8_cancel_workflow");
    appendLog("Private native catalog cancellation requested.");
  }catch(error){
    appendLog("Cannot cancel private native catalog: "+String(error));
  }
});
f8SampleConnections.addEventListener("click",event=>{
  const control=(event.target as HTMLElement).closest<HTMLButtonElement>("[data-f8-private-index]");
  if(!control || !currentF8Pair)return;
  const point=currentF8Pair.samplePoints[Number(control.dataset.f8PrivateIndex)];
  if(!point || !Number.isFinite(point.latitude) || !Number.isFinite(point.longitude))return;
  f8SampleMarker?.remove();
  f8SampleMarker=new Marker().setLngLat([point.longitude,point.latitude]).addTo(map);
  map.flyTo({center:[point.longitude,point.latitude],zoom:15});
  appendLog("Original native X "+point.latitude+", "+point.longitude+
    ": Graph A "+point.sourceGraphId+" → B "+point.receiverGraphIds.join(", "));
});

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
  if (publicationKind.value === "VISUAL") return "VISUAL";
  if (publicationKind.value === "SEARCH") return "SEARCH";
  return "ROUTING";
}

function publicationPrefix(): "routing" | "visual" | "search" {
  const kind = activePublicationKind();
  return kind === "VISUAL" ? "visual" : kind === "SEARCH" ? "search" : "routing";
}

function publicationTargets(): PublicationTarget[] {
  const kind = activePublicationKind();
  if (kind === "VISUAL") {
    return visualArtifacts.map(item => ({
      artifactKind: "VISUAL",
      region_id: item.region_id,
      version: item.version,
      sha256: item.sha256,
      manifest_path: item.manifest_path,
    }));
  }
  if (kind === "SEARCH") {
    return searchArtifacts.map(item => ({
      artifactKind: "SEARCH",
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
    ? `Choose ${kind === "VISUAL" ? "visual" : kind === "SEARCH" ? "search" : "routing"} build…`
    : `No retained ${kind === "VISUAL" ? "visual" : kind === "SEARCH" ? "search" : "routing"} builds`;
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
  center: [0, 25],
  zoom: 1.6,
});
map.addControl(new NavigationControl({ showCompass: true }), "bottom-right");

const LAYOUT_KEYS = {
  left: "roadpilot.graph-studio.left-pane",
  right: "roadpilot.graph-studio.right-pane",
  console: "roadpilot.graph-studio.console-height",
};

function readStoredSize(key: string, fallback: number): number {
  const value = Number(localStorage.getItem(key));
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function applyStoredLayout(): void {
  appRoot.style.setProperty("--left-pane", `${readStoredSize(LAYOUT_KEYS.left, 300)}px`);
  appRoot.style.setProperty("--right-pane", `${readStoredSize(LAYOUT_KEYS.right, 360)}px`);
  appRoot.style.setProperty("--console-height", `${readStoredSize(LAYOUT_KEYS.console, 196)}px`);
}

function numericCssVar(name: string, fallback: number): number {
  const value = Number.parseFloat(getComputedStyle(appRoot).getPropertyValue(name));
  return Number.isFinite(value) ? value : fallback;
}

function persistLayout(): void {
  localStorage.setItem(LAYOUT_KEYS.left, String(Math.round(numericCssVar("--left-pane", 300))));
  localStorage.setItem(LAYOUT_KEYS.right, String(Math.round(numericCssVar("--right-pane", 360))));
  localStorage.setItem(LAYOUT_KEYS.console, String(Math.round(numericCssVar("--console-height", 196))));
}

type WorkspacePane = "regions" | "map" | "tools";
const COMPACT_PANE_KEY = "roadpilot.graph-studio.compact-pane";
const CONSOLE_COLLAPSED_KEY = "roadpilot.graph-studio.console-collapsed";
let activeCompactPane: WorkspacePane = "map";
let consoleCollapsed = true;

function setCompactPane(pane: WorkspacePane, remember = true): void {
  activeCompactPane = pane;
  for (const [key, button] of Object.entries(workspaceButtons)) {
    const selected = key === pane;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-pressed", String(selected));
  }
  appRoot.dataset.workspacePane = pane;
  if (remember) localStorage.setItem(COMPACT_PANE_KEY, pane);
  map.resize();
}

function setConsoleCollapsed(collapsed: boolean, remember = true): void {
  consoleCollapsed = collapsed;
  appRoot.classList.toggle("console-collapsed", collapsed);
  consoleToggle.textContent = collapsed ? "Show log" : "Hide log";
  consoleToggle.setAttribute("aria-expanded", String(!collapsed));
  consoleSplitter.setAttribute("aria-disabled", String(collapsed));
  if (remember) localStorage.setItem(CONSOLE_COLLAPSED_KEY, String(collapsed));
  map.resize();
}

function reconcileDesktopPanes(): void {
  if (window.matchMedia("(max-width: 1100px)").matches) return;
  const workspace = document.querySelector<HTMLElement>(".workspace")!;
  const available = Math.max(0, workspace.clientWidth - 420 - 10);
  let left = numericCssVar("--left-pane", 300);
  let right = numericCssVar("--right-pane", 360);
  if (left + right > available) {
    const excess = left + right - available;
    const leftAllowance = Math.max(0, left - 220);
    const rightAllowance = Math.max(0, right - 280);
    const totalAllowance = leftAllowance + rightAllowance;
    if (totalAllowance > 0) {
      left -= Math.min(leftAllowance, excess * leftAllowance / totalAllowance);
      right -= Math.min(rightAllowance, excess * rightAllowance / totalAllowance);
    }
    if (left + right > available) {
      left = Math.max(220, available - right);
      right = Math.max(280, available - left);
    }
    appRoot.style.setProperty("--left-pane", `${Math.floor(left)}px`);
    appRoot.style.setProperty("--right-pane", `${Math.floor(right)}px`);
  }
}

function applyResponsiveWorkspace(): void {
  const compact = window.matchMedia("(max-width: 1100px)").matches;
  appRoot.classList.toggle("compact-workspace", compact);
  workspaceSwitcher.hidden = !compact;
  if (!compact) reconcileDesktopPanes();
  map.resize();
}

const storedCompactPane = localStorage.getItem(COMPACT_PANE_KEY);
activeCompactPane = storedCompactPane === "regions" || storedCompactPane === "tools" ? storedCompactPane : "map";
const storedConsoleCollapsed = localStorage.getItem(CONSOLE_COLLAPSED_KEY);
setCompactPane(activeCompactPane, false);
setConsoleCollapsed(storedConsoleCollapsed !== "false", false);
for (const [pane, button] of Object.entries(workspaceButtons)) {
  button.addEventListener("click", () => setCompactPane(pane as WorkspacePane));
}
consoleToggle.addEventListener("click", () => setConsoleCollapsed(!consoleCollapsed));
window.addEventListener("resize", applyResponsiveWorkspace);

function installVerticalSplitter(splitter: HTMLElement, side: "left" | "right"): void {
  splitter.addEventListener("pointerdown", event => {
    if (window.matchMedia("(max-width: 1100px)").matches) return;
    event.preventDefault();
    splitter.setPointerCapture(event.pointerId);
    document.body.classList.add("pane-resizing");
    const workspace = document.querySelector<HTMLElement>(".workspace")!;

    const move = (moveEvent: PointerEvent) => {
      const rect = workspace.getBoundingClientRect();
      const leftWidth = numericCssVar("--left-pane", 300);
      const rightWidth = numericCssVar("--right-pane", 360);
      const centerMinimum = 420;
      const splitterSpace = 10;

      if (side === "left") {
        const maximum = Math.max(220, rect.width - rightWidth - centerMinimum - splitterSpace);
        const next = Math.min(maximum, Math.max(220, moveEvent.clientX - rect.left));
        appRoot.style.setProperty("--left-pane", `${next}px`);
      } else {
        const maximum = Math.max(280, rect.width - leftWidth - centerMinimum - splitterSpace);
        const next = Math.min(maximum, Math.max(280, rect.right - moveEvent.clientX));
        appRoot.style.setProperty("--right-pane", `${next}px`);
      }
      map.resize();
    };

    const end = () => {
      document.body.classList.remove("pane-resizing");
      splitter.removeEventListener("pointermove", move);
      splitter.removeEventListener("pointerup", end);
      splitter.removeEventListener("pointercancel", end);
      persistLayout();
      map.resize();
    };

    splitter.addEventListener("pointermove", move);
    splitter.addEventListener("pointerup", end);
    splitter.addEventListener("pointercancel", end);
  });
}

function installConsoleSplitter(): void {
  consoleSplitter.addEventListener("pointerdown", event => {
    if (consoleCollapsed) return;
    event.preventDefault();
    consoleSplitter.setPointerCapture(event.pointerId);
    document.body.classList.add("pane-resizing");

    const move = (moveEvent: PointerEvent) => {
      const rect = appRoot.getBoundingClientRect();
      const topbar = 52;
      const splitterSize = 5;
      const mainMinimum = 280;
      const maximum = Math.max(140, rect.height - topbar - splitterSize - mainMinimum);
      const next = Math.min(maximum, Math.max(120, rect.bottom - moveEvent.clientY));
      appRoot.style.setProperty("--console-height", `${next}px`);
      map.resize();
    };

    const end = () => {
      document.body.classList.remove("pane-resizing");
      consoleSplitter.removeEventListener("pointermove", move);
      consoleSplitter.removeEventListener("pointerup", end);
      consoleSplitter.removeEventListener("pointercancel", end);
      persistLayout();
      map.resize();
    };

    consoleSplitter.addEventListener("pointermove", move);
    consoleSplitter.addEventListener("pointerup", end);
    consoleSplitter.addEventListener("pointercancel", end);
  });
}

applyStoredLayout();
installVerticalSplitter(leftSplitter, "left");
installVerticalSplitter(rightSplitter, "right");
installConsoleSplitter();
applyResponsiveWorkspace();

leftSplitter.addEventListener("dblclick", () => {
  appRoot.style.setProperty("--left-pane", "300px");
  persistLayout();
  map.resize();
});
rightSplitter.addEventListener("dblclick", () => {
  appRoot.style.setProperty("--right-pane", "360px");
  persistLayout();
  map.resize();
});
consoleSplitter.addEventListener("dblclick", () => {
  if (consoleCollapsed) return;
  appRoot.style.setProperty("--console-height", "196px");
  persistLayout();
  map.resize();
});

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

const mapLayerPreset = document.querySelector<HTMLSelectElement>("#mapLayerPreset")!;
const clearToolOverlaysBtn = document.querySelector<HTMLButtonElement>("#clearToolOverlaysBtn")!;
const MAP_PRESET_KEY = "roadpilot.graph-studio.map-preset";
const MAP_LAYER_KEY = "roadpilot.graph-studio.map-layer-choices";
const layerKeys = ["offlineVisual", "onlineReference", "graphEdges", "graphNodes", "shortcuts",
  "restrictions", "borderBuffer", "graphA", "graphB", "route", "expansion", "handoffs"] as const;
type LayerKey = typeof layerKeys[number];
const mapPresets: Record<Exclude<string, "custom">, ReadonlySet<LayerKey>> = {
  map: new Set<LayerKey>(["offlineVisual", "onlineReference", "graphEdges", "graphA", "graphB", "route"]),
  routing: new Set<LayerKey>(["offlineVisual", "onlineReference", "graphEdges", "graphNodes", "shortcuts", "restrictions", "route", "expansion"]),
  borders: new Set<LayerKey>(["offlineVisual", "onlineReference", "graphA", "graphB", "handoffs", "borderBuffer"]),
  all: new Set<LayerKey>(layerKeys),
};
function applyLayerSelection(chosen: ReadonlySet<LayerKey>): void {
  for (const key of layerKeys) {
    const input = mapLayerToggles.querySelector<HTMLInputElement>(`input[data-layer-toggle="${key}"]`)!;
    input.checked = chosen.has(key);
  }
  applyMapLayerToggles();
}
function persistLayerSelection(): void {
  const saved: Record<string, boolean> = {};
  for (const key of layerKeys) saved[key] = layerToggleChecked(key);
  localStorage.setItem(MAP_LAYER_KEY, JSON.stringify(saved));
  localStorage.setItem(MAP_PRESET_KEY, mapLayerPreset.value);
}
function selectMapLayerPreset(preset: string, remember = true): void {
  if (!Object.prototype.hasOwnProperty.call(mapPresets, preset)) return;
  mapLayerPreset.value = preset;
  applyLayerSelection(mapPresets[preset]);
  if (remember) persistLayerSelection();
}
function initializeMapLayerPreset(): void {
  const stored = localStorage.getItem(MAP_PRESET_KEY);
  if (stored && Object.prototype.hasOwnProperty.call(mapPresets, stored)) {
    selectMapLayerPreset(stored, false);
    return;
  }
  if (stored === "custom") {
    try {
      const state: unknown = JSON.parse(localStorage.getItem(MAP_LAYER_KEY) || "null");
      if (state && typeof state === "object" && !Array.isArray(state) &&
        layerKeys.every(key => typeof (state as Record<string, unknown>)[key] === "boolean")) {
        mapLayerPreset.value = "custom";
        applyLayerSelection(new Set(layerKeys.filter(key => (state as Record<string, boolean>)[key])));
        return;
      }
    } catch { /* corrupt saved state: fall back to the map preset */ }
  }
  selectMapLayerPreset("map", false);
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
  input.addEventListener("change", () => {
    mapLayerPreset.value = "custom";
    applyMapLayerToggles();
    persistLayerSelection();
  });
});
mapLayerPreset.addEventListener("change", () => selectMapLayerPreset(mapLayerPreset.value));
initializeMapLayerPreset();

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

function removeBorderPairLayers(): void {
  removeHandoffArtifactOverlay();
  for (const id of [borderLayerA, borderLayerB]) if (map.getLayer(id)) map.removeLayer(id);
  for (const id of [borderSourceA, borderSourceB]) if (map.getSource(id)) map.removeSource(id);
  exportBorderDiagnosticsBtn.disabled = true;
  borderReportSummary.className = "empty";
  borderReportSummary.textContent = "No diagnostics report exported.";
}

// Used by the retained-build comparison tool, not obsolete border overlap.
function edgeOsmId(feature: { properties?: Record<string, unknown> | null }): string | null {
  const value = feature.properties?.osm_id;
  if (value == null || value === "") return null;
  return String(value);
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
  refreshHandoffArtifactsBtn.disabled = false;
  exportBorderDiagnosticsBtn.disabled = false;
  applyMapLayerToggles();
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
  const options = uniqueBuiltRegions().map(id => `<option value="${id}">${id}</option>`).join("");
  borderRegionA.innerHTML = `<option value="">Choose A…</option>${options}`;
  borderRegionB.innerHTML = `<option value="">Choose B…</option>${options}`;
  /* removed old connector matrix selector */
  if ([...borderRegionA.options].some(option => option.value === currentA)) borderRegionA.value = currentA;
  if ([...borderRegionB.options].some(option => option.value === currentB)) borderRegionB.value = currentB;
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
        activateBorderTab("manual");
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
        No historical connectivity or manual handoff records found for this pair. Native F8 connectivity is not yet available.
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

const routeSourceId = "roadpilot-route";
const routeLayerId = "roadpilot-route-line";
const expansionSourceId = "roadpilot-expansion";
const expansionLayerId = "roadpilot-expansion-line";
const locateEdgeSourceId = "roadpilot-locate-edge";
const locateEdgeLayerId = "roadpilot-locate-edge-line";

function removeRouteLayers(): void {
  routeActualEndMarker?.remove();
  routeActualEndMarker = null;
  if (map.getLayer(expansionLayerId)) map.removeLayer(expansionLayerId);
  if (map.getSource(expansionSourceId)) map.removeSource(expansionSourceId);
  if (map.getLayer(routeLayerId)) map.removeLayer(routeLayerId);
  if (map.getSource(routeSourceId)) map.removeSource(routeSourceId);
  currentExpansion = null;
  expansionPlayback.hidden = true;
  expansionProgress.value = "1000";
  expansionProgressLabel.textContent = "0 / 0 edges";
}

function removeLocateEdgeOverlay(): void {
  if (map.getLayer(locateEdgeLayerId)) map.removeLayer(locateEdgeLayerId);
  if (map.getSource(locateEdgeSourceId)) map.removeSource(locateEdgeSourceId);
}

function decodePolyline6(encoded: string): number[][] {
  let index = 0;
  let lat = 0;
  let lng = 0;
  const coordinates: number[][] = [];
  const read = (): number => {
    let result = 0;
    let shift = 0;
    let byte = 0;
    do {
      if (index >= encoded.length) throw new Error("Truncated polyline6 shape.");
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    return (result & 1) ? ~(result >> 1) : (result >> 1);
  };
  while (index < encoded.length) {
    lat += read();
    lng += read();
    coordinates.push([lng * 1e-6, lat * 1e-6]);
  }
  return coordinates;
}

function expansionVisibleCount(): number {
  const total = currentExpansion?.features.length ?? 0;
  if (!total) return 0;
  const progress = Number(expansionProgress.value) / 1000;
  return Math.min(total, Math.floor(progress * Math.max(0, total - 1)) + 1);
}

function updateExpansionPlayback(): void {
  const total = currentExpansion?.features.length ?? 0;
  if (!total || !map.getLayer(expansionLayerId)) {
    expansionProgressLabel.textContent = "0 / 0 edges";
    return;
  }
  const progress = Number(expansionProgress.value) / 1000;
  map.setFilter(expansionLayerId, ["<=", ["get", "_rp_progress"], progress]);
  expansionProgressLabel.textContent = `${expansionVisibleCount().toLocaleString()} / ${total.toLocaleString()} edges`;
}

function showRouteGeometry(geometry: Geometry, requestedEnd?: { lat: number; lng: number }): void {
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
    if (requestedEnd) {
      lngs.push(requestedEnd.lng);
      lats.push(requestedEnd.lat);
    }
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
  const total = expansion.features.length;
  const denom = Math.max(1, total - 1);
  currentExpansion = {
    type: "FeatureCollection",
    features: expansion.features.map((feature, index) => ({
      ...feature,
      properties: {
        ...(feature.properties ?? {}),
        _rp_index: index,
        _rp_progress: index / denom,
      },
    })),
  };
  map.addSource(expansionSourceId, { type: "geojson", data: currentExpansion });
  map.addLayer({
    id: expansionLayerId,
    type: "line",
    source: expansionSourceId,
    paint: {
      "line-color": [
        "interpolate", ["linear"], ["get", "_rp_progress"],
        0, "#9b4dca",
        0.5, "#d68c45",
        1, "#f1c453",
      ],
      "line-width": ["interpolate", ["linear"], ["zoom"], 6, 1.2, 14, 2.4],
      "line-opacity": 0.62,
    },
  }, routeLayerId);
  expansionPlayback.hidden = total === 0;
  expansionProgress.value = "1000";
  updateExpansionPlayback();
  applyMapLayerToggles();
}


function candidateWayId(edge: LocateEdgeCandidate): string {
  return String(edge.edge_info?.way_id ?? "—");
}

function activeAccess(edge: LocateEdgeCandidate): string[] {
  const access = edge.edge?.access;
  if (!access) return [];
  return Object.entries(access).filter(([, allowed]) => allowed).map(([mode]) => mode);
}

function activeRestrictions(value: Record<string, boolean> | undefined): string[] {
  if (!value) return [];
  return Object.entries(value).filter(([, enabled]) => enabled).map(([name]) => name);
}

function edgeIdLabel(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (typeof value === "object") {
    const object = value as Record<string, unknown>;
    return String(object.value ?? object.id ?? JSON.stringify(value));
  }
  return String(value);
}

function showLocateCandidate(index: number): void {
  if (!locateCandidates.length) {
    locateCandidateIndex = 0;
    locateCandidateSummary.className = "empty";
    locateCandidateSummary.textContent = "No directed-edge candidates.";
    locateCandidateDetails.innerHTML = "";
    locatePrevBtn.disabled = true;
    locateNextBtn.disabled = true;
    removeLocateEdgeOverlay();
    return;
  }
  locateCandidateIndex = Math.max(0, Math.min(index, locateCandidates.length - 1));
  const edge = locateCandidates[locateCandidateIndex];
  const names = edge.edge_info?.names?.join(" / ") || "unnamed road";
  const access = activeAccess(edge);
  const startRestrictions = activeRestrictions(edge.edge?.start_restriction);
  const endRestrictions = activeRestrictions(edge.edge?.end_restriction);
  locateCandidateSummary.className = "ok";
  locateCandidateSummary.textContent =
    `Directed edge ${locateCandidateIndex + 1} of ${locateCandidates.length} • ${names}`;
  locateCandidateDetails.innerHTML = `
    <dt>OSM way</dt><dd>${escapeHtml(candidateWayId(edge))}</dd>
    <dt>Graph edge</dt><dd>${escapeHtml(edgeIdLabel(edge.edge_id))}</dd>
    <dt>Snap distance</dt><dd>${edge.distance == null ? "—" : Number(edge.distance).toFixed(1) + " m"}</dd>
    <dt>Percent along</dt><dd>${edge.percent_along == null ? "—" : (Number(edge.percent_along) * 100).toFixed(1) + "%"}</dd>
    <dt>Heading</dt><dd>${edge.heading == null ? "—" : Number(edge.heading).toFixed(1) + "°"}</dd>
    <dt>Access</dt><dd>${escapeHtml(access.length ? access.join(", ") : "none reported")}</dd>
    <dt>Start restrictions</dt><dd>${escapeHtml(startRestrictions.length ? startRestrictions.join(", ") : "none")}</dd>
    <dt>End restrictions</dt><dd>${escapeHtml(endRestrictions.length ? endRestrictions.join(", ") : "none")}</dd>
  `;
  locatePrevBtn.disabled = locateCandidateIndex === 0;
  locateNextBtn.disabled = locateCandidateIndex >= locateCandidates.length - 1;
  featureJson.textContent = JSON.stringify(edge, null, 2);

  removeLocateEdgeOverlay();
  const shape = edge.edge_info?.shape;
  if (shape) {
    try {
      const coordinates = decodePolyline6(shape);
      if (coordinates.length >= 2) {
        map.addSource(locateEdgeSourceId, {
          type: "geojson",
          data: {
            type: "Feature",
            properties: {},
            geometry: { type: "LineString", coordinates },
          },
        });
        map.addLayer({
          id: locateEdgeLayerId,
          type: "line",
          source: locateEdgeSourceId,
          paint: {
            "line-color": "#ff3b30",
            "line-width": ["interpolate", ["linear"], ["zoom"], 6, 4, 14, 8],
            "line-opacity": 0.95,
          },
        });
      }
    } catch (error) {
      appendLog(`Could not decode located edge shape: ${String(error)}`);
    }
  }
  applyMapLayerToggles();
}

async function inspectEdgesAt(lat: number, lng: number): Promise<void> {
  if (!activeRegion) return;
  locateCandidateSummary.className = "empty";
  locateCandidateSummary.textContent = "Running verbose Valhalla locate against the exact selected graph…";
  locateCandidateDetails.innerHTML = "";
  locatePrevBtn.disabled = true;
  locateNextBtn.disabled = true;
  try {
    const result = await invoke<LocateResult>("inspect_locate", {
      regionId: activeRegion.id,
      lat,
      lng,
    });
    const edges = Array.isArray(result) && result.length && Array.isArray(result[0]?.edges)
      ? result[0].edges ?? []
      : [];
    locateCandidates = edges.slice(0, 12);
    showLocateCandidate(0);
    if (!locateCandidates.length) {
      featureJson.textContent = JSON.stringify(result, null, 2);
    }
  } catch (error) {
    locateCandidates = [];
    removeLocateEdgeOverlay();
    locateCandidateSummary.className = "bad";
    locateCandidateSummary.textContent = `Locate failed: ${String(error)}`;
    featureJson.textContent = `Locate failed: ${String(error)}`;
  }
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
  updateRouteButtonState();
}

function renderRouteResult(result: RoutePlanResult, expansion?: ExpansionResult): void {
  const trip = result.response.trip;
  const summary = trip?.summary;
  routeSummary.className = "kv";
  const arrival = result.arrival;
  const arrivalLabel = arrival.destinationReached
    ? "Destination reached"
    : `INCOMPLETE — ${Math.round(arrival.endOffsetMeters).toLocaleString()} m from destination`;
  routeSummary.innerHTML = `
    <dt>Graph</dt><dd>${activeRegion?.id ?? "—"}</dd>
    <dt>Costing</dt><dd>${routeCosting.value}</dd>
    <dt>Distance</dt><dd>${summary?.length == null ? "—" : summary.length.toFixed(2) + " km"}</dd>
    <dt>Duration</dt><dd>${formatDuration(summary?.time)}</dd>
    <dt>Valhalla time</dt><dd>${result.elapsedMs} ms</dd>
    <dt>Arrival</dt><dd class="${arrival.destinationReached ? "" : "bad"}">${arrivalLabel}</dd>
    <dt>Start deviation</dt><dd>${arrival.startOffsetMeters.toFixed(1)} m</dd>
    <dt>Destination deviation</dt><dd>${arrival.endOffsetMeters.toFixed(1)} m</dd>
    <dt>Actual route end</dt><dd>${arrival.actualEnd.lat.toFixed(6)}, ${arrival.actualEnd.lng.toFixed(6)}</dd>
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
    showRouteGeometry(result.geometry, { lat: payload.endLat, lng: payload.endLng });
    // Successful Valhalla status does not necessarily mean the route arrived.
    setRoutePoint("start", payload.startLat, payload.startLng);
    setRoutePoint("end", payload.endLat, payload.endLng);
    if (!result.arrival.destinationReached) {
      routeActualEndMarker = new Marker({ color: "#e69b28" })
        .setLngLat([result.arrival.actualEnd.lng, result.arrival.actualEnd.lat])
        .addTo(map);
      appendLog(
        `Incomplete ${payload.regionId} route: ${result.arrival.endOffsetMeters.toFixed(1)} m from destination; ` +
        `actual end ${result.arrival.actualEnd.lat.toFixed(6)},${result.arrival.actualEnd.lng.toFixed(6)}`,
      );
    }
    let expansion: ExpansionResult | undefined;
    let expansionError: string | undefined;
    if (routeExpansionToggle.checked) {
      try {
        expansion = await invoke<ExpansionResult>("route_expansion", payload);
        showExpansion(expansion.geojson);
      } catch (error) {
        // Optional expansion is diagnostic only: a failed expansion must not
        // replace a successfully calculated route with "Route failed".
        expansionError = String(error);
        appendLog(`Valhalla expansion failed for ${payload.regionId}: ${expansionError}`);
      }
    }
    renderRouteResult(result, expansion);
    if (expansionError) {
      const title = document.createElement("dt");
      title.textContent = "Expansion";
      const message = document.createElement("dd");
      message.textContent = `Unavailable: ${expansionError}`;
      routeSummary.append(title, message);
    }
  } catch (error) {
    routeSummary.className = "bad";
    routeSummary.textContent = `Route failed for ${activeRegion?.id ?? "unknown region"}: ${String(error)}`;
    appendLog(`Valhalla route failed: ${String(error)}`);
  } finally {
    routeSubmitting = false;
    updateRouteButtonState();
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
  // A native X marker is meaningful only for the map region where it was shown.
  f8SampleMarker?.remove();
  f8SampleMarker=null;
  activeRegion = region;
  activeRegionBadge.textContent = region.name;
  fitBtn.disabled = !region.coverage;
  graphLayerBtn.disabled = false;
  editRegionBtn.disabled = false;
  locateBtn.disabled = true;
  locateCandidates = [];
  locateCandidateIndex = 0;
  locatePrevBtn.disabled = true;
  locateNextBtn.disabled = true;
  locateCandidateSummary.className = "empty";
  locateCandidateSummary.textContent = "Right-click the map to inspect directed edges from the exact selected graph.";
  locateCandidateDetails.innerHTML = "";
  featureJson.textContent = "No graph feature selected.";
  inspectorSummary.textContent = `${region.id} • ${region.border_buffer_km} km border buffer • Valhalla ${region.expected_valhalla_version}`;
  removeGraphLayer();
  removeLocateEdgeOverlay();
  removeRouteLayers();
  routeStartMarker?.remove();
  routeEndMarker?.remove();
  routeStartMarker = null;
  routeEndMarker = null;
  fitActiveRegion();
  renderRegions();
  renderVisualBuildSelectors();
  updateRouteButtonState();
}

function normalizedRegionSearchText(value: string): string {
  return value.trim().toLocaleLowerCase();
}

function regionIsBuilt(regionId: string): boolean {
  return artifacts.some(artifact => artifact.region_id === regionId);
}

function configuredRegionForCatalog(item: GeofabrikCatalogItem): RegionSummary | null {
  return regions.find(region => region.primary_geofabrik_id === item.id) ?? null;
}

function catalogContinent(item: GeofabrikCatalogItem): string {
  try {
    const path = new URL(item.pbfUrl).pathname.split("/").filter(Boolean);
    const root = path[0] ?? "other";
    const labels: Record<string, string> = {
      "africa": "Africa",
      "asia": "Asia",
      "australia-oceania": "Australia / Oceania",
      "central-america": "Central America",
      "europe": "Europe",
      "north-america": "North America",
      "south-america": "South America",
    };
    return labels[root] ?? "Other";
  } catch {
    return "Other";
  }
}

function regionMatchesQuery(name: string, id: string, country = ""): boolean {
  if (!regionBrowserQuery) return true;
  const haystack = normalizedRegionSearchText(`${name} ${id} ${country}`);
  return haystack.includes(regionBrowserQuery);
}

function makeStatusBadge(text: "AVAILABLE" | "CONFIGURED" | "BUILT"): HTMLSpanElement {
  const badge = document.createElement("span");
  badge.className = `region-status ${text.toLocaleLowerCase()}`;
  badge.textContent = text;
  return badge;
}

function updateBuildButtonState(): void {
  const versionValid = /^\d{4}\.\d{2}\.\d{2}-[A-Za-z0-9._-]+$/.test(packageVersionInput.value.trim());
  const selectedAny = selected.size > 0 || pendingCatalogSelection.size > 0;
  const reason = !toolchainReady ? "Toolchain is not ready." :
    latestBuildRunning || buildSubmitting ? "A regional build is already running." :
    !selectedAny ? "Choose at least one region in the left tree." :
    !versionValid ? "Enter a package version like 2026.10.16-1." : "Ready to build the selected regions.";
  buildBtn.disabled = !toolchainReady || latestBuildRunning || buildSubmitting || !selectedAny || !versionValid;
  buildPrerequisite.textContent = reason;
}

function updateRouteButtonState(): void {
  const selectedGraph = activeRegion && artifacts.some(item => item.region_id === activeRegion!.id);
  const fields: Array<[HTMLInputElement, number]> = [
    [routeStartLat, 90], [routeStartLng, 180], [routeEndLat, 90], [routeEndLng, 180],
  ];
  const coordinatesValid = fields.every(([field, limit]) =>
    field.value.trim() !== "" && Number.isFinite(Number(field.value)) && Math.abs(Number(field.value)) <= limit);
  const reason = !activeRegion ? "Select a region in the left tree." :
    !selectedGraph ? `Build ${activeRegion.id} first to enable routing.` :
    !coordinatesValid ? `Enter valid start and destination coordinates for ${activeRegion.id}.` :
    `Ready: ${activeRegion.id} · ${artifacts.find(item => item.region_id === activeRegion?.id)?.version ?? "retained build"}.`;
  runRouteBtn.disabled = routeSubmitting || !selectedGraph || !coordinatesValid;
  routePrerequisite.textContent = reason;
}

function updateRegionSelectionSummary(): void {
  const ready = selected.size;
  const toConfigure = pendingCatalogSelection.size;
  const status = `${ready} ready to build · ${toConfigure} awaiting setup`;
  buildSelectionSummary.textContent = ready || toConfigure ? status : "No regions selected.";
  updateBuildButtonState();
  configureQueuedBtn.disabled = toConfigure === 0;
  configureQueuedBtn.textContent = toConfigure
    ? `Configure queued (${toConfigure})` : "Configure queued regions";
  if (regionBrowserMode === "catalog" && geofabrikCatalog.length) {
    const count = geofabrikCatalog.filter(item =>
      regionMatchesQuery(item.name, item.id, item.countryName ?? "")
    ).length;
    regionBrowserSummary.textContent =
      `${count}/${geofabrikCatalog.length} regions · ${status}`;
  } else if (regionBrowserMode === "configured") {
    const count = regions.filter(item =>
      regionMatchesQuery(item.name, item.id, item.primary_geofabrik_id ?? "")
    ).length;
    regionBrowserSummary.textContent =
      `${count}/${regions.length} configured · ${status}`;
  }
}

async function configureNextQueuedRegion(): Promise<void> {
  const nextId = pendingCatalogSelection.values().next().value as string | undefined;
  if (!nextId) return;
  const item = geofabrikCatalog.find(region => region.id === nextId);
  if (!item) {
    appendLog(`Queued Geofabrik region is missing from the catalog: ${nextId}`);
    return;
  }
  await selectCatalogRegion(item);
  regionPreviewSummary.insertAdjacentHTML("afterbegin",
    '<span class="warn">Queued for setup. A real road-crossing validation route is required before building.</span><br/>');
}

function makeConfiguredRegionRow(region: RegionSummary): HTMLElement {
  const row = document.createElement("div");
  row.className = "region-row" + (activeRegion?.id === region.id ? " active" : "");

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = selected.has(region.id);
  checkbox.title = "Include in build queue";
  checkbox.addEventListener("change", () => {
    if (checkbox.checked) selected.add(region.id);
    else selected.delete(region.id);
    updateRegionSelectionSummary();
  });

  const label = document.createElement("button");
  label.type = "button";
  label.className = "region-label-button";
  const titleLine = document.createElement("span");
  titleLine.className = "region-title-line";
  const name = document.createElement("span");
  name.className = "region-name";
  name.textContent = region.name;
  titleLine.append(name, makeStatusBadge(regionIsBuilt(region.id) ? "BUILT" : "CONFIGURED"));
  const meta = document.createElement("span");
  meta.className = "region-meta";
  meta.textContent = `${region.border_buffer_km} km buffer • ${region.source_ids.length} sources`;
  label.append(titleLine, meta);
  label.addEventListener("click", () => setActiveRegion(region));

  const focus = document.createElement("button");
  focus.type = "button";
  focus.className = "region-focus";
  focus.title = "Inspect region";
  focus.textContent = "›";
  focus.addEventListener("click", () => setActiveRegion(region));

  row.append(checkbox, label, focus);
  return row;
}

async function selectCatalogRegion(item: GeofabrikCatalogItem): Promise<void> {
  const configured = configuredRegionForCatalog(item);
  if (configured) {
    setActiveRegion(configured);
    return;
  }

  if (item.bounds) {
    map.fitBounds(
      [[item.bounds.minLng, item.bounds.minLat], [item.bounds.maxLng, item.bounds.maxLat]],
      { padding: 44, duration: 350 },
    );
  }
  resetRegionEditor();
  openRegionEditor();
  if (!geofabrikCatalog.length) await loadGeofabrikCatalog(false);
  editorGeofabrik.value = item.id;
  editorName.value = item.name;
  editorRoadpilotId.value = item.id.replaceAll("/", "-");
  await previewEditorRegion(false);
}

function makeCatalogRegionRow(item: GeofabrikCatalogItem): HTMLElement {
  const configured = configuredRegionForCatalog(item);
  const row = document.createElement("div");
  const isChecked = configured
    ? selected.has(configured.id) : pendingCatalogSelection.has(item.id);
  row.className = "catalog-region-row" + (isChecked ? " selected" : "");
  row.title = configured ? "Select validated region for building" : "Queue this region for setup";

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.className = "catalog-region-checkbox";
  checkbox.checked = isChecked;
  checkbox.title = configured ? "Include configured region in build" : "Select for setup before building";
  checkbox.setAttribute("aria-label",
    configured ? `Build ${item.name}` : `Queue ${item.name} for setup`);
  checkbox.addEventListener("change", () => {
    if (configured) {
      if (checkbox.checked) selected.add(configured.id);
      else selected.delete(configured.id);
    } else {
      if (checkbox.checked) pendingCatalogSelection.add(item.id);
      else pendingCatalogSelection.delete(item.id);
    }
    row.classList.toggle("selected", checkbox.checked);
    updateRegionSelectionSummary();
  });

  const text = document.createElement("span");
  text.className = "catalog-region-copy";
  const titleLine = document.createElement("span");
  titleLine.className = "region-title-line";
  const name = document.createElement("span");
  name.className = "region-name";
  name.textContent = item.name;
  const status = configured
    ? (regionIsBuilt(configured.id) ? "BUILT" : "CONFIGURED")
    : "AVAILABLE";
  titleLine.append(name, makeStatusBadge(status));
  const meta = document.createElement("span");
  meta.className = "region-meta";
  meta.textContent = item.id;
  text.append(titleLine, meta);

  const arrow = document.createElement("span");
  arrow.className = "region-focus";
  arrow.textContent = "›";
  const open = document.createElement("button");
  open.type = "button";
  open.className = "catalog-region-open";
  open.append(text, arrow);
  open.title = configured ? "Inspect configured region" : "Preview and configure region";
  open.addEventListener("click", () => {
    selectCatalogRegion(item).catch(error => appendLog(`Could not preview ${item.name}: ${String(error)}`));
  });
  row.append(checkbox, open);
  return row;
}

function renderConfiguredRegions(): void {
  const filtered = regions.filter(region =>
    regionMatchesQuery(region.name, region.id, region.primary_geofabrik_id ?? "")
  );
  regionBrowserSummary.textContent =
    `${filtered.length}/${regions.length} configured · ${selected.size} ready · ${pendingCatalogSelection.size} to set up`;

  if (!filtered.length) {
    regionHost.innerHTML = '<div class="region-empty">No configured regions match this search.</div>';
    return;
  }
  for (const region of filtered) regionHost.appendChild(makeConfiguredRegionRow(region));
}

function renderCatalogRegions(): void {
  if (!geofabrikCatalog.length) {
    regionHost.innerHTML = "";
    regionBrowserSummary.textContent = catalogLoadError
      ? "Geofabrik catalog unavailable"
      : catalogLoadPromise ? "Loading Geofabrik catalog…" : "Catalog has no regions";
    const message = document.createElement("div");
    message.className = "region-empty";
    message.textContent = catalogLoadError
      ? `Unable to load region catalog: ${catalogLoadError}`
      : catalogLoadPromise ? "Loading catalog from Geofabrik…" : "No catalog regions were returned.";
    regionHost.appendChild(message);
    if (!catalogLoadPromise) {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "btn";
      retry.textContent = "Retry catalog";
      retry.addEventListener("click", () => {
        loadGeofabrikCatalog(true).catch(error => appendLog(`Catalog retry failed: ${String(error)}`));
      });
      regionHost.appendChild(retry);
    }
    return;
  }

  const filtered = geofabrikCatalog.filter(item =>
    regionMatchesQuery(item.name, item.id, item.countryName ?? "")
  );
  regionBrowserSummary.textContent =
    `${filtered.length}/${geofabrikCatalog.length} regions · ${selected.size} ready · ${pendingCatalogSelection.size} to set up`;

  if (!filtered.length) {
    regionHost.innerHTML = '<div class="region-empty">No catalog regions match this search.</div>';
    return;
  }

  const continents = new Map<string, GeofabrikCatalogItem[]>();
  for (const item of filtered) {
    const continent = catalogContinent(item);
    const list = continents.get(continent) ?? [];
    list.push(item);
    continents.set(continent, list);
  }

  for (const continentName of [...continents.keys()].sort()) {
    const continent = document.createElement("details");
    continent.className = "catalog-group catalog-continent";
    continent.open = !!regionBrowserQuery || continentName === "Europe";
    const continentSummary = document.createElement("summary");
    continentSummary.textContent = continentName;
    continent.appendChild(continentSummary);

    const byCountry = new Map<string, GeofabrikCatalogItem[]>();
    for (const item of continents.get(continentName) ?? []) {
      const country = item.countryName || "Other";
      const list = byCountry.get(country) ?? [];
      list.push(item);
      byCountry.set(country, list);
    }

    for (const countryName of [...byCountry.keys()].sort()) {
      const items = (byCountry.get(countryName) ?? []).sort((a, b) => a.name.localeCompare(b.name));
      const directCountry =
        items.length === 1 &&
        normalizedRegionSearchText(items[0].name) === normalizedRegionSearchText(countryName);

      if (directCountry) {
        continent.appendChild(makeCatalogRegionRow(items[0]));
        continue;
      }

      const country = document.createElement("details");
      country.className = "catalog-group catalog-country";
      country.open = !!regionBrowserQuery;
      const countrySummary = document.createElement("summary");
      countrySummary.textContent = countryName;
      country.appendChild(countrySummary);
      for (const item of items) country.appendChild(makeCatalogRegionRow(item));
      continent.appendChild(country);
    }
    regionHost.appendChild(continent);
  }
}

function renderRegions(): void {
  regionHost.innerHTML = "";
  configuredRegionsTab.classList.toggle("active", regionBrowserMode === "configured");
  catalogRegionsTab.classList.toggle("active", regionBrowserMode === "catalog");
  configuredRegionsTab.setAttribute("aria-selected", String(regionBrowserMode === "configured"));
  catalogRegionsTab.setAttribute("aria-selected", String(regionBrowserMode === "catalog"));

  if (regionBrowserMode === "configured") renderConfiguredRegions();
  else renderCatalogRegions();
  updateRegionSelectionSummary();
}

function setRegionBrowserMode(mode: "configured" | "catalog"): void {
  regionBrowserMode = mode;
  renderRegions();
  if (mode === "catalog" && !geofabrikCatalog.length) {
    loadGeofabrikCatalog(false).catch(error => appendLog(`Geofabrik catalog error: ${String(error)}`));
  }
}

async function refreshRegions(): Promise<void> {
  regions = await invoke<RegionSummary[]>("list_regions");
  renderRegions();
}

async function loadGeofabrikCatalog(refresh = false): Promise<void> {
  if (catalogLoadPromise) return catalogLoadPromise;
  catalogLoadPromise = performCatalogLoad(refresh);
  try {
    await catalogLoadPromise;
  } finally {
    catalogLoadPromise = null;
    renderRegions();
  }
}

async function performCatalogLoad(refresh: boolean): Promise<void> {
  catalogLoadError = null;
  editorGeofabrik.disabled = true;
  editorGeofabrik.innerHTML = '<option value="">Loading Geofabrik catalog…</option>';
  try {
    const result = await invoke<GeofabrikCatalogItem[]>("geofabrik_catalog", { refresh });
    if (!Array.isArray(result) || !result.length) throw new Error("Geofabrik returned an empty catalog");
    geofabrikCatalog = result;
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
    catalogLoadError = String(error);
    editorGeofabrik.innerHTML = '<option value="">Catalog unavailable</option>';
    appendLog(`Geofabrik catalog error: ${catalogLoadError}`);
  } finally {
    editorGeofabrik.disabled = false;
  }
}


function setEditorPinMode(kind: "start" | "end" | null): void {
  editorPickMode = kind;
  pickEditorStartBtn.classList.toggle("active-pin", kind === "start");
  pickEditorEndBtn.classList.toggle("active-pin", kind === "end");
  map.getCanvas().style.cursor = kind ? "crosshair" : "";
  if (kind && window.matchMedia("(max-width: 1100px)").matches) setCompactPane("map");
}
function clearEditorPinMarkers(): void {
  setEditorPinMode(null);
  editorStartMarker?.remove();
  editorEndMarker?.remove();
  editorStartMarker = null;
  editorEndMarker = null;
}
function setEditorPin(kind: "start" | "end", lat: number, lng: number): void {
  if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) return;
  const latField = kind === "start" ? editorStartLat : editorEndLat;
  const lngField = kind === "start" ? editorStartLng : editorEndLng;
  latField.value = lat.toFixed(6);
  lngField.value = lng.toFixed(6);
  const marker = kind === "start" ? editorStartMarker : editorEndMarker;
  marker?.remove();
  const updated = new Marker({ color: kind === "start" ? "#2dcc84" : "#ff6c6c", draggable: true })
    .setLngLat([lng, lat]).addTo(map);
  updated.on("dragend", () => {
    const position = updated.getLngLat();
    setEditorPin(kind, position.lat, position.lng);
  });
  if (kind === "start") editorStartMarker = updated;
  else editorEndMarker = updated;
}
function syncEditorPin(kind: "start" | "end"): void {
  const latField = kind === "start" ? editorStartLat : editorEndLat;
  const lngField = kind === "start" ? editorStartLng : editorEndLng;
  if (!latField.value.trim() || !lngField.value.trim()) {
    const marker = kind === "start" ? editorStartMarker : editorEndMarker;
    marker?.remove();
    if (kind === "start") editorStartMarker = null;
    else editorEndMarker = null;
    return;
  }
  setEditorPin(kind, Number(latField.value), Number(lngField.value));
}
pickEditorStartBtn.addEventListener("click", () =>
  setEditorPinMode(editorPickMode === "start" ? null : "start"));
pickEditorEndBtn.addEventListener("click", () =>
  setEditorPinMode(editorPickMode === "end" ? null : "end"));
clearEditorPinsBtn.addEventListener("click", () => {
  clearEditorPinMarkers();
  for (const field of [editorStartLat, editorStartLng, editorEndLat, editorEndLng]) field.value = "";
});
for (const field of [editorStartLat, editorStartLng]) field.addEventListener("change", () => syncEditorPin("start"));
for (const field of [editorEndLat, editorEndLng]) field.addEventListener("change", () => syncEditorPin("end"));

function resetRegionEditor(): void {
  clearEditorPinMarkers();
  editorExistingConfig = null;
  editorPreview = null;
  editorRoadpilotId.value = "";
  editorRoadpilotId.disabled = false;
  editorName.value = "";
  editorGeofabrik.value = "";
  editorBuffer.value = "25";
  editorRouteName.value = "border-smoke-test";
  editorSearchEnabled.checked = false;
  editorSearchCountry.value = "";
  editorSearchExpectedName.value = "";
  editorSearchQuery.value = "";
  editorSearchAddress.value = "";
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
  activateTool("region");
}

function closeRegionEditor(): void {
  clearEditorPinMarkers();
  removeEditorOverlays();
  activateTool(lastNonRegionTool);
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
    if (!editorSearchCountry.value.trim() && preview.countryIsoAlpha2) {
      editorSearchCountry.value = preview.countryIsoAlpha2;
    }
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
  const raw = field.value.trim();
  if (!raw) throw new Error(`${label} is required. Provide a real road-crossing route to save this region.`);
  const value = Number(raw);
  if (!Number.isFinite(value)) throw new Error(`${label} must be a valid number.`);
  const limit = label.toLowerCase().includes("latitude") ? 90 : 180;
  if (Math.abs(value) > limit) throw new Error(`${label} must be within ±${limit}°.`);
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

  const existing = editorExistingConfig ? structuredClone(editorExistingConfig) : {};
  const existingOverture = existing["overture"];
  const existingRouting = (existing["routing"] ?? {}) as Record<string, unknown>;
  const existingVisual = (existing["visual"] ?? {}) as Record<string, unknown>;
  const existingVisualValidation = (existingVisual.validation ?? {}) as Record<string, unknown>;
  const existingRoutes = Array.isArray(existingRouting.validationRoutes)
    ? existingRouting.validationRoutes as Array<Record<string, unknown>>
    : [];
  const validationRoutes = existingRoutes.map(route => structuredClone(route));
  const routeFields = [editorStartLat, editorStartLng, editorEndLat, editorEndLng];
  const anyRoute = routeFields.some(field => field.value.trim().length > 0);
  if (anyRoute) {
    if (!routeFields.every(field => field.value.trim().length > 0)) {
      throw new Error("Complete all four border test coordinates, or leave all blank for automatic route validation.");
    }
    const startLat = numberField(editorStartLat, "Start latitude");
    const startLng = numberField(editorStartLng, "Start longitude");
    const endLat = numberField(editorEndLat, "End latitude");
    const endLng = numberField(editorEndLng, "End longitude");
    if (startLat === endLat && startLng === endLng) {
      throw new Error("Border test start and end must differ.");
    }
    const editedBorderRoute = {
      name: editorRouteName.value.trim() || "border-smoke-test",
      kind: "border",
      costing: "motorcycle",
      start: { lat: startLat, lng: startLng },
      end: { lat: endLat, lng: endLng },
    };
    const firstBorderIndex = validationRoutes.findIndex(route => route.kind === "border");
    if (firstBorderIndex >= 0) validationRoutes[firstBorderIndex] = editedBorderRoute;
    else validationRoutes.push(editedBorderRoute);
  } else if (existingRouting.validationMode !== "auto" && !editorSearchEnabled.checked) {
    throw new Error("Provide a border validation route, or enable Search with automatic routing validation.");
  }
  const validationMode = !anyRoute && (existingRouting.validationMode === "auto" || editorSearchEnabled.checked)
    ? "auto" : String(existingRouting.validationMode ?? "manual");

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
      validationMode,
    },
    visual: {
      ...existingVisual,
      // Editing an automatic routing-only region must not start building
      // visual PMTiles unless the user explicitly enables that dataset.
      enabled: existingVisual.enabled === false ? false : true,
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
  // A Search-only edit must not silently populate unused Visual configuration.
  // In routing-only regions, preserve the entire explicitly disabled section.
  if (existingVisual.enabled === false) {
    config.visual = structuredClone(existingVisual);
  }
  if (editorSearchEnabled.checked) {
    const country = editorSearchCountry.value.trim().toUpperCase();
    if (!/^[A-Z]{2}$/.test(country)) {
      throw new Error("Search requires a real two-letter ISO country from Geofabrik.");
    }
    const expectedName = editorSearchExpectedName.value.trim();
    const query = editorSearchQuery.value.trim();
    if (!expectedName || query.length < 2) {
      throw new Error("Search needs an expected Overture place name and query for publication validation.");
    }
    const overtureOld = (existingOverture && typeof existingOverture === "object")
      ? existingOverture as Record<string, unknown> : {};
    const oldTargets = Array.isArray(overtureOld.validation)
      ? overtureOld.validation as Array<Record<string, unknown>> : [];
    config["overture"] = {
      ...overtureOld,
      enabled: true,
      country,
      databaseSchema: "roadpilot-overture-v1",
      fileName: String(overtureOld.fileName ?? (regionId + "-v1.sqlite")),
      manifestFileName: String(overtureOld.manifestFileName ?? (regionId + "-v1.json")),
      coverage: overtureOld.coverage ?? editorPreview.bounds,
      validation: [{
        nameEquals: expectedName,
        query,
        addressContainsAny: editorSearchAddress.value.split(",").map(value => value.trim()).filter(Boolean),
        limit: 8,
      }, ...oldTargets.slice(1)],
    };
  } else if (existingOverture && typeof existingOverture === "object") {
    config["overture"] = { ...existingOverture as Record<string, unknown>, enabled: false };
  }
  return config;
}

configuredRegionsTab.addEventListener("click", () => setRegionBrowserMode("configured"));
catalogRegionsTab.addEventListener("click", () => setRegionBrowserMode("catalog"));
regionSearch.addEventListener("input", () => {
  regionBrowserQuery = normalizedRegionSearchText(regionSearch.value);
  renderRegions();
});

newRegionBtn.addEventListener("click", async () => {
  closeRegionEditor();
  setRegionBrowserMode("catalog");
  if (!geofabrikCatalog.length) await loadGeofabrikCatalog(false);
  regionSearch.focus();
});

editRegionBtn.addEventListener("click", async () => {
  if (!activeRegion) return;
  resetRegionEditor();
  openRegionEditor();
  try {
    if (!geofabrikCatalog.length) await loadGeofabrikCatalog(false);
    const config = await invoke<Record<string, unknown>>("load_region_config", { regionId: activeRegion.id });
    editorExistingConfig = config;
    const overture = (config.overture ?? {}) as Record<string, unknown>;
    editorSearchEnabled.checked = overture.enabled === true;
    editorSearchCountry.value = String(overture.country ?? "");
    const searchTargets = Array.isArray(overture.validation)
      ? overture.validation as Array<Record<string, unknown>> : [];
    const target = searchTargets[0] ?? {};
    editorSearchExpectedName.value = String(target.nameEquals ?? "");
    editorSearchQuery.value = String(target.query ?? "");
    editorSearchAddress.value = (Array.isArray(target.addressContainsAny)
      ? target.addressContainsAny as string[] : []).join(", ");
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
      syncEditorPin("start");
      syncEditorPin("end");
    }
    await previewEditorRegion(false);
  } catch (error) {
    regionPreviewSummary.innerHTML = `<span class="bad">Could not load region:</span> ${String(error)}`;
  }
});

previewRegionBtn.addEventListener("click", () => previewEditorRegion(false));
refreshCatalogBtn.addEventListener("click", async () => {
  await loadGeofabrikCatalog(true);
  if (!catalogLoadError) appendLog("Geofabrik catalog refreshed.");
});
closeRegionEditorBtn.addEventListener("click", closeRegionEditor);
configureQueuedBtn.addEventListener("click", () => {
  configureNextQueuedRegion().catch(error => appendLog(`Could not prepare queued region: ${String(error)}`));
});

saveRegionBtn.addEventListener("click", async () => {
  saveRegionBtn.disabled = true;
  try {
    const config = configFromEditor();
    const saved = await invoke<Record<string, unknown>>("save_region_config", { config, refreshGeometry: false });
    appendLog(`Saved and validated region config: ${String(saved.id)}`);
    const catalogId = editorPreview?.geofabrikId;
    if (catalogId && pendingCatalogSelection.delete(catalogId)) {
      selected.add(String(saved.id));
      appendLog(`${String(saved.id)} promoted from setup queue to build selection.`);
    }
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
  toolchainBadge.innerHTML = `Toolchain <b class="${status.ready ? "ok" : "bad"}">${status.ready ? "ready" : "incomplete"}</b>`;
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
  updateBuildButtonState();
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
  cancelSearchBtn.disabled = !status.running || !status.stage.toLowerCase().includes("search");
  if (searchBuildPending) {
    searchProduceStatus.textContent = status.last_error ?? status.stage;
    searchProduceStatus.className = status.last_error ? "status-line bad" : "status-line";
    if (!status.running && (status.stage.includes("Search build complete")
        || status.stage.includes("Search build failed")
        || status.stage.includes("Search build cancelled"))) {
      searchBuildPending = false;
      if (!status.last_error) {
        void refreshSearchBuilds().then(() => {
          const match = searchArtifacts.find(b => b.region_id === activeRegion?.id
            && b.version === searchPackVersion.value.trim());
          if (match) {
            searchBuildSelect.value = match.region_id + "::" + match.version;
            renderSearchBuildSummary();
          }
          appendLog("Retained Search builds refreshed after independent validation.");
        }).catch(error => {
          searchProduceStatus.textContent = "Search completed but catalog refresh failed: " + String(error);
        });
      }
    }
  }
  document.querySelector("#statusTitle")!.textContent = status.running
    ? `Building ${status.current_region ?? "queue"}`
    : status.last_error ? "Build failed" : "Idle";
  document.querySelector("#statusStage")!.textContent = status.last_error ?? status.stage ?? "No build running.";
  document.querySelector("#statusQueue")!.textContent = status.queue.length ? `Queue: ${status.queue.join(" → ")}` : "";
  document.querySelector("#progress")!.classList.toggle("idle", !status.running);
  cancelBtn.disabled = !status.running;
  latestBuildRunning = status.running;
  updateBuildButtonState();
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

function formatSearchBuild(build: SearchBuildArtifact): string {
  return `${build.region_id} • ${build.version} • ${build.record_count.toLocaleString()} places`;
}
function selectedSearchBuild(): SearchBuildArtifact | null {
  const [regionId, version] = searchBuildSelect.value.split("::");
  return searchArtifacts.find(v => v.region_id === regionId && v.version === version) ?? null;
}
function renderSearchBuilds(): void {
  const previous = searchBuildSelect.value;
  const options = searchArtifacts.map(v => `<option value="${escapeHtml(v.region_id)}::${escapeHtml(v.version)}">${escapeHtml(formatSearchBuild(v))}</option>`).join("");
  searchBuildSelect.innerHTML = options || '<option value="">No retained search builds</option>';
  if ([...searchBuildSelect.options].some(v => v.value === previous)) searchBuildSelect.value = previous;
  const compare = '<option value="">Choose build…</option>' + options;
  searchCompareA.innerHTML = compare; searchCompareB.innerHTML = compare;
  renderSearchBuildSummary();
}
function renderSearchBuildSummary(): void {
  const build = selectedSearchBuild();
  if (!build) { searchBuildSummary.className="empty"; searchBuildSummary.textContent="No retained search build selected."; runSearchBtn.disabled=true; return; }
  runSearchBtn.disabled=false;
  searchBuildSummary.className = build.validation_passed ? "ok" : "bad";
  searchBuildSummary.textContent = `${build.version} • ${(build.size_bytes/1048576).toFixed(1)} MB • ${build.record_count.toLocaleString()} places • ${build.categorized_record_count.toLocaleString()} categorized • Overture ${build.source_release} • validation ${build.validation_passed ? "passed" : "FAILED"}`;
}
async function refreshSearchBuilds(): Promise<void> {
  searchArtifacts = await invoke<SearchBuildArtifact[]>("list_search_builds");
  renderSearchBuilds();
  if (activePublicationKind() === "SEARCH") renderPublicationBuildSelector();
}
function clearSearchOverlay(): void {
  currentSearchResults=[]; searchResults.innerHTML="";
  if (map.getLayer("search-poi-labels")) map.removeLayer("search-poi-labels");
  if (map.getLayer("search-poi-points")) map.removeLayer("search-poi-points");
  if (map.getSource("search-poi-results")) map.removeSource("search-poi-results");
}
function renderSearchOverlay(results: SearchResult[]): void {
  clearSearchOverlay(); currentSearchResults=results;
  const geojson: FeatureCollection = {type:"FeatureCollection",features:results.map((r,i)=>({type:"Feature",geometry:{type:"Point",coordinates:[r.longitude,r.latitude]},properties:{index:i,title:r.title,category:r.basicCategory || r.taxonomyPrimary,score:r.score}}))};
  map.addSource("search-poi-results",{type:"geojson",data:geojson});
  map.addLayer({id:"search-poi-points",type:"circle",source:"search-poi-results",paint:{"circle-radius":7,"circle-stroke-width":2,"circle-stroke-color":"#fff"}});
  map.addLayer({id:"search-poi-labels",type:"symbol",source:"search-poi-results",layout:{"text-field":["get","title"],"text-size":11,"text-offset":[0,1.2],"text-anchor":"top"}});
}
async function runSearchWorkspace(): Promise<void> {
  const build=selectedSearchBuild(); if(!build) return;
  if(!searchQuery.value.trim() && !searchCategory.value.trim()){ searchResultsSummary.className="bad"; searchResultsSummary.textContent="Enter a query and/or category."; return; }
  runSearchBtn.disabled=true; searchResultsSummary.className="empty"; searchResultsSummary.textContent="Searching exact retained SQLite artifact…";
  try {
    const center=searchUseMapCenter.checked ? map.getCenter() : null;
    const results=await invoke<SearchResult[]>("search_retained_build",{regionId:build.region_id,version:build.version,query:searchQuery.value,category:searchCategory.value,originLat:center?.lat ?? null,originLng:center?.lng ?? null,limit:50});
    renderSearchOverlay(results);
    searchResultsSummary.className=results.length ? "ok" : "empty"; searchResultsSummary.textContent=`${results.length} result(s) from ${build.database_file}`;
    searchResults.innerHTML=results.map((r,i)=>`<button class="search-result" type="button" data-search-result="${i}"><strong>${i+1}. ${escapeHtml(r.title)}</strong><span>${escapeHtml(r.address || [r.locality,r.region,r.country].filter(Boolean).join(", "))}</span><span>${escapeHtml(r.basicCategory || r.taxonomyPrimary || "uncategorized")} • score ${r.score}${r.distanceMeters==null?"":` • ${Math.round(r.distanceMeters)} m`}</span><small>text exact ${r.scoreExact}, prefix ${r.scorePrefix}, contains ${r.scoreContains}, tokens ${r.scoreTokenMatches}, category ${r.scoreCategory}, proximity ${r.scoreProximity}, confidence ${r.scoreConfidence}</small></button>`).join("");
  } catch(error){ searchResultsSummary.className="bad"; searchResultsSummary.textContent=`Search failed: ${String(error)}`; clearSearchOverlay(); }
  finally { runSearchBtn.disabled=false; }
}
async function compareSearchWorkspace(): Promise<void> {
  const [ra,va]=searchCompareA.value.split("::"), [rb,vb]=searchCompareB.value.split("::");
  if(!ra || !rb || ra!==rb || va===vb){ searchCompareSummary.textContent="Choose two different builds of the same region."; return; }
  compareSearchBtn.disabled=true; searchCompareSummary.textContent="Comparing exact retained SQLite artifacts…";
  try { const result=await invoke<SearchBuildComparison>("compare_search_builds",{regionId:ra,versionA:va,versionB:vb}); searchCompareSummary.textContent=JSON.stringify(result,null,2); }
  catch(error){ searchCompareSummary.textContent=`Comparison failed: ${String(error)}`; }
  finally{ compareSearchBtn.disabled=false; }
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
let visualComparisonGeneration = 0;
const visualDiffLayers = [
  "roadpilot-visual-diff-unchanged",
  "roadpilot-visual-diff-removed",
  "roadpilot-visual-diff-added",
  "roadpilot-visual-diff-changed",
];

function removeVisualComparison(): void {
  visualComparisonGeneration += 1;
  for (const id of visualDiffLayers) if (map.getLayer(id)) map.removeLayer(id);
  for (const id of [visualCompareHiddenA, visualCompareHiddenB]) if (map.getLayer(id)) map.removeLayer(id);
  for (const id of [visualDiffSource, visualCompareSourceA, visualCompareSourceB]) {
    if (map.getSource(id)) map.removeSource(id);
  }
}

// Removes temporary rendered diagnostics only, never graph archives, files, manual saved fixes,
// search queries or selected build IDs. Does not change the current map-layer preset.
function clearTransientMapOverlays(): void {
  f8SampleMarker?.remove();
  f8SampleMarker=null;
  // Prevent an outstanding async comparison/road-diff callback from restoring a cleared view.
  buildComparisonGeneration += 1;
  removeBuildDiffOverlay();
  removeVisualComparison();
  removeBorderPairLayers();
  removeRouteLayers();
  removeLocateEdgeOverlay();
  // POI result list/data is intentionally preserved. Remove its map rendering only.
  for (const id of ["search-poi-labels", "search-poi-points"]) if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource("search-poi-results")) map.removeSource("search-poi-results");
  // The user can re-load the selected A/B pair. Saved manual crossings, editor input,
  // displayed report files, retained graph versions and source data remain untouched.
  clearToolOverlaysBtn.textContent = "Cleared";
  window.setTimeout(() => { clearToolOverlaysBtn.textContent = "Clear"; }, 1800);
}
clearToolOverlaysBtn.addEventListener("click", clearTransientMapOverlays);

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
  const generation = visualComparisonGeneration;
  map.once("idle", () => {
    if (generation !== visualComparisonGeneration || !map.getSource(visualCompareSourceA) || !map.getSource(visualCompareSourceB)) return;
    classifyVisualRoadComparison(a, b);
  });
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
  renderF8BuildSelectors();
  renderPublicationBuildSelector();
  renderRegions();
  updateRouteButtonState();
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
buildSearchBtn.addEventListener("click", async () => {
  if (!activeRegion) {
    searchProduceStatus.textContent = "Select a configured region first.";
    return;
  }
  const version = searchPackVersion.value.trim();
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/.test(version) || version.includes("..")) {
    searchProduceStatus.textContent = "Enter a new safe, immutable Search version.";
    return;
  }
  const input = searchLocalInput.value.trim();
  const release = searchLocalRelease.value.trim();
  if (!!input !== !!release || (input && !input.startsWith("/"))) {
    searchProduceStatus.textContent = "Local source requires an absolute GeoJSONSeq path and its source release; leave both empty for live Overture download.";
    return;
  }
  buildSearchBtn.disabled = true;
  searchProduceStatus.className = "status-line";
  searchProduceStatus.textContent = "Preparing independently validated Overture Search build…";
  try {
    searchBuildPending = true;
    await invoke("start_search_build", {
      regionId: activeRegion.id, packVersion: version,
      sourceInput: input || null, sourceRelease: release || null,
    });
    await refreshBuildStatus();
    appendLog("Search-only producer started: " + activeRegion.id + " • " + version);
  } catch (error) {
    searchBuildPending = false;
    searchProduceStatus.className = "status-line bad";
    searchProduceStatus.textContent = "Could not start Search build: " + String(error);
  } finally { buildSearchBtn.disabled = false; }
});
cancelSearchBtn.addEventListener("click", async () => {
  try { await invoke("cancel_build"); } catch (error) {
    searchProduceStatus.textContent = "Could not cancel Search producer: " + String(error);
  }
});
importSearchBtn.addEventListener("click", async () => {
  if (!activeRegion || !searchImportManifest.value.trim()) {
    searchProduceStatus.textContent = "Select a configured region and a validated Search manifest path.";
    return;
  }
  importSearchBtn.disabled = true;
  searchProduceStatus.className = "status-line";
  searchProduceStatus.textContent = "Independently verifying original Search pack and preparing immutable import…";
  try {
    const item = await invoke<SearchBuildArtifact>("import_search_build", {
      regionId: activeRegion.id, manifestPath: searchImportManifest.value.trim(),
    });
    await refreshSearchBuilds();
    searchBuildSelect.value = item.region_id + "::" + item.version;
    renderSearchBuildSummary();
    searchProduceStatus.textContent = "Imported validated Search: " + item.region_id + " • " + item.version;
    appendLog("Retained Search import: " + item.manifest_path);
  } catch (error) {
    searchProduceStatus.className = "status-line bad";
    searchProduceStatus.textContent = "Search import rejected: " + String(error);
  } finally { importSearchBtn.disabled = false; }
});
refreshSearchBtn.addEventListener("click", () => {
  void refreshSearchBuilds().then(() => {
    searchProduceStatus.textContent = "Retained local Search catalog refreshed.";
  }).catch(error => {
    searchProduceStatus.textContent = "Search catalog refresh failed: " + String(error);
  });
});
searchBuildSelect.addEventListener("change", renderSearchBuildSummary);
runSearchBtn.addEventListener("click", () => void runSearchWorkspace());
searchQuery.addEventListener("keydown", event => { if(event.key==="Enter") void runSearchWorkspace(); });
searchCategory.addEventListener("keydown", event => { if(event.key==="Enter") void runSearchWorkspace(); });
clearSearchBtn.addEventListener("click", () => { searchQuery.value=""; searchCategory.value=""; clearSearchOverlay(); searchResultsSummary.className="empty"; searchResultsSummary.textContent="Search cleared."; });
compareSearchBtn.addEventListener("click", () => void compareSearchWorkspace());
searchResults.addEventListener("click", event => { const target=(event.target as HTMLElement).closest<HTMLElement>("[data-search-result]"); if(!target) return; const result=currentSearchResults[Number(target.dataset.searchResult)]; if(!result) return; map.flyTo({center:[result.longitude,result.latitude],zoom:16}); featureJson.textContent=JSON.stringify(result,null,2); });

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


function autoConfigFromPreview(item: GeofabrikCatalogItem, preview: RegionPreview): Record<string, unknown> {
  const id = item.id.replaceAll("/", "-");
  if (!/^[a-z0-9][a-z0-9-]*$/.test(id)) throw new Error(`Unsafe region id ${item.id}`);
  if (!preview.sources.some(source => source.primary && source.id === preview.geofabrikId))
    throw new Error(`Primary extract missing for ${item.id}`);
  return {
    schemaVersion: 1, id, name: item.name,
    routing: {
      enabled: true, validationMode: "auto", validationRoutes: [],
      expectedValhallaVersion: "3.6.3",
      borderBufferKm: preview.borderBufferKm, buildConcurrency: 12, coverage: preview.bounds,
      source: {
        primaryGeofabrikId: preview.geofabrikId, polygonUrl: preview.polygonUrl,
        pbfs: preview.sources.map(source => ({ id: source.id, url: source.pbfUrl })),
      },
      package: {
        fileNameTemplate: `${id}-routing-{version}.tar`,
        manifestFileNameTemplate: `${id}-routing-{version}-manifest.json`,
      },
    },
    visual: { enabled: false },
  };
}

async function autoPrepareSelectedRegions(): Promise<void> {
  const pending = [...pendingCatalogSelection];
  for (let i = 0; i < pending.length; i++) {
    const geofabrikId = pending[i];
    const existing = regions.find(region => region.primary_geofabrik_id === geofabrikId);
    if (existing) {
      selected.add(existing.id);
      pendingCatalogSelection.delete(geofabrikId);
      continue;
    }
    const item = geofabrikCatalog.find(row => row.id === geofabrikId);
    if (!item) throw new Error(`Catalog item not found: ${geofabrikId}`);
    appendLog(`Auto-setup ${i + 1}/${pending.length}: ${item.name} · finding exact sources…`);
    const preview = await invoke<RegionPreview>("preview_region", {
      geofabrikId, bufferKm: 25, refresh: false,
    });
    const config = autoConfigFromPreview(item, preview);
    await invoke("save_region_config", { config, refreshGeometry: false });
    pendingCatalogSelection.delete(geofabrikId);
    selected.add(String(config.id));
    appendLog(`Auto-configured ${item.name}; build-time Valhalla road-crossing proof required.`);
    await refreshRegions();
  }
  renderRegions();
}

packageVersionInput.addEventListener("input", updateBuildButtonState);
for (const field of [routeStartLat, routeStartLng, routeEndLat, routeEndLng]) {
  field.addEventListener("input", updateRouteButtonState);
}

buildBtn.addEventListener("click", async () => {
  const version = packageVersionInput.value.trim();
  if (!/^\d{4}\.\d{2}\.\d{2}-[A-Za-z0-9._-]+$/.test(version)) {
    appendLog("Package version must look like 2026.10.06-1.");
    return;
  }
  if (!selected.size && !pendingCatalogSelection.size) {
    appendLog("Select at least one region in the left tree.");
    return;
  }
  if (buildBtn.disabled) return;
  buildSubmitting = true;
  updateBuildButtonState();
  try {
    await autoPrepareSelectedRegions();
    const queue = [...selected].filter(id => regions.some(region => region.id === id));
    if (!queue.length) throw new Error("No configured regions remain in the build queue.");
    await invoke("start_build_queue", {
      regionIds: queue, packageVersion: version, refreshSources: refreshSourceCheckbox.checked,
    });
    await refreshBuildStatus();
  } catch (error) {
    appendLog(`Could not start automatic build: ${String(error)}`);
  } finally {
    buildSubmitting = false;
    updateBuildButtonState();
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
  handoffValidationSummary.textContent = `Overlay loaded: A=${a}, B=${b}. Manual validation uses correlated Valhalla directed edges; saved historical evidence is read-only and not native D-017 proof.`;
});

refreshHandoffArtifactsBtn.addEventListener("click", () => refreshHandoffArtifactOverlay());
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
      roadDiff: null,
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

pickHandoffABtn.addEventListener("click", () => {
  if (!borderRegionA.value) {
    handoffValidationSummary.className = "bad";
    handoffValidationSummary.textContent = "Choose Graph A first.";
    return;
  }
  handoffPickMode = "A";
  if (window.matchMedia("(max-width: 1100px)").matches) setCompactPane("map");
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
  if (window.matchMedia("(max-width: 1100px)").matches) setCompactPane("map");
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
  if (window.matchMedia("(max-width: 1100px)").matches) setCompactPane("map");
  pickRouteStartBtn.textContent = "Click map…";
  pickRouteEndBtn.textContent = "Pick end";
});
pickRouteEndBtn.addEventListener("click", () => {
  routePickMode = "end";
  if (window.matchMedia("(max-width: 1100px)").matches) setCompactPane("map");
  pickRouteEndBtn.textContent = "Click map…";
  pickRouteStartBtn.textContent = "Pick start";
});
runRouteBtn.addEventListener("click", () => {
  if (runRouteBtn.disabled) return;
  routeSubmitting = true;
  updateRouteButtonState();
  void runStandardRoute();
});
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
  if (editorPickMode && activeTool === "region") {
    const kind = editorPickMode;
    setEditorPinMode(null);
    setEditorPin(kind, event.lngLat.lat, event.lngLat.lng);
    if (window.matchMedia("(max-width: 1100px)").matches) setCompactPane("tools");
    return;
  }
  lastMapClick = { lat: event.lngLat.lat, lng: event.lngLat.lng };
  locateBtn.disabled = !activeRegion;
  if (handoffPickMode) {
    const mode = handoffPickMode;
    handoffPickMode = null;
    pickHandoffABtn.textContent = "Pick A edge";
    pickHandoffBBtn.textContent = "Pick B edge";
    snapHandoff(mode, event.lngLat.lat, event.lngLat.lng).catch(error => appendLog(String(error)));
    if (window.matchMedia("(max-width: 1100px)").matches) setCompactPane("tools");
    return;
  }
  if (routePickMode) {
    setRoutePoint(routePickMode, event.lngLat.lat, event.lngLat.lng);
    routePickMode = null;
    pickRouteStartBtn.textContent = "Pick start";
    pickRouteEndBtn.textContent = "Pick end";
    if (window.matchMedia("(max-width: 1100px)").matches) setCompactPane("tools");
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

map.on("contextmenu", (event) => {
  event.originalEvent.preventDefault();
  activateTool("graph");
  lastMapClick = { lat: event.lngLat.lat, lng: event.lngLat.lng };
  locateBtn.disabled = !activeRegion;
  inspectEdgesAt(event.lngLat.lat, event.lngLat.lng).catch(error => appendLog(String(error)));
});

locatePrevBtn.addEventListener("click", () => showLocateCandidate(locateCandidateIndex - 1));
locateNextBtn.addEventListener("click", () => showLocateCandidate(locateCandidateIndex + 1));
locateBtn.addEventListener("click", async () => {
  if (!activeRegion || !lastMapClick) return;
  locateBtn.disabled = true;
  try {
    await inspectEdgesAt(lastMapClick.lat, lastMapClick.lng);
  } finally {
    locateBtn.disabled = false;
  }
});

expansionProgress.addEventListener("input", updateExpansionPlayback);

async function bootstrap(): Promise<void> {
  await listen<{ line: string }>("graph-studio://build-log", event => appendLog(event.payload.line));
  await listen<BuildStatus>("graph-studio://build-status", event => {
    renderBuildStatus(event.payload);
    if (!event.payload.running) {
      refreshBuilds().catch(() => {});
      refreshVisualBuilds().catch(() => {});
      refreshSearchBuilds().catch(() => {});
    }
  });
  await listen<F8JobStatus>("graph-studio://f8-status", event => {
    renderF8Job(event.payload);
  });
  await listen<string>("graph-studio://f8-log", event => appendLog(event.payload));
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
    loadGeofabrikCatalog(false),
    refreshToolchain(),
    refreshBuildStatus(),
    invoke<F8JobStatus>("f8_workflow_status").then(renderF8Job),
    refreshBuilds(),
    refreshVisualBuilds(),
    refreshSearchBuilds(),
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
