/**
 * The design space's key, on the CAD in its design-space view: every layer a step made, switched on
 * and off where it is named, and the per-face paints. A layer whose step has not run yet is shown
 * but cannot be switched on - the run fills the key in as it goes.
 */

import type { LayerKey, PaintKind } from "../api/pipeline";
import { INTERFACE_COLOURS, LAYER_GROUPS, PAINTS } from "./spaceLayers";
import type { Painted } from "./spaceLayers";

/** How the part and the volumes are drawn: the part shown or hidden, and how opaque each is. */
export interface SpaceView {
  part: boolean;
  partOpacity: number;
  volumeOpacity: number;
}

interface Props {
  view: SpaceView;
  onView: (view: SpaceView) => void;
  shown: Set<LayerKey>;
  onToggle: (key: LayerKey) => void;
  done: Set<string>;
  paint: PaintKind | null;
  onPaint: (kind: PaintKind | null) => void;
  painted: Painted | null;
  paintReady: (kind: PaintKind) => boolean;
}

const css = (c: [number, number, number]) =>
  `rgb(${Math.round(c[0] * 255)},${Math.round(c[1] * 255)},${Math.round(c[2] * 255)})`;

export function SpaceLegend(props: Props) {
  const { view, onView } = props;
  return (
    <div className="space-legend">
      <div className="legend-group">
        <div className="legend-title">View</div>
        <div className="legend-slider">
          <button
            className="legend-row"
            data-on={view.part}
            onClick={() => onView({ ...view, part: !view.part })}
            title={view.part ? "Hide the part" : "Show the part"}
          >
            <span className="swatch" style={{ background: "#aeb3b8" }} />
            <span>Part</span>
          </button>
          <input
            type="range"
            min={10}
            max={100}
            step={5}
            value={Math.round(view.partOpacity * 100)}
            disabled={!view.part}
            onChange={(e) => onView({ ...view, partOpacity: Number(e.target.value) / 100 })}
            aria-label="how opaque the part is"
          />
          <span className="num">{Math.round(view.partOpacity * 100)}%</span>
        </div>
        <div className="legend-slider">
          <span className="legend-slider-label">Volumes</span>
          <input
            type="range"
            min={10}
            max={200}
            step={10}
            value={Math.round(view.volumeOpacity * 100)}
            onChange={(e) => onView({ ...view, volumeOpacity: Number(e.target.value) / 100 })}
            aria-label="how opaque the volumes are, against each one's own"
          />
          <span className="num">{Math.round(view.volumeOpacity * 100)}%</span>
        </div>
      </div>
      {LAYER_GROUPS.map((group) => (
        <div key={group.label} className="legend-group">
          <div className="legend-title">{group.label}</div>
          {group.layers.map((layer) => {
            const ready = props.done.has(layer.step);
            const on = props.shown.has(layer.key);
            return (
              <button
                key={layer.key}
                className="legend-row"
                data-on={on && ready}
                disabled={!ready}
                onClick={() => props.onToggle(layer.key)}
                title={ready ? undefined : "not derived yet"}
              >
                <span
                  className="swatch"
                  style={{
                    background:
                      layer.key === "benefit"
                        ? "linear-gradient(90deg, #fff0a0, #fc8c3c, #b30026)"
                        : css(layer.tint),
                  }}
                />
                <span>{layer.label}</span>
              </button>
            );
          })}
        </div>
      ))}
      <div className="legend-group">
        <div className="legend-title">Paint the part</div>
        <div className="legend-paints">
          <button data-active={props.paint === null} onClick={() => props.onPaint(null)}>
            none
          </button>
          {PAINTS.map((p) => (
            <button
              key={p.key}
              data-active={props.paint === p.key}
              disabled={!props.paintReady(p.key)}
              onClick={() => props.onPaint(p.key)}
            >
              {p.label}
            </button>
          ))}
        </div>
        {props.painted && props.paint === props.painted.kind ? <PaintKey painted={props.painted} /> : null}
      </div>
    </div>
  );
}

function PaintKey({ painted }: { painted: Painted }) {
  if (painted.kind === "interface") {
    return (
      <div className="paint-key">
        {Object.entries(INTERFACE_COLOURS).map(([key, c]) => (
          <span key={key}>
            <i style={{ background: css(c.tint) }} /> {c.label}
          </span>
        ))}
      </div>
    );
  }
  if (painted.kind === "sealing") {
    return (
      <div className="paint-key">
        <span>
          <i style={{ background: css(painted.low) }} /> holds the inside · {painted.paint.size} faces
        </span>
      </div>
    );
  }
  const [lo, hi] = painted.range ?? [0, 0];
  return (
    <div className="paint-key">
      <span className="paint-ramp" style={{ background: `linear-gradient(90deg, ${css(painted.low)}, ${css(painted.high)})` }} />
      <span className="num">
        {lo.toFixed(0)} – {hi.toFixed(0)} mm
      </span>
    </div>
  );
}
