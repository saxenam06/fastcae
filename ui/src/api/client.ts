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
  /** For a surface drawn over the part: how far each vertex stands off it, 0 on it to 255. */
  standing?: Uint8Array;
}

/** Where ribs may go, and whether a person has approved it. */
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

/** The engineer's words, verbatim, as a spec keeps them. */
export interface SpecWords {
  id: string;
  text: string;
}

export interface SpecLever {
  path: string;
  low: number;
  high: number;
  step: number;
  basis: string;
  cites: string[];
}

export interface SpecVersion {
  version: number;
  created: string;
  words: SpecWords[];
  placements: Record<string, unknown>[];
  rules: Record<string, unknown>;
  levers: SpecLever[];
  note: string;
  changes: string[];
}

export interface SpecInfo {
  spec: string | null;
  versions?: { version: number; created: string; note: string; changes: string[] }[];
  current?: SpecVersion;
}

/** What one free setting of a study may take: a range with a step, or choices. */
export interface StudyDomain {
  low: number | null;
  high: number | null;
  step: number | null;
  options: (string | number)[] | null;
  weights: number[] | null;
  unit: string;
  suggested: string | number | null;
  source: string;
  basis: string;
  cites: string[];
  confirmed: boolean;
}

export interface StudyBlock {
  id: string;
  add: string;
  where: { support: string[]; anchors: string[]; span: string };
  free: Record<string, StudyDomain>;
  cites: string[];
}

/** Something every design must satisfy, how firmly, and where it came from. */
export interface StudyConstraint {
  id: string;
  kind: string;
  refs: string[];
  params: Record<string, unknown>;
  block: string | null;
  strength: "hard" | "assumed" | "learned";
  source: string;
  basis: string;
  text: string;
  cites: string[];
  confirmed: boolean;
  /** Who wrote it into the study: the card, the agent from the engineer's words, the platform. */
  by: "" | "card" | "words" | "platform";
}

export interface StudyVersion {
  version: number;
  created: string;
  words: SpecWords[];
  blocks: StudyBlock[];
  constraints: StudyConstraint[];
  pull: { direction: number[] | null; along: string | null; source: string; basis: string } | null;
  target: { n: number; stratify: string; differ_by: number; seed: number };
  note: string;
  changes: string[];
}

/** The active study: the current version, what nothing enforces yet, what nobody confirmed. */
export interface StudyInfo {
  study: string | null;
  versions?: { version: number; created: string; note: string; changes: string[] }[];
  current?: StudyVersion;
  /** Every free setting and constraint in words: ``free[block][setting]``, ``constraints[id]``. */
  shown?: { free: Record<string, Record<string, string>>; constraints: Record<string, string> };
  open?: string[];
  assumed?: string[];
}

/** What happens during one message to the agent, as it happens. ``draft``: the agent filled the
 * card - the card shows what changed; this carries only what it asked the engineer to look at. */
export type AgentEvent =
  | { type: "token"; text: string }
  | { type: "tool_start"; id?: string; name: string; args?: unknown }
  | { type: "tool_result"; id?: string; name: string; summary: string }
  | { type: "draft"; attention: string[]; needed: string[] }
  | { type: "error"; message: string }
  | { type: "changed"; what: string[] }
  | { type: "done" };

/** One entry of the conversation, as the pane shows it. */
export type AgentMessage =
  | { role: "engineer"; text: string }
  | { role: "agent"; text: string }
  | { role: "tool"; name: string; args: unknown }
  | { role: "draft"; attention: string[]; needed: string[] };

/** One message to the agent, with the faces selected; each event is handed on as it arrives. */
async function chat(
  message: string,
  selection: number[],
  onEvent: (event: AgentEvent) => void,
): Promise<void> {
  const response = await fetch("/api/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, selection }),
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

export interface VerdictRow {
  check: string;
  outcome: Outcome;
  reason: string;
  rule: string;
  assumed?: boolean;
  cites?: string[];
  /** How long the check took, in seconds - two findings of one check share its time. */
  seconds?: number;
}

/** A design's verdict: the engineer's constraints first, then the checks - and, for a design made
 * from a study, what the study holds that nothing enforces yet. */
export interface Verdict {
  spec_version: number;
  study?: string;
  study_version?: number;
  fidelity: "preview" | "full";
  outcome: Outcome;
  ribs: number;
  pads?: number;
  holes?: number;
  added_cm3: number;
  mass_kg?: number | null;
  material?: string | null;
  seconds: number;
  /** How long each step of the build took, in seconds, by name. */
  steps?: Record<string, number>;
  /** The part's faces the design cuts - holes through them, faces thinned: the Field view hides
   * them and draws the design's own surface there. */
  cut_faces?: number[];
  constraints: VerdictRow[];
  checks: VerdictRow[];
  open?: string[];
  assumed?: string[];
}

/** Who a setting or a rule came from: the engineer - by hand, by selecting, or in words the agent
 * read - the drawing, the part measured, a default. */
export type Source = "you" | "selected" | "words" | "drawing" | "measured" | "default" | "cad";

/** What the study says of one setting of a block: fixed, or what it may take, and who said so. */
export interface StudySetting {
  name: string;
  label: string;
  says: string;
  source: string;
  fixed: boolean;
  basis: string;
  /** What it may take: a range with a step, or choices - to change by hand on the card. */
  domain: {
    low: number | null;
    high: number | null;
    step: number | null;
    options: (number | string)[] | null;
    /** Every choice the part offers - the engineer may have kept only some, in ``options``. */
    choices?: (number | string)[] | null;
    suggested: number | string | null;
    unit: string;
    /** For what the part is cast in: every material there is, to choose the one it is. */
    catalogue?: string[];
  };
  changed?: boolean;
  /** Varied over, never set: which free layout a design takes. */
  hidden?: boolean;
  /** A share of what each end meets, shown as a percentage. */
  percent?: boolean;
}

/** The variant being authored: its code, its name, whether it is kept yet, what it adds, how many
 * combinations it allows - null when free layouts give it no end - and the other variants a rule
 * of it may name. */
export interface VariantInfo {
  id: string;
  label: string;
  kept: boolean;
  kind: string | null;
  combinations: number | null;
  others: { id: string; label: string; kind: string }[];
}

/** A kind of rule a variant may hold: what it reads as, what it needs, whether it names faces. */
export interface OfferedRule {
  kind: string;
  says: string;
  needs: string[];
  names: boolean;
}

/** A variant as the library lists it. */
export interface VariantRow {
  id: string;
  label: string;
  kind: string;
  stand_on: string[];
  end_on: string[];
  combinations: number | null;
  version: number;
  created: string;
  changed: string;
  used_in: { run: string; name: string; version: number; changed_since: boolean }[];
}

/** A variant of the library, read only: what it adds and where, what it may vary, its rules. */
export interface VariantShown extends VariantRow {
  block: StudyBlockView;
  interfaces: number;
  names: Record<string, string>;
}

/** A piece repair left out, and the rule it broke. */
export interface LeftOut {
  block: string;
  what: "rib" | "hole";
  index: number;
  why: string;
}

/** The variant at a point that passes: its lines, what repair left out, what it made. */
export interface VariantSample extends CardPaths {
  values: Record<string, unknown>;
  about: string;
  left_out: LeftOut[];
  left_out_said: string;
  findings: { check: string; outcome: Outcome; reason: string; rule: string }[];
  tried: number;
  /** How it was drawn, in a sentence: its suggested point, or at random - and on which try. */
  drawn: string;
  waiting: string[];
}

/** What a campaign is: everything that decides its designs. */
export interface CampaignCard {
  name: string;
  variants: string[];
  checks_off: string[];
  method: "even" | "random" | "every";
  n: number;
  seed: number;
  /** 0: as drawn; k: keep k times n, then the n that differ most. */
  diverse: number;
}

/** How many designs a card's variants allow - null when free layouts give it no end. */
export interface CampaignEstimate {
  count: number | null;
  variants: { id: string; label: string; combinations: number | null }[];
  every: boolean;
}

/** A hundred designs drawn as the card would, placed, repaired and screened - nothing kept. */
export interface CampaignScreen {
  tried: number;
  passed: number;
  repaired: number;
  rejected: Record<string, number>;
  alone: Record<string, { kept: number; tried: number; rejected: Record<string, number> }>;
  seconds_per_design: number;
  estimate_seconds: number;
}

/** A campaign launched, as the list shows it. */
export interface LaunchedCampaign {
  run: string;
  id: string;
  name: string;
  variants: { id: string; label: string; kind: string; version: number }[];
  card: CampaignCard;
  count: number | null;
  created: string;
  state: "done" | "unfinished";
  made: number | null;
  tried: number | null;
  seconds: number | null;
  built: number;
  when: number;
}

/** What happens while a campaign runs, as it happens. */
export type CampaignEvent =
  | { type: "started"; run: string; id: string; name: string; n: number; count: number | null }
  | { type: "variant"; variant: string; label: string; kept: number; tried: number;
      rejected: Record<string, number> }  // prettier-ignore
  | ({ type: "progress"; repaired: number } & GoProgress)
  | ({ type: "design"; variants: string[] } & GoDesign)
  | ({ type: "done"; run: string; name: string; asked: number; repaired: number;
      layouts: number } & GoProgress)  // prettier-ignore
  | { type: "error"; message: string };

/** A rule as Design a variant shows it: in words, how firmly, from where and by whom, and whether
 * anything enforces it yet - and if not, until when. */
export interface StudyRule {
  id: string;
  kind: string;
  says: string;
  strength: "hard" | "assumed" | "learned";
  source: string;
  by: "" | "words" | "part" | "platform";
  refs: string[];
  params: Record<string, unknown>;
  basis: string;
  enforced: boolean;
  until: string;
  changed?: boolean;
}

/** Entities a block's ribs stand on or end on - named, or read off the part. */
export interface StudyEntities {
  refs: string[];
  read_off: boolean;
  changed?: boolean;
}

/** One block of the study: what it adds, what its ribs stand on, end on and keep clear of, its
 * settings and rules, and what it still needs or cannot be built for. */
export interface StudyBlockView {
  id: string;
  add: string;
  stand_on: StudyEntities;
  end_on: StudyEntities;
  /** What webs run to from what they end on: one side to the other, never within one. */
  other_side?: StudyEntities;
  keep_clear: StudyRule[];
  settings: StudySetting[];
  rules: StudyRule[];
  needed: string[];
  problems: string[];
  cannot: string | null;
  note: Record<string, string>;
  changed: boolean;
}

/** Design a variant: the draft of the study's next version, against the version last accepted. */
export interface StudyDraft {
  accepted: number | null;
  /** Null when the draft cannot be a version: a check refused it. */
  differs: boolean | null;
  changes: string[];
  cannot: string | null;
  refused: boolean;
  blocks: StudyBlockView[];
  /** Rules for the whole study. */
  rules: StudyRule[];
  /** The part's interfaces, closed by the platform. */
  interfaces: StudyRule[];
  rest: {
    prefer: { id: string; says: string; weight: number }[];
    objectives: { id: string; says: string; physical: boolean }[];
    pull: { says: string; source: string; basis: string } | null;
    target: { says: string };
  } | null;
  open: string[];
  assumed: string[];
  attention: string[];
  /** A few words for every face and feature the draft names. */
  names: Record<string, string>;
  /** Every run of Go kept for the project, newest first. */
  runs: KeptRun[];
  /** The variant being authored, when it is one. */
  variant: VariantInfo | null;
  /** The rules a variant may hold. */
  offered: OfferedRule[];
}

/** A campaign's run, kept in `_archived_designs`: its study and version, what it switched off, how
 * many designs it kept of how many tried, and how many of them are built. */
export interface KeptRun {
  run: string;
  name: string;
  study: string;
  version: number;
  made: number;
  tried: number;
  seconds: number;
  seed: number | null;
  off: Partial<CampaignOff>;
  built: number;
  where: string;
  when: number;
}

/** What one campaign switches off for itself alone: blocks and rules by id, checks by name. */
export interface CampaignOff {
  blocks: string[];
  rules: string[];
  checks: string[];
}

/** The stages a design goes through: paths placed and screened, field built, mesh, solver setup,
 * results. */
export type StageKey = "P" | "F" | "M" | "S" | "R";
/** How a stage came out - as screened, as checked - or ``done`` for one with no verdict, ``none``
 * for one not reached. */
export type StageState = "pass" | "warn" | "reject" | "done" | "none";

/** What a campaign runs, in the open. */
export interface CampaignPipeline {
  checks: { name: string; rule: string; source: string }[];
  /** The rules ribs, pads and holes are placed to, and what a block is read off the part as. */
  placement: { name: string; value: number | null; says: string }[];
  /** Every check a design goes through when its field is built. */
  full_checks: { name: string; rule: string }[];
  interfaces_clear_mm: number;
  knowledge: { name: string; value: number; source: string }[];
  materials: {
    id: string;
    name: string;
    density_kg_m3: number;
    min_wall_mm: number;
    source: string;
  }[];
  sampler: {
    says: string;
    pool: { least: number; most: number; tries: number };
    tries_per_design: number;
  };
  /** How a design whose pieces break a rule between them is mended. */
  repair: { says: string; rules: string[] };
  /** How designs may be drawn. */
  methods: { key: CampaignCard["method"]; label: string; says: string }[];
  stages: {
    key: StageKey;
    label: string;
    built: boolean;
    says: string;
    takes: string;
    gives: string;
  }[];
  runs: KeptRun[];
}

/** One design of a run, as the list of designs shows it. */
export interface RunRow {
  index: number;
  ribs: number;
  holes: number;
  pads: number;
  mass_kg: number;
  material: string | null;
  /** Where it comes among the designs that differ most - 1 the most - or null past them. */
  rank: number | null;
  stages: Record<StageKey, StageState>;
  short: [string, string][];
  /** The variants it holds, by code. */
  variants: string[];
  /** How many pieces repair left out of it. */
  left_out: number;
}

/** A run's designs as the list shows them, and how many are at each stage. */
export interface RunDesigns {
  run: string;
  version: number;
  of: number;
  /** How many hold the variant asked for - every one, when none is. */
  holding: number;
  variant: string | null;
  show: "varied" | "built" | "all";
  rows: RunRow[];
  counts: Record<StageKey, number>;
  /** The designs built, each with how its field was checked. */
  built: [number, StageState][];
  blocks: Record<string, string>;
  /** What the campaign calls each variant, by code. */
  labels: Record<string, string>;
}

/** One design of a run in full, with its verdict at each fidelity it was built at. */
export interface RunDesign extends GoDesign {
  run: string;
  rank: number | null;
  short: [string, string][];
  stages: Record<StageKey, StageState>;
  built: Partial<Record<"preview" | "full", Verdict>>;
  variants: string[];
  /** The campaign's variants this design leaves out. */
  absent: string[];
  labels: Record<string, string>;
  left_out: LeftOut[];
  left_out_said: string;
  recipe: string | null;
  seed: number | null;
  /** How the runner meshed and solved it, when it has. */
  solved: {
    outcome: "solved" | "set aside";
    reason: string;
    route: string;
    seconds: number | null;
    stages: Record<string, number>;
    mesh: { tets: number | null; unknowns: number | null; quality_min: number | null };
    mass_kg: number | null;
    signals: { name: string; component: string; value: number; unit: string; kind: string }[];
    solver: { name: string | null; residual: number | null };
  } | null;
}

/** A design seen along the pull: ribs and pads as lines - x1, y1, x2, y2, block - and holes as
 * circles - x, y, radius, block - in mm on the plan. */
export interface DesignPlan {
  ribs: [number, number, number, number, string][];
  pads: [number, number, number, number, string][];
  holes: [number, number, number, string][];
}

/** The designs Go kept that differ most, each as a plan with a few words a block, over the
 * outlines of what the study names and the part's bores. */
export interface VariedDesigns {
  of: number;
  run: string | null;
  designs: (GoDesign & { plan: DesignPlan; short: [string, string][] })[];
  outlines: [number, number, number, number][];
  /** xmin, ymin, xmax, ymax on the plan, in mm. */
  bounds: [number, number, number, number];
  blocks: Record<string, string>;
}

/** One design Go kept: its values, block by block, what every block made, how it screened and what
 * it weighs. */
export interface GoDesign {
  index: number;
  values: Record<string, Record<string, unknown>>;
  outcome: Outcome;
  ribs: number;
  pads: number;
  holes: number;
  mass_kg: number;
  added_kg: number;
  material: string | null;
  blocks: Record<string, { ribs?: number; holes?: number; pads?: number; says: string }>;
  about: Record<string, string>;
  findings: { check: string; outcome: Outcome; reason: string; rule: string }[];
}

/** How far Go has got: points tried, designs kept, and what screened the rest out. */
export interface GoProgress {
  tried: number;
  made: number;
  rejected: Record<string, number>;
  seconds: number;
}

/** A block of the study tried alone: how many of its points made something, of how many. */
export interface GoAlone {
  block: string;
  kept: number;
  tried: number;
  rejected: Record<string, number>;
}

/** What happens while Go makes designs, as it happens. */
export type GoEvent =
  | { type: "accepted"; version: number }
  | {
      type: "started";
      version: number;
      n: number;
      budget: number;
      waiting: string[];
      archive: string;
      run: string;
      off: CampaignOff;
    }
  | ({ type: "block" } & GoAlone)
  | ({ type: "progress" } & GoProgress)
  | ({ type: "design" } & GoDesign)
  | ({ type: "done"; asked: number; archive: string } & GoProgress)
  | { type: "error"; message: string };

/** Something done by hand on Design a variant. */
export interface HandAction {
  action:
    | "add"
    | "stand_on"
    | "end_on"
    | "other_side"
    | "setting"
    | "keep_clear"
    | "rule"
    | "drop"
    | "remove"
    | "confirm"
    | "designs";
  block?: string;
  add?: "ribs" | "webs" | "thicken" | "holes" | "material";
  refs?: string[];
  name?: string;
  value?: number | string;
  low?: number;
  high?: number;
  step?: number;
  options?: (number | string)[];
  clearance_mm?: number;
  rule?: string;
  /** For ``rule``: the kind a variant holds, and what it needs. */
  kind?: string;
  params?: Record<string, number>;
  n?: number;
  seed?: number;
  selected?: number[];
}

/** One stretch of path the card's layout tried, just off the part, and what became of it. */
export interface PathLine {
  a: number[];
  b: number[];
  /** ``rib``, or why not: missed, keep_out, open_end, ended_elsewhere, too_short, no_height. */
  outcome: string;
  /** For what is made - a rib, a pad - how wide it is, and which way it stands. */
  mm?: number;
  up?: number[];
}

/** Where the card would put ribs, before anything is made. */
export interface CardPaths {
  lines: PathLine[];
  ribs: number;
  pads?: number;
  holes?: number;
  paths: number;
  summary: string;
}

/** A face clicked on the part, and the angle it is grown by - zero for the face alone. */
export interface Seed {
  face: number;
  angle: number;
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

/** A campaign: many designs from the study - as many as its target asks for, unless ``n`` says -
 * spread from ``seed``, with what ``off`` names switched off for this campaign alone; each design
 * handed on as it is kept. */
async function go(
  campaign: { n: number | null; seed?: number | null; off?: Partial<CampaignOff> },
  onEvent: (event: GoEvent) => void,
): Promise<void> {
  return stream("/api/study/go", campaign, onEvent);
}

/** A campaign launched from its card; each variant pooled and each design kept handed on as it
 * happens. */
async function launch(card: CampaignCard, onEvent: (event: CampaignEvent) => void): Promise<void> {
  return stream("/api/campaign/go", card, onEvent);
}

/** Events a route streams, one JSON object a ``data:`` line, each handed on as it arrives. */
async function stream<T>(path: string, body: unknown, onEvent: (event: T) => void): Promise<void> {
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

async function deleteJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { method: "DELETE" });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${path}: ${response.status} ${text}`);
  }
  return response.json() as Promise<T>;
}

const variantPath = (id: string) => `/api/variants/${encodeURIComponent(id)}`;

/** A run's name in a path: it is one folder's name, and may hold spaces. */
const runPath = (run: string) => `/api/runs/${encodeURIComponent(run)}`;

export const api = {
  campaign: () => getJson<CampaignPipeline>("/api/campaign"),
  campaigns: () => getJson<LaunchedCampaign[]>("/api/campaigns"),
  estimateCampaign: (card: CampaignCard) =>
    postJson<CampaignEstimate>("/api/campaign/estimate", card),
  screenCampaign: (card: CampaignCard) => postJson<CampaignScreen>("/api/campaign/screen", card),
  launch,
  variants: () => getJson<{ variants: VariantRow[]; authoring: string | null }>("/api/variants"),
  variant: (id: string) => getJson<VariantShown>(variantPath(id)),
  variantDraft: () => getJson<{ draft: StudyDraft }>("/api/variant/draft"),
  newVariant: () => postJson<{ draft: StudyDraft }>("/api/variants/new", {}),
  openVariant: (id: string) => postJson<{ draft: StudyDraft }>(`${variantPath(id)}/open`, {}),
  handVariant: (action: HandAction) =>
    postJson<{ draft: StudyDraft }>("/api/variant/hand", action),
  sampleVariant: (another = false, seed?: number) =>
    postJson<VariantSample>("/api/variant/sample", { another, seed: seed ?? null }),
  saveVariant: (label: string | null) =>
    postJson<{ variant: string; version: number; label: string; draft: StudyDraft;
      variants: VariantRow[] }>("/api/variant/save", { label }),  // prettier-ignore
  discardVariant: () => postJson<{ draft: StudyDraft }>("/api/variant/discard", {}),
  duplicateVariant: (id: string) =>
    postJson<{ id: string; variants: VariantRow[] }>(`${variantPath(id)}/duplicate`, {}),
  deleteVariant: (id: string) => deleteJson<{ variants: VariantRow[] }>(variantPath(id)),
  runs: () => getJson<KeptRun[]>("/api/runs"),
  runDesigns: (
    run: string,
    show: "varied" | "built" | "all",
    k = 30,
    offset = 0,
    limit = 200,
    variant: string | null = null,
  ) =>
    getJson<RunDesigns>(
      `${runPath(run)}/designs?show=${show}&k=${k}&offset=${offset}&limit=${limit}` +
        (variant ? `&variant=${encodeURIComponent(variant)}` : ""),
    ),
  runDesign: (run: string, index: number) =>
    getJson<RunDesign>(`${runPath(run)}/designs/${index}`),
  buildRunDesign: (run: string, index: number, fidelity: "preview" | "full") =>
    postJson<RunDesign>(`${runPath(run)}/designs/${index}/build`, { fidelity }),
  runDesignMesh: (run: string, index: number, fidelity: "preview" | "full") =>
    fetchMesh(`${runPath(run)}/designs/${index}/mesh?fidelity=${fidelity}`),
  runDesignCells: (run: string, index: number, fidelity: "preview" | "full") =>
    fetchVoxels(`${runPath(run)}/designs/${index}/cells?fidelity=${fidelity}`),
  studyDraft: () => getJson<{ draft: StudyDraft }>("/api/study/draft"),
  acceptStudy: () => postJson<{ version: number; draft: StudyDraft }>("/api/study/accept", {}),
  undoStudy: () => postJson<{ draft: StudyDraft }>("/api/study/undo", {}),
  dropRule: (id: string) => postJson<{ draft: StudyDraft }>("/api/study/rules/drop", { id }),
  handStudy: (action: HandAction) => postJson<{ draft: StudyDraft }>("/api/study/hand", action),
  variedDesigns: (k: number, run?: string | null) =>
    getJson<VariedDesigns>(
      `/api/study/varied?k=${k}` + (run ? `&run=${encodeURIComponent(run)}` : ""),
    ),
  studyPaths: (which: { draft?: boolean; design?: number; run?: string | null } = {}) =>
    postJson<CardPaths>("/api/study/paths", which),
  studyDesign: (fidelity: "preview" | "full", design?: number, run?: string | null) =>
    postJson<Verdict>("/api/study/design", { fidelity, design: design ?? null, run: run ?? null }),
  go,
  spec: () => getJson<SpecInfo>("/api/spec"),
  specDesign: (fidelity: "preview" | "full", levers: Record<string, number> = {}) =>
    postJson<Verdict>("/api/spec/design", { fidelity, levers }),
  study: () => getJson<StudyInfo>("/api/study"),
  chat,
  newChat: () => postJson<{ thread: string }>("/api/agent/new", {}),
  agentHistory: () =>
    getJson<{ thread: string; messages: AgentMessage[] }>("/api/agent/history"),
  selectRefs: (refs: string[]) => postJson<Selection>("/api/select/refs", { refs }),
  currentDesign: () => getJson<Verdict>("/api/designs/current"),
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
  selectSeeds: (seeds: Seed[]) =>
    postJson<Selection>("/api/select/seeds", {
      seeds: seeds.map((s) => ({ face_id: s.face, grow_deg: s.angle })),
    }),
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
  approveZone: (id: string, approved: boolean) =>
    postJson<ZonesInfo>(`/api/zones/${encodeURIComponent(id)}`, { approved }),
  approveProtected: (approved: boolean) => postJson<ZonesInfo>("/api/protected", { approved }),
  formations: () => getJson<Formations>("/api/formations"),
  openSpace: (spacingMm?: number) =>
    postJson<SpaceInfo>("/api/designspace", { spacing_mm: spacingMm ?? null }),
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
