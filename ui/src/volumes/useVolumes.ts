/**
 * The design-volume view's state: the faces picked, the volume they bound - found again whenever the
 * picks, the band or the keep-outs change - and the volumes the project keeps, each drawn
 * see-through over the part.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import type { Mesh } from "../api/client";
import type { VolumeFound, VolumeKept } from "../api/volumes";
import { volumesApi } from "../api/volumes";
import type { Ghost } from "../render/renderer";

/** A volume being proposed: amber. */
export const PROPOSED_TINT: [number, number, number] = [0.93, 0.62, 0.16];
/** A volume the project keeps: teal. */
export const KEPT_TINT: [number, number, number] = [0.12, 0.58, 0.55];

export interface VolumesState {
  picks: number[];
  selected: Set<number>;
  band: [number, number] | null;
  off: string[];
  proposal: VolumeFound | null;
  finding: boolean;
  error: string | null;
  kept: VolumeKept[];
  hidden: Set<string>;
  ghosts: Ghost[];
  pick: (face: number, add: boolean) => void;
  unpick: (face: number) => void;
  clear: () => void;
  setBand: (band: [number, number] | null) => void;
  toggleOff: (keys: string[], off: boolean) => void;
  accept: (name: string | null) => Promise<void>;
  remove: (name: string) => Promise<void>;
  toggleHidden: (name: string) => void;
}

export function useVolumes(active: boolean): VolumesState {
  const [picks, setPicks] = useState<number[]>([]);
  const [band, setBand] = useState<[number, number] | null>(null);
  const [off, setOff] = useState<string[]>([]);
  const [proposal, setProposal] = useState<VolumeFound | null>(null);
  const [proposalMesh, setProposalMesh] = useState<Mesh | null>(null);
  const [finding, setFinding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [kept, setKept] = useState<VolumeKept[]>([]);
  const [meshes, setMeshes] = useState<Map<string, Mesh>>(new Map());
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [loaded, setLoaded] = useState(false);

  // The volumes the project keeps, once the view is first opened.
  useEffect(() => {
    if (!active || loaded) return;
    setLoaded(true);
    volumesApi
      .list()
      .then((r) => setKept(r.volumes))
      .catch((e: unknown) => setError(String((e as Error).message ?? e)));
  }, [active, loaded]);

  // Each kept volume's surface, fetched once.
  useEffect(() => {
    for (const volume of kept) {
      if (meshes.has(volume.key)) continue;
      volumesApi
        .mesh(volume.mesh)
        .then((mesh) => setMeshes((prev) => new Map(prev).set(volume.key, mesh)))
        .catch(() => undefined);
    }
  }, [kept, meshes]);

  // The volume the picks bound, found again a moment after they, the band or the keep-outs change.
  const picksKey = picks.join(",");
  const bandKey = band ? band.map((v) => v.toFixed(1)).join(",") : "";
  const offKey = off.join(",");
  useEffect(() => {
    if (!active || !picks.length) {
      setProposal(null);
      setProposalMesh(null);
      setFinding(false);
      return;
    }
    let live = true;
    setFinding(true);
    setError(null);
    const timer = window.setTimeout(() => {
      volumesApi
        .propose(picks, band, off)
        .then(async (found) => {
          if (!live) return;
          setProposal(found);
          // An empty volume has no surface to draw.
          const mesh = found.volume_L > 0 ? await volumesApi.mesh(found.mesh).catch(() => null) : null;
          if (live) setProposalMesh(mesh);
        })
        .catch((e: unknown) => {
          if (!live) return;
          setError(String((e as Error).message ?? e));
          setProposal(null);
          setProposalMesh(null);
        })
        .finally(() => {
          if (live) setFinding(false);
        });
    }, 250);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, picksKey, bandKey, offKey]);

  const pick = useCallback((face: number, add: boolean) => {
    setPicks((prev) => {
      if (add) return prev.includes(face) ? prev.filter((f) => f !== face) : [...prev, face];
      return prev.length === 1 && prev[0] === face ? [] : [face];
    });
    // New picks, new frame: the band and the keep-outs start from what these picks suggest.
    setBand(null);
    setOff([]);
  }, []);

  const unpick = useCallback((face: number) => {
    setPicks((prev) => prev.filter((f) => f !== face));
    setBand(null);
  }, []);

  const clear = useCallback(() => {
    setPicks([]);
    setBand(null);
    setOff([]);
  }, []);

  const toggleOff = useCallback((keys: string[], turnOff: boolean) => {
    setOff((prev) => {
      const next = new Set(prev);
      for (const key of keys) {
        if (turnOff) next.add(key);
        else next.delete(key);
      }
      return [...next].sort();
    });
  }, []);

  const accept = useCallback(
    async (name: string | null) => {
      if (!picks.length) return;
      const entry = await volumesApi.accept(picks, band ?? proposal?.band ?? null, off, name);
      if (proposalMesh) setMeshes((prev) => new Map(prev).set(entry.key, proposalMesh));
      setKept((prev) => [...prev, entry]);
      setPicks([]);
      setBand(null);
      setOff([]);
    },
    [picks, band, off, proposal, proposalMesh],
  );

  const remove = useCallback(async (name: string) => {
    const r = await volumesApi.remove(name);
    setKept(r.volumes);
  }, []);

  const toggleHidden = useCallback((name: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }, []);

  const ghosts = useMemo<Ghost[]>(() => {
    const out: Ghost[] = [];
    for (const volume of kept) {
      const mesh = meshes.get(volume.key);
      if (mesh && !hidden.has(volume.name)) out.push({ mesh, tint: KEPT_TINT, alpha: 0.32 });
    }
    if (proposalMesh && picks.length) out.push({ mesh: proposalMesh, tint: PROPOSED_TINT, alpha: 0.42 });
    return out;
  }, [kept, meshes, hidden, proposalMesh, picks.length]);

  const selected = useMemo(() => new Set(picks), [picks]);

  return {
    picks,
    selected,
    band,
    off,
    proposal,
    finding,
    error,
    kept,
    hidden,
    ghosts,
    pick,
    unpick,
    clear,
    setBand,
    toggleOff,
    accept,
    remove,
    toggleHidden,
  };
}
