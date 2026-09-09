/**
 * What the pipeline produced. Data, not prose.
 *
 * Skipped steps are shown rather than hidden: for a project with no drawing, "no Drawing" is the
 * most informative row on the screen, and hiding it leaves someone unsure whether the drawing was
 * read badly or not at all.
 */

import type { Callout, Step, Summary } from "../api/client";
import { CalloutRow, Metric, StepCard } from "../panel/cards";

interface PipelineStageProps {
  summary: Summary;
  steps: Step[];
  callouts: Callout[];
}

export function PipelineStage(props: PipelineStageProps) {
  const { summary } = props;
  const toleranced = props.callouts
    .filter((c) => c.tolerance !== null)
    .sort((a, b) => (b.nominal ?? 0) - (a.nominal ?? 0));
  const counted = props.callouts
    .filter((c) => c.count !== null && c.nominal !== null)
    .sort((a, b) => (b.count ?? 0) - (a.count ?? 0));

  return (
    <div className="stage-scroll">
      <div className="metrics">
        <Metric label="faces" value={summary.faces} />
        <Metric label="features" value={summary.features} />
        <Metric label="volume" value={summary.volume_cm3} unit="cm³" />
        <Metric label="surface" value={summary.area_m2} unit="m²" />
        <Metric
          label="watertight"
          value={summary.watertight === null ? null : summary.watertight ? "yes" : "no"}
          tone={summary.watertight ? "ok" : "bad"}
        />
        <Metric label="controlled" value={summary.controlled_faces} />
        <Metric label="extract" value={summary.seconds} unit="s" />
      </div>

      <section className="block">
        <h2>Pipeline</h2>
        <div className="cards">
          {props.steps.map((step) => (
            <StepCard key={step.id} step={step} />
          ))}
        </div>
      </section>

      {toleranced.length ? (
        <section className="block">
          <h2>
            Controlled sizes <span className="count">{toleranced.length}</span>
          </h2>
          {toleranced.map((callout, index) => (
            <CalloutRow key={index} callout={callout} />
          ))}
        </section>
      ) : null}

      {counted.length ? (
        <section className="block">
          <h2>
            Counted features <span className="count">{counted.length}</span>
          </h2>
          {counted.slice(0, 20).map((callout, index) => (
            <CalloutRow key={index} callout={callout} />
          ))}
        </section>
      ) : null}
    </div>
  );
}
