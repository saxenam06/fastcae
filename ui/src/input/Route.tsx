/**
 * Variant Setup → Route: the route every design will take, walked on the baseline itself - its field,
 * CGAL's mesh of the field, the deck's setup carried over by CAD face, cuDSS - and the answer set
 * against the engineer's own. What a design inherits from the deck and what fastcae makes is said
 * plainly, item by item.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import type { RouteState, Values } from "../api/simulate";
import { sim } from "../api/simulate";
import type { GlyphData, Skin } from "../render/fe";
import { CameraLink, FeStage } from "../stage/FeStage";
import type { Hovered } from "../stage/FeStage";
import { Legend } from "../stage/Legend";
import { JobLine, SignalTable } from "./Solve";
import { patchColours } from "./useDeck";
import type { DeckState } from "./useDeck";
import { Provenance, fmtCount, fmtSeconds } from "./shared";

type Step = "field" | "mesh" | "setup" | "solve";
type Show = "mesh" | "setup" | "result";

export interface RouteView {
  link: CameraLink;
  route: RouteState | null;
  refresh: () => Promise<void>;
  show: Show;
  setShow: (s: Show) => void;
  skin: Skin | null;
  glyphs: GlyphData | null;
  hovered: Hovered | null;
  setHovered: (h: Hovered | null) => void;
}

export function useRouteView(active: boolean, state: DeckState): RouteView {
  const link = useMemo(() => new CameraLink(), []);
  const [route, setRoute] = useState<RouteState | null>(null);
  const [show, setShow] = useState<Show>("mesh");
  const [skin, setSkin] = useState<Skin | null>(null);
  const [glyphs, setGlyphs] = useState<GlyphData | null>(null);
  const [hovered, setHovered] = useState<Hovered | null>(null);
  const refresh = useCallback(async () => {
    const found = await sim.route().catch(() => null);
    setRoute(found);
    if (found?.has_mesh) setSkin(await sim.routeSkin().catch(() => null));
    if (found?.has_setup) setGlyphs(await sim.routeGlyphs().catch(() => null));
    if (found?.steps.solve) setShow("result");
    else if (found?.has_setup) setShow("setup");
  }, []);
  useEffect(() => {
    if (active && state.deck?.present) void refresh();
  }, [active, state.deck, refresh]);
  return { link, route, refresh, show, setShow, skin, glyphs, hovered, setHovered };
}

const STEPS: { id: Step; title: string; what: string; button: string }[] = [
  { id: "field", title: "Field", what: "the baseline as a distance field, on the grid its designs are built on", button: "Build" },
  { id: "mesh", title: "Mesh", what: "CGAL meshes the field, held to the deck mesh's element sizes; the edges of the faces loads go in through followed", button: "Mesh" },
  { id: "setup", title: "Setup", what: "the deck's groups carried by the CAD faces they lie on; supports, couplings and loads as the deck has them", button: "Carry" },
  { id: "solve", title: "Solve", what: "cuDSS on the GPU", button: "Solve" },
];

function stepSummary(step: Step, meta: Record<string, unknown> | null): string {
  if (!meta) return "not yet";
  const n = (k: string) => (typeof meta[k] === "number" ? (meta[k] as number) : 0);
  switch (step) {
    case "field":
      return `${meta.spacing_mm} mm grid · ${fmtCount(n("points"))} points · ${meta.kept ? "kept" : fmtSeconds(n("seconds"))}`;
    case "mesh":
      return `${fmtCount(n("tets"))} TET10 · ${fmtCount(n("unknowns"))} unknowns · ${n("lines")} edge lines · ${fmtSeconds(n("mesh_s"))}`;
    case "setup": {
      const groups = (meta.groups ?? {}) as Record<string, { area: number; deck_area: number }>;
      const ratios = Object.values(groups).map((g) => g.area / Math.max(g.deck_area, 1e-9));
      const lo = Math.min(...ratios);
      const hi = Math.max(...ratios);
      return `${Object.keys(groups).length} groups · area ${(lo * 100).toFixed(0)}–${(hi * 100).toFixed(0)} % of the deck's`;
    }
    case "solve":
      return `${fmtCount(n("unknowns"))} unknowns · ${fmtSeconds((meta.times as Record<string, number> | undefined)?.total_s)}`;
  }
}

export function RouteRail({ state, view }: { state: DeckState; view: RouteView }) {
  const { deck, job } = state;
  if (!deck?.present) {
    return <div className="rail-note">The route is walked on the baseline's own deck; this project has none.</div>;
  }
  const route = view.route;
  const running = job && !["done", "failed", "cancelled", "interrupted"].includes(job.state);
  const run = async (step: Step | "all") => {
    await state.submit(() => sim.routeStep(step));
    await view.refresh();
  };
  const setup = deck.setup!;
  const heldCount = setup.held.reduce((n, h) => n + h.groups.length, 0);
  return (
    <>
      <section className="section">
        <header>The route every design takes</header>
        <ol className="route-steps">
          {STEPS.map((s, i) => {
            const meta = route?.steps[s.id] ?? null;
            const ready = i === 0 || Boolean(route?.steps[STEPS[i - 1].id]);
            return (
              <li key={s.id} data-done={Boolean(meta)}>
                <div className="route-step-head">
                  <span className="route-step-no">{i + 1}</span>
                  <b>{s.title}</b>
                  <Provenance kind="generated" small />
                  <button disabled={Boolean(running) || !ready} onClick={() => void run(s.id)}>
                    {meta ? "again" : s.button}
                  </button>
                </div>
                <div className="dim">{s.what}</div>
                <div className="route-step-meta num">{stepSummary(s.id, meta as Record<string, unknown> | null)}</div>
              </li>
            );
          })}
        </ol>
        <div className="body">
          <button className="primary" disabled={Boolean(running)} onClick={() => void run("all")}>
            Run all four
          </button>
        </div>
        {running ? <JobLine job={job!} /> : null}
        {job && job.state === "failed" ? <div className="body job-error">{job.error}</div> : null}
      </section>
      <section className="section">
        <header>What a design inherits</header>
        <table className="inherit num">
          <tbody>
            <tr><td>Geometry</td><td>built for each design</td><td><Provenance kind="generated" small /></td></tr>
            <tr><td>Mesh</td><td>CGAL, the deck mesh's sizes</td><td><Provenance kind="generated" small /></td></tr>
            <tr><td>Material</td><td>{setup.materials.map((m) => `${m.name}`).join(", ")}</td><td><Provenance kind="imported" small /></td></tr>
            <tr><td>Held</td><td>{heldCount} groups</td><td><Provenance kind="imported" small /></td></tr>
            <tr><td>Couplings</td><td>{setup.rigid.length} rigid · {setup.distributing.length} distributing</td><td><Provenance kind="imported" small /></td></tr>
            <tr><td>Loads</td><td>{setup.nodal_loads.length + setup.surface_loads.length} as the deck applies them</td><td><Provenance kind="imported" small /></td></tr>
            <tr><td>Analysis</td><td>{setup.analysis?.kind ?? "—"}, solved by cuDSS</td><td><Provenance kind="imported" small /></td></tr>
            <tr><td>Signals</td><td>the deck's {setup.outputs.length}</td><td><Provenance kind="imported" small /></td></tr>
          </tbody>
        </table>
      </section>
      {route?.steps.solve ? <SignalTable rows={state.signals?.rows ?? []} runs={["aster", "route"]} /> : null}
    </>
  );
}

export function RouteStage({ state, view }: { state: DeckState; view: RouteView }) {
  const { deck } = state;
  const [left, setLeft] = useState<Values | null>(null);
  const [right, setRight] = useState<Values | null>(null);
  const [range, setRange] = useState<[number, number] | null>(null);
  const solved = Boolean(view.route?.steps.solve);
  useEffect(() => {
    if (view.show !== "result" || !solved) return;
    let live = true;
    Promise.all([state.field("aster", "von Mises"), state.field("route", "von Mises")])
      .then(([a, b]) => { if (live) { setLeft(a); setRight(b); } })
      .catch(() => undefined);
    return () => { live = false; };
  }, [view.show, solved, state]);
  const colours = useMemo(() => patchColours(view.skin, deck), [view.skin, deck]);
  if (!deck?.present) return null;
  const bbox = deck.mesh?.bbox_mm ?? null;
  const tabs = (
    <div className="overlay">
      {(["mesh", "setup", "result"] as Show[]).map((s) => (
        <button
          key={s}
          data-active={view.show === s}
          disabled={(s === "mesh" && !view.route?.has_mesh) || (s === "setup" && !view.route?.has_setup) || (s === "result" && !solved)}
          onClick={() => view.setShow(s)}
        >
          {s === "result" ? "against Code_Aster" : s}
        </button>
      ))}
    </div>
  );
  if (!view.route?.has_mesh) {
    return (
      <div className="stage-page">
        <div className="later">
          <h2>The variant route, on the baseline</h2>
          <p>
            Every design will be built as a distance field, meshed from it by CGAL, given the deck's own
            supports, couplings and loads by the CAD faces they act on, and solved by cuDSS. Walk the route
            on the baseline first: its answer can then be set beside the engineer's own.
          </p>
          <p className="dim">Start with step 1 on the left, or run all four.</p>
        </div>
      </div>
    );
  }
  if (view.show === "result" && solved) {
    const data = rangeOf(left, right);
    const shown = range ?? data;
    return (
      <>
        <div className="split-stage" data-split="true">
          <FeStage skin={state.skin} values={left} mode="contour" range={shown} edges={false} showGlyphs={false} link={view.link} bbox={bbox} frameKey="route" caption={<><b>Code_Aster · the deck's mesh</b> <Provenance kind="imported" /></>} />
          <FeStage skin={view.skin} values={right} mode="contour" range={shown} edges={false} showGlyphs={false} link={view.link} bbox={bbox} frameKey="route" caption={<><b>cuDSS · the field's mesh</b> <Provenance kind="generated" /></>} />
        </div>
        {tabs}
        <Legend title="von Mises" unit="MPa" range={shown} data={data} bands={48} onRange={setRange} />
      </>
    );
  }
  return (
    <>
      <FeStage
        skin={view.skin}
        glyphs={view.show === "setup" ? view.glyphs : null}
        mode={view.show === "setup" ? "patches" : "plain"}
        groupColours={colours}
        edges
        showGlyphs={view.show === "setup"}
        link={view.link}
        bbox={bbox}
        frameKey="route"
        onHover={view.setHovered}
        caption={<><b>the field's mesh</b> <Provenance kind="generated" /></>}
      />
      {tabs}
      <div className="fe-readout">
        {view.hovered ? (
          <>
            <b className="mono">{view.hovered.name}</b> <span className="dim">{view.hovered.detail || state.roleOf(view.hovered.name).join(", ")}</span>
          </>
        ) : (
          <span className="dim">hover a patch or glyph</span>
        )}
      </div>
    </>
  );
}

function rangeOf(a: Values | null, b: Values | null): [number, number] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of [a, b]) {
    if (!v) continue;
    for (const x of v.values) {
      if (!Number.isFinite(x)) continue;
      if (x < lo) lo = x;
      if (x > hi) hi = x;
    }
  }
  return lo === Infinity ? [0, 1] : [lo, hi];
}
