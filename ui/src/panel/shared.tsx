/**
 * What the rib card and the study both show: where ribs would go, drawn as coloured lines with a key
 * to the colours; and text with the part's faces and features in it as chips that show them on the
 * part.
 */

import { useState, type ReactElement } from "react";

import type { CardPaths, StageKey, StageState, Verdict, VerdictRow } from "../api/client";
import type { LineSet } from "../render/renderer";

/** What became of a stretch of path, by its colour on the part. */
export const OUTCOMES: Record<string, { colour: [number, number, number]; label: string }> = {
  rib: { colour: [0.0, 0.62, 0.62], label: "a rib" },
  keep_out: { colour: [0.93, 0.55, 0.1], label: "stopped by something to keep clear of" },
  ended_elsewhere: { colour: [0.85, 0.2, 0.2], label: "ends on something not named" },
  open_end: { colour: [0.25, 0.45, 0.85], label: "ends at an edge with nothing to meet" },
  too_short: { colour: [0.6, 0.35, 0.8], label: "too short" },
  no_height: { colour: [0.6, 0.35, 0.8], label: "no room for its height" },
  crowded: { colour: [0.6, 0.35, 0.8], label: "no room for the mould beside another rib" },
  one_thing: { colour: [0.85, 0.2, 0.2], label: "ends on one thing at both ends" },
  one_side: { colour: [0.9, 0.45, 0.45], label: "runs within one side, not from one side to the other" },
  thin_wall: { colour: [0.85, 0.3, 0.1], label: "ends on a wall too thin for it" },
  thin_floor: { colour: [0.3, 0.3, 0.3], label: "left out: too thick for the floor under it" },
  closed: { colour: [0.75, 0.05, 0.35], label: "would reach a hole or bore the part keeps closed" },
  missed: { colour: [0.55, 0.55, 0.55], label: "misses where ribs stand" },
  pad: { colour: [0.9, 0.75, 0.1], label: "a pad: the wall thickened where a rib meets it" },
  hole: { colour: [0.85, 0.2, 0.65], label: "a hole" },
  left_out: { colour: [0.3, 0.3, 0.3], label: "left out so the rest hold together" },
};

/** Patterns as a person names them. */
export const PATTERN_NAMES: Record<string, string> = {
  parallel: "parallel",
  grid: "square grid",
  triangle: "triangle grid",
  radial: "spokes",
  free: "free lines",
};

/** Whether a setting makes any difference, given the patterns allowed: every setting does for
 * every pattern - how many and how far apart included - but what spokes turn about and how they
 * spread, which only spokes have. */
export function matters(name: string, patterns: string[]): boolean {
  if (!patterns.length) return true;
  if (name === "centre" || name === "spread") return patterns.includes("radial");
  return true;
}

/** The lines to draw on the part, each coloured by what became of it. What was made - ribs and
 * pads - drawn as their outline, as wide as they are; every piece of a line that was not made
 * drawn faint, in a paler shade of what became of it, so the eye goes to the ribs and a line over
 * a hole is plainly not one. */
export function toLines(paths: CardPaths): LineSet {
  const positions: number[] = [];
  const colours: number[] = [];
  const add = (a: number[], b: number[], colour: number[]) => {
    positions.push(...a, ...b);
    colours.push(...colour, ...colour);
  };
  for (const line of paths.lines) {
    const colour = (OUTCOMES[line.outcome] ?? OUTCOMES.missed).colour;
    const made = line.outcome === "rib" || line.outcome === "pad";
    if (made && line.mm && line.up) {
      const along = [0, 1, 2].map((i) => line.b[i] - line.a[i]);
      // Square to the rib, in the floor: across = along x up, a half-width long.
      const across = [
        along[1] * line.up[2] - along[2] * line.up[1],
        along[2] * line.up[0] - along[0] * line.up[2],
        along[0] * line.up[1] - along[1] * line.up[0],
      ];
      const size = Math.hypot(...across) || 1;
      const half = across.map((v) => (v / size) * (line.mm as number) * 0.5);
      const corner = (p: number[], sign: number) => p.map((v, i) => v + sign * half[i]);
      const [a1, a2, b1, b2] = [corner(line.a, 1), corner(line.a, -1), corner(line.b, 1), corner(line.b, -1)];
      add(a1, b1, colour);
      add(a2, b2, colour);
      add(a1, a2, colour);
      add(b1, b2, colour);
      continue;
    }
    add(line.a, line.b, made ? colour : colour.map((c) => 0.35 * c + 0.65 * 0.78));
  }
  return { positions: new Float32Array(positions), colours: new Float32Array(colours) };
}

/** What became of the lines, counted in words, and what each colour on the part means - the
 * words folded away when the key sits over the part. */
export function PathsKey({
  paths,
  note,
  folded = false,
  quiet = false,
}: {
  paths: CardPaths | null;
  note: string | null;
  folded?: boolean;
  /** The colours folded away too, with the words: only what was made shows. */
  quiet?: boolean;
}) {
  if (note || !paths) return <div className="card-note">{note}</div>;
  const shown = [...new Set(paths.lines.map((line) => line.outcome))];
  const legend = shown.map((outcome) => {
    const known = OUTCOMES[outcome] ?? OUTCOMES.missed;
    const [r, g, b] = known.colour.map((c) => Math.round(c * 255));
    return (
      <span key={outcome} className="paths-key-item">
        <span className="swatch" style={{ background: `rgb(${r}, ${g}, ${b})` }} />
        {known.label}
      </span>
    );
  });
  const many = (n: number, what: string) => `${n} ${what}${n === 1 ? "" : "s"}`;
  const made = `${many(paths.ribs, "rib")}${paths.pads ? ` · ${many(paths.pads, "pad")}` : ""}${
    paths.holes ? ` · ${many(paths.holes, "hole")}` : ""
  }`;
  if (quiet) {
    return (
      <div className="paths-key">
        <details className="paths-said">
          <summary className="verdict-line">
            {made} <span className="dim">- what the colours mean</span>
          </summary>
          <div className="paths-legend">{legend}</div>
          <div className="dim">{paths.summary}</div>
        </details>
      </div>
    );
  }
  return (
    <div className="paths-key">
      {folded ? (
        <details className="paths-said">
          <summary className="verdict-line">{made} - what became of each path</summary>
          <div className="dim">{paths.summary}</div>
        </details>
      ) : (
        <div className="verdict-line">{paths.summary}</div>
      )}
      {legend}
    </div>
  );
}

/** A face or feature id, as the card and the words write it - to find them all, and to ask
 * whether there is one (a global pattern remembers where it last matched). */
export const REFERENCE = /\b[a-z_]+:\d+\b/g;
export const HAS_REFERENCE = /\b[a-z_]+:\d+\b/;

/** Words with the faces and features in them as chips: a click shows one on the part. */
export function Said(props: {
  text: string;
  onShow: (refs: string[]) => void;
  names?: Record<string, string>;
}) {
  const pieces: (string | { ref: string })[] = [];
  let last = 0;
  for (const match of props.text.matchAll(REFERENCE)) {
    const at = match.index ?? 0;
    if (at > last) pieces.push(props.text.slice(last, at));
    pieces.push({ ref: match[0] });
    last = at + match[0].length;
  }
  if (last < props.text.length) pieces.push(props.text.slice(last));
  return (
    <>
      {pieces.map((piece, index) =>
        typeof piece === "string" ? (
          <span key={index}>{piece}</span>
        ) : (
          <button
            key={index}
            className="ref-inline"
            onClick={() => props.onShow([piece.ref])}
            title={props.names?.[piece.ref] ?? `show ${piece.ref} on the part`}
          >
            {piece.ref}
          </button>
        ),
      )}
    </>
  );
}

/** What the agent wrote, as plain lines: a line starting "- " is a point in a list, emphasis
 * marks are dropped, and faces and features are chips. */
export function Written({ text, onShow }: { text: string; onShow: (refs: string[]) => void }) {
  const lines = text
    .replace(/\*\*|__|`/g, "")
    .split("\n")
    .map((line) => line.trimEnd())
    .filter((line, index, all) => line || (index > 0 && all[index - 1]));
  const out: ReactElement[] = [];
  let points: string[] = [];
  const flush = () => {
    if (!points.length) return;
    out.push(
      <ul key={`list-${out.length}`} className="written-list">
        {points.map((point, index) => (
          <li key={index}>
            <Said text={point} onShow={onShow} />
          </li>
        ))}
      </ul>,
    );
    points = [];
  };
  for (const line of lines) {
    const point = /^\s*[-*]\s+(.*)$/.exec(line);
    if (point) {
      points.push(point[1]);
      continue;
    }
    flush();
    if (line)
      out.push(
        <p key={`line-${out.length}`}>
          <Said text={line} onShow={onShow} />
        </p>,
      );
  }
  flush();
  return <div className="written">{out}</div>;
}

/** What a design came out as when it was built: the outcome, and whatever did not pass. */
export function VerdictView({ verdict }: { verdict: Verdict }) {
  const [open, setOpen] = useState(false);
  const rows = [...verdict.constraints, ...verdict.checks];
  const shown = (row: VerdictRow) => row.outcome !== "pass" || row.check.startsWith("supports");
  const notPassed = rows.filter(shown);
  const passed = rows.filter((row) => !shown(row));
  const steps = Object.entries(verdict.steps ?? {});
  return (
    <div className="rib-verdict">
      <div className="verdict-line">
        <span className="chip" data-outcome={verdict.outcome}>
          {verdict.outcome}
        </span>{" "}
        {verdict.ribs} ribs{verdict.pads ? ` · ${verdict.pads} pads` : ""}
        {verdict.holes ? ` · ${verdict.holes} holes` : ""} ·{" "}
        {verdict.added_cm3 >= 0 ? "+" : ""}
        {verdict.added_cm3.toLocaleString(undefined, { maximumFractionDigits: 0 })} cm³
        {verdict.mass_kg ? ` · ${verdict.mass_kg} kg ${verdict.material ?? ""}` : ""} ·{" "}
        {verdict.fidelity} · study v{verdict.study_version ?? verdict.spec_version} ·{" "}
        <span
          title={
            steps.length
              ? steps.map(([step, seconds]) => `${step} ${seconds} s`).join("\n")
              : undefined
          }
        >
          {verdict.seconds} s
        </span>
      </div>
      {notPassed.map((row) => (
        <FindingLine key={row.check} row={row} />
      ))}
      {passed.length ? (
        <button className="link" onClick={() => setOpen((was) => !was)}>
          {open ? "hide what passed" : `${passed.length} passed`}
        </button>
      ) : null}
      {open ? passed.map((row) => <FindingLine key={row.check} row={row} />) : null}
    </div>
  );
}

export function FindingLine({
  row,
}: {
  row: Pick<VerdictRow, "check" | "outcome" | "reason" | "rule" | "seconds">;
}) {
  return (
    <div className="finding" data-outcome={row.outcome} title={row.rule}>
      <span className="mark">{row.outcome}</span>
      <span className="what">
        <b>{row.check}</b> {row.reason}
        {row.seconds !== undefined ? <span className="dim"> · {row.seconds} s</span> : null}
      </span>
    </div>
  );
}

/** The stages a design goes through, in order, as the letters the list shows them by. */
export const STAGE_KEYS: StageKey[] = ["P", "F", "M", "S", "R"];

export const STAGE_NAMES: Record<StageKey, string> = {
  P: "paths - placed and screened",
  F: "field - built and checked",
  M: "mesh",
  S: "solver setup",
  R: "results",
};

/** Where a design is in its stages: a letter a stage, filled once it is done. */
export function StageBadges({ stages }: { stages: Record<StageKey, StageState> }) {
  return (
    <span className="stage-badges">
      {STAGE_KEYS.map((key) => (
        <span
          key={key}
          className="stage-badge"
          data-state={stages[key]}
          title={`${STAGE_NAMES[key]}: ${stageSaid(stages[key])}`}
        >
          {key}
        </span>
      ))}
    </span>
  );
}

/** How a stage came out, in words. */
export function stageSaid(state: StageState): string {
  return state === "none" ? "not yet" : state === "done" ? "done" : state;
}

/** An error from the server, as the sentence it carries. */
export function plain(caught: unknown): string {
  const text = String(caught instanceof Error ? caught.message : caught);
  const body = text.indexOf("{");
  if (body >= 0) {
    try {
      const detail = (JSON.parse(text.slice(body)) as { detail?: unknown }).detail;
      if (typeof detail === "string") return detail;
    } catch {
      // Not JSON after all: say it as it came.
    }
  }
  return text;
}
