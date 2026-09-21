// Designs made in the design space, as the server keeps them: campaigns, and every stage of every
// design - see src/fastcae/designs/ and src/fastcae/api/designs.py.

import { fetchMesh, fetchVoxels, getJson, type Mesh, type VoxelCells } from "../api/client";
import type { JobStatus, Values } from "../api/simulate";
import { fetchSection, fetchSkin, fetchValues, planeQuery } from "../api/simulate";
import type { Plane } from "../stage/sectionPlane";
import type { Skin } from "../render/fe";

/** A design's stages. A library design has five; a network design nine - the seed laid down, the
 * pass that moves every fin, the oracle that judges each, the chooser that keeps a network, the
 * polish with the topology fixed - then the ribs, CAD, mesh and solve both share. */
export type StageId =
  | "seed"
  | "pass"
  | "oracle"
  | "chooser"
  | "polish"
  | "optimise"
  | "ribs"
  | "cad"
  | "mesh"
  | "solve";
export type StageStatus = "pending" | "running" | "done" | "failed";

/** How many of a network design's fins went how far. */
export interface Counts {
  seeded: number;
  passed: number;
  chosen: number;
  built: number;
}

/** What happened to a fin at a stage: the state word the record uses, and the reason when it was
 * refused or dropped. */
export type FinState = "seeded" | "moved" | "passed" | "refused" | "kept" | "dropped" | "built";

export interface FinRun {
  id: string;
  kind?: string;
  value?: number | null;
  metal_L?: number | null;
  state: FinState;
  reason: string;
  /** The fin's run in the part's frame: along its floor, and along its top. */
  base: [number, number, number][];
  top: [number, number, number][];
}

export interface FinsAtStage {
  stage: StageId;
  fins: FinRun[];
  counts: Counts;
}

/** One seeded fin's line in the record's ledger: what it was, what it was worth, and every
 * verdict it met. */
export interface FinLedger {
  id: string;
  kind?: string;
  value?: number | null;
  metal_L?: number | null;
  chooser?: string;
  verdicts?: { stage: string; ok: boolean; reason: string; measured?: Record<string, number> }[];
}

export interface StageState {
  status: StageStatus;
  seconds?: number;
  detail?: string;
  started?: number;
}

export interface LoadCase {
  name: string;
  forces: Record<string, [number, number, number]>;
  weight: number;
}

export interface Mix {
  name: string;
  words: string;
  /** The load cases in full. A design record made by a rib campaign keeps the mix's name and words
   * only - the forces themselves belong to the deck, not to the design - so this is often absent. */
  cases?: LoadCase[];
}

export interface DesignSummary {
  id: string;
  index: number;
  name: string;
  budget_L: number;
  budget_share: number;
  stages: Record<StageId, StageState>;
  metrics: {
    headline?: { work_share?: number; largest_displacement_share?: number; added_kg?: number };
    [key: string]: unknown;
  } | null;
  failed: string | null;
  mix: { name: string; words: string };
  /** What the design was judged on, once solved: the objective and the misalignment most of it is,
   * each as a share of the production housing's under the same loads. */
  objective?: {
    j_robust: number;
    j_nominal?: number;
    lead_um?: number | null;
    ranked?: string | null;
    load_case?: string | null;
    j_share?: number;
    lead_share?: number;
  } | null;
  /** Why this design was tried - the reason whoever chose its settings gave. */
  why?: string | null;
  /** Failed a stage's checks, rather than an error. */
  rejected?: boolean | null;
  /** Its work, largest displacement and added mass as shares of the target's. */
  vs_target?: Partial<Record<"work_Nmm" | "largest_displacement_mm" | "added_kg", number>> | null;
  /** A network design: how many fins went how far. */
  counts?: Counts | null;
}

export interface Target {
  name: string;
  metal_L: number | null;
  objective?: { j_robust?: number | null; lead_um?: number | null; ranked?: string | null };
  headline?: { work_share?: number; largest_displacement_mm?: number; added_kg?: number; work_Nmm?: number };
  words?: string;
}

export interface CheckRow {
  name: string;
  value: number | string;
  limit: number | string;
  ok: boolean;
}

export interface Campaign {
  id: string;
  name: string;
  made: number;
  designs: DesignSummary[];
  /** What kind of campaign: ribs in the design volumes, or the older voxel layouts. */
  kind?: string;
  /** How its designs were made, in a few sentences. */
  about?: string;
  /** Its own stages, in its own order; the campaigns' shared list when absent. */
  stages?: { id: StageId; label: string }[];
}

export interface Campaigns {
  stages: { id: StageId; label: string }[];
  campaigns: Campaign[];
  job: JobStatus | null;
  target?: Target | null;
}

export interface PlannedDesign {
  name: string;
  mix: Mix;
  budget_share: number;
  budget_L: number;
}

export interface Iteration {
  iteration: number;
  cells: number;
  volume_L: number;
  objective: number;
  /** How the step ran. Only the free voxel optimisation records these; a rib network's sizing or a
   * plate run writes a step of its own shape, so anything reading them must cope without. */
  compliance?: Record<string, number>;
  changed?: number;
  cg_iterations?: number;
  seconds?: number;
}

export interface PlateRow {
  name: string;
  outline: [number, number, number][];
  holes?: [number, number, number][][];
  normal: [number, number, number];
  thickness_mm: number;
  stats: {
    kind?: string;
    plane?: string;
    litres?: number;
    cells?: number;
    holes?: number;
    /** A rib from a design volume: which volume, and its angle round the volume's axis. */
    volume?: string;
    angle_deg?: number;
    family?: string;
    form?: string;
  };
  coverage?: { part: number; design: number; outside: number };
}

export interface Design extends Omit<DesignSummary, "mix"> {
  mix: Mix;
  /** Which load case the design was sized against, when its campaign varied them. */
  load_case?: { name: string; words?: string; per_case_um?: Record<string, number> };
  optimise?: {
    /** What each generator records differs; read every part of this defensively. */
    history?: Iteration[];
    baseline_compliance?: Record<string, number>;
    stats?: Record<string, unknown>;
  };
  plates?: { plates: PlateRow[]; rib_mm?: number | null; covered?: number | null };
  cad?: Record<string, unknown>;
  solve?: Record<string, unknown>;
  files: Record<string, boolean>;
  checks?: Record<string, CheckRow[]>;
  target?: { name: string; metal_L: number | null; shares: Record<string, number> };
  /** The design's stages in the order its campaign made them. */
  stage_order?: { id: StageId; label: string }[];
  /** A network design: its ledger, the chooser's answer, and the two passes' histories. */
  counts?: Counts | null;
  fins?: FinLedger[];
  network?: { kept: string[]; score: number; metal_L: number; why: Record<string, string> };
  /** A network design read against the target on the cubes, after its polish. */
  against_target?: {
    largest_mm: number;
    target_largest_mm: number;
    metal_L: number;
    target_metal_L: number;
    margin?: number;
    beats: boolean;
    beats_by_the_margin?: boolean;
  };
  /** What the gate of placement refused when the network was seeded. */
  placement?: { rays: number; refused: { volume: string; why: string }[] };
  pass?: { history?: Iteration[] };
  polish?: { history?: Iteration[] };
}

const path = (id: string) => `/api/designs/${id}`;

export const designsApi = {
  campaigns: () => getJson<Campaigns>("/api/campaigns"),
  design: (id: string) => getJson<Design>(path(id)),
  /** A network design's fins at one of its stages, each with its run and its state there. */
  fins: (id: string, stage: StageId) => getJson<FinsAtStage>(`${path(id)}/fins?stage=${stage}`),
  voxels: (id: string, iteration = -1): Promise<VoxelCells> =>
    fetchVoxels(`${path(id)}/voxels?iteration=${iteration}`),
  domain: (id: string, iteration = -1): Promise<VoxelCells> =>
    fetchVoxels(`${path(id)}/domain?iteration=${iteration}`),
  fine: (id: string): Promise<VoxelCells> => fetchVoxels(`${path(id)}/fine`),
  cad: (id: string): Promise<Mesh> => fetchMesh(`${path(id)}/cad?show=new`),
  skin: (id: string): Promise<Skin> => fetchSkin(`${path(id)}/fe/mesh`),
  field: (id: string, name: string, vectors = false): Promise<Values> =>
    fetchValues(`${path(id)}/fe/field?name=${encodeURIComponent(name)}&vectors=${vectors}`),
  /** The design's mesh cut by a plane - with a field of its answer on the cut, when one is named. */
  section: (id: string, plane: Plane, name?: string) =>
    fetchSection(`${path(id)}/fe/section?${planeQuery(plane)}${name ? `&name=${encodeURIComponent(name)}` : ""}`),
  stepUrl: (id: string) => `${path(id)}/step`,
};
