/**
 * The rail for the Drawing tab: what was read off the sheets, and what could not be.
 *
 * Nothing here is geometric. This tab answers "what did the drawing say", so the rail is the
 * grammar it was read with - counted callouts, toleranced pairs, threads, datums - and the steps
 * that did the reading, warnings included. A project with no drawing gets a rail that says so
 * rather than an empty panel that looks broken.
 */

import type { Callout, Step } from "../api/client";

interface DrawingIndexProps {
  steps: Step[];
  callouts: Callout[];
  pages: number | null;
  filter: string | null;
  onFilter: (kind: string | null) => void;
}

export function DrawingIndex(props: DrawingIndexProps) {
  const byKind = new Map<string, number>();
  for (const callout of props.callouts) {
    byKind.set(callout.kind, (byKind.get(callout.kind) ?? 0) + 1);
  }

  const steps = props.steps.filter((step) => step.needs.includes("drawing"));

  return (
    <nav className="index">
      {byKind.size ? (
        <section className="section">
          <header>
            Callouts <span className="count">{props.callouts.length}</span>
          </header>
          <div className="chips">
            <button data-active={props.filter === null} onClick={() => props.onFilter(null)}>
              all
            </button>
            {[...byKind.entries()]
              .sort((a, b) => b[1] - a[1])
              .map(([kind, count]) => (
                <button
                  key={kind}
                  data-active={props.filter === kind}
                  onClick={() => props.onFilter(props.filter === kind ? null : kind)}
                >
                  {kind.replace(/_/g, " ")} <span className="count">{count}</span>
                </button>
              ))}
          </div>
          {props.pages ? (
            <div className="card-note" style={{ padding: "2px 12px 10px" }}>
              across {props.pages} page{props.pages === 1 ? "" : "s"}
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="section">
        <header>Reading</header>
        <div className="body">
          {steps.length ? (
            steps.map((step) => (
              <div key={step.id} style={{ marginBottom: 10 }}>
                <div className="axis-row">
                  <span className={`status status-${step.status}`}>{step.status}</span>
                  <span className="detail">{step.label}</span>
                </div>
                <div className="card-note">{step.detail}</div>
                {step.warnings.map((warning, index) => (
                  <div key={index} className="warn">
                    {warning}
                  </div>
                ))}
              </div>
            ))
          ) : (
            <div className="empty">No drawing in this project.</div>
          )}
        </div>
      </section>
    </nav>
  );
}
