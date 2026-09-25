/**
 * Input → Mesh & setup → Solve results: the deck solved - as the engineer's own solver wrote it, and
 * as cuDSS solves the same mesh and setup - contours on the deck's mesh. The two are tabs under the
 * picture; the field, how it is drawn and the signals the deck asks for are chosen on the canvas.
 */

import { useState } from "react";
import type { Run } from "../api/simulate";
import { sim } from "../api/simulate";
import type { SolveView } from "./Solve";
import { JobLine, SignalTable, SolveStage } from "./Solve";
import type { DeckState } from "./useDeck";
import { Provenance, fmtCount, fmtSeconds } from "./shared";

const FIELDS = ["displacement", "DX", "DY", "DZ", "von Mises"] as const;

export function ResultsStage({ state, view }: { state: DeckState; view: SolveView }) {
  const [signals, setSignals] = useState(false);
  const { deck, job } = state;
  if (!deck) return <div className="rail-note">{state.loading ? "reading the deck…" : state.error ?? ""}</div>;
  const answers = deck.answers ?? [];
  const available = (run: Run) => answers.find((a) => a.id === run)?.available ?? false;
  if (!deck.present || !available("aster")) {
    return (
      <div className="stage-page">
        <div className="later">
          <h2>Solve results</h2>
          <p>
            {deck.present
              ? "The deck came without its results: no .rmed named by its export, or none in the project. Add the results the engineer's run wrote, then extract again."
              : "No solver deck in this project."}
          </p>
        </div>
      </div>
    );
  }
  const hasVm = (deck.fields ?? []).some((f) => f.name === "SIEQ_NOEU") || view.left === "cudss";
  const rows = state.signals?.rows ?? [];
  const solving = Boolean(job && !["done", "failed", "cancelled", "interrupted"].includes(job.state));
  const cudss = answers.find((a) => a.id === "cudss");
  const tabs = (
    <span className="run-tabs">
      <button
        data-active={view.left === "aster"}
        onClick={() => view.setLeft("aster")}
        title={answers.find((a) => a.id === "aster")?.detail ?? "the engineer's run"}
      >
        Code_Aster <Provenance kind="imported" small />
      </button>
      <button
        data-active={view.left === "cudss"}
        disabled={solving}
        onClick={() => (available("cudss") ? view.setLeft("cudss") : void state.submit(sim.solve))}
        title={
          available("cudss") && cudss?.meta
            ? `${fmtCount(cudss.meta.unknowns ?? 0)} unknowns · ${fmtSeconds(cudss.meta.times?.total_s)}`
            : "The deck's own mesh and setup, solved on the GPU"
        }
      >
        cuDSS{" "}
        {available("cudss") ? <Provenance kind="generated" small /> : solving ? "· solving…" : "· solve it"}
      </button>
    </span>
  );
  return (
    <>
      <SolveStage state={state} view={view} caption={tabs} />
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
      {solving && job ? (
        <div className="solve-job">
          <JobLine job={job} />
        </div>
      ) : null}
      {signals ? (
        <div className="signals-panel">
          <SignalTable rows={rows} runs={available("cudss") ? ["aster", "cudss"] : ["aster"]} />
        </div>
      ) : null}
    </>
  );
}
