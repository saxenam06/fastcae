/**
 * The agent's pane. Hidden until asked for, because an empty panel is worse than a wide view.
 *
 * Not built. It is shown rather than left out for the same reason the unbuilt stages are shown: a
 * shell that hides what is coming describes a tool, one that shows it describes a product. What it
 * must not do is pretend - there is no chat box here, because there is nothing behind one yet.
 */

import type { SessionState } from "../api/client";
import type { View } from "../app/product";

interface AgentPanelProps {
  session: SessionState;
  view: View;
  openQuestions: number;
}

const WHERE: Record<View, string> = {
  drawing: "reading the drawing",
  geometry: "the geometry and what was detected on it",
  field: "the field a design will be edited in",
  generate: "the levers on the geometry, and what they produce",
};

export function AgentPanel(props: AgentPanelProps) {
  return (
    <div className="agent-body">
      <section className="section">
        <header>Where you are</header>
        <div className="body">
          <dl className="kv compact">
            <dt>stage</dt>
            <dd>{props.session.stage === "model" ? "Model" : "Extract"}</dd>
            <dt>looking at</dt>
            <dd>{WHERE[props.view]}</dd>
            <dt>open questions</dt>
            <dd>{props.openQuestions}</dd>
          </dl>
          <div className="card-note">
            A question asked here will go to the stage it belongs to. Which stage that is decides
            which tools and which sources answer it, so it is worth being able to see.
          </div>
        </div>
      </section>

      <section className="section">
        <header>Not built</header>
        <div className="body">
          <div className="card-note">
            The agent will rank what is worth a person&rsquo;s attention, search a drawing for
            something you have labelled on the model, and propose associations it cannot confirm.
          </div>
          <div className="card-note">
            <b>It proposes; you dispose.</b> Nothing it produces enters the record as verified.
            Every proposal arrives as a task you confirm or decline, which is also what makes the
            person who decided it part of the provenance.
          </div>
        </div>
      </section>
    </div>
  );
}
