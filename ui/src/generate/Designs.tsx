/**
 * Generate, Designs: every design a campaign kept, and how far each has got.
 *
 * On the left a run's designs - the ones that differ most, those built, or all of them a page at a
 * time - each with its stages as letters: P its paths placed and screened, F its field built and
 * checked, M meshed, S the solver set up, R results. In the middle the design at the stage chosen:
 * its paths on the part, its field, and - side by side as plans - the designs that differ most. On
 * the right what it is made of, how it screened, what it weighs, and its verdict once built; Build
 * field builds it from the study version the run was made from and keeps it beside the run, so its
 * F stays done.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import type {
  CardPaths,
  KeptRun,
  Mesh,
  RunDesign,
  RunDesigns,
  StageKey,
  VoxelCells,
} from "../api/client";
import { api } from "../api/client";
import type { LineSet } from "../render/renderer";
import {
  FindingLine,
  PathsKey,
  STAGE_KEYS,
  STAGE_NAMES,
  StageBadges,
  VerdictView,
  plain,
  stageSaid,
  toLines,
} from "../panel/shared";
import { DesignFe } from "./DesignFe";
import { Plans, blockColours } from "./Plans";

export type DesignTab = "paths" | "field" | "mesh" | "setup" | "results" | "plans";

/** The stages as tabs, each with the stage it shows - the plans are of the run, not a stage. */
export const DESIGN_TABS: { id: DesignTab; label: string; stage: StageKey | null }[] = [
  { id: "paths", label: "Paths", stage: "P" },
  { id: "field", label: "Field", stage: "F" },
  { id: "mesh", label: "Mesh", stage: "M" },
  { id: "setup", label: "Setup", stage: "S" },
  { id: "results", label: "Results", stage: "R" },
  { id: "plans", label: "Plans", stage: null },
];

/** Which of a run's designs the list shows. */
export type DesignShow = { kind: "varied"; k: number } | { kind: "built" } | { kind: "all"; offset: number };

const PAGE = 200;
const HOW_MANY = [20, 30, 50];

export interface Designs {
  runs: KeptRun[];
  run: string | null;
  openRun: (run: string) => void;
  show: DesignShow;
  setShow: (show: DesignShow) => void;
  /** Only the designs holding this variant, by code - or every design. */
  variant: string | null;
  setVariant: (variant: string | null) => void;
  listing: RunDesigns | null;
  selected: number | null;
  select: (index: number) => void;
  detail: RunDesign | null;
  tab: DesignTab;
  setTab: (tab: DesignTab) => void;
  paths: CardPaths | null;
  pathsNote: string | null;
  lines: LineSet | null;
  overlay: Mesh | null;
  /** The part's faces the design cuts - holes through them, faces thinned: hidden while its field
   * is shown, its own surface drawn there instead. */
  cutFaces: Set<number>;
  cells: VoxelCells | null;
  showCells: boolean;
  setShowCells: (on: boolean) => void;
  fieldNote: string | null;
  building: string | null;
  build: (fidelity: "preview" | "full") => Promise<void>;
  problem: string | null;
  reread: () => void;
}

/** The designs of the run open, and the one picked: read when the tab is open. */
export function useDesigns(active: boolean, project: string | null): Designs {
  const [runs, setRuns] = useState<KeptRun[]>([]);
  const [run, setRun] = useState<string | null>(null);
  const [show, setShow] = useState<DesignShow>({ kind: "varied", k: 30 });
  const [variant, setVariant] = useState<string | null>(null);
  const [listing, setListing] = useState<RunDesigns | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<RunDesign | null>(null);
  const [tab, setTab] = useState<DesignTab>("paths");
  const [paths, setPaths] = useState<CardPaths | null>(null);
  const [pathsNote, setPathsNote] = useState<string | null>(null);
  const [overlay, setOverlay] = useState<Mesh | null>(null);
  const [cells, setCells] = useState<VoxelCells | null>(null);
  const [showCells, setShowCells] = useState(false);
  const [fieldNote, setFieldNote] = useState<string | null>(null);
  const [building, setBuilding] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [stamp, setStamp] = useState(0);

  useEffect(() => {
    setRuns([]);
    setRun(null);
    setListing(null);
    setSelected(null);
    setDetail(null);
  }, [project]);

  // The runs kept: read each time the tab opens, since a campaign may have added one.
  useEffect(() => {
    if (!active || !project) return;
    api
      .runs()
      .then((found) => {
        setRuns(found);
        setRun((was) => (was && found.some((r) => r.run === was) ? was : (found[0]?.run ?? null)));
      })
      .catch((caught) => setProblem(plain(caught)));
  }, [active, project, stamp]);

  // The list: of the run open, as chosen.
  useEffect(() => {
    if (!active || !run) return;
    let live = true;
    const [kind, k, offset] =
      show.kind === "varied"
        ? (["varied", show.k, 0] as const)
        : show.kind === "built"
          ? (["built", 30, 0] as const)
          : (["all", 30, show.offset] as const);
    api
      .runDesigns(run, kind, k, offset, PAGE, variant)
      .then((reply) => {
        if (!live) return;
        setListing(reply);
        setProblem(null);
        setSelected((was) =>
          was !== null && reply.rows.some((r) => r.index === was)
            ? was
            : (reply.rows[0]?.index ?? null),
        );
      })
      .catch((caught) => live && setProblem(plain(caught)));
    return () => {
      live = false;
    };
  }, [active, run, show, variant, stamp]);

  // The design picked, in full.
  useEffect(() => {
    if (!run || selected === null) {
      setDetail(null);
      return;
    }
    let live = true;
    api
      .runDesign(run, selected)
      .then((reply) => live && setDetail(reply))
      .catch((caught) => live && setProblem(plain(caught)));
    return () => {
      live = false;
    };
  }, [run, selected, stamp]);

  // Its paths, on the part: placed again from its values, the first time in a while in minutes.
  useEffect(() => {
    setPaths(null);
    if (!active || tab !== "paths" || !run || selected === null) {
      setPathsNote(null);
      return;
    }
    let live = true;
    setPathsNote(
      "Reading its paths. A run kept without them is placed again: the first design of it drawn " +
        "opens the part on the run's grid, a few minutes; every one after, a second.",
    );
    api
      .studyPaths({ design: selected, run })
      .then((reply) => {
        if (!live) return;
        setPaths(reply);
        setPathsNote(null);
      })
      .catch((caught) => live && setPathsNote(plain(caught)));
    return () => {
      live = false;
    };
  }, [active, tab, run, selected]);

  // Its field, as kept when it was built: the surfaces it changes, and its new metal as cells.
  const fidelity = detail?.built.full ? "full" : "preview";
  const isBuilt = Boolean(detail && detail.stages.F !== "none");
  useEffect(() => {
    setOverlay(null);
    setCells(null);
    setFieldNote(null);
    // A design of the run open only: the one picked in the run before may still be in hand.
    if (!active || tab !== "field" || !run || !detail || detail.run !== run || !isBuilt) return;
    let live = true;
    setFieldNote("Reading its field.");
    const index = detail.index;
    Promise.all([
      api.runDesignMesh(run, index, fidelity),
      showCells ? api.runDesignCells(run, index, fidelity) : Promise.resolve(null),
    ])
      .then(([mesh, found]) => {
        if (!live) return;
        setOverlay(mesh);
        setCells(found);
        setFieldNote(null);
      })
      .catch((caught) => live && setFieldNote(plain(caught)));
    return () => {
      live = false;
    };
  }, [active, tab, run, detail, isBuilt, fidelity, showCells]);

  const openRun = useCallback((name: string) => {
    setRun(name);
    setSelected(null);
    setVariant(null);
    setShow({ kind: "varied", k: 30 });
    setStamp((n) => n + 1);
  }, []);

  const select = useCallback((index: number) => setSelected(index), []);

  const build = useCallback(
    async (level: "preview" | "full") => {
      if (!run || selected === null) return;
      setBuilding(
        level === "preview"
          ? "Building its field: faces moved, ribs and pads placed and joined, holes cut, then checked - a few minutes on this part."
          : "Building its field in full. Minutes on a large part.",
      );
      setProblem(null);
      try {
        const made = await api.buildRunDesign(run, selected, level);
        setDetail(made);
        setTab("field");
        setStamp((n) => n + 1);
      } catch (caught) {
        setProblem(plain(caught));
      } finally {
        setBuilding(null);
      }
    },
    [run, selected],
  );

  const lines = useMemo(() => (paths ? toLines(paths) : null), [paths]);
  const cutFaces = useMemo(
    () => new Set<number>(detail?.built[fidelity]?.cut_faces ?? []),
    [detail, fidelity],
  );

  return {
    runs,
    run,
    openRun,
    show,
    setShow,
    variant,
    setVariant,
    listing,
    selected,
    select,
    detail,
    tab,
    setTab,
    paths,
    pathsNote,
    lines,
    overlay,
    cutFaces,
    cells,
    showCells,
    setShowCells,
    fieldNote,
    building,
    build,
    problem,
    reread: () => setStamp((n) => n + 1),
  };
}

/** The rail: the run open, how many of its designs are at each stage, which to list - and the list. */
export function DesignsRail({ designs }: { designs: Designs }) {
  const { listing, show } = designs;
  const counts = listing?.counts;
  const colours = useMemo(() => blockColours(listing?.blocks ?? {}), [listing]);
  return (
    <nav className="index designs-rail">
      <section className="section">
        <header>Campaign</header>
        <div className="body">
          {designs.runs.length ? (
            <select
              className="run-select"
              value={designs.run ?? ""}
              onChange={(e) => designs.openRun(e.target.value)}
            >
              {designs.runs.map((run) => (
                <option key={run.run} value={run.run}>
                  {run.name} · {run.made.toLocaleString()} designs
                </option>
              ))}
            </select>
          ) : (
            <div className="card-note">No campaign launched yet - compose one on Campaign.</div>
          )}
          {counts ? (
            <div className="stage-counts">
              {STAGE_KEYS.map((key) => (
                <span key={key} className="stage-count" title={STAGE_NAMES[key]}>
                  <span className="stage-badge" data-state={counts[key] ? "done" : "none"}>
                    {key}
                  </span>
                  <span className="mono">{counts[key].toLocaleString()}</span>
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </section>
      <section className="section">
        <header>Show</header>
        <div className="body design-filters">
          <span className="segmented">
            {HOW_MANY.map((k) => (
              <button
                key={k}
                data-active={show.kind === "varied" && show.k === k}
                onClick={() => designs.setShow({ kind: "varied", k })}
                title={`The ${k} designs that differ most from each other`}
              >
                {k} most different
              </button>
            ))}
          </span>
          <span className="segmented">
            <button
              data-active={show.kind === "built"}
              onClick={() => designs.setShow({ kind: "built" })}
              title="The designs whose field is built"
            >
              built ({listing?.built.length ?? 0})
            </button>
            <button
              data-active={show.kind === "all"}
              onClick={() => designs.setShow({ kind: "all", offset: 0 })}
              title="Every design, a page at a time"
            >
              all
            </button>
          </span>
          {listing && Object.keys(listing.labels).length ? (
            <label className="variant-filter">
              <span className="dim">holding</span>
              <select
                value={designs.variant ?? ""}
                onChange={(e) => designs.setVariant(e.target.value || null)}
                aria-label="only the designs holding this variant"
              >
                <option value="">any variant</option>
                {Object.entries(listing.labels).map(([id, label]) => (
                  <option key={id} value={id}>
                    {id} · {label}
                  </option>
                ))}
              </select>
              {designs.variant ? (
                <span className="dim">
                  {" "}
                  {listing.holding.toLocaleString()} of {listing.of.toLocaleString()}
                </span>
              ) : null}
            </label>
          ) : null}
        </div>
      </section>
      <section className="section design-list">
        {listing && !listing.rows.length ? (
          <div className="body card-note">
            {show.kind === "built"
              ? "None of its designs is built yet: pick one and Build field on the right."
              : "No designs."}
          </div>
        ) : null}
        {listing?.rows.map((row) => (
          <button
            key={row.index}
            className="row design-row"
            data-active={designs.selected === row.index}
            onClick={() => designs.select(row.index)}
          >
            <StageBadges stages={row.stages} />
            <span className="design-name">
              <b>#{row.index + 1}</b>
              {row.rank !== null && row.rank <= 100 ? (
                <span className="rank" title="where it comes among the designs that differ most">
                  {row.rank}
                </span>
              ) : null}
            </span>
            <span className="design-detail">
              {row.ribs} ribs{row.holes ? ` · ${row.holes} holes` : ""}
              {row.pads ? ` · ${row.pads} pads` : ""} · {Math.round(row.mass_kg)} kg
              {row.left_out ? ` · ${row.left_out} left out` : ""}
            </span>
            {Object.keys(listing.labels).length ? (
              <span className="design-variants">
                {row.variants.map((id) => (
                  <span
                    key={id}
                    className="variant-dot"
                    style={{ background: colours[id] ?? "#888" }}
                    title={`${id} · ${listing.labels[id] ?? ""}`}
                  >
                    {id}
                  </span>
                ))}
              </span>
            ) : null}
          </button>
        ))}
        {show.kind === "all" && listing ? (
          <div className="body pager">
            <button
              disabled={show.offset === 0}
              onClick={() => designs.setShow({ kind: "all", offset: Math.max(0, show.offset - PAGE) })}
            >
              previous
            </button>
            <span className="dim">
              {(show.offset + 1).toLocaleString()}–
              {Math.min(show.offset + PAGE, listing.holding).toLocaleString()} of{" "}
              {listing.holding.toLocaleString()}
            </span>
            <button
              disabled={show.offset + PAGE >= listing.holding}
              onClick={() => designs.setShow({ kind: "all", offset: show.offset + PAGE })}
            >
              next
            </button>
          </div>
        ) : null}
      </section>
      {designs.problem ? <div className="body warn">{designs.problem}</div> : null}
    </nav>
  );
}

/** The stages as tabs above the design, each lit when the design has got that far. */
export function DesignTabs({ designs }: { designs: Designs }) {
  const stages = designs.detail?.stages;
  return (
    <nav className="stage-tabs design-tabs">
      {DESIGN_TABS.map((entry) => (
        <button
          key={entry.id}
          data-active={designs.tab === entry.id}
          onClick={() => designs.setTab(entry.id)}
          title={entry.stage ? STAGE_NAMES[entry.stage] : "the designs that differ most, as plans"}
        >
          {entry.stage && stages ? (
            <span className="stage-badge" data-state={stages[entry.stage]}>
              {entry.stage}
            </span>
          ) : null}
          {entry.label}
        </button>
      ))}
    </nav>
  );
}

/** What is over the part at each stage: the key to its paths, the layers of its field - or, for a
 * stage not built yet or the plans, a page of its own. */
export function DesignStage(props: { designs: Designs; showPart: boolean; onPart: (on: boolean) => void }) {
  const { designs } = props;
  const { tab, detail } = designs;
  if (!designs.run) {
    return (
      <div className="stage-page">
        <p className="card-note">No campaign launched yet. Compose one on Campaign.</p>
      </div>
    );
  }
  if (tab === "plans") {
    const k = designs.show.kind === "varied" ? designs.show.k : 30;
    return (
      <div className="stage-page">
        <Plans
          run={designs.run}
          k={k}
          selected={designs.selected}
          built={new Map(designs.listing?.built ?? [])}
          onPick={designs.select}
          onOpen={(index, to) => {
            designs.select(index);
            designs.setTab(to);
          }}
        />
      </div>
    );
  }
  if (tab === "mesh" || tab === "setup" || tab === "results") {
    const letter = { mesh: "M", setup: "S", results: "R" }[tab] as StageKey;
    if (detail && detail.stages[letter] === "pass") {
      return <DesignFe run={designs.run} index={detail.index} tab={tab} />;
    }
    const what = {
      mesh: "Its mesh: CGAL from its field, held to the solver deck mesh's sizes and two elements through every rib.",
      setup: "Its setup: the deck's supports, couplings and loads, carried to its mesh by the CAD faces they lie on.",
      results: "Its results: displacement and stress everywhere, and the deck's signals - solved by cuDSS.",
    }[tab];
    return (
      <div className="stage-page">
        <div className="later">
          <h2>{DESIGN_TABS.find((t) => t.id === tab)?.label} - not solved yet</h2>
          <p>{what}</p>
          <p className="dim">
            {detail?.solved?.outcome === "set aside"
              ? `The runner set it aside: ${detail.solved.reason}`
              : "Solve a campaign's designs on Campaign; the runner meshes, sets up and solves each."}
          </p>
        </div>
      </div>
    );
  }
  if (tab === "paths") {
    return (
      <div className="overlay design-key">
        <PathsKey paths={designs.paths} note={designs.pathsNote} folded />
      </div>
    );
  }
  // The field.
  return (
    <div className="overlay design-key">
      {!detail ? null : detail.stages.F === "none" ? (
        <div className="card-note">
          Its field is not built yet - Build field on the right builds it and keeps it.
        </div>
      ) : (
        <div className="layers inline-layers">
          <button
            data-on={props.showPart}
            onClick={() => props.onPart(!props.showPart)}
            title={
              designs.cutFaces.size
                ? `The part as its CAD describes it - the ${designs.cutFaces.size} faces the design cuts shown as its own surface`
                : "The part as its CAD describes it"
            }
          >
            <span className="swatch" style={{ background: "#a5a9a4" }} />
            part
          </button>
          <button data-on={true} disabled title="What the design adds and takes away">
            <span className="swatch" style={{ background: "#0e6e74" }} />
            surfaces it changes
          </button>
          <button data-on={designs.showCells} onClick={() => designs.setShowCells(!designs.showCells)}>
            <span className="swatch" style={{ background: "#0f3d91" }} />
            new metal, as cells
          </button>
          {designs.fieldNote ? <span className="card-note">{designs.fieldNote}</span> : null}
        </div>
      )}
    </div>
  );
}

/** The design picked: where it is in its stages, what it is made of, how it screened, what it
 * weighs - its verdict once built - and Build field. */
export function DesignReadout(props: { designs: Designs; onCollapse: () => void }) {
  const { designs } = props;
  const { detail, listing } = designs;
  const colours = useMemo(() => blockColours(listing?.blocks ?? {}), [listing]);
  return (
    <div className="rib-card readout-card">
      <header className="rib-card-head">
        <span className="card-title">
          {detail ? `Design #${detail.index + 1}` : "Design"}
        </span>
        {detail?.rank ? (
          <span className="chip" title="where it comes among the designs that differ most">
            {ordinal(detail.rank)} most different
          </span>
        ) : null}
        <button className="icon pane-fold" onClick={props.onCollapse} aria-label="Fold away">
          ›
        </button>
      </header>
      {!detail ? (
        <div className="card-note">Pick a design on the left.</div>
      ) : (
        <div className="rib-slots">
          <section className="rib-slot">
            <div className="readout-stages">
              {STAGE_KEYS.map((key) => (
                <div key={key} className="readout-stage">
                  <span className="stage-badge" data-state={detail.stages[key]}>
                    {key}
                  </span>
                  <span>{STAGE_NAMES[key]}</span>
                  <span className="dim">{stageSaid(detail.stages[key])}</span>
                </div>
              ))}
            </div>
            <div className="actions">
              <button
                className="primary"
                disabled={designs.building !== null}
                onClick={() => void designs.build("preview")}
                title="Build its field on the preview grid from the study version the run was made from, check it, and keep it beside the run"
              >
                {detail.stages.F !== "none" ? "Build its field again" : "Build field"}
              </button>
              <button
                disabled={designs.building !== null}
                onClick={() => void designs.build("full")}
                title="The same at full resolution - what a design is accepted at"
              >
                Full
              </button>
            </div>
            {designs.building ? <div className="card-note busy-note">{designs.building}</div> : null}
          </section>
          <section className="rib-slot">
            <header>
              <span className="slot-label">made of</span>
            </header>
            <div className="readout-made">
              {detail.short.map(([block, words]) => (
                <div key={block} className="made-row">
                  <b style={{ color: colours[block] ?? "inherit" }}>{block}</b>
                  {detail.labels[block] ? <span> {detail.labels[block]}</span> : null}
                  <span className="dim"> - {words}</span>
                  {detail.about[block] ? <div className="dim made-values">{detail.about[block]}</div> : null}
                </div>
              ))}
              {detail.absent.length ? (
                <div className="dim">
                  not in this design:{" "}
                  {detail.absent.map((id) => `${id} ${detail.labels[id] ?? ""}`.trim()).join(", ")}
                </div>
              ) : null}
              {detail.left_out_said ? <div className="card-note">{detail.left_out_said}</div> : null}
            </div>
            <div className="dim">
              {detail.ribs} ribs · {detail.pads} pads · {detail.holes} holes · {detail.mass_kg} kg{" "}
              {detail.material} · {detail.added_kg >= 0 ? "+" : ""}
              {detail.added_kg} kg on the part
            </div>
            {detail.recipe ? (
              <div className="dim mono recipe">
                recipe {detail.recipe} · seed {detail.seed}
              </div>
            ) : null}
          </section>
          <section className="rib-slot">
            <header>
              <span className="slot-label">screened</span>
              <span className="chip" data-outcome={detail.outcome}>
                {detail.outcome}
              </span>
            </header>
            {detail.findings.length ? (
              detail.findings.map((finding) => <FindingLine key={finding.check} row={finding} />)
            ) : (
              <div className="dim">every screening check passed</div>
            )}
          </section>
          {(["full", "preview"] as const).map((level) =>
            detail.built[level] ? (
              <section key={level} className="rib-slot">
                <header>
                  <span className="slot-label">its field, {level}</span>
                </header>
                <VerdictView verdict={detail.built[level]!} />
              </section>
            ) : null,
          )}
          {detail.solved ? <SolvedView solved={detail.solved} /> : null}
          {designs.problem ? <div className="card-note warn">{designs.problem}</div> : null}
        </div>
      )}
    </div>
  );
}

/** How the runner meshed and solved the design - or why it set it aside - and the signals derived
 * from its answer, under the deck's names. */
function SolvedView({ solved }: { solved: NonNullable<RunDesign["solved"]> }) {
  const stages = Object.entries(solved.stages)
    .map(([name, seconds]) => `${name} ${Math.round(seconds)} s`)
    .join(" · ");
  return (
    <section className="rib-slot">
      <header>
        <span className="slot-label">solved</span>
        <span className="chip" data-outcome={solved.outcome === "solved" ? "pass" : "reject"}>
          {solved.outcome}
        </span>
      </header>
      {solved.outcome === "set aside" ? <div className="card-note warn">{solved.reason}</div> : null}
      <div className="dim">
        {solved.route}
        {solved.seconds ? ` · ${Math.round(solved.seconds)} s` : ""}
      </div>
      {stages ? <div className="dim">{stages}</div> : null}
      {solved.mesh?.unknowns ? (
        <div className="dim">
          {solved.mesh.tets?.toLocaleString()} TET10 · {(solved.mesh.unknowns / 1e6).toFixed(2)} M unknowns
          {solved.mass_kg ? ` · ${solved.mass_kg.toFixed(1)} kg from its mesh` : ""}
        </div>
      ) : null}
      {solved.signals.length ? (
        <div className="solved-signals">
          {solved.signals
            .filter((s) => s.component !== "spin" && s.component !== "reaction")
            .map((s) => (
              <div key={`${s.name}.${s.component}`} className="made-row">
                <span className="mono">{s.name}</span> <span className="dim">{s.component}</span>{" "}
                <b>{s.value.toPrecision(3)}</b> <span className="dim">{s.unit}</span>
              </div>
            ))}
        </div>
      ) : null}
    </section>
  );
}

function ordinal(n: number): string {
  const tail = n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] ?? "th";
  return `${n}${tail}`;
}
