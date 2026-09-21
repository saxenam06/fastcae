/**
 * What the engineer is looking at: an entity, a group of them, or a step - and what that shows on
 * which canvas. The rail, the card and the canvases all read this one value; nothing else decides
 * what is highlighted.
 */

import type { CanvasName, EntitySummary, Group, Show, StepRun } from "../api/pipeline";

export interface Focus {
  kind: "entity" | "group" | "step";
  /** The step it belongs to. */
  step: string | null;
  group: Group | null;
  entity: string | null;
  /** What to show, merged over every entity in focus. */
  show: Show;
  /** Whether the camera goes to it: yes when it was picked in the rail or on a card, not when it
   * was clicked on the canvas, where it is already in view. */
  look?: boolean;
}

export const NOTHING: Show = {
  canvas: "none",
  faces: [],
  page: null,
  text: null,
  group: null,
  layers: [],
  point: null,
};

/** Where a step's work is seen, when it has no entities to say so. */
export const STEP_CANVAS: Record<string, CanvasName> = {
  discover: "none",
  "cad.load": "cad",
  "cad.health": "cad",
  "cad.atlas": "cad",
  "cad.features": "cad",
  "drawing.read": "drawing",
  crosscheck: "cad",
  "deck.read": "mesh",
  "deck.results": "mesh",
  "deck.anchor": "cad",
  space: "space",
};

/** One show for many entities: every face and layer of them, on the canvas most of them use. */
export function merged(members: EntitySummary[], fallback: CanvasName = "none"): Show {
  if (!members.length) return { ...NOTHING, canvas: fallback };
  if (members.length === 1) return members[0].show;
  const votes = new Map<CanvasName, number>();
  for (const m of members) {
    if (m.show.canvas !== "none") votes.set(m.show.canvas, (votes.get(m.show.canvas) ?? 0) + 1);
  }
  const canvas = [...votes.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? fallback;
  const faces = new Set<number>();
  const layers = new Set<string>();
  for (const m of members) {
    for (const f of m.show.faces) faces.add(f);
    for (const l of m.show.layers) layers.add(l);
  }
  return {
    canvas,
    faces: [...faces],
    page: null,
    text: null,
    group: null,
    layers: [...layers],
    point: null,
  };
}

export function stepFocus(step: StepRun, members: EntitySummary[]): Focus {
  const fallback = STEP_CANVAS[step.id] ?? "none";
  return { kind: "step", step: step.id, group: null, entity: null, show: merged(members, fallback) };
}
