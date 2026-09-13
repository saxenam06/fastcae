/**
 * Plans: the designs of a run that differ most, side by side - each as a plan seen along the pull,
 * its ribs and pads as lines and its holes as circles, coloured by block, over the outlines of what
 * the study names and the part's bores. Paths, not geometry: designs are compared before anything
 * is built.
 *
 * A click picks a design; its paths and field are one more click away.
 */

import { useEffect, useMemo, useState } from "react";
import type { StageState, VariedDesigns } from "../api/client";
import { api } from "../api/client";
import { plain } from "../panel/shared";

/** One colour a block, in the order the study lists them. */
export const PALETTE = [
  "#1b7f8c",
  "#d9480f",
  "#5f3dc4",
  "#2b8a3e",
  "#c2255c",
  "#1864ab",
  "#e67700",
  "#495057",
  "#0b7285",
  "#862e9c",
];
const PAD = "#e0a800";
const HOLE = "#c2255c";

/** A block's colour: its place among the study's blocks. */
export function blockColours(blocks: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  Object.keys(blocks).forEach((block, index) => {
    out[block] = PALETTE[index % PALETTE.length];
  });
  return out;
}

export function Plans(props: {
  run: string;
  k: number;
  selected: number | null;
  /** The designs built, and how each field was checked. */
  built: Map<number, StageState>;
  onPick: (index: number) => void;
  onOpen: (index: number, tab: "paths" | "field") => void;
}) {
  const [shown, setShown] = useState<VariedDesigns | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setProblem(null);
    api
      .variedDesigns(props.k, props.run)
      .then((reply) => live && setShown(reply))
      .catch((caught) => live && setProblem(plain(caught)));
    return () => {
      live = false;
    };
  }, [props.k, props.run]);

  const colours = useMemo(() => blockColours(shown?.blocks ?? {}), [shown]);

  if (problem) return <div className="plans"><div className="card-note warn">{problem}</div></div>;
  if (!shown) return <div className="plans"><div className="card-note">Drawing the plans…</div></div>;
  return (
    <div className="plans">
      <header className="varied-head">
        <span className="card-title">
          The {shown.designs.length} that differ most, of {shown.of.toLocaleString()} designs - seen
          along the pull
        </span>
        <span className="varied-key">
          {Object.entries(shown.blocks).map(([block, add]) =>
            add === "ribs" || add === "holes" ? (
              <span key={block} className="paths-key-item">
                <span className="swatch" style={{ background: colours[block] }} />
                {block} {add}
              </span>
            ) : null,
          )}
          <span className="paths-key-item">
            <span className="swatch" style={{ background: PAD }} />
            pads
          </span>
        </span>
      </header>
      <div className="varied-grid">
        <svg className="varied-defs" width="0" height="0" aria-hidden="true">
          <defs>
            <path
              id="varied-outline"
              d={shown.outlines.map(([x1, y1, x2, y2]) => `M${x1} ${y1}L${x2} ${y2}`).join("")}
            />
          </defs>
        </svg>
        {shown.designs.map((design, position) => (
          <figure
            key={design.index}
            className="varied-card"
            data-selected={props.selected === design.index}
            onClick={() => props.onPick(design.index)}
          >
            <Plan design={design} bounds={shown.bounds} colours={colours} />
            <figcaption>
              <div className="varied-line">
                <span className="rank">{position + 1}</span> <b>#{design.index + 1}</b> ·{" "}
                {design.ribs} ribs
                {design.holes ? ` · ${design.holes} holes` : ""}
                {design.pads ? ` · ${design.pads} pads` : ""} · {design.mass_kg} kg ·{" "}
                {design.material}
                {props.built.has(design.index) ? (
                  <span
                    className="stage-badge"
                    data-state={props.built.get(design.index)}
                    title={`its field is built: ${props.built.get(design.index)}`}
                  >
                    F
                  </span>
                ) : null}
              </div>
              <div className="varied-blocks">
                {design.short.map(([block, words]) => (
                  <span key={block} style={{ color: colours[block] ?? "inherit" }}>
                    {block} {words}
                  </span>
                ))}
              </div>
              <div className="actions">
                <button
                  className="link"
                  onClick={(event) => {
                    event.stopPropagation();
                    props.onOpen(design.index, "paths");
                  }}
                  title="Its paths on the part"
                >
                  paths
                </button>
                <button
                  className="link"
                  onClick={(event) => {
                    event.stopPropagation();
                    props.onOpen(design.index, "field");
                  }}
                  title="Its field - built, or to build"
                >
                  field
                </button>
              </div>
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}

/** One design as a plan: the outlines, then its holes, pads and ribs. The plan's y runs up. */
function Plan(props: {
  design: VariedDesigns["designs"][number];
  bounds: VariedDesigns["bounds"];
  colours: Record<string, string>;
}) {
  const [x0, y0, x1, y1] = props.bounds;
  const { plan } = props.design;
  return (
    <svg
      className="varied-plan"
      viewBox={`${x0} ${-y1} ${x1 - x0} ${y1 - y0}`}
      preserveAspectRatio="xMidYMid meet"
    >
      <g transform="scale(1,-1)">
        <use href="#varied-outline" className="varied-outline" />
        {plan.holes.map(([x, y, r], index) => (
          <circle key={`h${index}`} cx={x} cy={y} r={r} fill="none" stroke={HOLE} className="varied-hole" />
        ))}
        {plan.pads.map(([ax, ay, bx, by], index) => (
          <line key={`p${index}`} x1={ax} y1={ay} x2={bx} y2={by} stroke={PAD} className="varied-pad" />
        ))}
        {plan.ribs.map(([ax, ay, bx, by, block], index) => (
          <line
            key={`r${index}`}
            x1={ax}
            y1={ay}
            x2={bx}
            y2={by}
            stroke={props.colours[block] ?? "#333"}
            className="varied-rib"
          />
        ))}
      </g>
    </svg>
  );
}
