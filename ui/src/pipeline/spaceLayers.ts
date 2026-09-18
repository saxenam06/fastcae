/**
 * The design space on the CAD: each layer a step made, in its own colour, and the per-face values
 * painted on the part. Colours say what a volume is for - green where metal may go, amber where an
 * answer is awaited, reds for what something else occupies, blue for the inside - and stay the same
 * on every part.
 */

import { useEffect, useRef, useState } from "react";
import type { VoxelCells } from "../api/client";
import type { FaceValues, LayerKey, PaintKind } from "../api/pipeline";
import { pipelineApi } from "../api/pipeline";
import type { VoxelLayer } from "../render/renderer";

type Rgb = [number, number, number];

export interface LayerStyle {
  key: LayerKey;
  label: string;
  tint: Rgb;
  alpha: number;
  /** The step that makes it. */
  step: string;
}

export const LAYER_GROUPS: { label: string; layers: LayerStyle[] }[] = [
  {
    label: "The grid",
    layers: [{ key: "part", label: "The part in cells", tint: [0.55, 0.58, 0.62], alpha: 0.35, step: "grid" }],
  },
  {
    label: "Design space",
    layers: [
      { key: "allowed", label: "Allowed", tint: [0.2, 0.62, 0.36], alpha: 0.55, step: "labels" },
      { key: "unknown", label: "Waiting on an answer", tint: [0.93, 0.64, 0.12], alpha: 0.7, step: "labels" },
      { key: "benefit", label: "Where metal helps", tint: [0.8, 0.3, 0.1], alpha: 1, step: "physics" },
    ],
  },
  {
    label: "Kept clear",
    layers: [
      { key: "plug", label: "What sits in a bore", tint: [0.78, 0.2, 0.2], alpha: 0.5, step: "sweeps" },
      { key: "beyond", label: "Beyond the bores", tint: [0.55, 0.12, 0.18], alpha: 0.45, step: "beyond" },
      { key: "mating", label: "What mates on a plane", tint: [0.88, 0.42, 0.2], alpha: 0.5, step: "sweeps" },
      { key: "ring", label: "What fits over a boss", tint: [0.7, 0.24, 0.55], alpha: 0.5, step: "sweeps" },
      { key: "hole", label: "Fastener and tool", tint: [0.45, 0.3, 0.72], alpha: 0.55, step: "sweeps" },
      { key: "buffer", label: "Buffer round frozen faces", tint: [0.42, 0.45, 0.5], alpha: 0.4, step: "sweeps" },
      { key: "waiting", label: "Round faces in doubt", tint: [0.93, 0.64, 0.12], alpha: 0.5, step: "sweeps" },
    ],
  },
  {
    label: "The inside",
    layers: [
      { key: "cavity", label: "Inside", tint: [0.25, 0.5, 0.86], alpha: 0.25, step: "inside" },
      { key: "leak", label: "Behind narrow openings", tint: [0.56, 0.36, 0.86], alpha: 0.55, step: "inside" },
    ],
  },
  {
    label: "Candidate",
    layers: [
      { key: "panel", label: "Layer over the wall", tint: [0.45, 0.74, 0.45], alpha: 0.45, step: "band" },
      { key: "pocket", label: "Pockets between features", tint: [0.12, 0.58, 0.6], alpha: 0.55, step: "band" },
    ],
  },
];

export const LAYER_STYLE = new Map<string, LayerStyle>(
  LAYER_GROUPS.flatMap((g) => g.layers.map((l) => [l.key, l] as const)),
);

export const DEFAULT_LAYERS: LayerKey[] = ["allowed", "unknown"];

/** The layers each step makes, by step. */
export const STEP_LAYERS: Record<string, LayerKey[]> = {};
for (const group of LAYER_GROUPS) {
  for (const layer of group.layers) (STEP_LAYERS[layer.step] ??= []).push(layer.key);
}

export const PAINTS: { key: PaintKind; label: string }[] = [
  { key: "thickness", label: "Wall thickness" },
  { key: "cap", label: "Height straight out" },
  { key: "interface", label: "Interfaces" },
  { key: "sealing", label: "Sealing walls" },
];

/** Interfaces by what froze them, or that they were asked about. */
export const INTERFACE_COLOURS: Record<string, { tint: Rgb; label: string }> = {
  deck_load: { tint: [0.1, 0.32, 0.72], label: "loaded by the deck" },
  deck_support: { tint: [0.1, 0.55, 0.55], label: "held by the deck" },
  drawing: { tint: [0.5, 0.28, 0.7], label: "toleranced on the drawing" },
  deck_hole_plane: { tint: [0.38, 0.45, 0.6], label: "clamped by a held bolt" },
  confirmed: { tint: [0.2, 0.6, 0.3], label: "confirmed by you" },
  asked: { tint: [0.93, 0.64, 0.12], label: "asked about" },
};

const SEALING: Rgb = [0.18, 0.42, 0.8];

/** Light to dark through the part's own range of values: the 5th to the 95th percentile. */
function ramp(values: number[], low: Rgb, high: Rgb): { at: (v: number) => Rgb; range: [number, number] } {
  const sorted = [...values].sort((a, b) => a - b);
  const lo = sorted[Math.floor(sorted.length * 0.05)] ?? 0;
  const hi = sorted[Math.floor(sorted.length * 0.95)] ?? 1;
  return {
    range: [lo, hi],
    at: (v: number) => {
      const t = hi > lo ? Math.min(Math.max((v - lo) / (hi - lo), 0), 1) : 0.5;
      return [0, 1, 2].map((i) => low[i] + (high[i] - low[i]) * t) as Rgb;
    },
  };
}

export interface Painted {
  kind: PaintKind;
  paint: Map<number, Rgb>;
  /** For values: the range the colours run over, in mm. */
  range: [number, number] | null;
  low: Rgb;
  high: Rgb;
}

export const THIN: Rgb = [0.99, 0.85, 0.45];
export const THICK: Rgb = [0.12, 0.25, 0.55];

export function painted(values: FaceValues): Painted {
  const paint = new Map<number, Rgb>();
  const entries = Object.entries(values.faces);
  if (values.kind === "interface") {
    for (const [face, group] of entries) {
      const colour = INTERFACE_COLOURS[String(group)];
      if (colour) paint.set(Number(face), colour.tint);
    }
    return { kind: values.kind, paint, range: null, low: THIN, high: THICK };
  }
  if (values.kind === "sealing") {
    for (const [face] of entries) paint.set(Number(face), SEALING);
    return { kind: values.kind, paint, range: null, low: SEALING, high: SEALING };
  }
  const numbers = entries.map(([, v]) => Number(v)).filter(Number.isFinite);
  const low: Rgb = values.kind === "cap" ? [0.85, 0.2, 0.15] : THIN;
  const high: Rgb = values.kind === "cap" ? [0.2, 0.6, 0.36] : THICK;
  const scale = ramp(numbers, low, high);
  for (const [face, v] of entries) {
    const n = Number(v);
    if (Number.isFinite(n)) paint.set(Number(face), scale.at(n));
  }
  return { kind: values.kind, paint, range: scale.range, low, high };
}

interface Loaded {
  version: number;
  cells: VoxelCells;
  values?: Float32Array;
  range?: [number, number];
}

/**
 * The layers shown, read from the server as they are first asked for and kept until the space
 * changes. A layer a run has not made yet is simply not there; one the space has replaced is shown
 * as it was until its new cells arrive, so the part never blinks empty in between.
 */
export function useSpaceLayers(active: boolean, version: number, shown: LayerKey[], done: Set<string>) {
  const cache = useRef(new Map<string, Loaded>());
  const [loaded, setLoaded] = useState(0);
  const [layers, setLayers] = useState<VoxelLayer[]>([]);

  const wanted = shown.filter((key) => done.has(LAYER_STYLE.get(key)?.step ?? ""));
  const wantedKey = wanted.join(",");

  useEffect(() => {
    if (!active) return;
    let live = true;
    const missing = wanted.filter((key) => cache.current.get(key)?.version !== version);
    Promise.all(
      missing.map(async (key) => {
        try {
          const cells = await pipelineApi.cells(key);
          if (key === "benefit") {
            const values = await pipelineApi.benefit();
            cache.current.set(key, { version, cells, values: values.values, range: values.range });
          } else {
            cache.current.set(key, { version, cells });
          }
        } catch {
          // Not made yet, or not made at all on this part: the layer stays as it was, or off.
        }
      }),
    ).then(() => live && setLoaded((n) => n + 1));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, version, wantedKey]);

  useEffect(() => {
    const out: VoxelLayer[] = [];
    for (const key of wanted) {
      const found = cache.current.get(key);
      const style = LAYER_STYLE.get(key);
      if (!found || !style) continue;
      out.push({
        key,
        cells: found.cells,
        tint: style.tint,
        alpha: style.alpha,
        values: found.values,
        range: found.range,
      });
    }
    setLayers(out);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, wantedKey, version]);

  return active ? layers : EMPTY_LAYERS;
}

const EMPTY_LAYERS: VoxelLayer[] = [];

/** A per-face paint, read once per space. */
export function useFacePaint(kind: PaintKind | null, version: number, ready: boolean): Painted | null {
  const [found, setFound] = useState<Painted | null>(null);
  const cache = useRef(new Map<string, Painted>());
  useEffect(() => {
    if (!kind || !ready) {
      setFound(null);
      return;
    }
    const key = `${version}:${kind}`;
    const known = cache.current.get(key);
    if (known) {
      setFound(known);
      return;
    }
    let live = true;
    pipelineApi
      .faces(kind)
      .then((values) => {
        const p = painted(values);
        cache.current.set(key, p);
        if (live) setFound(p);
      })
      .catch(() => live && setFound(null));
    return () => {
      live = false;
    };
  }, [kind, version, ready]);
  return found;
}
