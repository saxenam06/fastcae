// The pipeline as the server holds it: steps in two stages, the typed entities they produced, and
// the engineer's answers. The same JSON an agent reads - see src/fastcae/pipeline/entities.py.

import { fetchVoxels, getJson, postJson, stream, type VoxelCells } from "./client";

export type Origin = "imported" | "derived" | "inferred" | "confirmed" | "generated";

export type CanvasName = "drawing" | "cad" | "mesh" | "space" | "none";

/** Where an entity can be seen, and what to highlight there. */
export interface Show {
  canvas: CanvasName;
  faces: number[];
  page: number | null;
  text: string | null;
  group: string | null;
  layers: string[];
  paint: PaintKind | null;
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
  stage: "read" | "space";
  label: string;
  status: RunStatus;
  seconds: number | null;
  detail: string;
  inputs: Group[];
  outputs: Group[];
  warnings: string[];
}

export interface PipelineStage {
  id: "read" | "space";
  label: string;
  steps: StepRun[];
}

export interface Pipeline {
  stages: PipelineStage[];
  running: boolean;
  cached: boolean;
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

/** A question's own fields. */
export interface QuestionDetail extends EntityDetail {
  question_kind: string;
  text: string;
  detail: string;
  options: string[];
  meanwhile: string;
  answer: string | null;
}

/** What a run streams: each step as it starts and finishes, then how it ended. */
export type PipelineEvent =
  | {
      type: "step";
      id: string;
      label: string;
      status: RunStatus;
      seconds?: number;
      detail?: string;
    }
  | { type: "done"; cached: boolean }
  | { type: "error"; message: string };

export interface RunRequest {
  reuse?: boolean;
  inside?: boolean | null;
  panel_layer?: number | null;
  pocket_reach?: number | null;
}

/** Design-space layers of cells, as the server names them. */
export type LayerKey =
  | "part"
  | "plug"
  | "beyond"
  | "mating"
  | "ring"
  | "hole"
  | "buffer"
  | "waiting"
  | "cavity"
  | "leak"
  | "panel"
  | "pocket"
  | "allowed"
  | "unknown"
  | "benefit";

export type PaintKind = "thickness" | "cap" | "interface" | "sealing";

/** A per-face value: millimetres, or the group that froze or asked about a face. */
export interface FaceValues {
  kind: PaintKind;
  faces: Record<string, number | string>;
}

/** The benefit of metal on each visible face of the allowed space, and the range to colour it by. */
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
  /** Run the design-space stage - or read it back - reporting each step as it goes. */
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
  answer: (question: string, value: string | null) =>
    postJson<{ answers: Record<string, string>; rerun: string }>("/api/answers", { question, value }),
  cells: (layer: LayerKey): Promise<VoxelCells> => fetchVoxels(`/api/designspace/cells/${layer}`),
  benefit,
  faces: (kind: PaintKind) => getJson<FaceValues>(`/api/designspace/faces/${kind}`),
};
