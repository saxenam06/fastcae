/**
 * Input → Mesh & setup: the deck's mesh, and every support, coupling and load where the deck puts
 * it, under the deck's own names. Nothing here is fastcae's: it is what the engineer's deck says,
 * read and drawn. What the deck holds is listed by the pipeline, on the left; picking a group there
 * lights it here.
 */

import { useMemo, useState } from "react";
import { sim } from "../api/simulate";
import { FE_COLOURS } from "../render/fe";
import { CameraLink, FeStage } from "../stage/FeStage";
import type { Hovered } from "../stage/FeStage";
import type { DeckState } from "./useDeck";
import { Provenance } from "./shared";

export interface MeshView {
  link: CameraLink;
  edges: boolean;
  setEdges: (v: boolean) => void;
  glyphs: boolean;
  setGlyphs: (v: boolean) => void;
  patches: boolean;
  setPatches: (v: boolean) => void;
  hovered: Hovered | null;
  setHovered: (h: Hovered | null) => void;
  focus: string | null;
  setFocus: (g: string | null) => void;
}

export function useMeshView(): MeshView {
  const link = useMemo(() => new CameraLink(), []);
  const [edges, setEdges] = useState(true);
  const [glyphs, setGlyphs] = useState(true);
  const [patches, setPatches] = useState(true);
  const [hovered, setHovered] = useState<Hovered | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  return { link, edges, setEdges, glyphs, setGlyphs, patches, setPatches, hovered, setHovered, focus, setFocus };
}

/** The deck's mesh cut by the section's plane: its elements' edges on the cut. */
const DECK_MESH_SECTION = { key: "deck:mesh", fetch: sim.section };

function rgb(c: number[]): string {
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export function MeshStage({ state, view }: { state: DeckState; view: MeshView }) {
  const { deck, skin } = state;
  const focusIndex = view.focus && skin ? skin.groupNames.indexOf(view.focus) : -1;
  const hoveredIndex = view.hovered?.pick.kind === "group" ? view.hovered.pick.index : focusIndex;
  if (!deck?.present) {
    return <div className="stage-page"><div className="later"><h2>Mesh &amp; setup</h2><p>No solver deck in this project.</p></div></div>;
  }
  return (
    <>
      <FeStage
        skin={skin}
        glyphs={state.glyphs}
        mode={view.patches ? "patches" : "plain"}
        groupColours={state.colours}
        edges={view.edges}
        showGlyphs={view.glyphs}
        link={view.link}
        bbox={deck.mesh?.bbox_mm}
        frameKey="deck"
        hoveredGroup={hoveredIndex}
        onHover={view.setHovered}
        sectionSource={DECK_MESH_SECTION}
        caption={
          <>
            <b>{deck.files.find((f) => f.role === "mesh")?.name}</b> <Provenance kind="imported" />
          </>
        }
      />
      <div className="overlay">
        <button data-active={view.edges} onClick={() => view.setEdges(!view.edges)}>
          edges
        </button>
        <button data-active={view.patches} onClick={() => view.setPatches(!view.patches)}>
          groups
        </button>
        <button data-active={view.glyphs} onClick={() => view.setGlyphs(!view.glyphs)}>
          supports · couplings · loads
        </button>
      </div>
      <div className="fe-key">
        <span><i style={{ background: rgb(FE_COLOURS.distributing) }} /> distributing coupling</span>
        <span><i style={{ background: rgb(FE_COLOURS.rigid) }} /> rigid coupling</span>
        <span><i style={{ background: rgb(FE_COLOURS.spokes) }} /> spokes</span>
        <span><i style={{ background: rgb(FE_COLOURS.support) }} /> held</span>
        <span><i style={{ background: rgb(FE_COLOURS.x) }} /><i style={{ background: rgb(FE_COLOURS.y) }} /><i style={{ background: rgb(FE_COLOURS.z) }} /> force X Y Z</span>
      </div>
      <div className="fe-readout">
        {view.hovered ? (
          <>
            <b className="mono">{view.hovered.name}</b>{" "}
            <span className="dim">{view.hovered.detail || state.roleOf(view.hovered.name).join(", ")}</span>
          </>
        ) : (
          <span className="dim">drag orbit · shift-drag pan · wheel zoom · hover a patch or glyph</span>
        )}
      </div>
    </>
  );
}
