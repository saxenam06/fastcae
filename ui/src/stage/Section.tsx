/**
 * The section control, in the corner of every 3D canvas, and the one section every canvas reads.
 *
 * Held above the views rather than in any one of them: the plane is in the part's own frame, so
 * cutting the CAD at z = 60 mm and then opening the design space, a design's CAD or the deck's
 * answer shows the same cut there. Turning it off in any view turns it off everywhere.
 */

import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { Section, SectionAxis } from "./sectionPlane";
import { flipFor, offsetRange, SECTION_OFF, whereLabel } from "./sectionPlane";

interface SectionState {
  section: Section;
  setSection: (s: Section) => void;
}

const SectionContext = createContext<SectionState | null>(null);

export function SectionProvider({ children }: { children: ReactNode }) {
  const [section, setSection] = useState<Section>(SECTION_OFF);
  const value = useMemo(() => ({ section, setSection }), [section]);
  return <SectionContext.Provider value={value}>{children}</SectionContext.Provider>;
}

export function useSection(): SectionState {
  return useContext(SectionContext) ?? { section: SECTION_OFF, setSection: () => undefined };
}

const PRESETS: { axis: SectionAxis; label: string; title: string }[] = [
  { axis: "x", label: "X", title: "Square to the part's X axis" },
  { axis: "y", label: "Y", title: "Square to the part's Y axis" },
  { axis: "z", label: "Z", title: "Square to the part's Z axis" },
  { axis: "view", label: "facing me", title: "Square to the way you are looking now" },
];

/**
 * The button that turns a section on, and once on, the plane: square to an axis or to the view,
 * moved along its normal, tilted and turned to any orientation, flipped to keep the other side.
 */
export function SectionControl({
  bbox,
  facing,
}: {
  bbox: number[] | null | undefined;
  /** The way the viewer looks, towards them: what "facing me" sets the normal to. */
  facing: () => [number, number, number] | null;
}) {
  const { section, setSection } = useSection();
  // A cut chosen here faces the viewer here: "facing me" takes the view as it is now, and an axis
  // keeps the half away from them.
  const facingHere = (s: Section): Section => {
    const view = facing();
    if (s.axis === "view") return view ? { ...s, view, flip: false } : s;
    return { ...s, flip: flipFor(s, view) };
  };
  if (!section.on) {
    return (
      <button
        className="section-toggle"
        onClick={() => setSection(facingHere({ ...section, on: true }))}
        title="Cut the model with a plane: X, Y, Z, facing you, or any tilt"
      >
        <SectionIcon /> section
      </button>
    );
  }
  const [lo, hi] = offsetRange(section, bbox);
  const offset = Math.min(Math.max(section.offset, lo), hi);
  const set = (change: Partial<Section>) => setSection({ ...section, ...change });
  const choose = (axis: SectionAxis) => setSection(facingHere({ ...section, axis, tilt: 0, turn: 0, offset: 0 }));
  return (
    <div className="section-panel" onPointerDown={(e) => e.stopPropagation()}>
      <header>
        <b>Section</b>
        <span className="dim num">{whereLabel({ ...section, offset }, bbox)}</span>
        <button className="icon" onClick={() => set({ on: false })} title="No section">
          ×
        </button>
      </header>
      <span className="segmented">
        {PRESETS.map((p) => (
          <button key={p.axis} data-active={section.axis === p.axis} onClick={() => choose(p.axis)} title={p.title}>
            {p.label}
          </button>
        ))}
      </span>
      <label className="section-row" title="Move the plane along its normal">
        <span>at</span>
        <input
          type="range"
          min={lo}
          max={hi}
          step={Math.max((hi - lo) / 600, 0.01)}
          value={offset}
          onChange={(e) => set({ offset: Number(e.target.value) })}
          aria-label="where the plane is"
        />
        <span className="num">{Math.round(offset)}</span>
      </label>
      <label className="section-row" title="Tilt the plane about its first in-plane axis">
        <span>tilt</span>
        <input
          type="range"
          min={-90}
          max={90}
          step={1}
          value={section.tilt}
          onChange={(e) => set({ tilt: Number(e.target.value) })}
          aria-label="tilt"
        />
        <span className="num">{section.tilt}°</span>
      </label>
      <label className="section-row" title="Turn the plane about its second in-plane axis">
        <span>turn</span>
        <input
          type="range"
          min={-90}
          max={90}
          step={1}
          value={section.turn}
          onChange={(e) => set({ turn: Number(e.target.value) })}
          aria-label="turn"
        />
        <span className="num">{section.turn}°</span>
      </label>
      <div className="section-actions">
        <button data-active={section.flip} onClick={() => set({ flip: !section.flip })} title="Keep the other side">
          flip
        </button>
        <button
          onClick={() => setSection(facingHere({ ...section, tilt: 0, turn: 0, offset: 0 }))}
          title="Back to the centre, square, facing you"
        >
          reset
        </button>
      </div>
    </div>
  );
}

function SectionIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" aria-hidden="true">
      <rect x="1.5" y="1.5" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <path d="M1.5 11.5 L11.5 1.5" stroke="currentColor" strokeWidth="1.2" />
      <path d="M1.5 7 L7 1.5 M6 11.5 L11.5 6" stroke="currentColor" strokeWidth="0.8" opacity="0.6" />
    </svg>
  );
}
