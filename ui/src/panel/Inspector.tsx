/**
 * What is selected, what it geometrically is, and how anything about it is known.
 *
 * Everything here is geometric or evidential. What a bore is *for* is not something this panel
 * claims. What it does claim is that a toleranced drawing dimension matched it, and it shows the
 * page and the literal text so anyone can check.
 */

import type { FaceDetail, Feature, Selection } from "../api/client";
import { FactCard, FeatureRow, Metric } from "./cards";

interface InspectorProps {
  face: FaceDetail | null;
  selection: Selection | null;
  onGrow: () => void;
  onSimilar: () => void;
  onClear: () => void;
  onSelectFeature: (feature: Feature) => void;
  growAngle: number;
  onGrowAngle: (angle: number) => void;
}

export function Inspector(props: InspectorProps) {
  const { face, selection } = props;

  return (
    <div className="selection-panel">
      <section className="section">
        <header>
          Selection {selection ? <span className="count">{selection.count} faces</span> : null}
        </header>
        <div className="body">
          {selection ? (
            <>
              <div className="metrics">
                <Metric label="faces" value={selection.count} />
                <Metric
                  label="area"
                  value={
                    selection.area_mm2 >= 1e6
                      ? Number((selection.area_mm2 / 1e6).toFixed(3))
                      : Math.round(selection.area_mm2)
                  }
                  unit={selection.area_mm2 >= 1e6 ? "m²" : "mm²"}
                />
                <Metric
                  label="controlled"
                  value={selection.controlled_face_ids.length}
                  tone={selection.touches_controlled ? "warn" : undefined}
                />
              </div>
              <div className="card-note">{selection.reason}</div>
              {selection.touches_controlled ? (
                <div className="conflict" style={{ marginTop: 8 }}>
                  <div className="subject">
                    Includes {selection.controlled_face_ids.length} controlled faces
                  </div>
                  <div className="card-note">Toleranced on the drawing. Cannot be moved.</div>
                </div>
              ) : null}
            </>
          ) : (
            <div className="empty">Nothing selected. Click a face.</div>
          )}

          <div className="actions">
            <button onClick={props.onGrow} disabled={!face && !selection}>
              Grow
            </button>
            <button onClick={props.onSimilar} disabled={!face}>
              Similar
            </button>
            <button onClick={props.onClear} disabled={!selection}>
              Clear
            </button>
          </div>
          <label className="slider">
            grow angle
            <input
              type="range"
              min={5}
              max={90}
              step={5}
              value={props.growAngle}
              onChange={(event) => props.onGrowAngle(Number(event.target.value))}
            />
            <span className="mono">{props.growAngle}&deg;</span>
          </label>
        </div>
      </section>

      {face ? (
        <>
          <section className="section">
            <header>
              Face {face.face_id}
              {face.controlled ? (
                <span className="state" data-state="measured">
                  controlled
                </span>
              ) : null}
            </header>
            <div className="body">
              <dl className="kv">
                <dt>surface</dt>
                <dd>{face.surface_type}</dd>
                {face.diameter_mm !== null ? (
                  <>
                    <dt>diameter</dt>
                    <dd>&#8960;{face.diameter_mm.toFixed(2)} mm</dd>
                  </>
                ) : null}
                {face.minor_radius_mm !== null ? (
                  <>
                    <dt>blend radius</dt>
                    <dd>{face.minor_radius_mm.toFixed(2)} mm</dd>
                  </>
                ) : null}
                <dt>area</dt>
                <dd>
                  {face.area_mm2.toLocaleString()} mm&sup2;
                  {!face.analytic_area_is_valid ? (
                    <span
                      className="state"
                      data-state="conflicted"
                      style={{ marginLeft: 6 }}
                      title={`the kernel reports ${face.analytic_area_mm2} mm2 analytically`}
                    >
                      analytic area invalid
                    </span>
                  ) : null}
                </dd>
                <dt>station z</dt>
                <dd>{face.z_mm.toFixed(1)} mm</dd>
                <dt>visibility</dt>
                <dd>{face.exterior ? "exterior" : "internal"}</dd>
                {face.concave !== null ? (
                  <>
                    <dt>curvature</dt>
                    <dd>{face.concave ? "concave" : "convex"}</dd>
                  </>
                ) : null}
                <dt>neighbours</dt>
                <dd>{face.neighbours.length}</dd>
              </dl>
            </div>
          </section>

          {face.features.length ? (
            <section className="section">
              <header>
                Belongs to <span className="count">{face.features.length}</span>
              </header>
              <div className="body" style={{ padding: 0 }}>
                {face.features.map((feature) => (
                  <FeatureRow
                    key={feature.id}
                    feature={feature}
                    onSelect={props.onSelectFeature}
                    selected={false}
                  />
                ))}
              </div>
              {face.features
                .filter((f) => f.controlled)
                .map((f) => (
                  <div key={f.id} className="body">
                    <FactCard label="controlled" fact={f.controlled!} />
                  </div>
                ))}
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
