/**
 * Small pieces the Input and Variant Setup views share: where a thing came from, and how numbers
 * are written.
 */

import type { Provenance as Kind } from "../api/simulate";

const WORDS: Record<Kind, string> = {
  imported: "imported",
  derived: "derived",
  generated: "generated",
};

const TIPS: Record<Kind, string> = {
  imported: "Read from the engineer's files, as they are",
  derived: "Computed by fastcae from the engineer's files, without solving",
  generated: "Meshed or solved by fastcae",
};

/** Where something on screen came from: the engineer's files, computed from them, or made here. */
export function Provenance({ kind, small }: { kind: Kind; small?: boolean }) {
  return (
    <span className="prov" data-kind={kind} data-small={small ?? false} title={TIPS[kind]}>
      {WORDS[kind]}
    </span>
  );
}

export function fmtCount(n: number): string {
  return n.toLocaleString("en-GB");
}

export function fmtSeconds(s: number | undefined | null): string {
  if (s === undefined || s === null || !Number.isFinite(s)) return "–";
  if (s < 60) return `${s.toFixed(s < 10 ? 1 : 0)} s`;
  return `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`;
}

export function fmtRelative(d: number): string {
  if (!Number.isFinite(d)) return "–";
  const a = Math.abs(d);
  if (a === 0) return "0";
  if (a < 1e-4) return d.toExponential(1);
  return `${(d * 100).toFixed(a < 0.01 ? 3 : 2)} %`;
}
