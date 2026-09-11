/**
 * The rail for the Field tab: what the field is, and which layers are drawn.
 *
 * Three things can occupy the same space at once - the field's own cells, the surface contoured
 * out of them, and the tessellated B-rep they were built from - and the only way to tell which is
 * which is to be able to switch each off.
 */

import type { FieldSummary, SurfaceSummary } from "../api/client";

export interface Layers {
  /** The field's own cells. What the field literally holds. */
  voxels: boolean;
  /** The surface contoured out of the field. A reconstruction, not the field. */
  contour: boolean;
  /** The tessellated B-rep. What the field was built from, for reference. */
  geometry: boolean;
}

/**
 * Cells and contour are two drawings of **one** surface, in the same place.
 *
 * Whichever is in front hides the other completely, so having both on is twice the work for a
 * picture only one of them is in - and at 2.5 mm that is 21 million vertices a frame instead of
 * 10.8. Turning one on therefore turns the other off. Geometry is independent, because comparing
 * against it is the whole point of the tab.
 */
export function switchLayer(layers: Layers, name: keyof Layers): Layers {
  const next = { ...layers, [name]: !layers[name] };
  if (name === "voxels" && next.voxels) next.contour = false;
  if (name === "contour" && next.contour) next.voxels = false;
  return next;
}

/** What each layer is actually drawn in. Kept in step with the renderer by hand, because a
 *  swatch that disagrees with the picture is worse than no swatch at all. */
export const LAYER_COLOURS: Record<keyof Layers, string> = {
  voxels: "#0f3d91",
  contour: "#8a6a1f",
  geometry: "#a5a9a4",
};

const LAYER_LABELS: Record<keyof Layers, string> = {
  voxels: "Field cells",
  contour: "Contour",
  geometry: "Geometry",
};

interface FieldIndexProps {
  field: FieldSummary | null;
  surface: SurfaceSummary | null;
  layers: Layers;
  onLayers: (layers: Layers) => void;
  contourLoaded: boolean;
  voxelsLoaded: boolean;
  /** Vertices each layer costs per frame. The only honest answer to "why is this slow". */
  cost: Record<keyof Layers, number>;
  onSpacing: () => void;
}

export function FieldIndex(props: FieldIndexProps) {
  const { field, surface } = props;

  const toggle = (name: keyof Layers) => props.onLayers(switchLayer(props.layers, name));

  const detail = (name: keyof Layers) => {
    if (name === "contour" && !props.contourLoaded) return "not loaded";
    if (name === "voxels" && !props.voxelsLoaded) return "not loaded";
    return props.layers[name] ? millions(props.cost[name]) : "";
  };

  const drawn = (Object.keys(props.layers) as (keyof Layers)[])
    .filter((name) => props.layers[name])
    .reduce((total, name) => total + props.cost[name], 0);

  return (
    <nav className="index">
      <section className="section">
        <header>Layers</header>
        <div className="layers">
          {(Object.keys(LAYER_LABELS) as (keyof Layers)[]).map((name) => (
            <button
              key={name}
              data-on={props.layers[name]}
              onClick={() => toggle(name)}
              title={`Show or hide ${LAYER_LABELS[name].toLowerCase()}`}
            >
              <span className="swatch" style={{ background: LAYER_COLOURS[name] }} />
              {LAYER_LABELS[name]}
              <span className="detail">{detail(name)}</span>
            </button>
          ))}
        </div>
        <div className="card-note" style={{ padding: "0 12px 10px" }}>
          {millions(drawn)} vertices a frame. Cells and contour are two drawings of the same
          surface in the same place, so only one is ever shown.
        </div>
      </section>

      {field ? (
        <section className="section">
          <header>Field</header>
          <div className="body">
            <dl className="kv compact">
              <dt>voxel</dt>
              <dd>{field.spacing_mm} mm</dd>
              <dt>grid</dt>
              <dd>{field.shape.join(" × ")}</dd>
              <dt>band</dt>
              <dd>{millions(field.band_cells)} of {millions(field.cells)} cells</dd>
              <dt>solid</dt>
              <dd>{millions(field.solid_cells)} cells</dd>
              <dt>reach</dt>
              <dd>±{field.reach_mm} mm</dd>
              <dt>volume</dt>
              <dd>{field.volume_cm3.toLocaleString()} cm³</dd>
            </dl>
            <div className="card-note">
              Distance is stored within {field.reach_mm} mm of the surface; beyond it a cell carries
              only which side it is on.
            </div>
          </div>
        </section>
      ) : null}

      {surface ? (
        <section className="section">
          <header>Contour</header>
          <div className="body">
            <dl className="kv compact">
              <dt>triangles</dt>
              <dd>
                {surface.triangles.toLocaleString()}
                {surface.brep_triangles
                  ? ` · ${(surface.triangles / surface.brep_triangles).toFixed(1)}× the STEP`
                  : ""}
              </dd>
              <dt>volume</dt>
              <dd>
                {surface.volume_cm3.toLocaleString()} cm³
                {surface.volume_error_pct !== null ? ` · off by ${surface.volume_error_pct}%` : ""}
              </dd>
              <dt>closed</dt>
              <dd>
                {surface.watertight
                  ? "yes"
                  : `${surface.non_manifold_edges} non-manifold edges`}
              </dd>
            </dl>
            {!surface.watertight ? (
              <div className="warn">
                One vertex per cell cannot represent a cell the surface passes through twice, so
                thin features leave edges shared by more than two triangles. Fine to look at;
                not yet something a design can ship through.
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      <section className="section">
        <div className="actions" style={{ padding: "0 12px 12px" }}>
          <button onClick={props.onSpacing}>Different voxel</button>
        </div>
      </section>
    </nav>
  );
}

function millions(value: number): string {
  return value >= 1e6 ? `${(value / 1e6).toFixed(2)} M` : value.toLocaleString();
}
