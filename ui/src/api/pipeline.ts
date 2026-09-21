// The pipeline as the server holds it: the steps that read the engineer's files, the design space
// last, and the typed entities they produced. The same JSON an agent reads - see
// src/fastcae/pipeline/entities.py.

import { fetchVoxels, getJson, stream, type VoxelCells } from "./client";

export type Origin = "imported" | "derived" | "inferred" | "generated";

export type CanvasName = "drawing" | "cad" | "mesh" | "space" | "none";

/** Where an entity can be seen, and what to highlight there. */
export interface Show {
  canvas: CanvasName;
  faces: number[];
  page: number | null;
  text: string | null;
  group: string | null;
  layers: string[];
  point: [number, number, number] | null;
}

/** Some of a step's inputs or outputs: a few words, how many, which. An input with no ids is every
 * entity of its kind the producing step made. */
export interface Group {
  key: string;
  label: string;
  count: number;
  kind: string;
  ids: string[];
  step: string;
}

export type RunStatus = "pending" | "running" | "done" | "cached" | "skipped" | "failed";

export interface StepRun {
  id: string;
  stage: "read";
  label: string;
  status: RunStatus;
  seconds: number | null;
  detail: string;
  inputs: Group[];
  outputs: Group[];
  warnings: string[];
}

export interface PipelineStage {
  id: "read";
  label: string;
  steps: StepRun[];
}

export interface Pipeline {
  stages: PipelineStage[];
  /** The design space is being read, or defined. */
  running: boolean;
}

export interface EntitySummary {
  id: string;
  kind: string;
  label: string;
  step: string;
  origin: Origin;
  status: string;
  show: Show;
}

export interface Proof {
  source: string;
  locator: string;
  detail: string;
  confidence: number | null;
}

export interface LinkRow {
  to: string;
  role: string;
  label: string;
  kind: string;
}

export interface BacklinkRow {
  from: string;
  role: string;
  label: string;
  kind: string;
}

/** One entity in full: the fields every entity has, its kind's own typed fields, and its links
 * both ways, each named. */
export interface EntityDetail extends EntitySummary {
  links: LinkRow[];
  backlinks: BacklinkRow[];
  evidence: Proof[];
  [field: string]: unknown;
}

/** What reading - or defining - the design space streams: what the rules say as they go, then how
 * it ended. */
export type PipelineEvent =
  | { type: "say"; detail: string }
  | { type: "done"; cached: boolean }
  | { type: "error"; message: string };

export interface RunRequest {
  /** Define it again by the rules - never over one the engineer brought. */
  again?: boolean;
}

/** Where metal helps, on each visible face of the design space, and the range to colour it by. */
export interface BenefitValues {
  range: [number, number];
  values: Float32Array;
}

async function benefit(): Promise<BenefitValues> {
  const response = await fetch("/api/designspace/values/benefit");
  if (!response.ok) throw new Error(`benefit: ${response.status}`);
  const buffer = await response.arrayBuffer();
  const view = new DataView(buffer);
  const range: [number, number] = [view.getFloat32(0, true), view.getFloat32(4, true)];
  return { range, values: new Float32Array(buffer.slice(8)) };
}

export const pipelineApi = {
  pipeline: () => getJson<Pipeline>("/api/pipeline"),
  /** Read the design space - or define it - reporting what the rules say as they go. */
  run: (request: RunRequest, onEvent: (event: PipelineEvent) => void) =>
    stream<PipelineEvent>("/api/pipeline/run", request, onEvent),
  entities: (query: { kind?: string; step?: string; ids?: string[]; text?: string; limit?: number }) => {
    const params = new URLSearchParams();
    if (query.kind) params.set("kind", query.kind);
    if (query.step) params.set("step", query.step);
    if (query.ids?.length) params.set("ids", query.ids.join(","));
    if (query.text) params.set("text", query.text);
    if (query.limit) params.set("limit", String(query.limit));
    return getJson<{ total: number; entities: EntitySummary[] }>(`/api/entities?${params}`);
  },
  entity: (id: string) => getJson<EntityDetail>(`/api/entities/${encodeURI(id)}`),
  /** The design space's cells. */
  cells: (): Promise<VoxelCells> => fetchVoxels("/api/designspace/cells/design"),
  benefit,
};
