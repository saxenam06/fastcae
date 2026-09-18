/**
 * Input → Mesh & setup → Answer: the engineer's own answer, as their solver wrote it - contours on
 * the deck's mesh, the field and how it is drawn chosen on the canvas, and the signals the deck asks
 * for beside it.
 */

import { useState } from "react";
import type { SolveView } from "./Solve";
import { SignalTable, SolveStage } from "./Solve";
import type { DeckState } from "./useDeck";

const FIELDS = ["displacement", "DX", "DY", "DZ", "von Mises"] as const;

export function AnswerStage({ state, view }: { state: DeckState; view: SolveView }) {
  const [signals, setSignals] = useState(false);
  const { deck } = state;
  if (!deck) return <div className="rail-note">{state.loading ? "reading the deck…" : state.error ?? ""}</div>;
  const available = (deck.answers ?? []).find((a) => a.id === "aster")?.available ?? false;
  if (!deck.present || !available) {
    return (
      <div className="stage-page">
        <div className="later">
          <h2>The engineer's answer</h2>
          <p>
            {deck.present
              ? "The deck came without its results: no .rmed named by its export, or none in the project. Add the results the engineer's run wrote, then extract again."
              : "No solver deck in this project."}
          </p>
        </div>
      </div>
    );
  }
  const hasVm = (deck.fields ?? []).some((f) => f.name === "SIEQ_NOEU");
  const rows = state.signals?.rows ?? [];
  return (
    <>
      <SolveStage state={state} view={view} />
      <div className="overlay">
        <span className="segmented">
          {FIELDS.filter((f) => f !== "von Mises" || hasVm).map((f) => (
            <button
              key={f}
              data-active={view.field === f}
              onClick={() => {
                view.setField(f);
                view.setRange(null);
              }}
            >
              {f}
            </button>
          ))}
        </span>
        <button data-active={view.deformed} onClick={() => view.setDeformed(!view.deformed)}>
          deformed
        </button>
        <button data-active={view.edges} onClick={() => view.setEdges(!view.edges)}>
          edges
        </button>
        {rows.length ? (
          <button data-active={signals} onClick={() => setSignals(!signals)}>
            signals {rows.length}
          </button>
        ) : null}
      </div>
      {signals ? (
        <div className="signals-panel">
          <SignalTable rows={rows} runs={["aster"]} />
        </div>
      ) : null}
    </>
  );
}
