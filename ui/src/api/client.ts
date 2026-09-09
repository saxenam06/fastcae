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
  steps: Step[];
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

export interface Mesh {
  positions: Float32Array;
  normals: Float32Array;
  faceIds: Uint32Array;
  vertexCount: number;
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
  extract: (project: string, paths?: string[]) =>
    postJson<SessionState>("/api/extract", { project, paths }),
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
   * Fetch and unpack the render mesh.
   *
   * Un-welded - three vertices per triangle - because WebGL2 has no primitive id in the fragment
   * shader, so the CAD face id has to travel as a vertex attribute. That also lets normals be
   * smoothed per face rather than per vertex, keeping machined edges sharp.
   */
  async mesh(): Promise<Mesh> {
    const response = await fetch("/api/mesh");
    if (!response.ok) throw new Error(`/api/mesh: ${response.status}`);
    const buffer = await response.arrayBuffer();

    const magic = new TextDecoder().decode(new Uint8Array(buffer, 0, 8));
    if (magic !== "FCMESH02") {
      throw new Error(`unexpected mesh format "${magic}", expected FCMESH02`);
    }

    const vertexCount = new DataView(buffer).getUint32(8, true);
    let offset = 12;
    const positions = new Float32Array(buffer, offset, vertexCount * 3);
    offset += vertexCount * 3 * 4;
    const normals = new Float32Array(buffer, offset, vertexCount * 3);
    offset += vertexCount * 3 * 4;
    const faceIds = new Uint32Array(buffer, offset, vertexCount);

    return { positions, normals, faceIds, vertexCount };
  },
};
