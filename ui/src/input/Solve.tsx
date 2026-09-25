/**
 * The deck solved, as contours on its own mesh: the engineer's Code_Aster run or cuDSS on the same
 * mesh, whichever is chosen, and every signal the deck asks for set against the reference.
 */

import { useEffect, useMemo, useState } from "react";
import { sim } from "../api/simulate";
import type { Run, SignalRow, Values } from "../api/simulate";
import { CameraLink, FeStage } from "../stage/FeStage";
import type { Hovered } from "../stage/FeStage";
import { Legend, fmt, typicalRange } from "../stage/Legend";
import type { DeckState } from "./useDeck";
import { Provenance, fmtRelative } from "./shared";

export type FieldName = "displacement" | "DX" | "DY" | "DZ" | "von Mises";

export interface SolveView {
  link: CameraLink;
  /** The answer shown. */
  left: Run;
  setLeft: (r: Run) => void;
  field: FieldName;
  setField: (f: FieldName) => void;
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
  const [field, setField] = useState<FieldName>("von Mises");
  const [deformed, setDeformed] = useState(false);
  const [edges, setEdges] = useState(false);
  const [range, setRange] = useState<[number, number] | null>(null);
  const [hovered, setHovered] = useState<Hovered | null>(null);
  return { link, left, setLeft, field, setField, deformed, setDeformed, edges, setEdges, range, setRange, hovered, setHovered };
}

const UNIT: Record<FieldName, string> = { displacement: "mm", DX: "mm", DY: "mm", DZ: "mm", "von Mises": "MPa" };
const LABEL: Record<Run, string> = { aster: "Code_Aster", cudss: "cuDSS · same mesh" };

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
  const order: Run[] = (["aster", "cudss"] as Run[]).filter((r) => runs.includes(r));
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
        <div key={r} className="verdict" data-good={worst[r] < 1e-6}>
          <b>{LABEL[r]}</b>{" "}
          {worst[r] < 1e-6
            ? `reproduces Code_Aster: every signal within ${fmtRelative(worst[r])}`
            : `differs from Code_Aster by up to ${fmtRelative(worst[r])}`}
        </div>
      ))}
      <div className="signal-table-wrap">
        <table className="signal-table num">
          <thead>
            <tr>
              <th>signal</th>
              {order.map((r) => (
                <th key={r}>{r === "aster" ? "Code_Aster" : "cuDSS"}</th>
              ))}
              {others.map((r) => (
                <th key={`d${r}`}>Δ cuDSS</th>
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

export function SolveStage({
  state,
  view,
  caption,
}: {
  state: DeckState;
  view: SolveView;
  /** What stands under the picture: the tabs that choose the answer, or its name. */
  caption?: React.ReactNode;
}) {
  const { deck, skin } = state;
  const [values, setValues] = useState<Values | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setError(null);
    state
      .field(view.left, view.field, view.deformed)
      .then((found) => live && setValues(found))
      .catch((caught) => live && setError(String(caught)));
    return () => {
      live = false;
    };
  }, [state, view.left, view.field, view.deformed]);
  const typical = useMemo(() => typicalRange(values?.values ?? null), [values]);

  if (!deck?.present) return null;
  const data = dataRange(values);
  const range = view.range ?? typical;
  const bbox = deck.mesh?.bbox_mm ?? null;
  const deformScale = view.deformed ? deformFactor(values, bbox) : 0;
  return (
    <>
      <FeStage
        skin={skin}
        values={values}
        mode="contour"
        range={range}
        edges={view.edges}
        showGlyphs={false}
        deform={deformScale}
        link={view.link}
        bbox={bbox}
        frameKey="deck"
        onHover={view.setHovered}
        sectionSource={{
          key: `deck:${view.left}:${view.field}`,
          fetch: (plane) => sim.section(plane, view.left, view.field),
        }}
        caption={
          caption ?? (
            <>
              <b>{LABEL[view.left]}</b>{" "}
              <Provenance kind={view.left === "aster" ? "imported" : "generated"} />
            </>
          )
        }
      />
      <Legend
        title={view.field}
        unit={UNIT[view.field]}
        range={range}
        data={data}
        bands={48}
        onRange={(r) => view.setRange(r)}
      />
      {view.deformed ? <div className="fe-note">deformed ×{fmt(deformScale)}</div> : null}
      {error ? <div className="fe-error">{error}</div> : null}
    </>
  );
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
