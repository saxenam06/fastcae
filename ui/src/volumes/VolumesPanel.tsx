/**
 * The design-volume view's panel, over the part: the faces picked, the volume they bound - how
 * much, how high, what it keeps clear - and the volumes the project keeps.
 */

import { useState } from "react";
import type { KeptClear, VolumeFound } from "../api/volumes";
import type { VolumesState } from "./useVolumes";
import { KEPT_TINT, PROPOSED_TINT } from "./useVolumes";

const KINDS: { kind: KeptClear["kind"]; label: string; title: string }[] = [
  { kind: "bore", label: "bores", title: "What sits in each bore, over its length" },
  { kind: "beyond", label: "past bores", title: "What carries on past a bore's end: a shaft inside, the hub outside" },
  { kind: "line", label: "bearing lines", title: "Each bearing's shaft line, right through the part" },
  { kind: "hole", label: "holes", title: "Every hole and room for its tool" },
  { kind: "lid", label: "mating faces", title: "What mates against a face the deck holds" },
];

function rgb(c: [number, number, number]): string {
  return `rgb(${c.map((v) => Math.round(v * 255)).join(",")})`;
}

/** How a position along the volume's axis reads: as x, y or z when the axis is one of them. */
function along(found: VolumeFound): { letter: string; world: (s: number) => number } {
  const k = [0, 1, 2].find((i) => Math.abs(found.axis[i]) > 0.99);
  if (k === undefined) return { letter: "along the axis", world: (s) => s };
  return { letter: "xyz"[k], world: (s) => found.point[k] + s * found.axis[k] };
}

export function VolumesPanel({ state }: { state: VolumesState }) {
  const [name, setName] = useState("");
  const [open, setOpen] = useState(false);
  const found = state.proposal;
  const axis = found ? along(found) : null;
  const band = state.band ?? found?.band ?? null;

  return (
    <div className="volumes-panel" onPointerDown={(e) => e.stopPropagation()}>
      <header>
        <b>Design volumes</b>
        <span className="dim">click a face · ctrl-click adds</span>
      </header>

      {state.picks.length ? (
        <div className="volume-picks">
          {state.picks.map((f) => (
            <button key={f} className="chip" onClick={() => state.unpick(f)} title="Take it out">
              face:{f} ×
            </button>
          ))}
          <button className="link" onClick={state.clear}>
            clear
          </button>
        </div>
      ) : (
        <p className="dim volume-help">
          Pick the floor ribs would stand on, or the ring or boss they would grow from.
        </p>
      )}

      {state.picks.length ? (
        <div className="volume-proposal">
          <div className="volume-line">
            <i className="swatch" style={{ background: rgb(PROPOSED_TINT) }} />
            {state.finding ? (
              <span className="dim">finding the volume…</span>
            ) : found ? (
              <span>
                <b className="num">{found.volume_L.toFixed(1)} L</b>{" "}
                {found.kind === "floor" ? "over the floor" : "round the anchor"}
                {axis && band ? (
                  <span className="dim num">
                    {" "}
                    · {axis.letter} {Math.round(Math.min(axis.world(band[0]), axis.world(band[1])))}–
                    {Math.round(Math.max(axis.world(band[0]), axis.world(band[1])))} mm
                  </span>
                ) : null}
              </span>
            ) : null}
          </div>
          {state.error ? <div className="fe-error">{state.error}</div> : null}
          {found && !state.finding && found.volume_L <= 0 ? (
            <div className="dim">No air there ribs could use: every pocket is outside the band or kept clear.</div>
          ) : null}
          {found && band ? (
            <BandControl found={found} band={band} onBand={state.setBand} />
          ) : null}
          {found ? (
            <div className="volume-kept-clear">
              <span className="dim">kept clear</span>
              {KINDS.map(({ kind, label, title }) => {
                const rows = found.keepouts.filter((k) => k.kind === kind);
                if (!rows.length) return null;
                const on = rows.filter((k) => !state.off.includes(k.key)).length;
                return (
                  <button
                    key={kind}
                    className="pill"
                    data-active={on > 0}
                    title={`${title}. Click to ${on ? "stop keeping them clear" : "keep them clear"}.`}
                    onClick={() => state.toggleOff(rows.map((k) => k.key), on > 0)}
                  >
                    {label} {on}/{rows.length}
                  </button>
                );
              })}
              <button className="link" onClick={() => setOpen(!open)}>
                {open ? "hide" : "each"}
              </button>
            </div>
          ) : null}
          {found && open ? (
            <ul className="volume-keepouts">
              {found.keepouts.map((k) => (
                <li key={k.key}>
                  <label>
                    <input
                      type="checkbox"
                      checked={!state.off.includes(k.key)}
                      onChange={(e) => state.toggleOff([k.key], !e.target.checked)}
                    />
                    {k.words}
                  </label>
                </li>
              ))}
            </ul>
          ) : null}
          {found && !state.finding ? (
            <div className="volume-accept">
              <input
                placeholder={`V${state.kept.length + 1}`}
                value={name}
                onChange={(e) => setName(e.target.value)}
                aria-label="name"
              />
              <button
                className="primary"
                disabled={found.volume_L <= 0}
                onClick={() => {
                  state
                    .accept(name.trim() || null)
                    .then(() => setName(""))
                    .catch(() => undefined);
                }}
              >
                Keep volume
              </button>
            </div>
          ) : null}
        </div>
      ) : null}

      {state.kept.length ? (
        <div className="volume-list">
          {state.kept.map((v) => (
            <div key={v.name} className="volume-row">
              <button
                className="eye"
                data-active={!state.hidden.has(v.name)}
                onClick={() => state.toggleHidden(v.name)}
                title="Show or hide it"
              >
                <i className="swatch" style={{ background: rgb(KEPT_TINT) }} />
              </button>
              <b>{v.name}</b>
              <span className="num">{v.volume_L.toFixed(1)} L</span>
              <span className="dim">faces {v.recipe.faces.join(", ")}</span>
              <button className="icon" onClick={() => void state.remove(v.name)} title="Delete it">
                ×
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** Where the volume starts and stops along its axis. */
function BandControl({
  found,
  band,
  onBand,
}: {
  found: VolumeFound;
  band: [number, number];
  onBand: (band: [number, number] | null) => void;
}) {
  const [lo, hi] = found.band_limits;
  const axis = along(found);
  const step = Math.max((hi - lo) / 400, 0.5);
  const moved = band[0] !== found.band_default[0] || band[1] !== found.band_default[1];
  return (
    <div className="volume-band">
      {(["from", "to"] as const).map((which, i) => (
        <label key={which} className="section-row">
          <span>{which}</span>
          <input
            type="range"
            min={lo}
            max={hi}
            step={step}
            value={band[i]}
            onChange={(e) => {
              const v = Number(e.target.value);
              onBand(i === 0 ? [Math.min(v, band[1] - 5), band[1]] : [band[0], Math.max(v, band[0] + 5)]);
            }}
            aria-label={`${which} along the axis`}
          />
          <span className="num">
            {axis.letter.length === 1 ? axis.letter : ""} {Math.round(axis.world(band[i]))}
          </span>
        </label>
      ))}
      {moved ? (
        <button className="link" onClick={() => onBand(null)} title="Back to the height the picks suggest">
          as picked
        </button>
      ) : null}
    </div>
  );
}
