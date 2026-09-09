/**
 * The left rail: what the model is made of.
 *
 * Ordered by what demands attention rather than alphabetically. Feature kinds arrive from the
 * server with their counts, so the filter builds itself - a bracket shows a bracket's kinds and
 * nothing here needs to know which is which.
 */

import type { Axis, Feature } from "../api/client";
import { FeatureRow } from "./cards";

interface ModelIndexProps {
  features: Feature[];
  kinds: { kind: string; count: number; controlled: number }[];
  axes: Axis[];
  selectedFaces: Set<number>;
  kindFilter: string | null;
  onKindFilter: (kind: string | null) => void;
  onSelectFeature: (feature: Feature) => void;
  view: "pipeline" | "geometry";
  onView: (view: "pipeline" | "geometry") => void;
}

const FEATURE_LIMIT = 60;

export function ModelIndex(props: ModelIndexProps) {
  const shown = props.features;
  // How many exist, not how many were fetched. The features route returns a capped page, so
  // counting what arrived would report 300 beside chips that add up to 719.
  const total = props.kindFilter
    ? (props.kinds.find((k) => k.kind === props.kindFilter)?.count ?? shown.length)
    : props.kinds.reduce((n, k) => n + k.count, 0);

  return (
    <nav className="index">
      <section className="section">
        <div className="viewswitch">
          <button data-active={props.view === "pipeline"} onClick={() => props.onView("pipeline")}>
            What was read
          </button>
          <button data-active={props.view === "geometry"} onClick={() => props.onView("geometry")}>
            Geometry
          </button>
        </div>
      </section>

      {props.axes.length ? (
        <section className="section">
          <header>
            Axes <span className="count">{props.axes.length}</span>
          </header>
          <div className="body">
            {props.axes.slice(0, 5).map((axis) => (
              <div key={axis.id} className="axis-row">
                <span className="mono">{axis.id}</span>
                <span className="detail">
                  ({axis.point[0].toFixed(0)}, {axis.point[1].toFixed(0)}) &middot;{" "}
                  {axis.feature_count} features
                </span>
              </div>
            ))}
            {props.axes.length > 5 ? (
              <div className="card-note">+{props.axes.length - 5} more</div>
            ) : null}
          </div>
        </section>
      ) : null}

      <section className="section">
        <header>
          Geometry <span className="count">{total}</span>
        </header>
        <div className="chips">
          <button data-active={props.kindFilter === null} onClick={() => props.onKindFilter(null)}>
            all
          </button>
          {props.kinds.map((kind) => (
            <button
              key={kind.kind}
              data-active={props.kindFilter === kind.kind}
              onClick={() => props.onKindFilter(kind.kind)}
              title={
                kind.controlled
                  ? `${kind.controlled} of ${kind.count} matched a controlled drawing dimension`
                  : `${kind.count} detected, none matched to the drawing`
              }
            >
              {kind.kind.replace(/_/g, " ")} <span className="count">{kind.count}</span>
            </button>
          ))}
        </div>
        {shown.slice(0, FEATURE_LIMIT).map((feature) => (
          <FeatureRow
            key={feature.id}
            feature={feature}
            onSelect={props.onSelectFeature}
            selected={feature.face_ids.some((id) => props.selectedFaces.has(id))}
          />
        ))}
        {total > FEATURE_LIMIT ? (
          <div className="card-note" style={{ padding: "6px 12px" }}>
            showing the largest {Math.min(FEATURE_LIMIT, shown.length)} of {total}
          </div>
        ) : null}
      </section>
    </nav>
  );
}
