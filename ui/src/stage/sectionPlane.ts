/**
 * A section: one plane cutting whatever the centre canvas shows, kept for every view.
 *
 * Every canvas draws the part in its own millimetre frame - the CAD, the design space's cells, a
 * design's metal, the deck's mesh and its answer - so one plane means the same cut in all of them,
 * and moving from one view to another keeps it where it was.
 *
 * The plane is chosen as a CAD tool offers it: square to one of the part's axes or to the view,
 * tilted by two angles to any orientation, moved along its normal, and flipped to keep the other
 * side. What is kept is the side ``normal . x <= d``.
 */

export type SectionAxis = "x" | "y" | "z" | "view";

export interface Section {
  on: boolean;
  axis: SectionAxis;
  /** The normal "facing me" was set with: towards the viewer when it was chosen. */
  view: [number, number, number];
  /** Degrees about the plane's first and second in-plane axes. */
  tilt: number;
  turn: number;
  /** Millimetres along the normal from the model's centre. */
  offset: number;
  /** Keep the other side. */
  flip: boolean;
}

export const SECTION_OFF: Section = {
  on: false,
  axis: "z",
  view: [0, 0, 1],
  tilt: 0,
  turn: 0,
  offset: 0,
  flip: false,
};

export interface Plane {
  normal: [number, number, number];
  d: number;
}

type Vec = [number, number, number];

const AXES: Record<Exclude<SectionAxis, "view">, Vec> = { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] };

function dot(a: Vec, b: Vec): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function cross(a: Vec, b: Vec): Vec {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

function unit(v: Vec): Vec {
  const l = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / l, v[1] / l, v[2] / l];
}

/** Rotate ``v`` by ``degrees`` about the unit axis ``k`` (Rodrigues). */
function rotate(v: Vec, k: Vec, degrees: number): Vec {
  const a = (degrees * Math.PI) / 180;
  const c = Math.cos(a);
  const s = Math.sin(a);
  const kv = cross(k, v);
  const kd = dot(k, v) * (1 - c);
  return [v[0] * c + kv[0] * s + k[0] * kd, v[1] * c + kv[1] * s + k[1] * kd, v[2] * c + kv[2] * s + k[2] * kd];
}

/** Two axes lying in the plane square to ``n``. */
function inPlane(n: Vec): [Vec, Vec] {
  const helper: Vec = Math.abs(n[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0];
  const u = unit(cross(n, helper));
  return [u, cross(n, u)];
}

/** The section's normal before it is flipped: its axis, tilted and turned. */
export function normalOf(s: Section): Vec {
  const base = unit(s.axis === "view" ? s.view : AXES[s.axis]);
  const [u, v] = inPlane(base);
  return unit(rotate(rotate(base, u, s.tilt), v, s.turn));
}

/**
 * Whether a fresh cut keeps the other side: a CAD tool opens a section with the half nearest the
 * viewer taken away, so the cut faces them. ``towards`` is the way the viewer looks, towards them.
 */
export function flipFor(s: Section, towards: [number, number, number] | null): boolean {
  return towards ? dot(normalOf(s), towards) < 0 : s.flip;
}

function centreOf(bbox: number[]): Vec {
  return [(bbox[0] + bbox[3]) / 2, (bbox[1] + bbox[4]) / 2, (bbox[2] + bbox[5]) / 2];
}

function cornersOf(bbox: number[]): Vec[] {
  const out: Vec[] = [];
  for (const x of [bbox[0], bbox[3]]) for (const y of [bbox[1], bbox[4]]) for (const z of [bbox[2], bbox[5]]) out.push([x, y, z]);
  return out;
}

/** The plane that cuts, or null when there is no section. */
export function planeOf(s: Section, bbox: number[] | null | undefined): Plane | null {
  if (!s.on || !bbox) return null;
  const n = normalOf(s);
  const d = dot(n, centreOf(bbox)) + s.offset;
  return s.flip ? { normal: [-n[0], -n[1], -n[2]], d: -d } : { normal: n, d };
}

/** How far the plane can move along its normal and still cross the model's box. */
export function offsetRange(s: Section, bbox: number[] | null | undefined): [number, number] {
  if (!bbox) return [-1, 1];
  const n = normalOf(s);
  const c = dot(n, centreOf(bbox));
  const along = cornersOf(bbox).map((p) => dot(n, p) - c);
  return [Math.min(...along), Math.max(...along)];
}

/** Where the plane is, in words: a coordinate when it is square to an axis, else from the centre. */
export function whereLabel(s: Section, bbox: number[] | null | undefined): string {
  if (!bbox) return "";
  if (s.axis !== "view" && s.tilt === 0 && s.turn === 0) {
    const k = { x: 0, y: 1, z: 2 }[s.axis];
    return `${s.axis} = ${Math.round(centreOf(bbox)[k] + s.offset)} mm`;
  }
  const sign = s.offset > 0 ? "+" : "";
  return `${sign}${Math.round(s.offset)} mm from the centre`;
}

/**
 * The plane's outline inside the model's box, as line segments (two points each): where the cut
 * is, drawn over the picture.
 */
export function outlineOf(plane: Plane, bbox: number[]): Float32Array {
  const n = plane.normal;
  const corners = cornersOf(bbox);
  // The box's twelve edges, as pairs of corner indices (corner bits: x, y, z from high to low).
  const edges = [
    [0, 1], [2, 3], [4, 5], [6, 7],
    [0, 2], [1, 3], [4, 6], [5, 7],
    [0, 4], [1, 5], [2, 6], [3, 7],
  ];
  const points: Vec[] = [];
  for (const [i, j] of edges) {
    const a = corners[i];
    const b = corners[j];
    const sa = dot(n, a) - plane.d;
    const sb = dot(n, b) - plane.d;
    if ((sa < 0 && sb >= 0) || (sa >= 0 && sb < 0)) {
      const t = sa / (sa - sb);
      points.push([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), a[2] + t * (b[2] - a[2])]);
    }
  }
  if (points.length < 3) return new Float32Array(0);
  // Round the polygon's centre, in the plane's own axes.
  const mid: Vec = [0, 1, 2].map((k) => points.reduce((sum, p) => sum + p[k], 0) / points.length) as Vec;
  const [u, v] = inPlane(n);
  points.sort((p, q) => {
    const dp: Vec = [p[0] - mid[0], p[1] - mid[1], p[2] - mid[2]];
    const dq: Vec = [q[0] - mid[0], q[1] - mid[1], q[2] - mid[2]];
    return Math.atan2(dot(dp, v), dot(dp, u)) - Math.atan2(dot(dq, v), dot(dq, u));
  });
  const out: number[] = [];
  points.forEach((p, k) => out.push(...p, ...points[(k + 1) % points.length]));
  return new Float32Array(out);
}

/** The same plane, one key: a change of it changes the key, and nothing else does. */
export function planeKey(plane: Plane | null): string {
  if (!plane) return "";
  return [...plane.normal, plane.d].map((v) => v.toFixed(4)).join(",");
}
