/**
 * The design space on the CAD: one volume of cells, drawn opaque in its own green - or, asked for,
 * coloured by where metal helps, on a heat scale. The same colours on every part.
 */

import { useEffect, useRef, useState } from "react";
import type { VoxelCells } from "../api/client";
import { pipelineApi } from "../api/pipeline";
import type { VoxelLayer } from "../render/renderer";

type Rgb = [number, number, number];

/** The design space's own colour: green, where metal may go. */
export const SPACE_TINT: Rgb = [0.2, 0.62, 0.36];

interface Loaded {
  version: number;
  cells: VoxelCells;
  values?: Float32Array;
  range?: [number, number];
}

/**
 * The design space's cells, read once per space and kept; with ``heat``, where metal helps on each
 * of them. Nothing while it is being read or defined.
 */
export function useDesignSpace(active: boolean, version: number, heat: boolean, ready: boolean) {
  const cache = useRef<Loaded | null>(null);
  const [layers, setLayers] = useState<VoxelLayer[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!active || !ready) return;
    let live = true;
    const load = async () => {
      let found = cache.current;
      if (!found || found.version !== version) {
        found = { version, cells: await pipelineApi.cells() };
        cache.current = found;
      }
      if (heat && !found.values) {
        try {
          const values = await pipelineApi.benefit();
          found.values = values.values;
          found.range = values.range;
        } catch (caught) {
          if (live) setError(String(caught));
        }
      }
      if (!live) return;
      setLayers([
        {
          key: "design",
          cells: found.cells,
          tint: SPACE_TINT,
          alpha: 1,
          values: heat ? found.values : undefined,
          range: heat ? found.range : undefined,
        },
      ]);
    };
    load().catch((caught) => live && setError(String(caught)));
    return () => {
      live = false;
    };
  }, [active, version, heat, ready]);

  return { layers: active && ready ? layers : EMPTY_LAYERS, error };
}

const EMPTY_LAYERS: VoxelLayer[] = [];
