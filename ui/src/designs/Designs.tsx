/**
 * Generate: designs made in the design space, every stage of every one in view.
 *
 * **Campaign** - the campaigns kept, and a new one planned from what the deck offers: every load mix
 * at every budget. A campaign shows as a grid - a design a row, a stage a column - each cell saying
 * where that stage is and what it found, filled in as the runner makes them.
 *
 * **Designs** - one design, stage by stage, on the canvas each stage belongs to:
 * - *Optimisation*: where metal could go - the design space on the candidate rib planes - and the
 *   metal the optimiser had put there at any iteration, beside how its compliance and volume went;
 * - *Ribs*: each plane's metal read as rib plates, their outlines drawn over it;
 * - *CAD*: the plates fused into the part's CAD, the new faces over the part;
 * - *Mesh* and *Solve results*: the design's CAD meshed face by face, and the deck's answer on it.
 *
 * Nothing here is part-specific: the mixes, the stages and their numbers are whatever the campaign
 * made.
 */

import { RibPlanPage } from "./RibPlan";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Mesh, VoxelCells } from "../api/client";
import type { Values } from "../api/simulate";
import { Provenance } from "../input/shared";
import type { Skin } from "../render/fe";
import type { LineSet, VoxelLayer } from "../render/renderer";
import { CameraLink, FeStage } from "../stage/FeStage";
import type { Hovered } from "../stage/FeStage";
import { Legend, typicalRange } from "../stage/Legend";
import { SPACE_TINT } from "../pipeline/spaceLayers";
import type {
  Campaign,
  Campaigns,
  Design,
  DesignSummary,
  FinLedger,
  FinsAtStage,
  FinState,
  Iteration,
  StageId,
  StageState,
  Target,
} from "./api";
import { designsApi } from "./api";

export type DesignTab = StageId;

export const DESIGN_TABS: { id: DesignTab; label: string }[] = [
  { id: "optimise", label: "Optimisation" },
  { id: "ribs", label: "Path" },
  { id: "cad", label: "CAD" },
  { id: "mesh", label: "Mesh" },
  { id: "solve", label: "Solve results" },
];

const TAB_LABELS: Partial<Record<StageId, string>> = {
  optimise: "Optimisation",
  solve: "Solve results",
};

/** The tabs a campaign's designs are looked at in: the campaign's own stages, in its own order. */
export function tabsFor(campaign: Campaign | null): { id: DesignTab; label: string }[] {
  const own = campaign?.stages;
  if (!own?.length) return DESIGN_TABS;
  return own.map((s) => ({ id: s.id, label: TAB_LABELS[s.id] ?? s.label }));
}

/** The stages of a network design that are drawn as fins on the part: everything before the ribs
 * are built. */
export const FIN_TABS = new Set<DesignTab>(["seed", "pass", "oracle", "chooser", "polish"]);

/** Whether a stage is looked at on the part's canvas, rather than on the mesh's. */
export function onPart(tab: DesignTab): boolean {
  return tab !== "mesh" && tab !== "solve";
}

/** Each fin state's colour, the same on the canvas, in the legend and on the card. */
export const FIN_COLOURS: Record<FinState, [number, number, number]> = {
  seeded: [0.45, 0.5, 0.6],
  moved: [0.16, 0.45, 0.75],
  passed: [0.1, 0.55, 0.3],
  refused: [0.8, 0.2, 0.15],
  kept: [0.1, 0.55, 0.3],
  dropped: [0.7, 0.72, 0.75],
  built: [0.1, 0.1, 0.12],
};

const STATE_WORDS: Record<FinState, string> = {
  seeded: "seeded",
  moved: "moved",
  passed: "pass",
  refused: "refused",
  kept: "kept",
  dropped: "dropped",
  built: "built",
};

/** The metal a design adds: teal, a colour nothing else uses. */
export const METAL_TINT: [number, number, number] = [0.055, 0.431, 0.455];
/** Where the optimiser could have put metal and did not: the rib planes, pale. */
export const PLANES_TINT: [number, number, number] = [0.8, 0.82, 0.86];
const PLATE_COLOUR = [0.85, 0.33, 0.1];

// --- the campaigns ----------------------------------------------------------------------------------

export interface CampaignsState {
  data: Campaigns | null;
  error: string | null;
  campaign: Campaign | null;
  selectCampaign: (id: string | null) => void;
  design: string | null;
  selectDesign: (id: string | null) => void;
  refresh: () => Promise<void>;
  /** Some design is still being made. */
  busy: boolean;
}

export function useCampaigns(active: boolean, project: string | null): CampaignsState {
  const [data, setData] = useState<Campaigns | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [design, setDesign] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setData(await designsApi.campaigns());
      setError(null);
    } catch (caught) {
      setError(String(caught));
    }
  }, []);

  // Start again only when the engineer opens a DIFFERENT project - not when the session blinks.
  // The server is polled, and it can answer "no project" for a moment: it restarts whenever a
  // source file is saved, and a request can simply fail. Clearing on that would throw away the
  // design being looked at, several times an hour, for no reason the engineer can see.
  const opened = useRef<string | null>(project);
  useEffect(() => {
    if (project === null || project === opened.current) return;
    opened.current = project;
    setData(null);
    setSelected(null);
    setDesign(null);
  }, [project]);

  const busy = useMemo(
    () =>
      Boolean(data?.job) ||
      (data?.campaigns ?? []).some((c) =>
        c.designs.some((d) => Object.values(d.stages).some((s) => s.status === "running")),
      ),
    [data],
  );

  useEffect(() => {
    if (!active || !project) return;
    void refresh();
    if (!busy) return;
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(timer);
  }, [active, project, busy, refresh]);

  const campaigns = data?.campaigns ?? [];
  const campaign =
    selected === "new" ? null : (campaigns.find((c) => c.id === selected) ?? campaigns[0] ?? null);

  return {
    data,
    error,
    campaign,
    selectCampaign: setSelected,
    design,
    selectDesign: setDesign,
    refresh,
    busy,
  };
}

const STATUS_WORDS: Record<string, string> = {
  pending: "to do",
  running: "running",
  done: "done",
  failed: "failed",
};

function stageTime(s: StageState | undefined): string {
  if (!s || s.seconds === undefined) return "";
  const t = s.seconds;
  return t < 60 ? `${t.toFixed(0)} s` : `${Math.floor(t / 60)} min ${Math.round(t % 60)} s`;
}

function progress(d: DesignSummary): number {
  return Object.values(d.stages).filter((s) => s.status === "done").length;
}

export function CampaignRail({
  state,
  onNew,
}: {
  state: CampaignsState;
  onNew: () => void;
}) {
  const campaigns = state.data?.campaigns ?? [];
  return (
    <nav className="pipeline">
      <header className="pipeline-head">
        <span>Campaigns</span>
        <button className="link" onClick={onNew}>
          + new
        </button>
      </header>
      {state.error ? <div className="pipeline-error">{state.error}</div> : null}
      {!campaigns.length ? <div className="rail-note">No campaign yet.</div> : null}
      {campaigns.map((c) => {
        const done = c.designs.reduce((n, d) => n + progress(d), 0);
        const count = c.stages?.length || (state.data?.stages.length ?? 5);
        const total = c.designs.length * count;
        return (
          <button
            key={c.id}
            className="campaign-row"
            data-active={state.campaign?.id === c.id}
            onClick={() => state.selectCampaign(c.id)}
          >
            <span className="campaign-name">{c.name}</span>
            <span className="dim num">
              {c.designs.length} designs · {Math.round((100 * done) / Math.max(total, 1))} %
            </span>
            <span className="campaign-dots">
              {c.designs.map((d) => (
                <i
                  key={d.id}
                  data-status={d.failed ? "failed" : progress(d) >= count ? "done" : "running"}
                  title={d.name}
                />
              ))}
            </span>
          </button>
        );
      })}
    </nav>
  );
}

/** A campaign as a grid - a design a row, a stage a column - or, for a new one, the plan. */
export function CampaignPage({
  state,
  onOpen,
}: {
  state: CampaignsState;
  onOpen: (design: string) => void;
}) {
  const campaign = state.campaign;
  if (!campaign)
    return (
      <RibPlanPage
        onLaunched={() => {
          state.selectCampaign(null);
          void state.refresh();
        }}
      />
    );
  const stages = campaign.stages?.length ? campaign.stages : (state.data?.stages ?? []);
  const job = state.data?.job;
  return (
    <div className="campaign-page">
      <header className="campaign-head">
        <h2>{campaign.name}</h2>
        <span className="dim">
          {new Date(campaign.made * 1000).toLocaleString("en-GB")} · {campaign.designs.length} designs
        </span>
        {job ? <span className="campaign-job">{job.message ?? job.state}</span> : null}
      </header>
      <div className="campaign-grid-wrap">
        <table className="campaign-grid">
          <thead>
            <tr>
              <th>design</th>
              <th>load mix</th>
              <th className="num">metal</th>
              {state.data?.target ? <th>vs {state.data.target.name}</th> : null}
              {stages.map((s) => (
                <th key={s.id}>{s.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {campaign.designs.map((d) => (
              <tr key={d.id} onClick={() => onOpen(d.id)} data-failed={Boolean(d.failed)}>
                <td>
                  <b>#{d.index}</b> {d.name}
                </td>
                <td className="dim" title={d.mix.words}>
                  {d.mix.words}
                </td>
                <td className="num">{d.budget_L.toFixed(1)} L</td>
                {state.data?.target ? (
                  <td>
                  {d.vs_target || d.objective ? (
                    <VsTarget shares={d.vs_target} objective={d.objective} />
                  ) : (
                    <span className="dim">–</span>
                  )}
                </td>
                ) : null}
                {stages.map((s) => {
                  const st = d.stages[s.id as StageId];
                  return (
                    <td key={s.id} className="stage-cell" data-status={st?.status ?? "pending"} title={st?.detail}>
                      <i className="dot" />
                      <span className="stage-cell-text">
                        {st?.status === "done" || st?.status === "running"
                          ? (st.detail ?? STATUS_WORDS[st.status])
                          : STATUS_WORDS[st?.status ?? "pending"]}
                      </span>
                      <span className="dim num">{stageTime(st)}</span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="dim campaign-note">
        {campaign.about ??
          "Each design: optimised on the voxel grid for its load mix and volume of metal, only on the rib planes the design space offers; read as rib plates; built as CAD fused into the part; meshed face by face as the deck was; solved with cuDSS."}{" "}
        Click a design to see every stage.
      </p>
      <TradeOff designs={campaign.designs} onOpen={onOpen} target={state.data?.target ?? null} />
    </div>
  );
}

/** What each solved design bought: metal added against how much of the part's strain energy
 * under the deck is left - lower is stiffer - the bare part at the top left. */
/** What a design bought, against the production housing under the same loads: the objective it was
 * judged on, the gear-mesh misalignment most of it is, and the metal it cost. Shown as the change,
 * so a minus is always an improvement and nobody has to remember which way 96 % points. */
function VsTarget({
  shares,
  objective,
  name,
}: {
  shares: DesignSummary["vs_target"];
  objective?: DesignSummary["objective"];
  name?: string;
}) {
  const items: [string, number | undefined, string][] = [
    ["J", objective?.j_share, "the objective: robust gear-mesh lead, deflection and stress"],
    ["lead", objective?.lead_share, "the gear mesh's misalignment across its face, robust over the load band"],
    ["mass", shares?.added_kg, "the metal the ribs add"],
  ];
  const shown = items.filter((x): x is [string, number, string] => typeof x[1] === "number");
  if (!shown.length) return null;
  return (
    <span className="vs-target" title={name ? `against the ${name}, under the same loads` : undefined}>
      {shown.map(([k, v, why]) => (
        <span key={k} className="vs-pill" data-better={v < 0.98} data-worse={v > 1.02} title={why}>
          {k} {v > 1 ? "+" : ""}
          {Math.round((v - 1) * 100)}%
        </span>
      ))}
    </span>
  );
}

function TradeOff({
  designs,
  onOpen,
  target,
}: {
  designs: DesignSummary[];
  onOpen: (design: string) => void;
  target: Target | null;
}) {
  const solved = designs
    .map((d) => ({ d, h: d.metrics?.headline }))
    .filter((x): x is { d: DesignSummary; h: { work_share: number; added_kg: number } } =>
      Boolean(x.h && typeof x.h.work_share === "number" && typeof x.h.added_kg === "number"),
    );
  if (!solved.length) return null;
  const w = 460;
  const h = 240;
  const left = 48;
  const bottom = 34;
  const maxKg = Math.max(...solved.map((x) => x.h.added_kg), 1) * 1.15;
  const minShare = Math.min(...solved.map((x) => x.h.work_share), 1) - 0.05;
  const lo = Math.max(0, Math.floor(minShare * 10) / 10);
  const x = (kg: number) => left + (kg / maxKg) * (w - left - 16);
  const y = (share: number) => 10 + ((1 - share) / (1 - lo)) * (h - bottom - 10);
  const ticks = [lo, (lo + 1) / 2, 1];
  return (
    <figure className="trade-off">
      <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label="metal added against strain energy left, per design">
        <line x1={left} y1={h - bottom} x2={w - 8} y2={h - bottom} stroke="currentColor" strokeOpacity="0.35" />
        <line x1={left} y1={10} x2={left} y2={h - bottom} stroke="currentColor" strokeOpacity="0.35" />
        {ticks.map((t) => (
          <g key={t}>
            <line x1={left - 4} y1={y(t)} x2={w - 8} y2={y(t)} stroke="currentColor" strokeOpacity="0.08" />
            <text x={left - 6} y={y(t) + 3} fontSize="10" textAnchor="end" fill="currentColor">
              {Math.round(t * 100)} %
            </text>
          </g>
        ))}
        <text x={left} y={h - 8} fontSize="10" fill="currentColor">0 kg</text>
        <text x={w - 8} y={h - 8} fontSize="10" textAnchor="end" fill="currentColor">
          +{Math.round(maxKg)} kg added
        </text>
        <circle cx={x(0)} cy={y(1)} r="4" fill="none" stroke="currentColor" />
        <text x={x(0) + 8} y={y(1) + 4} fontSize="10" fill="currentColor">the part</text>
        {target?.headline?.work_share !== undefined && target.headline.added_kg !== undefined ? (
          <g className="trade-target">
            <rect
              x={x(target.headline.added_kg) - 5}
              y={y(target.headline.work_share) - 5}
              width="10"
              height="10"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            />
            <text
              x={x(target.headline.added_kg) - 9}
              y={y(target.headline.work_share) + 4}
              fontSize="10.5"
              textAnchor="end"
              fill="currentColor"
            >
              {target.name}
            </text>
          </g>
        ) : null}
        {solved.map(({ d, h: m }) => (
          <g key={d.id} className="trade-point" onClick={() => onOpen(d.id)}>
            <circle cx={x(m.added_kg)} cy={y(m.work_share)} r="5" />
            {/* Named on the side with room: left of a point near the right edge. */}
            <text
              x={x(m.added_kg) + (x(m.added_kg) > 0.6 * w ? -8 : 8)}
              y={y(m.work_share) + 4}
              fontSize="10.5"
              textAnchor={x(m.added_kg) > 0.6 * w ? "end" : "start"}
              fill="currentColor"
            >
              #{d.index} {d.name}
            </text>
          </g>
        ))}
      </svg>
      <figcaption className="dim">
        Strain energy under the deck left, as a share of the bare part's - lower is stiffer - against the metal
        each design adds, from each design's own CAD solved by cuDSS. Click a point to open the design.
      </figcaption>
    </figure>
  );
}

// --- one design ----------------------------------------------------------------------------------

export function DesignsRail({ state }: { state: CampaignsState }) {
  const campaign = state.campaign;
  if (!campaign) return <div className="rail-note">No campaign yet: plan one on Campaign.</div>;
  return (
    <nav className="pipeline">
      <header className="pipeline-head">
        <span>{campaign.name}</span>
      </header>
      {campaign.designs.map((d) => (
        <button
          key={d.id}
          className="design-row"
          data-active={state.design === d.id}
          onClick={() => state.selectDesign(d.id)}
        >
          <span className="design-row-head">
            <b>#{d.index}</b> {d.name}
          </span>
          <span className="design-stages">
            {tabsFor(campaign).map((s) => (
              <i
                key={s.id}
                data-status={d.stages[s.id]?.status ?? "pending"}
                title={`${s.label}: ${d.stages[s.id]?.detail ?? ""}`}
              />
            ))}
          </span>
          {d.counts ? <CountPills counts={d.counts} /> : null}
          {d.vs_target || d.objective ? (
            <VsTarget shares={d.vs_target} objective={d.objective} name={state.data?.target?.name} />
          ) : null}
          {d.failed ? <span className="design-failed">{d.failed}</span> : null}
        </button>
      ))}
    </nav>
  );
}

/** The same reasons counted, the commonest first - for a hover. */
function tally(reasons: string[]): string {
  const counts = new Map<string, number>();
  for (const r of reasons) counts.set(r, (counts.get(r) ?? 0) + 1);
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([why, n]) => `${n} × ${why}`)
    .join(" · ");
}

/** A network against the target: on the cubes after its polish, and on the mesh once solved. It
 * beats the target only with a lower largest displacement and no more metal. */
function AgainstTarget({
  cubes,
  mesh,
}: {
  cubes: NonNullable<Design["against_target"]>;
  mesh: Design["vs_target"] | null;
}) {
  const moved = mesh?.largest_displacement_mm;
  const added = mesh?.added_kg;
  const solved = moved !== undefined && added !== undefined;
  const beats = solved ? moved < 1 && added <= 1 : cubes.beats;
  const percent = (share: number) => `${share < 1 ? "−" : "+"}${Math.abs(Math.round((share - 1) * 100))} %`;
  return (
    <div className="card-pad against-target">
      <span className="vs-pill" data-better={beats} data-worse={!beats}>
        {beats ? "beats the target" : "does not beat the target"}
        <span className="dim"> {solved ? "on the mesh" : "on the cubes"}</span>
      </span>
      <dl className="fields-list">
        {solved ? (
          <>
            <dt>mesh</dt>
            <dd className="num">
              {percent(moved)} displacement · {percent(added)} metal
            </dd>
          </>
        ) : null}
        <dt>cubes</dt>
        <dd
          className="num"
          title={
            cubes.margin
              ? `the cubes flatter a rib network ${cubes.margin.toFixed(2)} times more than they flatter the target`
              : undefined
          }
        >
          {cubes.largest_mm.toFixed(2)} mm <span className="dim">target {cubes.target_largest_mm.toFixed(2)}</span> ·{" "}
          {cubes.metal_L.toFixed(1)} L <span className="dim">of {cubes.target_metal_L.toFixed(1)}</span>
        </dd>
      </dl>
    </div>
  );
}

/** How many of a network design's fins went how far, as pills. */
function CountPills({ counts }: { counts: NonNullable<DesignSummary["counts"]> }) {
  return (
    <span className="count-pills">
      <span className="vs-pill" title="fins laid down as the seed">{counts.seeded} seeded</span>
      <span className="vs-pill" title="fins the oracle passed after the pass">{counts.passed} pass</span>
      <span className="vs-pill" title="fins the chooser kept as the network">{counts.chosen} kept</span>
      <span className="vs-pill" title="fins built as ribs after the polish">{counts.built} built</span>
    </span>
  );
}

/** A design read from the server, again while any of its stages is running. */
export function useDesign(id: string | null): Design | null {
  const [design, setDesign] = useState<Design | null>(null);
  const running = design ? Object.values(design.stages).some((s) => s.status === "running") : false;
  useEffect(() => {
    if (!id) {
      setDesign(null);
      return;
    }
    let live = true;
    let arrived = false;
    const read = () =>
      designsApi
        .design(id)
        .then((d) => {
          if (!live) return;
          arrived = true;
          setDesign(d);
        })
        .catch(() => undefined);
    void read();
    // Keep asking while the design is still being made, and until the first answer arrives at all:
    // a request that lands while the server is restarting simply fails, and without this the panel
    // would stay empty until the engineer thought to click the design again.
    const timer = window.setInterval(() => {
      if (running || !arrived) void read();
    }, 3000);
    return () => {
      live = false;
      window.clearInterval(timer);
    };
  }, [id, running]);
  return design && design.id === id ? design : null;
}

/** What the part's canvas draws for a design's stage: cells, plate outlines, the CAD's new faces. */
export function useDesignCanvas(
  design: Design | null,
  tab: DesignTab,
  iteration: number,
  showSpace: boolean,
  space: VoxelLayer[],
  showPlanes = false,
): {
  layers: VoxelLayer[];
  lines: LineSet | null;
  overlay: Mesh | null;
  fins: FinsAtStage | null;
  error: string | null;
} {
  const [cells, setCells] = useState<VoxelCells | null>(null);
  const [planes, setPlanes] = useState<VoxelCells | null>(null);
  const [overlay, setOverlay] = useState<Mesh | null>(null);
  const [fins, setFins] = useState<FinsAtStage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const id = design?.id ?? null;
  const has = design?.files ?? {};
  const want = tab === "optimise" ? `voxels:${iteration}` : tab === "ribs" ? "fine" : null;

  // A network design's fins at the stage looked at: their runs, each in the colour of what
  // happened to it there.
  useEffect(() => {
    if (!id || !FIN_TABS.has(tab) || !has["fins.npz"]) {
      setFins(null);
      return;
    }
    let live = true;
    designsApi
      .fins(id, tab)
      .then((f) => live && setFins(f))
      .catch((e) => live && setError(String(e)));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, tab, has["fins.npz"]]);

  useEffect(() => {
    if (!id || !want) {
      setCells(null);
      return;
    }
    if ((want === "fine" && !has["fine.npz"]) || (want !== "fine" && !has["optimise.npz"])) return;
    let live = true;
    const read = want === "fine" ? designsApi.fine(id) : designsApi.voxels(id, iteration);
    read.then((c) => live && setCells(c)).catch((e) => live && setError(String(e)));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, want, has["fine.npz"], has["optimise.npz"]]);

  useEffect(() => {
    if (!id || tab !== "optimise" || !showPlanes || !has["optimise.npz"]) {
      setPlanes(null);
      return;
    }
    let live = true;
    designsApi
      .domain(id, iteration)
      .then((c) => live && setPlanes(c))
      .catch(() => live && setPlanes(null));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, tab, iteration, showPlanes, has["optimise.npz"]]);

  useEffect(() => {
    if (!id || tab !== "cad" || !has["cad.npz"]) {
      setOverlay(null);
      return;
    }
    let live = true;
    designsApi
      .cad(id)
      .then((m) => live && setOverlay(m))
      .catch((e) => live && setError(String(e)));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, tab, has["cad.npz"]]);

  const lines = useMemo(() => {
    if (FIN_TABS.has(tab)) {
      if (!fins || fins.stage !== tab) return null;
      return finLines(fins);
    }
    if (tab !== "ribs" || !design?.plates) return null;
    const positions: number[] = [];
    const colours: number[] = [];
    for (const plate of design.plates.plates) {
      for (const loop of [plate.outline, ...(plate.holes ?? [])]) {
        const n = loop.length;
        for (let i = 0; i < n; i++) {
          positions.push(...loop[i], ...loop[(i + 1) % n]);
          colours.push(...PLATE_COLOUR, ...PLATE_COLOUR);
        }
      }
    }
    return { positions: new Float32Array(positions), colours: new Float32Array(colours) };
  }, [tab, design, fins]);

  const layers = useMemo(() => {
    const out: VoxelLayer[] = [];
    if (showSpace && (tab === "optimise" || tab === "ribs" || FIN_TABS.has(tab))) out.push(...space);
    if (planes && tab === "optimise") out.push({ key: "planes", cells: planes, tint: PLANES_TINT, alpha: 1 });
    if (cells && (tab === "optimise" || tab === "ribs")) {
      out.push({ key: "metal", cells, tint: METAL_TINT, alpha: 1 });
    }
    return out;
  }, [cells, planes, tab, showSpace, space]);

  return { layers, lines, overlay: tab === "cad" ? overlay : null, fins, error };
}

/** A stage's fins as lines on the part: each fin's base and top along its run, its two ends, and a
 * rung every few stations so it reads as a standing rib - in the colour of its state. */
function finLines(fins: FinsAtStage): LineSet {
  const positions: number[] = [];
  const colours: number[] = [];
  const segment = (a: number[], b: number[], c: number[]) => {
    positions.push(...a, ...b);
    colours.push(...c, ...c);
  };
  for (const fin of fins.fins) {
    const colour = FIN_COLOURS[fin.state] ?? FIN_COLOURS.seeded;
    const n = Math.min(fin.base.length, fin.top.length);
    for (let i = 0; i + 1 < n; i++) {
      segment(fin.base[i], fin.base[i + 1], colour);
      segment(fin.top[i], fin.top[i + 1], colour);
    }
    for (let i = 0; i < n; i += 6) segment(fin.base[i], fin.top[i], colour);
    if (n > 0) segment(fin.base[n - 1], fin.top[n - 1], colour);
  }
  return { positions: new Float32Array(positions), colours: new Float32Array(colours) };
}

const FIELDS = ["von Mises", "displacement", "DX", "DY", "DZ"] as const;
type FieldName = (typeof FIELDS)[number];
const UNIT: Record<FieldName, string> = { "von Mises": "MPa", displacement: "mm", DX: "mm", DY: "mm", DZ: "mm" };

/** A design's mesh, or the deck's answer on it: the deck's own canvas. */
export function DesignFe({ design, tab }: { design: Design; tab: "mesh" | "solve" }) {
  const link = useMemo(() => new CameraLink(), []);
  const [skin, setSkin] = useState<Skin | null>(null);
  const [values, setValues] = useState<Values | null>(null);
  const [field, setField] = useState<FieldName>("von Mises");
  const [edges, setEdges] = useState(tab === "mesh");
  const [range, setRange] = useState<[number, number] | null>(null);
  const [hovered, setHovered] = useState<Hovered | null>(null);
  const [error, setError] = useState<string | null>(null);
  const meshed = design.files["mesh.npz"];
  const solved = design.files["result.npz"];

  useEffect(() => setEdges(tab === "mesh"), [tab]);

  useEffect(() => {
    if (!meshed) return;
    let live = true;
    setSkin(null);
    designsApi
      .skin(design.id)
      .then((s) => live && setSkin(s))
      .catch((e) => live && setError(String(e)));
    return () => {
      live = false;
    };
  }, [design.id, meshed]);

  useEffect(() => {
    if (tab !== "solve" || !solved) return;
    let live = true;
    setRange(null);
    designsApi
      .field(design.id, field)
      .then((v) => live && setValues(v))
      .catch((e) => live && setError(String(e)));
    return () => {
      live = false;
    };
  }, [design.id, tab, field, solved]);

  const bbox = useMemo(() => boundsOf(skin), [skin]);
  const data = useMemo(() => dataRange(values), [values]);
  const typical = useMemo(() => typicalRange(values?.values ?? null), [values]);
  const shown = range ?? typical;
  if (!meshed) {
    return (
      <div className="stage-page">
        <div className="later">
          <h2>{tab === "mesh" ? "Mesh" : "Solve results"}</h2>
          <p>{design.stages.mesh?.detail ?? "Not meshed yet."}</p>
        </div>
      </div>
    );
  }
  return (
    <div className="fe-page">
      <div className="overlay">
        <button data-active={edges} onClick={() => setEdges(!edges)}>
          edges
        </button>
        {tab === "solve" ? (
          <span className="segmented">
            {FIELDS.map((f) => (
              <button key={f} data-active={field === f} onClick={() => setField(f)}>
                {f}
              </button>
            ))}
          </span>
        ) : null}
      </div>
      <FeStage
        skin={skin}
        values={tab === "solve" ? values : null}
        mode={tab === "solve" && values ? "contour" : "plain"}
        range={shown}
        edges={edges}
        showGlyphs={false}
        link={link}
        bbox={bbox}
        frameKey={design.id}
        onHover={setHovered}
        sectionSource={{
          key: `${design.id}:${tab === "solve" && solved ? field : "mesh"}`,
          fetch: (plane) => designsApi.section(design.id, plane, tab === "solve" && solved ? field : undefined),
        }}
        caption={
          <>
            <b>#{design.index}</b>{" "}
            {tab === "mesh" ? "second-order tets, face by face from its CAD" : "cuDSS, the deck carried onto it"}{" "}
            <Provenance kind="generated" />
          </>
        }
      />
      {tab === "solve" && values ? (
        <Legend title={field} unit={UNIT[field]} range={shown} data={data} bands={48} onRange={setRange} />
      ) : null}
      {tab === "solve" && !solved ? <div className="fe-note">{design.stages.solve?.detail ?? "not solved yet"}</div> : null}
      <div className="fe-readout">
        {hovered ? (
          <>
            <b>{hovered.name}</b> <span className="dim">{hovered.detail}</span>
          </>
        ) : (
          <span className="dim">drag orbit · shift-drag pan · wheel zoom</span>
        )}
      </div>
      {error ? <div className="fe-error">{error}</div> : null}
    </div>
  );
}

/** Over the part's canvas, for the optimisation, ribs and CAD stages: what is drawn, the iteration
 * shown, and how the optimisation went. */
export function DesignOverlay({
  design,
  tab,
  iteration,
  onIteration,
  showSpace,
  onShowSpace,
  showPart,
  onShowPart,
  showPlanes,
  onShowPlanes,
  fins = null,
}: {
  design: Design;
  tab: DesignTab;
  iteration: number;
  onIteration: (i: number) => void;
  showSpace: boolean;
  onShowSpace: (on: boolean) => void;
  showPart: boolean;
  onShowPart: (on: boolean) => void;
  showPlanes: boolean;
  onShowPlanes: (on: boolean) => void;
  fins?: FinsAtStage | null;
}) {
  // each continuous stage has a history of its own: the pass's, the polish's, or the one
  // optimisation a library design ran
  const history =
    tab === "pass"
      ? (design.pass?.history ?? [])
      : tab === "polish"
        ? (design.polish?.history ?? [])
        : tab === "optimise"
          ? (design.optimise?.history ?? [])
          : [];
  const steps = Math.max(history.length - 1, 0);
  const [playing, setPlaying] = useState(false);
  const shown = iteration < 0 ? steps - 1 : iteration;
  const timer = useRef<number | null>(null);
  useEffect(() => {
    if (!playing) return;
    timer.current = window.setInterval(() => {
      onIteration(shown + 1 >= steps ? 0 : shown + 1);
    }, 700);
    return () => {
      if (timer.current !== null) window.clearInterval(timer.current);
    };
  }, [playing, shown, steps, onIteration]);
  const swatch = (c: number[]) => `rgb(${c.map((v) => Math.round(v * 255)).join(",")})`;
  const stage = design.stages[tab] ?? design.stages[tab === "ribs" ? "ribs" : "cad"];
  const planeCount = (design.optimise?.stats?.planes as unknown[] | undefined)?.length ?? 0;
  const finTab = FIN_TABS.has(tab);
  // which states this stage's fins can be in, in the order they read: what stands, then what
  // was set aside
  const states = finTab && fins ? [...new Set(fins.fins.map((f) => f.state))] : [];
  const tally = (s: FinState) => (fins ? fins.fins.filter((f) => f.state === s).length : 0);
  return (
    <>
      <div className="overlay">
        <button data-active={showPart} onClick={() => onShowPart(!showPart)}>
          part
        </button>
        {tab !== "cad" ? (
          <button data-active={showSpace} onClick={() => onShowSpace(!showSpace)}>
            <i className="swatch" style={{ background: swatch(SPACE_TINT) }} /> design space
          </button>
        ) : null}
        {tab === "optimise" && planeCount ? (
          <button
            data-active={showPlanes}
            onClick={() => onShowPlanes(!showPlanes)}
            title="Where metal could go: the design space on the candidate rib planes"
          >
            <i className="swatch" style={{ background: swatch(PLANES_TINT) }} /> rib planes
          </button>
        ) : null}
        {finTab ? (
          states.map((s) => (
            <span key={s} className="legend-chip" title={STATE_TITLES[s]}>
              <i className="swatch" style={{ background: swatch(FIN_COLOURS[s]) }} />
              {tally(s)} {STATE_WORDS[s]}
            </span>
          ))
        ) : (
          <span className="legend-chip">
            <i className="swatch" style={{ background: swatch(METAL_TINT) }} />
            {tab === "optimise" ? "metal added" : tab === "ribs" ? "metal, and its plates" : "the design's new faces"}
          </span>
        )}
        {tab === "cad" && design.files["design.step"] ? (
          <a className="button-link" href={designsApi.stepUrl(design.id)}>
            STEP
          </a>
        ) : null}
      </div>
      {finTab && fins ? <FinReasons fins={fins} /> : null}
      {(tab === "optimise" || tab === "pass" || tab === "polish") && history.length ? (
        <div className="optimise-panel">
          <div className="optimise-controls">
            <button onClick={() => setPlaying(!playing)}>{playing ? "❚❚" : "▶"}</button>
            <input
              type="range"
              min={0}
              max={Math.max(steps - 1, 0)}
              value={Math.max(shown, 0)}
              onChange={(e) => {
                setPlaying(false);
                onIteration(Number(e.target.value));
              }}
              aria-label="iteration"
            />
            <span className="num">
              iteration {Math.max(shown, 0) + 1} of {steps}
            </span>
          </div>
          <History history={history} at={Math.max(shown, 0) + 1} unit={tab === "optimise" ? "%" : "J"} />
        </div>
      ) : null}
      <div className="space-readout">
        <span>{stage?.detail ?? "not made yet"}</span>
      </div>
    </>
  );
}

const STATE_TITLES: Record<FinState, string> = {
  seeded: "laid down as the seed, before the loads moved it",
  moved: "where the pass left it",
  passed: "the oracle found nothing against it",
  refused: "the oracle refused it: hover the fin's row on the card for the reason",
  kept: "the chooser kept it in the network",
  dropped: "the chooser left it out: the card says which rule",
  built: "built as a rib after the polish",
};

/** Why fins were refused or dropped at this stage, tallied by reason: a pill each. */
function FinReasons({ fins }: { fins: FinsAtStage }) {
  const reasons = new Map<string, number>();
  for (const f of fins.fins) {
    if (!f.reason) continue;
    const key = f.reason.split(":")[0].split(" for ")[0].slice(0, 40);
    reasons.set(key, (reasons.get(key) ?? 0) + 1);
  }
  if (!reasons.size) return null;
  return (
    <div className="fin-reasons">
      {[...reasons.entries()]
        .sort((a, b) => b[1] - a[1])
        .map(([why, n]) => (
          <span key={why} className="vs-pill" data-worse="true">
            {n} {why}
          </span>
        ))}
    </div>
  );
}

/** How an optimisation went: the objective - compliance against the bare part's - and the metal
 * added, iteration by iteration. */
function History({ history, at, unit = "%" }: { history: Iteration[]; at: number; unit?: "%" | "J" }) {
  const w = 280;
  const h = 110;
  const pad = 26;
  const n = history.length;
  const x = (i: number) => pad + (i / Math.max(n - 1, 1)) * (w - pad - 8);
  // a history written by another optimiser may lack a number: draw what is there, never crash
  const num = (v: unknown): number => (typeof v === "number" && Number.isFinite(v) ? v : 0);
  const maxV = Math.max(...history.map((r) => num(r.volume_L)), 1e-9);
  // a share runs 0 to 1; an objective in its own units is drawn against its largest value
  const top = unit === "%" ? 1 : Math.max(...history.map((r) => num(r.objective)), 1e-9);
  const yObj = (v: number) => 8 + (1 - num(v) / top) * (h - 30);
  const yVol = (v: number) => 8 + (1 - num(v) / maxV) * (h - 30);
  const path = (f: (r: Iteration) => number) =>
    history.map((r, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${f(r).toFixed(1)}`).join(" ");
  const last = history[Math.min(at, n - 1)];
  // What a step recorded about how it ran differs by what made it - a free voxel optimisation
  // counts the cells it changed and its CG iterations, a rib sizing has neither - so say what is
  // there and leave out what is not.
  const count = (v: number | undefined) => (typeof v === "number" ? v.toLocaleString("en-GB") : null);
  const ran = [
    count(last?.changed) && `${count(last?.changed)} cells changed`,
    count(last?.cg_iterations) && `${count(last?.cg_iterations)} CG iterations`,
    typeof last?.seconds === "number" ? `${last.seconds} s` : null,
  ].filter(Boolean) as string[];
  return (
    <figure className="history">
      <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label="compliance and metal added by iteration">
        <line x1={pad} y1={h - 22} x2={w - 8} y2={h - 22} stroke="currentColor" strokeOpacity="0.3" />
        <path d={path((r) => yObj(r.objective))} fill="none" stroke="#b30026" strokeWidth="1.8" />
        <path d={path((r) => yVol(r.volume_L))} fill="none" stroke="rgb(14,110,116)" strokeWidth="1.8" strokeDasharray="4 3" />
        {n ? <line x1={x(Math.min(at, n - 1))} y1={6} x2={x(Math.min(at, n - 1))} y2={h - 22} stroke="currentColor" strokeOpacity="0.5" /> : null}
        <text x={pad} y={h - 8} fontSize="10" fill="currentColor">0</text>
        <text x={w - 8} y={h - 8} fontSize="10" textAnchor="end" fill="currentColor">
          {n - 1}
        </text>
        <text x={2} y={12} fontSize="10" fill="#b30026">{unit === "%" ? "1.0" : top.toFixed(1)}</text>
      </svg>
      <figcaption>
        <span style={{ color: "#b30026" }}>
          — objective{" "}
          {last ? (unit === "%" ? `${Math.round(num(last.objective) * 100)} %` : `J ${num(last.objective).toFixed(2)}`) : ""}
        </span>{" "}
        ·{" "}
        <span style={{ color: "rgb(14,110,116)" }}>- - metal {last ? `${num(last.volume_L).toFixed(1)} L` : ""}</span>
        {ran.length ? ` · ${ran.join(" · ")}` : ""}
      </figcaption>
    </figure>
  );
}

/** The design's card: what it was made for, and what each stage found. */
export function DesignCard({ design, onCollapse }: { design: Design | null; onCollapse: () => void }) {
  return (
    <div className="entity-card">
      <div className="entity-card-bar">
        <span className="dim">design</span>
        <button className="icon" onClick={onCollapse} title="Fold the card away">
          ›
        </button>
      </div>
      <div className="entity-card-scroll">
        {!design ? (
          <div className="dim card-pad">Pick a design.</div>
        ) : (
          <>
            <header className="entity-head">
              <div className="entity-kind">
                <span className="kind-chip">design #{design.index}</span>
                <span className="origin-pill" data-origin="generated">
                  generated
                </span>
                {design.failed ? <span className="status-pill">failed</span> : null}
              </div>
              <h2 className="entity-title">{design.name}</h2>
              <div className="entity-made">{design.mix.words}</div>
              {design.why ? <p className="design-why">{design.why}</p> : null}
            </header>
            <details className="card-section" open>
              <summary>Made for</summary>
              <dl className="fields-list">
                <dt>metal</dt>
                <dd className="num">
                  {design.budget_L.toFixed(2)} L{" "}
                  <span className="dim">
                    {design.target?.metal_L
                      ? `(${Math.round((design.budget_L / design.target.metal_L) * 100)} % of the ${design.target.name}'s)`
                      : design.budget_share
                        ? `(${Math.round(design.budget_share * 100)} % of the part)`
                        : ""}
                  </span>
                </dd>
                {(design.mix.cases ?? []).map((c) => (
                  <FragmentCase key={c.name} name={c.name} forces={c.forces} />
                ))}
                {design.load_case ? (
                  <>
                    <dt>load case</dt>
                    <dd title={design.load_case.words}>{design.load_case.name}</dd>
                  </>
                ) : null}
              </dl>
            </details>
            <details className="card-section" open>
              <summary>Stages</summary>
              <dl className="fields-list">
                {(design.stage_order ?? DESIGN_TABS).map((s) => (
                  <StageRow key={s.id} name={s.label} state={design.stages[s.id]} />
                ))}
              </dl>
            </details>
            {design.counts && design.network ? (
              <details className="card-section" open>
                <summary>Network</summary>
                <div className="card-pad">
                  <CountPills counts={design.counts} />
                </div>
                <dl className="fields-list">
                  <dt>kept</dt>
                  <dd className="num">
                    {design.network.kept.length} fins · {design.network.metal_L.toFixed(2)} L
                  </dd>
                  {design.placement ? (
                    <>
                      <dt>placement</dt>
                      <dd
                        className="num"
                        title={tally(design.placement.refused.map((r) => r.why))}
                      >
                        {design.placement.refused.length} refused{" "}
                        <span className="dim">of {design.placement.rays} rays a volume</span>
                      </dd>
                    </>
                  ) : null}
                </dl>
                {design.against_target ? (
                  <AgainstTarget cubes={design.against_target} mesh={design.vs_target ?? null} />
                ) : null}
              </details>
            ) : null}
            {design.fins?.length ? <FinsSection fins={design.fins} /> : null}
            {design.optimise ? (
              <details className="card-section">
                <summary>Optimisation</summary>
                <dl className="fields-list">
                  <dt>iterations</dt>
                  <dd className="num">{(design.optimise.history?.length ?? 1) - 1}</dd>
                  {design.optimise.stats?.planes ? (
                    <>
                      <dt>rib planes</dt>
                      <dd className="num">
                        {(design.optimise.stats?.planes as unknown[] | undefined)?.length ?? 0}{" "}
                        <span className="dim">{String(design.optimise.stats?.domain_L)} L of the design space on them</span>
                      </dd>
                      <dt>rib</dt>
                      <dd className="num">{String(design.optimise.stats?.rib_mm)} mm thick</dd>
                    </>
                  ) : null}
                  <dt>cell</dt>
                  <dd className="num">{String(design.optimise.stats?.cell_mm)} mm</dd>
                  <dt>thinnest member</dt>
                  <dd className="num">{String(design.optimise.stats?.filter_mm)} mm</dd>
                  {Object.entries(design.optimise.history?.[design.optimise.history.length - 1]?.compliance ?? {}).map(
                    ([k, v]) => (
                      <FragmentRow key={k} label={`compliance, ${k}`} value={`${Math.round(v * 100)} % of the bare part's`} />
                    ),
                  )}
                </dl>
              </details>
            ) : null}
            {design.plates ? (
              <details className="card-section">
                <summary>
                  Plates <span className="count">{design.plates.plates.length}</span>
                </summary>
                {design.plates.covered != null ? (
                  <p className="dim card-pad">
                    covering {Math.round(design.plates.covered * 100)} % of the optimised metal
                  </p>
                ) : null}
                <table className="plate-table num">
                  <thead>
                    <tr>
                      <th />
                      <th>plane</th>
                      <th>holes</th>
                      <th>L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {design.plates.plates.map((p) => (
                      <tr key={p.name}>
                        <td>{p.name}</td>
                        <td>
                          {p.stats.plane ??
                            (p.stats.angle_deg !== undefined
                              ? `${p.stats.volume} · ${p.stats.family ?? ""} ${p.stats.angle_deg}° · ${p.stats.form ?? ""}`
                              : "–")}
                        </td>
                        <td>{p.holes?.length ?? 0}</td>
                        <td>{(p.stats.litres ?? 0).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            ) : null}
            {design.checks ? <ChecksSection checks={design.checks} /> : null}
            {design.solve ? <SolveSection solve={design.solve} target={design.target?.name} /> : null}
            {design.failed ? <div className="card-error">{design.failed}</div> : null}
          </>
        )}
      </div>
    </div>
  );
}

function FragmentCase({ name, forces }: { name: string; forces: Record<string, [number, number, number]> }) {
  const total = Object.values(forces).reduce((t, f) => t + Math.hypot(...f), 0);
  return (
    <>
      <dt>{name}</dt>
      <dd>
        {Object.keys(forces).length} loaded groups <span className="dim num">{(total / 1000).toFixed(0)} kN in all</span>
      </dd>
    </>
  );
}

function FragmentRow({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  );
}

function StageRow({ name, state }: { name: string; state: StageState | undefined }) {
  return (
    <>
      <dt>
        <i className="dot" data-status={state?.status ?? "pending"} /> {name}
      </dt>
      <dd>
        {state?.detail ?? STATUS_WORDS[state?.status ?? "pending"]}{" "}
        <span className="dim num">{stageTime(state)}</span>
      </dd>
    </>
  );
}

/** Every seeded fin and how far it went: its value, and a pill for each verdict it met, the reason
 * on hover. Sorted by value, the worthiest first. */
function FinsSection({ fins }: { fins: FinLedger[] }) {
  const rows = [...fins].sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
  const fate = (f: FinLedger): { state: FinState; reason: string } => {
    const chooser = f.chooser ?? "";
    if (chooser.startsWith("refused by the oracle")) return { state: "refused", reason: chooser.slice(23) };
    if (chooser && chooser !== "kept") return { state: "dropped", reason: chooser };
    const later = (f.verdicts ?? []).filter((v) => v.stage !== "numbers");
    const bad = later.find((v) => !v.ok);
    if (chooser === "kept" && bad) return { state: "refused", reason: bad.reason };
    if (chooser === "kept") return { state: "built", reason: "" };
    return { state: "seeded", reason: "" };
  };
  return (
    <details className="card-section">
      <summary>
        Fins <span className="count">{fins.length}</span>
      </summary>
      <table className="plate-table num fins-table">
        <thead>
          <tr>
            <th>fin</th>
            <th>value</th>
            <th>L</th>
            <th>fate</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((f) => {
            const { state, reason } = fate(f);
            return (
              <tr key={f.id}>
                <td title={f.kind}>{f.id}</td>
                <td>{typeof f.value === "number" ? f.value.toFixed(3) : "–"}</td>
                <td>{typeof f.metal_L === "number" ? f.metal_L.toFixed(2) : "–"}</td>
                <td>
                  <span className="fin-pill" data-state={state} title={reason || STATE_TITLES[state]}>
                    {STATE_WORDS[state]}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </details>
  );
}

function ChecksSection({ checks }: { checks: NonNullable<Design["checks"]> }) {
  const rows = Object.entries(checks).flatMap(([stage, list]) => list.map((r) => ({ stage, ...r })));
  const bad = rows.filter((r) => !r.ok).length;
  return (
    <details className="card-section" open={bad > 0}>
      <summary>
        Checks <span className="count">{bad ? `${bad} failed` : `${rows.length} passed`}</span>
      </summary>
      <table className="plate-table num checks-table">
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.stage}.${r.name}`} data-ok={r.ok}>
              <td>{r.ok ? "✓" : "✗"}</td>
              <td className="dim">{r.stage}</td>
              <td>{r.name}</td>
              <td>{String(r.value)}</td>
              <td className="dim">{String(r.limit)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

function SolveSection({ solve, target }: { solve: Record<string, unknown>; target?: string }) {
  const rows = (solve.signals as SignalRow[] | undefined) ?? [];
  return (
    <details className="card-section" open>
      <summary>Solved</summary>
      <dl className="fields-list">
        {Object.entries(solve)
          .filter(([k, v]) => k !== "signals" && (typeof v === "number" || typeof v === "string"))
          .map(([k, v]) => (
            <FragmentRow key={k} label={k.replace(/_/g, " ")} value={typeof v === "number" ? v.toLocaleString("en-GB", { maximumSignificantDigits: 4 }) : String(v)} />
          ))}
      </dl>
      {rows.length ? (
        <table className="plate-table num">
          <thead>
            <tr>
              <th>signal</th>
              <th>design</th>
              {target ? <th>{target}</th> : null}
              {target ? <th title={`The design against the ${target}: below is better`}>vs {target}</th> : null}
              <th>part</th>
              <th title="How much the design moves the signal, against the bare part">change</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const change = changeOf(r.design, r.baseline, scaleOf(rows, r));
              const against = target ? changeOf(r.design, r.target, scaleOf(rows, r, "target")) : null;
              return (
                <tr key={`${r.name}.${r.component}`}>
                  <td>
                    {r.name} <span className="dim">{r.component}</span>
                  </td>
                  <td>{fmt(r.design)}</td>
                  {target ? <td>{fmt(r.target)}</td> : null}
                  {target ? (
                    <td
                      className="change"
                      data-sense={against === null ? "none" : against < -0.02 ? "less" : against > 0.02 ? "more" : "same"}
                    >
                      {against === null ? "–" : `${against > 0 ? "+" : ""}${Math.round(against * 100)} %`}
                    </td>
                  ) : null}
                  <td>{fmt(r.baseline)}</td>
                  <td className="change" data-sense={change === null ? "none" : change < -0.02 ? "less" : change > 0.02 ? "more" : "same"}>
                    {change === null ? "–" : `${change > 0 ? "+" : ""}${Math.round(change * 100)} %`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : null}
    </details>
  );
}

type SignalRow = { name: string; component: string; design: number; baseline: number; target?: number };

/** Which components a signal is compared within: a bearing's three displacements, its three
 * rotations, or a quantity of its own. */
function familyOf(component: string): string {
  if (/^D[XYZ]$/.test(component)) return "moves";
  if (/^DR[XYZ]$/.test(component)) return "turns";
  return component;
}

/** The size a signal is measured against: the largest of its family on the bare part. */
function scaleOf(rows: SignalRow[], row: SignalRow, against: "baseline" | "target" = "baseline"): number {
  const family = familyOf(row.component);
  return Math.max(
    ...rows
      .filter((r) => r.name === row.name && familyOf(r.component) === family)
      .map((r) => Math.abs(r[against] ?? 0)),
  );
}

/** How much a signal moved against the part's, as a share of the part's own; none where the part's
 * is a twentieth or less of its family's largest - a share of next to nothing means nothing. */
function changeOf(design: number | undefined, part: number | undefined, scale: number): number | null {
  if (design === undefined || part === undefined || !Number.isFinite(design) || !Number.isFinite(part)) return null;
  if (Math.abs(part) < 1e-9 || Math.abs(part) < 0.05 * scale) return null;
  return (Math.abs(design) - Math.abs(part)) / Math.abs(part);
}

function fmt(v: number | undefined): string {
  if (v === undefined || v === null || !Number.isFinite(v)) return "–";
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-3 || a >= 1e6)) return v.toExponential(2);
  return v.toLocaleString("en-GB", { maximumSignificantDigits: 4 });
}

function boundsOf(skin: Skin | null): number[] | null {
  if (!skin || !skin.positions.length) return null;
  const lo = [Infinity, Infinity, Infinity];
  const hi = [-Infinity, -Infinity, -Infinity];
  const p = skin.positions;
  for (let i = 0; i < p.length; i += 3) {
    for (let k = 0; k < 3; k++) {
      if (p[i + k] < lo[k]) lo[k] = p[i + k];
      if (p[i + k] > hi[k]) hi[k] = p[i + k];
    }
  }
  return [...lo, ...hi];
}

function dataRange(values: Values | null): [number, number] {
  if (!values) return [0, 1];
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values.values) {
    if (!Number.isFinite(v)) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  return lo === Infinity ? [0, 1] : lo === hi ? [lo, lo + 1e-12] : [lo, hi];
}
