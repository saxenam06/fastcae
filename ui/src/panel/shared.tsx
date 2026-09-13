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
  thin_wall: { colour: [0.85, 0.3, 0.1], label: "ends on a wall too thin for it" },
  missed: { colour: [0.55, 0.55, 0.55], label: "misses where ribs stand" },
  pad: { colour: [0.9, 0.75, 0.1], label: "a pad: the wall thickened where a rib meets it" },
  hole: { colour: [0.85, 0.2, 0.65], label: "a hole" },
};

/** The lines to draw on the part, each coloured by what became of it. */
export function toLines(paths: CardPaths): LineSet {
  const positions = new Float32Array(paths.lines.length * 6);
  const colours = new Float32Array(paths.lines.length * 6);
  paths.lines.forEach((line, index) => {
    positions.set([...line.a, ...line.b], index * 6);
    const colour = (OUTCOMES[line.outcome] ?? OUTCOMES.missed).colour;
    colours.set([...colour, ...colour], index * 6);
  });
  return { positions, colours };
}

/** What became of the lines, counted in words, and what each colour on the part means - the
 * words folded away when the key sits over the part. */
export function PathsKey({
  paths,
  note,
  folded = false,
}: {
  paths: CardPaths | null;
  note: string | null;
  folded?: boolean;
}) {
  if (note || !paths) return <div className="card-note">{note}</div>;
  const shown = [...new Set(paths.lines.map((line) => line.outcome))];
  return (
    <div className="paths-key">
      {folded ? (
        <details className="paths-said">
          <summary className="verdict-line">
            {paths.ribs} ribs{paths.pads ? ` · ${paths.pads} pads` : ""}
            {paths.holes ? ` · ${paths.holes} holes` : ""} - what became of each path
          </summary>
          <div className="dim">{paths.summary}</div>
        </details>
      ) : (
        <div className="verdict-line">{paths.summary}</div>
      )}
      {shown.map((outcome) => {
        const known = OUTCOMES[outcome] ?? OUTCOMES.missed;
        const [r, g, b] = known.colour.map((c) => Math.round(c * 255));
        return (
          <span key={outcome} className="paths-key-item">
            <span className="swatch" style={{ background: `rgb(${r}, ${g}, ${b})` }} />
            {known.label}
          </span>
        );
      })}
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
        {verdict.seconds} s
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

export function FindingLine({ row }: { row: Pick<VerdictRow, "check" | "outcome" | "reason" | "rule"> }) {
  return (
    <div className="finding" data-outcome={row.outcome} title={row.rule}>
      <span className="mark">{row.outcome}</span>
      <span className="what">
        <b>{row.check}</b> {row.reason}
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
