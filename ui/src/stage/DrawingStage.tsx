/**
 * What the drawing said, callout by callout.
 *
 * Every row shows the parsed reading beside the **literal text** it came from, because that is
 * what makes a reading checkable: anyone can search the page for that string and judge it. A
 * reading with no source text next to it is a number somebody has to take on trust.
 *
 * The sheet itself is not drawn yet. Text extraction gives no coordinates, so there is nothing to
 * put a box around - see docs/verification.md for what changes when there is.
 */

import type { Callout, Step } from "../api/client";
import { Metric } from "../panel/cards";

interface DrawingStageProps {
  callouts: Callout[];
  all: Callout[];
  steps: Step[];
  filter: string | null;
  pages: number | null;
}

export function DrawingStage(props: DrawingStageProps) {
  const drawingStep = props.steps.find((step) => step.id === "drawing.read");

  if (drawingStep && drawingStep.status === "skipped") {
    return (
      <div className="empty-stage">
        <p>{drawingStep.detail}</p>
        <p className="card-note">
          Everything derivable from the CAD alone still ran. A project without a drawing is not a
          broken project.
        </p>
      </div>
    );
  }

  const toleranced = props.all.filter((c) => c.tolerance !== null).length;
  const counted = props.all.filter((c) => c.count !== null).length;

  return (
    <div className="stage-scroll">
      <div className="metrics">
        <Metric label="pages" value={props.pages} />
        <Metric label="callouts" value={props.all.length} />
        <Metric label="toleranced" value={toleranced} />
        <Metric label="counted" value={counted} />
      </div>

      <section className="block">
        <h2>
          {props.filter ? props.filter.replace(/_/g, " ") : "Every callout"}{" "}
          <span className="count">{props.callouts.length}</span>
        </h2>
        <div className="callouts">
          {props.callouts.map((callout, index) => (
            <div key={index} className="callout">
              <span className="kind">p{callout.page}</span>
              <span className="mono">
                {callout.count ? `${callout.count}× ` : ""}
                {callout.is_diameter ? "⌀" : ""}
                {callout.nominal !== null
                  ? callout.nominal.toFixed(callout.tolerance ? 3 : 2)
                  : ""}
                {callout.tolerance ? ` ±${callout.tolerance.toFixed(3)}` : ""}
                {callout.through ? " THRU" : ""}
                {callout.nominal === null && callout.text ? callout.text : ""}
              </span>
              <span className="raw">{callout.raw}</span>
            </div>
          ))}
        </div>
        {props.callouts.length === 0 ? (
          <div className="empty">Nothing of that kind on this drawing.</div>
        ) : null}
      </section>
    </div>
  );
}
