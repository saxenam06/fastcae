/**
 * The baseline's deck as the interface holds it: the summary, the mesh's outside, the glyphs, each
 * answer's fields as they are asked for, the signals, and whichever runner job is in flight.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Deck, JobStatus, Run, Signals, Values } from "../api/simulate";
import { sim } from "../api/simulate";
import type { GlyphData, Skin } from "../render/fe";
import { FE_COLOURS } from "../render/fe";

export interface DeckState {
  deck: Deck | null;
  skin: Skin | null;
  glyphs: GlyphData | null;
  signals: Signals | null;
  error: string | null;
  loading: boolean;
  reload: () => Promise<void>;
  colours: ([number, number, number] | null)[];
  roleOf: (group: string) => string[];
  field: (run: Run, name: string, vectors?: boolean) => Promise<Values>;
  difference: (name: string, a: Run, b: Run) => Promise<Values>;
  job: JobStatus | null;
  submit: (start: () => Promise<{ job: string }>) => Promise<void>;
}

/** Each patch's colour by what the deck does there: distributing couplings blue, rigid amber. */
export function patchColours(skin: Skin | null, deck: Deck | null): ([number, number, number] | null)[] {
  if (!skin || !deck?.setup) return [];
  const distributing = new Set(deck.setup.distributing.map((d) => d.group));
  const rigid = new Set(deck.setup.rigid.flatMap((r) => r.groups.filter((g) => g !== r.reference)));
  return skin.groupNames.map((name) => {
    if (distributing.has(name)) return FE_COLOURS.distributing as [number, number, number];
    if (rigid.has(name)) return FE_COLOURS.rigid as [number, number, number];
    return FE_COLOURS.support as [number, number, number];
  });
}

export function useDeck(active: boolean, project: string | null): DeckState {
  const [deck, setDeck] = useState<Deck | null>(null);
  const [skin, setSkin] = useState<Skin | null>(null);
  const [glyphs, setGlyphs] = useState<GlyphData | null>(null);
  const [signals, setSignals] = useState<Signals | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [job, setJob] = useState<JobStatus | null>(null);
  const cache = useRef(new Map<string, Values>());
  const loadedFor = useRef<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const found = await sim.deck();
      setDeck(found);
      cache.current.clear();
      if (found.present) {
        const [s, g, sig] = await Promise.all([sim.deckSkin(), sim.deckGlyphs(), sim.signals().catch(() => null)]);
        setSkin(s);
        setGlyphs(g);
        setSignals(sig);
      } else {
        setSkin(null);
        setGlyphs(null);
        setSignals(null);
      }
    } catch (caught) {
      setError(String(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!active || !project || loadedFor.current === project) return;
    loadedFor.current = project;
    void reload();
  }, [active, project, reload]);

  const field = useCallback(async (run: Run, name: string, vectors = false) => {
    const key = `${run}:${name}:${vectors}`;
    const known = cache.current.get(key);
    if (known) return known;
    const values = await sim.field(run, name, vectors);
    cache.current.set(key, values);
    return values;
  }, []);

  const difference = useCallback(async (name: string, a: Run, b: Run) => {
    const key = `diff:${name}:${a}:${b}`;
    const known = cache.current.get(key);
    if (known) return known;
    const values = await sim.difference(name, a, b);
    cache.current.set(key, values);
    return values;
  }, []);

  // A job in flight is followed until it ends; then everything it could have changed is read again.
  const submit = useCallback(
    async (start: () => Promise<{ job: string }>) => {
      const { job: id } = await start();
      setJob({ id, kind: "", project, state: "queued", message: "waiting for the runner" });
      for (;;) {
        await new Promise((r) => setTimeout(r, 1000));
        const status = await sim.job(id).catch(() => null);
        if (!status) continue;
        setJob(status);
        if (["done", "failed", "cancelled", "interrupted"].includes(status.state)) break;
      }
      await reload();
    },
    [project, reload],
  );

  const colours = useMemo(() => patchColours(skin, deck), [skin, deck]);
  const roleOf = useCallback(
    (group: string) => deck?.groups?.find((g) => g.name === group)?.roles ?? [],
    [deck],
  );

  return { deck, skin, glyphs, signals, error, loading, reload, colours, roleOf, field, difference, job, submit };
}
