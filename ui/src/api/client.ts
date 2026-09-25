/**
 * The API surface. Every call here is an HTTP route, the same one anything else driving the
 * engine would use.
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
  centroid_mm: number[];
  /** Which way it faces: a planar group's normal, a hole's axis. */
  normal: number[] | null;
  /** The faces a hole opens onto. */
  opens_onto: number[];
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

export interface FaceDetail {
  face_id: number;
  surface_type: string;
  area_mm2: number;
  analytic_area_mm2: number;
  analytic_area_is_valid: boolean;
  centroid_mm: number[];
  /** Where the face reaches, from its own triangles: x0, y0, z0, x1, y1, z1. */
  bbox_mm: number[] | null;
  normal: number[] | null;
  axis: number[] | null;
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
  /** For a surface drawn over the part: how far each vertex stands off it, 0 on it to 255. */
  standing?: Uint8Array;
}

/** What happens during one message to the agent, as it happens. ``show``: entities the agent
 * showed the engineer, to bring into focus; ``changed``: what it changed - answers, the space. */
export type AgentEvent =
  | { type: "token"; text: string }
  | { type: "tool_start"; id?: string; name: string; args?: unknown }
  | { type: "tool_result"; id?: string; name: string; summary: string }
  | { type: "show"; ids: string[] }
  | { type: "error"; message: string }
  | { type: "changed"; what: string[] }
  | { type: "done" };

/** One entry of the conversation, as the pane shows it. */
export type AgentMessage =
  | { role: "engineer"; text: string }
  | { role: "agent"; text: string }
  | { role: "tool"; name: string; args: unknown }
  | { role: "shown"; ids: string[] };

/** One message to the agent, with the entities in focus; each event is handed on as it arrives. */
async function chat(
  message: string,
  focus: string[],
  onEvent: (event: AgentEvent) => void,
): Promise<void> {
  const response = await fetch("/api/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, focus }),
  });
  if (!response.ok || !response.body) {
    const text = await response.text();
    throw new Error(text || `the agent answered ${response.status}`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut = buffer.indexOf("\n\n");
    while (cut >= 0) {
      const chunk = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)) as AgentEvent);
      }
      cut = buffer.indexOf("\n\n");
    }
  }
}

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
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

/** Events a route streams, one JSON object a ``data:`` line, each handed on as it arrives. */
export async function stream<T>(path: string, body: unknown, onEvent: (event: T) => void): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) {
    const text = await response.text();
    throw new Error(text || `${path} answered ${response.status}`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut = buffer.indexOf("\n\n");
    while (cut >= 0) {
      const chunk = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)) as T);
      }
      cut = buffer.indexOf("\n\n");
    }
  }
}

export const api = {
  chat,
  newChat: () => postJson<{ thread: string }>("/api/agent/new", {}),
  agentHistory: () =>
    getJson<{ thread: string; messages: AgentMessage[] }>("/api/agent/history"),
  state: () => getJson<SessionState>("/api/state"),
  projects: () => getJson<ProjectRow[]>("/api/projects"),
  extract: (project: string, paths?: string[], reuse = true) =>
    postJson<SessionState>("/api/extract", { project, paths, reuse }),

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
  callouts: (kind?: string) =>
    getJson<Callout[]>(`/api/callouts${kind ? `?kind=${encodeURIComponent(kind)}` : ""}`),
  controlled: () =>
    getJson<{ face_ids: number[]; count: number; by_feature: Record<string, Fact> }>(
      "/api/controlled",
    ),
  face: (id: number) => getJson<FaceDetail>(`/api/faces/${id}`),

  /**
   * The part's surface: the tessellated B-rep.
   *
   * Un-welded - three vertices per triangle - because WebGL2 has no primitive id in the fragment
   * shader, so the CAD face id has to travel as a vertex attribute. That also lets normals be
   * smoothed per face rather than per vertex, keeping machined edges sharp.
   */
  mesh: () => fetchMesh("/api/mesh"),
};

/** The field's own cells: one packed integer per visible face, and the grid it indexes into. */
export async function fetchVoxels(path: string): Promise<VoxelCells> {
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

export async function fetchMesh(path: string): Promise<Mesh> {
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
  offset += triangleCount * 12;
  // A surface drawn over the part may end with a byte per vertex: how far it stands off the part.
  const standing =
    buffer.byteLength >= offset + vertexCount
      ? new Uint8Array(buffer, offset, vertexCount)
      : undefined;

  return {
    positions,
    normals,
    faceIds,
    indices,
    vertexCount,
    indexCount: triangleCount * 3,
    standing,
  };
}
