/**
 * A contour's legend: the colour bar in its bands, five ticks, the unit, and the limits - which can
 * be set, or put back to the field's own range. When a limit cuts the field off, it says by how much.
 */

import { useEffect, useState } from "react";
import { CONTOUR_STOPS, DIFFERENCE_STOPS } from "../render/fe";

interface Props {
  title: string;
  unit: string;
  range: [number, number];
  data: [number, number];
  bands: number;
  diverging?: boolean;
  onRange: (range: [number, number]) => void;
}

export function Legend({ title, unit, range, data, bands, diverging, onRange }: Props) {
  const stops = diverging ? DIFFERENCE_STOPS : CONTOUR_STOPS;
  const gradient = stops
    .map((s, i) => `rgb(${s[0]},${s[1]},${s[2]}) ${((i / (stops.length - 1)) * 100).toFixed(1)}%`)
    .join(", ");
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => range[1] - t * (range[1] - range[0]));
  const clipped = data[1] > range[1] + 1e-12 || data[0] < range[0] - 1e-12;
  const [low, setLow] = useState(String(range[0]));
  const [high, setHigh] = useState(String(range[1]));
  useEffect(() => {
    setLow(fmt(range[0]));
    setHigh(fmt(range[1]));
  }, [range]);
  const commit = () => {
    const a = Number(low);
    const b = Number(high);
    if (Number.isFinite(a) && Number.isFinite(b) && b > a) onRange([a, b]);
  };
  return (
    <div className="fe-legend">
      <div className="fe-legend-title">{title}</div>
      <div className="fe-legend-body">
        <div
          className="fe-legend-bar"
          style={{ background: `linear-gradient(to top, ${gradient})`, backgroundSize: `100% 100%` }}
          title={`${bands} bands`}
        />
        <div className="fe-legend-ticks num">
          {ticks.map((v, i) => (
            <span key={i}>{fmt(v)}</span>
          ))}
        </div>
      </div>
      <div className="fe-legend-unit">{unit}</div>
      {clipped ? (
        <div className="fe-legend-clip num">
          field {fmt(data[0])} … {fmt(data[1])}
        </div>
      ) : null}
      <div className="fe-legend-limits">
        <input className="num" value={high} onChange={(e) => setHigh(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && commit()} aria-label="upper limit" />
        <input className="num" value={low} onChange={(e) => setLow(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && commit()} aria-label="lower limit" />
        <button onClick={() => onRange(data)} title="The field's own range">auto</button>
      </div>
    </div>
  );
}

/**
 * The range a contour opens on: the field's own, less the last half percent at either end - a
 * coupling's or a support's few nodes can carry many times the stress anywhere else, and a bar
 * stretched to them leaves the rest of the part one colour. The legend says what is cut off.
 */
export function typicalRange(values: ArrayLike<number> | null): [number, number] {
  if (!values || !values.length) return [0, 1];
  const finite = Float64Array.from(values).filter((v) => Number.isFinite(v));
  if (!finite.length) return [0, 1];
  finite.sort();
  const at = (q: number) => finite[Math.min(finite.length - 1, Math.max(0, Math.round(q * (finite.length - 1))))];
  const lo = at(0.005);
  const hi = at(0.995);
  return hi > lo ? [lo, hi] : [finite[0], finite[finite.length - 1] + 1e-12];
}

export function fmt(v: number): string {
  if (!Number.isFinite(v)) return "–";
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-3 || a >= 1e5)) return v.toExponential(2);
  return Number(v.toPrecision(3)).toString();
}
