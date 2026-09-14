/**
 * A solved design at its mesh, setup and results, from what the runner recorded: its mesh with the
 * deck's groups where they landed, the deck's supports, couplings and loads on it, and its answer
 * as contours - drawn as the baseline's are on Input, under the deck's names.
 */

import { useEffect, useMemo, useState } from "react";
import type { Deck, Values } from "../api/simulate";
import { sim } from "../api/simulate";
import { patchColours } from "../input/useDeck";
import { Provenance } from "../input/shared";
import type { GlyphData, Skin } from "../render/fe";
import { CameraLink, FeStage } from "../stage/FeStage";
import type { Hovered } from "../stage/FeStage";
import { Legend } from "../stage/Legend";

type Tab = "mesh" | "setup" | "results";
type FieldName = "von Mises" | "displacement" | "DX" | "DY" | "DZ";
const FIELDS: FieldName[] = ["von Mises", "displacement", "DX", "DY", "DZ"];
const UNIT: Record<FieldName, string> = {
  "von Mises": "MPa",
  displacement: "mm",
  DX: "mm",
  DY: "mm",
  DZ: "mm",
};

export function DesignFe({ run, index, tab }: { run: string; index: number; tab: Tab }) {
  const link = useMemo(() => new CameraLink(), []);
  const [deck, setDeck] = useState<Deck | null>(null);
  const [skin, setSkin] = useState<Skin | null>(null);
  const [glyphs, setGlyphs] = useState<GlyphData | null>(null);
  const [values, setValues] = useState<Values | null>(null);
  const [field, setField] = useState<FieldName>("von Mises");
  const [edges, setEdges] = useState(true);
  const [range, setRange] = useState<[number, number] | null>(null);
  const [hovered, setHovered] = useState<Hovered | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    sim.deck().then(setDeck).catch(() => setDeck(null));
  }, []);

  useEffect(() => {
    let live = true;
    setSkin(null);
    setError(null);
    sim
      .designSkin(run, index)
      .then((s) => live && setSkin(s))
      .catch((e) => live && setError(String(e)));
    return () => {
      live = false;
    };
  }, [run, index]);

  useEffect(() => {
    if (tab !== "setup") return;
    let live = true;
    sim
      .designGlyphs(run, index)
      .then((g) => live && setGlyphs(g))
      .catch((e) => live && setError(String(e)));
    return () => {
      live = false;
    };
  }, [run, index, tab]);

  useEffect(() => {
    if (tab !== "results") return;
    let live = true;
    setRange(null);
    sim
      .designField(run, index, field)
      .then((v) => live && setValues(v))
      .catch((e) => live && setError(String(e)));
    return () => {
      live = false;
    };
  }, [run, index, tab, field]);

  const colours = useMemo(() => patchColours(skin, deck), [skin, deck]);
  const bbox = useMemo(() => boundsOf(skin), [skin]);
  const data = useMemo(() => dataRange(values), [values]);
  const shown = range ?? data;

  return (
    <div className="fe-page">
      <div className="overlay">
        <button data-active={edges} onClick={() => setEdges(!edges)}>
          edges
        </button>
        {tab === "results"
          ? FIELDS.map((f) => (
              <button key={f} data-active={field === f} onClick={() => setField(f)}>
                {f}
              </button>
            ))
          : null}
      </div>
      <FeStage
        skin={skin}
        glyphs={tab === "setup" ? glyphs : null}
        values={tab === "results" ? values : null}
        mode={tab === "results" ? "contour" : "patches"}
        range={shown}
        groupColours={colours}
        edges={edges}
        showGlyphs={tab === "setup"}
        link={link}
        bbox={bbox}
        frameKey={`${run}:${index}`}
        onHover={setHovered}
        caption={
          <>
            <b>design #{index + 1}</b>{" "}
            {tab === "mesh" ? "CGAL from its field" : tab === "setup" ? "the deck's setup, by CAD face" : "cuDSS"}{" "}
            <Provenance kind="generated" />
          </>
        }
      />
      {tab === "results" && values ? (
        <Legend title={field} unit={UNIT[field]} range={shown} data={data} bands={48} onRange={setRange} />
      ) : null}
      <div className="fe-readout">
        {hovered ? (
          <>
            <b>{hovered.name}</b> <span className="dim">{hovered.detail}</span>
          </>
        ) : (
          <span className="dim">drag orbit · shift-drag pan · wheel zoom · hover a patch or glyph</span>
        )}
      </div>
      {error ? <div className="fe-error">{error}</div> : null}
    </div>
  );
}

function boundsOf(skin: Skin | null): number[] | null {
  if (!skin || !skin.positions.length) return null;
  const lo = [Infinity, Infinity, Infinity];
  const hi = [-Infinity, -Infinity, -Infinity];
  const p = skin.positions;
  for (let i = 0; i < p.length; i += 3) {
    for (let k = 0; k < 3; k++) {
      if (p[i + k] < lo[k]) lo[k] = p[i + k];
      if (p[i + k] > hi[k]) hi[k] = p[i + k];
    }
  }
  return [...lo, ...hi];
}

function dataRange(values: Values | null): [number, number] {
  if (!values) return [0, 1];
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values.values) {
    if (!Number.isFinite(v)) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  return lo === Infinity ? [0, 1] : lo === hi ? [lo, lo + 1e-12] : [lo, hi];
}
