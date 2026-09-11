/**
 * The API surface. Every call here is an HTTP route the agent can call too.
 *
 * No type names a component kind. A feature has a geometric `kind`; a callout has a drawing
 * `kind`. Both are strings the server chose, so a bracket needs no new types.
 */

export type Stage = "upload" | "extract_failed" | "model";
export type StepStatus = "pending" | "running" | "done" | "skipped" | "failed";
export type EvidenceState = "measured" | "derived" | "assumed" | "conflicted";

export interface ArtifactRow {
  name: string;
  kind: string;
  label: string;
  path: string;
  size_bytes: number;
}

export interface ProjectRow {
  name: string;
  title: string;
  path: string;
  artifacts: ArtifactRow[];
  has_cad: boolean;
  has_drawing: boolean;
}

export interface Step {
  id: string;
  label: string;
  status: StepStatus;
  detail: string;
  needs: string[];
  produced: Record<string, unknown>;
  warnings: string[];
  seconds: number;
}

export interface SessionState {
  stage: Stage;
  project: ProjectRow | null;
  extracted: boolean;
  /** Whether this came back from disk rather than being read again. Null before anything is open. */
  from_cache: boolean | null;
  seconds: number | null;
  steps: Step[];
}

export interface FieldSummary {
  spacing_mm: number;
  shape: number[];
  cells: number;
  band_cells: number;
  solid_cells: number;
  reach_mm: number;
  headroom_mm: number;
  volume_cm3: number;
  from_cache: boolean;
}

export interface FieldOption {
  spacing_mm: number;
  field_ready: boolean;
  surface_ready: boolean;
}

/**
 * The field's cells, ready to draw: one packed integer per visible face.
 *
 * ``faces`` holds ``cell_index << 3 | direction``, decoded in the vertex shader against ``shape``
 * and ``origin``. Packed rather than positioned because a cell has six faces and at most three
 * show, so sending whole cubes is six times the geometry for the same picture.
 */
export interface VoxelCells {
  faces: Uint32Array;
  size: number;
  shape: [number, number, number];
  origin: [number, number, number];
}

/** One lever on the geometry. The placement is fixed; the height is what moves. */
export interface ParameterRow {
  id: string;
  name: string;
  kind: string;
  low_mm: number;
  high_mm: number;
  default_mm: number;
  /** The tallest the grid can hold. A range beyond this would be a slider that lies. */
  ceiling_mm: number;
  length_mm: number;
  thickness_mm: number;
  origin_mm: number[];
  up: number[];
  host_face_ids: number[];
}

export interface DesignSummary {
  key: string;
  values_mm: number[];
  blend_mm: number;
  blend_ceiling_mm: number;
  volume_cm3: number;
  added_cm3: number;
  base_volume_cm3: number;
  seconds: number;
}

export interface SurfaceSummary {
  spacing_mm: number;
  vertices: number;
  triangles: number;
  volume_cm3: number;
  area_m2: number;
  watertight: boolean;
  boundary_edges: number;
  non_manifold_edges: number;
  inconsistent_edges: number;
  brep_volume_cm3: number | null;
  volume_error_pct: number | null;
  brep_triangles: number | null;
  shell_cells: number;
  solid_cells: number;
  band_cells: number;
}

export interface Evidence {
  kind: "cad" | "drawing" | "report" | "fem" | "derived" | "assumed";
  locator: string;
  method: string;
  detail: string;
  confidence: number;
}

export interface Fact {
  value: unknown;
  state: EvidenceState;
  confidence: number;
  note: string;
  evidence: Evidence[];
}

export interface Summary {
  project: string;
  title: string;
  seconds: number;
  solids: number | null;
  faces: number | null;
  triangles: number | null;
  volume_cm3: number | null;
  area_m2: number | null;
  bbox_mm: number[] | null;
  watertight: boolean | null;
  features: number | null;
  controlled_faces: number;
  has_drawing: boolean;
}

export interface Feature {
  id: string;
  kind: string;
  face_ids: number[];
  area_mm2: number;
  axis_id: string | null;
  diameter_mm: number | null;
  station_mm: number | null;
  count: number;
  metrics: Record<string, number | null>;
  controlled: Fact | null;
}

export interface Callout {
  kind: string;
  page: number;
  raw: string;
  nominal: number | null;
  tolerance: number | null;
  count: number | null;
  is_diameter: boolean;
  through: boolean;
  text: string;
}

export interface Axis {
  id: string;
  point: number[];
  direction: number[];
  face_count: number;
  area_mm2: number;
  feature_count: number;
}

export interface FaceDetail {
  face_id: number;
  surface_type: string;
  area_mm2: number;
  analytic_area_mm2: number;
  analytic_area_is_valid: boolean;
  centroid_mm: number[];
  diameter_mm: number | null;
  minor_radius_mm: number | null;
  half_angle_deg: number | null;
  concave: boolean | null;
  exterior: boolean;
  z_mm: number;
  neighbours: number[];
  controlled: boolean;
  features: Feature[];
}

export interface Selection {
  face_ids: number[];
  count: number;
  area_mm2: number;
  controlled_face_ids: number[];
  touches_controlled: boolean;
  reason: string;
}

/**
 * A surface, indexed and welded by normal.
 *
 * ``normals`` is four signed bytes per vertex - three used, one for alignment - read as normalised
 * floats by the shader. Half a degree of accuracy for a third of what floats cost.
 */
export interface Mesh {
  positions: Float32Array;
  normals: Int8Array;
  faceIds: Uint32Array;
  indices: Uint32Array;
  vertexCount: number;
  indexCount: number;
}

/** Where ribs may go, as proposed from the part and approved - or not yet - by a person. */
export interface ZoneRow {
  id: string;
  label: string;
  host: string;
  status?: "proposed" | "approved";
  summary: string;
  region: Record<string, unknown>;
}

export interface ZonesInfo {
  zones: ZoneRow[];
  protected: { kinds: string[]; clearance_mm: number; status: "proposed" | "approved" };
  corrections: { kind: string; approved: boolean; available: boolean }[];
  can_propose: boolean;
}

export interface LeverRow {
  name: string;
  label: string;
  low: number;
  high: number;
  step: number;
  unit: string;
  integer: boolean;
}

export interface FormationRow {
  name: string;
  label: string;
  levers: LeverRow[];
}

export interface Formations {
  formations: FormationRow[];
  /** What every rib shares, from the casting rules: not a lever. */
  fixed: { root_fillet_mm: number; edge_round_mm: number; draft_deg: number };
  rules: { name: string; basis: string; assumed: boolean }[];
}

export interface SpaceInfo {
  zones: ZoneRow[];
  spacing_mm: number;
  base_volume_cm3: number;
  base_faults: number[];
  radius_mm: number;
  density: { g_cm3?: number; basis?: string; state?: string };
  corrections: { kind: string; removed_cm3: number }[];
}

export type Outcome = "pass" | "warn" | "reject";

export interface FindingRow {
  check: string;
  outcome: Outcome;
  reason: string;
  rule: string;
  assumed: boolean;
  where: number[] | null;
  value: number | null;
}

export interface MadeDesign {
  digest: string;
  outcome: Outcome;
  settings: Record<string, Record<string, unknown>>;
  findings: FindingRow[];
  stats: {
    ribs: number;
    dropped: number;
    volume_cm3: number;
    base_volume_cm3: number;
    added_cm3: number;
    mass_kg: number | null;
    base_mass_kg: number | null;
    smallest_fillet_mm: number | null;
    seconds: Record<string, number>;
  };
}

/** A formation chosen for a zone, and its lever values. */
export interface ZoneSettings {
  formation: string;
  values: Record<string, number>;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${path}: ${response.status} ${text}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  state: () => getJson<SessionState>("/api/state"),
  projects: () => getJson<ProjectRow[]>("/api/projects"),
  extract: (project: string, paths?: string[], reuse = true) =>
    postJson<SessionState>("/api/extract", { project, paths, reuse }),
  buildField: (spacingMm?: number, reuse = true, headroomMm?: number) =>
    postJson<FieldSummary>("/api/field", {
      spacing_mm: spacingMm ?? null,
      headroom_mm: headroomMm ?? null,
      reuse,
    }),
  field: () => getJson<FieldSummary>("/api/field"),
  fieldSurface: () => getJson<SurfaceSummary>("/api/field/surface"),
  fieldOptions: () => getJson<FieldOption[]>("/api/field/options"),

  parameters: () => getJson<ParameterRow[]>("/api/parameters"),
  addRib: (faceIds: number[], name: string, thicknessMm: number, highMm: number) =>
    postJson<ParameterRow>("/api/parameters", {
      face_ids: faceIds,
      name,
      thickness_mm: thicknessMm,
      high_mm: highMm,
    }),
  async removeParameter(id: string): Promise<ParameterRow[]> {
    const response = await fetch(`/api/parameters/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
    if (!response.ok) throw new Error(`delete ${id}: ${response.status}`);
    return response.json() as Promise<ParameterRow[]>;
  },
  evaluate: (valuesMm: number[], blendMm: number) =>
    postJson<DesignSummary>("/api/design", { values_mm: valuesMm, blend_mm: blendMm }),
  designVoxels: () => fetchVoxels("/api/design/voxels"),
  check: (path: string) =>
    getJson<{
      path: string;
      exists: boolean;
      kind: string | null;
      label: string | null;
      size_bytes: number;
    }>(`/api/check?path=${encodeURIComponent(path)}`),
  reset: () => postJson<SessionState>("/api/reset", {}),

  summary: () => getJson<Summary>("/api/summary"),
  steps: () => getJson<Step[]>("/api/steps"),
  features: (kind?: string) =>
    getJson<Feature[]>(`/api/features${kind ? `?kind=${encodeURIComponent(kind)}` : ""}`),
  featureKinds: () =>
    getJson<{ kind: string; count: number; controlled: number }[]>("/api/feature-kinds"),
  axes: () => getJson<Axis[]>("/api/axes"),
  callouts: (kind?: string) =>
    getJson<Callout[]>(`/api/callouts${kind ? `?kind=${encodeURIComponent(kind)}` : ""}`),
  controlled: () =>
    getJson<{ face_ids: number[]; count: number; by_feature: Record<string, Fact> }>(
      "/api/controlled",
    ),
  face: (id: number) => getJson<FaceDetail>(`/api/faces/${id}`),

  selectFaces: (faceIds: number[]) =>
    postJson<Selection>("/api/select/faces", { face_ids: faceIds }),

  grow: (seed: number[], maxDihedralDeg: number) =>
    postJson<Selection>("/api/select/grow", { seed, max_dihedral_deg: maxDihedralDeg }),
  similar: (faceId: number) => postJson<Selection>("/api/select/similar", { face_id: faceId }),
  selectFeature: (featureId: string) =>
    getJson<Selection>(`/api/select/feature/${encodeURIComponent(featureId)}`),

  /**
   * Both surfaces arrive in one format: the tessellated B-rep, and the field contoured back into
   * triangles. Same path through the renderer, so a difference on screen is a difference in the
   * geometry rather than in how it was drawn.
   *
   * Un-welded - three vertices per triangle - because WebGL2 has no primitive id in the fragment
   * shader, so the CAD face id has to travel as a vertex attribute. That also lets normals be
   * smoothed per face rather than per vertex, keeping machined edges sharp.
   */
  mesh: () => fetchMesh("/api/mesh"),
  fieldMesh: () => fetchMesh("/api/field/mesh"),

  /** The field's own cells: one packed integer per visible face, and the grid it indexes into. */
  fieldVoxels: () => fetchVoxels("/api/field/voxels"),

  zones: () => getJson<ZonesInfo>("/api/zones"),
  proposeZones: (spacingMm = 2.5) =>
    postJson<ZonesInfo>("/api/zones/propose", { spacing_mm: spacingMm }),
  approveZone: (id: string, approved: boolean) =>
    postJson<ZonesInfo>(`/api/zones/${encodeURIComponent(id)}`, { approved }),
  approveProtected: (approved: boolean) => postJson<ZonesInfo>("/api/protected", { approved }),
  approveCorrection: (kind: string, approved: boolean) =>
    postJson<unknown>(`/api/corrections/${encodeURIComponent(kind)}`, { approved }),
  formations: () => getJson<Formations>("/api/formations"),
  openSpace: (spacingMm = 2.5) => postJson<SpaceInfo>("/api/designspace", { spacing_mm: spacingMm }),
  generate: (settings: Record<string, ZoneSettings>) =>
    postJson<MadeDesign>("/api/designs", {
      zones: Object.fromEntries(
        Object.entries(settings).map(([id, s]) => [id, { formation: s.formation, ...s.values }]),
      ),
    }),
  /** The current design's new surfaces - ribs and fillets - to draw over the part. */
  designMesh: () => fetchMesh("/api/designs/current/mesh"),
};

/** The field's own cells: one packed integer per visible face, and the grid it indexes into. */
async function fetchVoxels(path: string): Promise<VoxelCells> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  const buffer = await response.arrayBuffer();

  const magic = new TextDecoder().decode(new Uint8Array(buffer, 0, 8));
  if (magic !== "FCVOXL02") throw new Error(`unexpected voxel format "${magic}"`);

  const view = new DataView(buffer);
  const count = view.getUint32(8, true);
  const size = view.getFloat32(12, true);
  const shape: [number, number, number] = [
    view.getInt32(16, true),
    view.getInt32(20, true),
    view.getInt32(24, true),
  ];
  const origin: [number, number, number] = [
    view.getFloat32(28, true),
    view.getFloat32(32, true),
    view.getFloat32(36, true),
  ];
  return { faces: new Uint32Array(buffer, 40, count), size, shape, origin };
}

async function fetchMesh(path: string): Promise<Mesh> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  const buffer = await response.arrayBuffer();

  const magic = new TextDecoder().decode(new Uint8Array(buffer, 0, 8));
  if (magic !== "FCMESH03") {
    throw new Error(`unexpected mesh format "${magic}", expected FCMESH03`);
  }

  const view = new DataView(buffer);
  const vertexCount = view.getUint32(8, true);
  const triangleCount = view.getUint32(12, true);

  // Laid out so every array starts on a four-byte boundary: positions, then four bytes of normal
  // per vertex, then the face id, then the index buffer.
  let offset = 16;
  const positions = new Float32Array(buffer, offset, vertexCount * 3);
  offset += vertexCount * 12;
  const normals = new Int8Array(buffer, offset, vertexCount * 4);
  offset += vertexCount * 4;
  const faceIds = new Uint32Array(buffer, offset, vertexCount);
  offset += vertexCount * 4;
  const indices = new Uint32Array(buffer, offset, triangleCount * 3);

  return { positions, normals, faceIds, indices, vertexCount, indexCount: triangleCount * 3 };
}
