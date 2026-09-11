/**
 * What is under the cursor: one face, by the one name that is its own - ``face:N`` - which the rib
 * card takes wherever it takes a feature, as a chip or in words.
 *
 * Small on purpose, on every 3D tab: it is read while looking at the part, not instead of it.
 * Hovering shows a face; clicking pins it, so it can be read while the cursor moves on. The name
 * can be selected as text, to type into the card's words.
 */

import type { FaceDetail } from "../api/client";

interface HoverCardProps {
  /** The face the card is about, or the design's own surface. Null: nothing under the cursor. */
  target: number | "design" | null;
  face: FaceDetail | null;
  pinned: boolean;
  onRelease: () => void;
}

export function HoverCard({ target, face, pinned, onRelease }: HoverCardProps) {
  if (target === null) return null;

  if (target === "design") {
    return (
      <aside className="hover-card" data-pinned={pinned}>
        <header>
          <span className="name">design</span>
          <span className="detail">ribs and fillets</span>
          {pinned ? <Release onRelease={onRelease} /> : null}
        </header>
      </aside>
    );
  }

  const known = face && face.face_id === target ? face : null;
  return (
    <aside className="hover-card" data-pinned={pinned}>
      <header>
        <span className="name" title="Its name - the rib card takes it as a chip or in words">
          face:{target}
        </span>
        <span className="detail">{known?.surface_type ?? ""}</span>
        {pinned ? <Release onRelease={onRelease} /> : null}
      </header>
      {known ? (
        <dl className="kv compact">
          <dt>area</dt>
          <dd>{known.area_mm2.toLocaleString(undefined, { maximumFractionDigits: 0 })} mm²</dd>
          {known.surface_type === "plane" && known.normal ? (
            <>
              <dt>faces</dt>
              <dd>{vector(known.normal)}</dd>
            </>
          ) : known.axis ? (
            <>
              <dt>axis</dt>
              <dd>{vector(known.axis)}</dd>
            </>
          ) : null}
          {known.diameter_mm !== null ? (
            <>
              <dt>Ø</dt>
              <dd>{known.diameter_mm}</dd>
            </>
          ) : null}
          {known.bbox_mm ? (
            <>
              <dt>z</dt>
              <dd>{range(known.bbox_mm[2], known.bbox_mm[5])}</dd>
            </>
          ) : null}
          {known.controlled ? (
            <>
              <dt>drawing</dt>
              <dd>controlled</dd>
            </>
          ) : null}
        </dl>
      ) : null}
    </aside>
  );
}

function Release({ onRelease }: { onRelease: () => void }) {
  return (
    <button className="release" onClick={onRelease} title="Stop pinning this face">
      ×
    </button>
  );
}

function vector(v: number[]): string {
  return v.map((c) => (Math.abs(c) < 5e-3 ? "0" : c.toFixed(2))).join("  ");
}

function range(lo: number, hi: number): string {
  return Math.abs(hi - lo) < 0.05 ? `${lo.toFixed(1)}` : `${lo.toFixed(1)} – ${hi.toFixed(1)}`;
}
