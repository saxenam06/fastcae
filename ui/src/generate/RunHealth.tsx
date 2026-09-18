/**
 * A launched campaign's designs being solved: start the runner on them, and watch - how many are
 * solved and set aside, how many an hour, where each design is and what happened, in order.
 */

import { useCallback, useEffect, useState } from "react";
import type { DesignState, Solving } from "../api/simulate";
import { sim } from "../api/simulate";

const STAGES = [
  ["build", "B", "built: its field, from the campaign"],
  ["mesh", "M", "meshed by CGAL from the field"],
  ["setup", "S", "the deck's setup carried by CAD face"],
  ["solve", "R", "solved"],
  ["record", "D", "recorded: Zarr, JSON and a row of metrics"],
] as const;

const RUNNING = new Set(["queued", "starting", "running"]);

export function RunHealth(props: { run: string; name?: string; onOpen: (run: string) => void }) {
  const { run } = props;
  const [solving, setSolving] = useState<Solving | null>(null);
  const [count, setCount] = useState(20);
  const [inFlight, setInFlight] = useState(3);
  const [error, setError] = useState<string | null>(null);
  const running = solving?.job ? RUNNING.has(solving.job.state) : false;

  const read = useCallback(() => {
    sim
      .solving(run)
      .then((s) => {
        setSolving(s);
        setError(null);
      })
      .catch((e) => setError(String(e)));
  }, [run]);

  useEffect(() => {
    read();
    const timer = window.setInterval(read, running ? 3000 : 20000);
    return () => window.clearInterval(timer);
  }, [read, running]);

  const start = () => {
    setError(null);
    sim
      .solveRun(run, count, inFlight)
      .then(read)
      .catch((e) => setError(String(e)));
  };
  const stop = () => {
    if (solving?.job) sim.cancel(solving.job.id).then(read).catch((e) => setError(String(e)));
  };

  const designs = solving?.designs ?? [];
  const solved = designs.filter((d) => d.outcome === "solved");
  const aside = designs.filter((d) => d.outcome === "set aside");
  const flying = designs.filter((d) => !d.outcome);
  const job = solving?.job ?? null;
  const elapsed = job?.started ? (job.finished ?? Date.now() / 1000) - job.started : null;
  const perHour = job?.per_hour ?? (solved.length && elapsed ? solved.length / (elapsed / 3600) : null);
  const typical = median(solved.map((d) => d.seconds ?? 0).filter((s) => s > 0));

  return (
    <div className="run-health">
      <header className="run-health-head">
        <div className="run-health-names">
          <div className="run-health-title" title={props.name ?? run}>
            <span className="mono dim">{run.split("-")[0]}</span> {props.name ?? run}
          </div>
        </div>
        <button onClick={() => props.onOpen(run)}>Open its designs →</button>
      </header>

      <div className="run-health-controls">
        {running ? (
          <>
            <span className="busy-dot" aria-hidden />
            <span>{job?.message ?? "solving"}</span>
            <button onClick={stop}>Stop after the designs in flight</button>
          </>
        ) : (
          <>
            <span>Solve the</span>
            <select id="solve-count" value={count} onChange={(e) => setCount(Number(e.target.value))}>
              {[5, 10, 20, 40, 100].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
            <span>designs that differ most,</span>
            <select id="solve-in-flight" value={inFlight} onChange={(e) => setInFlight(Number(e.target.value))}>
              {[1, 2, 3].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
            <span>at a time</span>
            <button className="primary" onClick={start}>
              Solve
            </button>
          </>
        )}
      </div>
      {error ? <div className="card-note warn">{error}</div> : null}

      <div className="health-tiles">
        <Tile value={solved.length} label="solved" good={solved.length > 0} />
        <Tile value={aside.length} label="set aside" bad={aside.length > 0} />
        <Tile value={flying.length} label="in flight" />
        <Tile value={perHour === null ? "–" : perHour.toFixed(1)} label="an hour" />
        <Tile value={typical === null ? "–" : `${Math.round(typical)} s`} label="a design, typically" />
        <Tile value={elapsed === null ? "–" : duration(elapsed)} label={running ? "running" : "last run"} />
      </div>

      <section className="run-health-list">
        <header>
          Designs <span className="count">{designs.length}</span>
        </header>
        {!designs.length ? (
          <div className="dim body">None solved yet. Solve starts the runner on them; this page can be closed meanwhile.</div>
        ) : null}
        {designs.map((d) => (
          <DesignRow key={d.index} state={d} />
        ))}
      </section>

      <section className="run-health-events">
        <header>What happened</header>
        {(solving?.events ?? [])
          .slice(-40)
          .reverse()
          .map((e, i) => (
            <div key={`${e.t}-${i}`} className="event" data-outcome={e.outcome ?? ""}>
              <span className="mono dim">{clock(e.t)}</span> {e.message}
            </div>
          ))}
      </section>
    </div>
  );
}

function DesignRow({ state }: { state: DesignState }) {
  const now = state.stage && !state.outcome ? state.stage : null;
  return (
    <div className="design-state" data-outcome={state.outcome ?? "going"}>
      <span className="mono">#{state.index + 1}</span>
      <span className="stage-chips">
        {STAGES.map(([key, letter, says]) => {
          const seconds = state.stages?.[key];
          const status = seconds !== undefined ? "done" : now === key ? "now" : "none";
          return (
            <span
              key={key}
              className="stage-chip"
              data-status={status}
              title={`${says}${seconds !== undefined ? ` · ${seconds.toFixed(0)} s` : ""}`}
            >
              {letter}
            </span>
          );
        })}
      </span>
      <span className="design-state-said">
        {state.outcome === "set aside" ? (
          <span className="warn-text">set aside: {state.reason}</span>
        ) : state.outcome === "solved" ? (
          <>
            {Math.round(state.seconds ?? 0)} s
            {state.unknowns ? ` · ${(state.unknowns / 1e6).toFixed(2)} M unknowns` : ""}
            {state.mass_kg ? ` · ${state.mass_kg.toFixed(0)} kg` : ""}
            <span className="dim"> · {state.route}</span>
          </>
        ) : (
          <span className="dim">{now ?? "waiting"}…</span>
        )}
      </span>
    </div>
  );
}

function Tile(props: { value: number | string; label: string; good?: boolean; bad?: boolean }) {
  return (
    <div className="health-tile" data-good={props.good ? "true" : undefined} data-bad={props.bad ? "true" : undefined}>
      <b>{props.value}</b>
      <span>{props.label}</span>
    </div>
  );
}

function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function duration(seconds: number): string {
  if (seconds < 90) return `${Math.round(seconds)} s`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} min`;
  return `${(seconds / 3600).toFixed(1)} h`;
}

function clock(t: number): string {
  return new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
