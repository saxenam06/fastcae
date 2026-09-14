/**
 * Input → Solve: the engineer's own answer, and fastcae's answers to the same question beside it -
 * the same mesh solved by cuDSS, and the field route every variant will take - as contours, side by
 * side or as their difference, with every signal set against the reference.
 */

import { useEffect, useMemo, useState } from "react";
import type { Certificate, CertificateRow, Run, SignalRow, Values } from "../api/simulate";
import { sim } from "../api/simulate";
import { CameraLink, FeStage } from "../stage/FeStage";
import type { Hovered } from "../stage/FeStage";
import { Legend, fmt } from "../stage/Legend";
import type { DeckState } from "./useDeck";
import { Provenance, fmtCount, fmtRelative, fmtSeconds } from "./shared";

export type FieldName = "displacement" | "DX" | "DY" | "DZ" | "von Mises";
export type Layout = "single" | "split" | "difference";

export interface SolveView {
  link: CameraLink;
  left: Run;
  setLeft: (r: Run) => void;
  right: Run;
  setRight: (r: Run) => void;
  field: FieldName;
  setField: (f: FieldName) => void;
  layout: Layout;
  setLayout: (l: Layout) => void;
  deformed: boolean;
  setDeformed: (v: boolean) => void;
  edges: boolean;
  setEdges: (v: boolean) => void;
  range: [number, number] | null;
  setRange: (r: [number, number] | null) => void;
  hovered: Hovered | null;
  setHovered: (h: Hovered | null) => void;
}

export function useSolveView(): SolveView {
  const link = useMemo(() => new CameraLink(), []);
  const [left, setLeft] = useState<Run>("aster");
  const [right, setRight] = useState<Run>("cudss");
  const [field, setField] = useState<FieldName>("von Mises");
  const [layout, setLayout] = useState<Layout>("single");
  const [deformed, setDeformed] = useState(false);
  const [edges, setEdges] = useState(false);
  const [range, setRange] = useState<[number, number] | null>(null);
  const [hovered, setHovered] = useState<Hovered | null>(null);
  return { link, left, setLeft, right, setRight, field, setField, layout, setLayout, deformed, setDeformed, edges, setEdges, range, setRange, hovered, setHovered };
}

const FIELDS: FieldName[] = ["displacement", "DX", "DY", "DZ", "von Mises"];
const UNIT: Record<FieldName, string> = { displacement: "mm", DX: "mm", DY: "mm", DZ: "mm", "von Mises": "MPa" };
const LABEL: Record<Run, string> = { aster: "Code_Aster", cudss: "cuDSS · same mesh", route: "cuDSS · field route" };

/**
 * ``input`` shows the engineer's own answer alone, as their solver wrote it; ``reproduce`` sets
 * fastcae's answers beside it.
 */
export function SolveRail({
  state,
  view,
  mode,
  onRoute,
  onReproduce,
}: {
  state: DeckState;
  view: SolveView;
  mode: "input" | "reproduce";
  onRoute: () => void;
  onReproduce: () => void;
}) {
  const { deck, signals, job } = state;
  if (!deck?.present) return <div className="rail-note">No solver deck in this project.</div>;
  const answers = (deck.answers ?? []).filter((a) => mode === "reproduce" || a.id === "aster");
  const available = (run: Run) => (deck.answers ?? []).find((a) => a.id === run)?.available ?? false;
  const running = job && !["done", "failed", "cancelled", "interrupted"].includes(job.state);
  const hasVm = (deck.fields ?? []).some((f) => f.name === "SIEQ_NOEU");
  if (mode === "input" && !available("aster")) {
    return (
      <section className="section">
        <header>Solve</header>
        <div className="body dim">
          The deck came without its results: no .rmed named by its export, or none in the project. Add the
          results the engineer's run wrote, then extract again.
        </div>
      </section>
    );
  }
  return (
    <>
      <section className="section">
        <header>{mode === "input" ? "The engineer's answer" : "Answers"}</header>
        <div className="answers">
          {answers.map((a) => (
            <div key={a.id} className="answer" data-available={a.available}>
              <div className="answer-head">
                <b>{a.label}</b> <Provenance kind={a.provenance} />
              </div>
              <div className="dim answer-detail">
                {a.id === "aster"
                  ? a.available
                    ? `${a.detail} · the engineer's run`
                    : "no results file in the project"
                  : a.available && a.meta
                    ? `${fmtCount(a.meta.unknowns ?? 0)} unknowns · ${fmtSeconds(a.meta.times?.total_s)}${
                        a.meta.agreement ? ` · off Code_Aster by ${fmtRelative(a.meta.agreement.displacement)}` : ""
                      }`
                    : a.id === "cudss"
                      ? "the deck's own mesh and setup, solved on the GPU"
                      : "the variant route on the baseline - see Variant Setup"}
              </div>
              {a.id === "cudss" ? (
                <button
                  className="primary"
                  disabled={Boolean(running)}
                  onClick={() => void state.submit(sim.solve)}
                >
                  {a.available ? "Solve again with cuDSS" : "Solve with cuDSS"}
                </button>
              ) : null}
              {a.id === "route" ? (
                <button onClick={onRoute}>{a.available ? "Open the route" : "Run the route"}</button>
              ) : null}
            </div>
          ))}
        </div>
        {running ? <JobLine job={job!} /> : null}
        {job && job.state === "failed" ? <div className="body job-error">{job.error}</div> : null}
        {mode === "input" ? (
          <div className="body">
            <button className="primary" onClick={onReproduce}>
              Reproduce it with fastcae →
            </button>
          </div>
        ) : null}
      </section>
      <section className="section">
        <header>Show</header>
        <div className="body">
          <div className="segmented wrap">
            {FIELDS.filter((f) => f !== "von Mises" || hasVm || (mode === "reproduce" && available("cudss"))).map((f) => (
              <button key={f} data-active={view.field === f} onClick={() => { view.setField(f); view.setRange(null); }}>
                {f}
              </button>
            ))}
          </div>
          <div className="segmented" hidden={mode === "input"}>
            <button data-active={view.layout === "single"} onClick={() => view.setLayout("single")}>one</button>
            <button
              data-active={view.layout === "split"}
              disabled={answers.filter((a) => a.available).length < 2}
              onClick={() => view.setLayout("split")}
            >
              side by side
            </button>
            <button
              data-active={view.layout === "difference"}
              disabled={!(available("aster") && available("cudss"))}
              onClick={() => { view.setLayout("difference"); view.setRange(null); }}
              title="cuDSS minus Code_Aster on the same mesh"
            >
              difference
            </button>
          </div>
          {mode === "reproduce" ? (
            <div className="pickers">
              <RunPicker label={view.layout === "split" ? "left" : "answer"} value={view.left} onChange={view.setLeft} available={available} />
              {view.layout === "split" ? <RunPicker label="right" value={view.right} onChange={view.setRight} available={available} /> : null}
            </div>
          ) : null}
          <label className="check">
            <input type="checkbox" checked={view.deformed} onChange={(e) => view.setDeformed(e.target.checked)} /> deformed shape
          </label>
          <label className="check">
            <input type="checkbox" checked={view.edges} onChange={(e) => view.setEdges(e.target.checked)} /> element edges
          </label>
        </div>
      </section>
      {mode === "reproduce" ? <CertificateSection state={state} /> : null}
      <SignalTable
        rows={signals?.rows ?? []}
        runs={mode === "input" ? ["aster"] : (Object.keys(signals?.runs ?? {}) as Run[])}
      />
    </>
  );
}

/** The reproduction certificate: every quantity compared, with the tolerance it is held to. */
function CertificateSection({ state }: { state: DeckState }) {
  const answers = state.deck?.answers ?? [];
  const others = answers.filter((a) => a.id !== "aster" && a.available).map((a) => a.id as Run);
  const [other, setOther] = useState<Run | null>(null);
  const [cert, setCert] = useState<Certificate | null>(null);
  const chosen = other && others.includes(other) ? other : others[0] ?? null;
  useEffect(() => {
    if (!chosen) return;
    let live = true;
    sim.certificate(chosen).then((c) => live && setCert(c)).catch(() => live && setCert(null));
    return () => { live = false; };
  }, [chosen, state.deck]);
  if (!chosen) {
    return (
      <section className="section">
        <header>Reproduction certificate</header>
        <div className="body dim">Solve the deck with cuDSS to set fastcae's answer beside the engineer's.</div>
      </section>
    );
  }
  return (
    <section className="section">
      <header>
        Reproduction certificate <Provenance kind="derived" small />
      </header>
      {others.length > 1 ? (
        <div className="body segmented">
          {others.map((r) => (
            <button key={r} data-active={chosen === r} onClick={() => setOther(r)}>
              {LABEL[r]}
            </button>
          ))}
        </div>
      ) : null}
      {cert ? (
        <>
          <div className="verdict" data-good={cert.holds}>
            <b>{LABEL[chosen]}</b>{" "}
            {cert.holds ? "holds on every quantity checked" : "misses on the quantities marked"}
          </div>
          <ul className="cert-list">
            {cert.rows.map((row) => (
              <li
                key={row.quantity}
                data-holds={row.holds === null ? "info" : String(row.holds)}
                title={certDetail(row, LABEL.aster, LABEL[chosen])}
              >
                <span className="mark">{row.holds === null ? "·" : row.holds ? "✓" : "✕"}</span>
                <span className="q">
                  {row.of ? `out of balance · ${row.of === "reference" ? LABEL.aster : LABEL[chosen]}` : row.quantity}
                </span>
                <span className="d">{fmtRelative(row.difference)}</span>
              </li>
            ))}
          </ul>
          <div className="body dim cert-solvers">
            <div>reference: {cert.solver.reference}</div>
            <div>reproduction: {cert.solver.other}{cert.residual ? ` · residual ${cert.residual.toExponential(1)}` : ""}</div>
          </div>
        </>
      ) : (
        <div className="body dim">reading…</div>
      )}
    </section>
  );
}

/** A certificate row in full, for its hover: both values, the tolerance, what it measures. */
function certDetail(row: CertificateRow, reference: string, other: string): string {
  const unit = row.unit ? ` ${row.unit}` : "";
  const values = row.of
    ? `load ${fmt(row.reference)}${unit} · left over ${fmt(row.other)}${unit}`
    : row.unit
      ? `${reference} ${fmt(row.reference)}${unit} · ${other} ${fmt(row.other)}${unit}`
      : "";
  const held = row.tolerance === null ? "not held to a tolerance" : `held to ${fmtRelative(row.tolerance)}`;
  return [values, held, row.note].filter(Boolean).join("\n");
}

function RunPicker({ label, value, onChange, available }: { label: string; value: Run; onChange: (r: Run) => void; available: (r: Run) => boolean }) {
  return (
    <label className="picker">
      <span className="dim">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value as Run)}>
        {(["aster", "cudss", "route"] as Run[]).map((r) => (
          <option key={r} value={r} disabled={!available(r)}>
            {LABEL[r]}
          </option>
        ))}
      </select>
    </label>
  );
}

export function JobLine({ job }: { job: { state: string; message?: string; progress?: number; stage?: string } }) {
  return (
    <div className="job-line">
      <div className="job-bar"><i style={{ width: `${Math.round((job.progress ?? 0) * 100)}%` }} /></div>
      <span className="dim">{job.stage ? `${job.stage}: ` : ""}{job.message ?? job.state}</span>
    </div>
  );
}

export function SignalTable({ rows, runs }: { rows: SignalRow[]; runs: Run[] }) {
  const [showAll, setShowAll] = useState(false);
  if (!rows.length) return null;
  const order: Run[] = (["aster", "cudss", "route"] as Run[]).filter((r) => runs.includes(r));
  const others = order.filter((r) => r !== "aster");
  const worst: Record<string, number> = {};
  for (const r of others) {
    worst[r] = Math.max(
      0,
      ...rows
        .filter((row) => row.values.aster !== undefined && row.values[r] !== undefined && Math.abs(row.values.aster) > 1e-12)
        .filter((row) => row.kind === "deck" || ["tilt", "p99.9", "largest", "reaction"].includes(row.component))
        .map((row) => Math.abs((row.values[r] - row.values.aster) / row.values.aster)),
    );
  }
  const shown = showAll ? rows : rows.filter((r) => r.kind === "derived" && r.component !== "spin");
  return (
    <section className="section">
      <header>
        Signals <span className="count">{rows.length}</span>
      </header>
      {others.map((r) => (
        <div key={r} className="verdict" data-good={r === "cudss" ? worst[r] < 1e-6 : worst[r] < 0.05}>
          <b>{LABEL[r]}</b>{" "}
          {r === "cudss"
            ? worst[r] < 1e-6
              ? `reproduces Code_Aster: every signal within ${fmtRelative(worst[r])}`
              : `differs from Code_Aster by up to ${fmtRelative(worst[r])}`
            : `within ${fmtRelative(worst[r])} of Code_Aster on its own mesh`}
        </div>
      ))}
      <div className="signal-table-wrap">
        <table className="signal-table num">
          <thead>
            <tr>
              <th>signal</th>
              {order.map((r) => (
                <th key={r}>{r === "aster" ? "Code_Aster" : r === "cudss" ? "cuDSS" : "route"}</th>
              ))}
              {others.map((r) => (
                <th key={`d${r}`}>Δ {r === "cudss" ? "cuDSS" : "route"}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => (
              <tr key={`${row.name}.${row.component}`} data-kind={row.kind}>
                <td title={row.kind === "deck" ? "asked for by the deck" : "derived by fastcae"}>
                  <span className="mono">{row.name}</span> <span className="dim">{row.component}</span>
                </td>
                {order.map((r) => (
                  <td key={r}>{row.values[r] === undefined ? "–" : fmt(row.values[r])}</td>
                ))}
                {others.map((r) => (
                  <td key={`d${r}`} className="delta">
                    {row.values[r] === undefined || row.values.aster === undefined || Math.abs(row.values.aster) < 1e-12
                      ? "–"
                      : fmtRelative((row.values[r] - row.values.aster) / row.values.aster)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="body">
        <button onClick={() => setShowAll(!showAll)}>{showAll ? "derived only" : `all ${rows.length}, the deck's too`}</button>
      </div>
    </section>
  );
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

export function SolveStage({ state, view }: { state: DeckState; view: SolveView }) {
  const { deck, skin } = state;
  const [left, setLeft] = useState<Values | null>(null);
  const [right, setRight] = useState<Values | null>(null);
  const [routeSkin, setRouteSkin] = useState<typeof skin>(null);
  const [error, setError] = useState<string | null>(null);
  const needsRoute = view.left === "route" || (view.layout === "split" && view.right === "route");

  useEffect(() => {
    if (!needsRoute || routeSkin) return;
    sim.routeSkin().then(setRouteSkin).catch(() => setRouteSkin(null));
  }, [needsRoute, routeSkin]);

  useEffect(() => {
    let live = true;
    setError(null);
    const vectors = view.deformed;
    const load = async () => {
      try {
        if (view.layout === "difference") {
          const d = await state.difference(view.field, "aster", "cudss");
          if (live) { setLeft(d); setRight(null); }
          return;
        }
        const a = await state.field(view.left, view.field, vectors);
        const b = view.layout === "split" ? await state.field(view.right, view.field, vectors) : null;
        if (live) { setLeft(a); setRight(b); }
      } catch (caught) {
        if (live) setError(String(caught));
      }
    };
    void load();
    return () => { live = false; };
  }, [state, view.layout, view.left, view.right, view.field, view.deformed]);

  if (!deck?.present) return null;
  const data: [number, number] = rangeOf(left, right, view.layout);
  const range = view.range ?? data;
  const bbox = deck.mesh?.bbox_mm ?? null;
  const skinFor = (run: Run) => (run === "route" ? routeSkin : skin);
  const deformScale = view.deformed ? deformFactor(left, bbox) : 0;
  const caption = (run: Run) => (
    <>
      <b>{LABEL[run]}</b> <Provenance kind={run === "aster" ? "imported" : "generated"} />
    </>
  );
  return (
    <>
      <div className="split-stage" data-split={view.layout === "split"}>
        <FeStage
          skin={skinFor(view.layout === "difference" ? "aster" : view.left)}
          values={left}
          mode={view.layout === "difference" ? "difference" : "contour"}
          range={range}
          edges={view.edges}
          showGlyphs={false}
          deform={deformScale}
          link={view.link}
          bbox={bbox}
          frameKey="deck"
          onHover={view.setHovered}
          caption={view.layout === "difference" ? <><b>cuDSS − Code_Aster</b> <Provenance kind="derived" /></> : caption(view.left)}
        />
        {view.layout === "split" ? (
          <FeStage
            skin={skinFor(view.right)}
            values={right}
            mode="contour"
            range={range}
            edges={view.edges}
            showGlyphs={false}
            deform={deformScale}
            link={view.link}
            bbox={bbox}
            frameKey="deck"
            onHover={view.setHovered}
            caption={caption(view.right)}
          />
        ) : null}
      </div>
      <Legend
        title={view.layout === "difference" ? `${view.field} difference` : view.field}
        unit={UNIT[view.field]}
        range={range}
        data={data}
        bands={48}
        diverging={view.layout === "difference"}
        onRange={(r) => view.setRange(r)}
      />
      {view.deformed ? <div className="fe-note">deformed ×{fmt(deformScale)}</div> : null}
      {error ? <div className="fe-error">{error}</div> : null}
    </>
  );
}

function rangeOf(left: Values | null, right: Values | null, layout: Layout): [number, number] {
  const a = dataRange(left);
  if (layout === "difference") {
    const m = Math.max(Math.abs(a[0]), Math.abs(a[1])) || 1e-12;
    return [-m, m];
  }
  if (layout !== "split" || !right) return a;
  const b = dataRange(right);
  return [Math.min(a[0], b[0]), Math.max(a[1], b[1])];
}

/** How much to exaggerate the displacement so the largest reads as a twentieth of the part. */
function deformFactor(values: Values | null, bbox: number[] | null): number {
  if (!values?.vectors || !bbox) return 0;
  let max = 0;
  const v = values.vectors;
  for (let i = 0; i < v.length; i += 3) max = Math.max(max, Math.hypot(v[i], v[i + 1], v[i + 2]));
  const extent = Math.max(bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2]);
  if (max === 0) return 0;
  const raw = (extent * 0.05) / max;
  const p = 10 ** Math.floor(Math.log10(raw));
  return Math.round(raw / p) * p;
}
