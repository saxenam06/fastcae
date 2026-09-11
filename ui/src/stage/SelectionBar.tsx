/**
 * The selection, on the stage: the faces clicked, each grown by its own angle, and how many faces
 * that comes to.
 *
 * Click a face to start, ctrl-click to add another or take one out. The grow control acts on one
 * click only - the last, or whichever is picked from the list - so raising the angle for a floor
 * never grows the wall clicked after it. Selecting is how faces get into the rib card.
 */

import type { Seed } from "../api/client";

interface SelectionBarProps {
  count: number;
  seeds: Seed[];
  /** The face the grow control is on. */
  active: number | null;
  onActive: (face: number) => void;
  onAngle: (angle: number) => void;
  onRemove: (face: number) => void;
  onClear: () => void;
}

/** Clicks listed before the rest are summed up. A selection made from a feature can be hundreds. */
const LISTED = 6;

export function SelectionBar(props: SelectionBarProps) {
  const { seeds, active } = props;
  const current = seeds.find((s) => s.face === active) ?? null;
  const listed = seeds.slice(-LISTED);
  const hidden = seeds.length - listed.length;
  return (
    <div className="selection-bar" data-empty={seeds.length === 0}>
      <span className="count">
        {seeds.length === 0
          ? "click a face · ctrl-click adds"
          : `${props.count} face${props.count === 1 ? "" : "s"}`}
      </span>
      {hidden > 0 ? <span className="dim">+{hidden}</span> : null}
      {listed.map((seed) => (
        <span key={seed.face} className="seed" data-active={seed.face === active}>
          <button
            onClick={() => props.onActive(seed.face)}
            title="Grow this click - the angle below acts on it alone"
          >
            face:{seed.face}
            {seed.angle > 0 ? <span className="grown"> ↗{seed.angle}°</span> : null}
          </button>
          <button className="remove" onClick={() => props.onRemove(seed.face)} title="Take it out">
            ×
          </button>
        </span>
      ))}
      <label
        title={
          current
            ? `Grow face:${current.face} across every edge shallower than this angle`
            : "Pick a click to grow"
        }
      >
        grow
        <input
          type="range"
          min={0}
          max={90}
          step={5}
          value={current?.angle ?? 0}
          disabled={current === null}
          onChange={(event) => props.onAngle(Number(event.target.value))}
        />
        <span className="mono">{current?.angle ?? 0}&deg;</span>
      </label>
      <button onClick={props.onClear} disabled={seeds.length === 0}>
        Clear
      </button>
    </div>
  );
}
