/**
 * Design volumes over HTTP: what picked faces bound, and the volumes the project keeps.
 */

import { fetchMesh } from "./client";
import type { Mesh } from "./client";

export interface KeptClear {
  key: string;
  kind: "bore" | "beyond" | "line" | "hole" | "lid";
  ref: string;
  words: string;
  off: boolean;
}

/** A volume found from picks: its recipe, what it holds, and where its surface is. */
export interface VolumeFound {
  key: string;
  faces: number[];
  kind: "floor" | "between";
  axis: [number, number, number];
  point: [number, number, number];
  band: [number, number];
  band_default: [number, number];
  band_limits: [number, number];
  radius_mm: number;
  anchors: number[];
  floors: number[];
  off: string[];
  volume_L: number;
  pockets: number;
  left_out: number;
  keepouts: KeptClear[];
  words: string;
  seconds: number;
  mesh: string;
}

/** A volume the project keeps. */
export interface VolumeKept {
  name: string;
  accepted: string;
  recipe: { faces: number[]; band: [number, number]; off: string[]; axis: number[]; point: number[] };
  volume_L: number;
  words: string;
  key: string;
  mesh: string;
}

async function send<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const text = await response.text();
    let said = text;
    try {
      said = (JSON.parse(text) as { detail?: string }).detail ?? text;
    } catch {
      // not JSON: the text as it is
    }
    throw new Error(said);
  }
  return response.json() as Promise<T>;
}

function posted(body: unknown): RequestInit {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export const volumesApi = {
  propose: (faces: number[], band: [number, number] | null, off: string[]) =>
    send<VolumeFound>("/api/volumes/propose", posted({ faces, band, off })),
  list: () => send<{ volumes: VolumeKept[] }>("/api/volumes"),
  accept: (faces: number[], band: [number, number] | null, off: string[], name: string | null) =>
    send<VolumeKept>("/api/volumes", posted({ faces, band, off, name })),
  remove: (name: string) =>
    send<{ volumes: VolumeKept[] }>(`/api/volumes/${encodeURIComponent(name)}`, { method: "DELETE" }),
  mesh: (path: string): Promise<Mesh> => fetchMesh(path),
};
