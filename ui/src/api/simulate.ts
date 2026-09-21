/**
 * Simulate's calls: the baseline's deck and answers, and the runner's jobs.
 *
 * Meshes arrive as their outside only - boundary triangles and the nodes on them - with each
 * triangle's group; fields as one value per node of that outside, so a result redraws without the
 * mesh being fetched again.
 */

import type { GlyphData, Skin, Slice } from "../render/fe";
import type { Plane } from "../stage/sectionPlane";

export type Provenance = "imported" | "derived" | "generated";

export interface DeckFile {
  role: string;
  kind: "deck" | "results";
  name: string | null;
  present: boolean;
  size_bytes: number;
}

export interface DeckGroup {
  name: string;
  of: "nodes" | "cells";
  cells: Record<string, number>;
  count: number;
  roles: string[];
}

export interface DeckSetup {
  materials: { name: string; young: number; poisson: number; density: number | null; groups: string[] }[];
  held: { load_set: string; groups: string[]; dofs: Record<string, number> }[];
  rigid: { load_set: string; groups: string[]; reference: string | null }[];
  distributing: {
    load_set: string;
    reference: string;
    group: string;
    reference_dofs: string[];
    group_dofs: string[];
    weights: number[];
  }[];
  nodal_loads: { load_set: string; group: string; values: Record<string, number> }[];
  surface_loads: { load_set: string; kind: string; group: string; values: Record<string, number> }[];
  outputs: { name: string; group: string; field: string; components: string[] | null; operation: string; table: string }[];
  analysis: { kind: string; load_sets: string[]; solver: Record<string, unknown>; fields: string[]; written: string[] } | null;
  model: { groups: string[]; physics: string; modelling: string }[];
  discrete: { groups: string[]; kind: string }[];
  not_read: string[];
}

export interface DeckAnswer {
  id: "aster" | "cudss";
  label: string;
  provenance: Provenance;
  available: boolean;
  detail?: string;
  meta?: {
    unknowns?: number;
    times?: Record<string, number>;
    residual?: number;
    agreement?: { displacement: number; von_mises?: number };
    made?: number;
  } | null;
}

export interface Anchoring {
  groups: Record<string, { faces: number[]; area: number; face_area: number; gap: number; triangles: number }>;
  references: Record<string, number[]>;
  not_anchored: string[];
}

export interface Deck {
  present: boolean;
  files: DeckFile[];
  mesh?: { name: string; nodes: number; cells: Record<string, number>; unknowns: number | null; bbox_mm: number[] };
  groups?: DeckGroup[];
  setup?: DeckSetup;
  skipped?: string[];
  warnings?: string[];
  fields?: { name: string; components: string[]; nodes: number }[];
  tables?: { columns: string[]; rows: number }[];
  anchoring?: Anchoring | null;
  patches?: string[];
  answers?: DeckAnswer[];
  read_s?: number;
}

export interface SignalRow {
  name: string;
  component: string;
  unit: string;
  kind: "deck" | "derived";
  group: string;
  values: Record<string, number>;
}

export interface Signals {
  runs: Record<string, string>;
  rows: SignalRow[];
  agreement: Record<string, { displacement: number; von_mises?: number }>;
}

export interface JobStatus {
  id: string;
  kind: string;
  project: string | null;
  state: "queued" | "starting" | "running" | "done" | "failed" | "cancelled" | "interrupted" | "unknown";
  stage?: string;
  progress?: number;
  message?: string;
  error?: string;
  result?: Record<string, unknown>;
  started?: number;
  finished?: number;
  created?: number;
  events?: { t: number; message: string }[];
}

export type Run = "aster" | "cudss";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${response.status} ${await response.text()}`);
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  });
  if (!response.ok) throw new Error(`${path}: ${response.status} ${await response.text()}`);
  return response.json() as Promise<T>;
}

export async function fetchSkin(path: string): Promise<Skin> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  const buffer = await response.arrayBuffer();
  const magic = new TextDecoder().decode(new Uint8Array(buffer, 0, 8));
  if (magic !== "FCSKIN01") throw new Error(`unexpected mesh format "${magic}"`);
  const view = new DataView(buffer);
  const headerLength = view.getUint32(8, true);
  const vertices = view.getUint32(12, true);
  const triangles = view.getUint32(16, true);
  let offset = 20;
  const header = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, offset, headerLength)));
  offset += headerLength;
  const positions = new Float32Array(buffer, offset, vertices * 3);
  offset += vertices * 12;
  const tris = new Uint32Array(buffer, offset, triangles * 3);
  offset += triangles * 12;
  const groups = new Uint16Array(buffer, offset, triangles);
  offset += triangles * 2 + (triangles % 2) * 2;
  const nodes = new Uint32Array(buffer, offset, vertices);
  return { positions, triangles: tris, groups, nodes, groupNames: header.groups as string[] };
}

export interface Values {
  values: Float32Array;
  vectors: Float32Array | null;
}

export async function fetchValues(path: string): Promise<Values> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${response.status} ${await response.text()}`);
  const buffer = await response.arrayBuffer();
  const view = new DataView(buffer);
  const count = view.getUint32(8, true);
  const width = view.getUint32(12, true);
  const values = new Float32Array(buffer, 16, count);
  const vectors = width ? new Float32Array(buffer, 16 + count * 4, count * width) : null;
  return { values, vectors };
}

/** Where a plane cuts a mesh, as the server sends it (``FCSECT01``): the triangles' corners, the
 * field and the displacement at them when there are any, and each triangle's element edges. */
export async function fetchSection(path: string): Promise<Slice> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${response.status} ${await response.text()}`);
  const buffer = await response.arrayBuffer();
  const view = new DataView(buffer);
  const triangles = view.getUint32(8, true);
  const flags = view.getUint32(12, true);
  let at = 16;
  const positions = new Float32Array(buffer, at, triangles * 9);
  at += triangles * 36;
  let values: Float32Array | null = null;
  if (flags & 1) {
    values = new Float32Array(buffer, at, triangles * 3);
    at += triangles * 12;
  }
  let vectors: Float32Array | null = null;
  if (flags & 2) {
    vectors = new Float32Array(buffer, at, triangles * 9);
    at += triangles * 36;
  }
  const edges = new Uint8Array(buffer, at, triangles);
  return { triangles, positions, values, vectors, edges };
}

/** The query naming a plane. */
export function planeQuery(plane: Plane): string {
  const [nx, ny, nz] = plane.normal;
  return `nx=${nx}&ny=${ny}&nz=${nz}&d=${plane.d}`;
}

export const sim = {
  deck: () => getJson<Deck>("/api/deck"),
  deckSkin: () => fetchSkin("/api/deck/mesh"),
  deckGlyphs: () => getJson<GlyphData>("/api/deck/glyphs"),
  field: (run: Run, name: string, vectors = false) =>
    fetchValues(`/api/deck/field?run=${run}&name=${encodeURIComponent(name)}&vectors=${vectors}`),
  signals: () => getJson<Signals>("/api/deck/signals"),
  /** The deck's mesh cut by a plane - with a field of one answer on the cut, when one is named. */
  section: (plane: Plane, run?: Run, name?: string) =>
    fetchSection(
      `/api/deck/section?${planeQuery(plane)}${run ? `&run=${run}` : ""}${name ? `&name=${encodeURIComponent(name)}` : ""}`,
    ),
  solve: () => postJson<{ job: string }>("/api/deck/solve"),
  job: (id: string, since = 0) => getJson<JobStatus>(`/api/jobs/${encodeURIComponent(id)}?since=${since}`),
};
