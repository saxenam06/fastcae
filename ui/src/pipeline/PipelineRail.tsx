/**
 * The pipeline on the left: every step in the order it runs - the engineer's files read, the design
 * space last - what each read and what it produced. A step opens to its inputs - each naming the
 * step that made it - and its outputs, each a group that opens to its entities. Clicking anything
 * shows it on its canvas and on the card; nothing here is part-specific, it is whatever the steps
 * reported.
 */

import { useEffect, useState } from "react";
import type { EntitySummary, Group, Origin, PipelineStage, StepRun } from "../api/pipeline";
import type { Focus } from "./focus";
import type { PipelineState } from "./usePipeline";

interface Props {
  state: PipelineState;
  focus: Focus | null;
  onStep: (step: StepRun) => void;
  onGroup: (group: Group, step: StepRun) => void;
  onEntity: (entity: EntitySummary) => void;
}

export const ORIGIN_WORDS: Record<Origin, string> = {
  imported: "Read from the engineer's files, as they are",
  derived: "Computed from them by a rule",
  inferred: "A reading that could be wrong",
  generated: "Proposed by fastcae",
};

export function PipelineRail({ state, focus, onStep, onGroup, onEntity }: Props) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());
  // A clock for the step running now, so a long step reads as working, not stuck.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!state.running) return;
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(tick);
  }, [state.running]);

  // Whatever the focus moves to - from an input, the card, a click on a canvas - has its step
  // opened, so the rail always shows where it came from.
  useEffect(() => {
    const step = focus?.step;
    if (step) setOpen((was) => (was.has(step) ? was : new Set(was).add(step)));
  }, [focus?.step]);

  const toggle = (id: string) =>
    setOpen((was) => {
      const next = new Set(was);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const toggleGroup = (id: string) =>
    setOpenGroups((was) => {
      const next = new Set(was);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const stages: PipelineStage[] = (state.pipeline?.stages ?? []).map((stage) => ({
    ...stage,
    steps: stage.steps.map((s) => state.steps.get(s.id) ?? s),
  }));

  return (
    <nav className="pipeline">
      <header className="pipeline-head">
        <span>Pipeline</span>
        <span className="pipeline-state">{state.running ? "design space…" : ""}</span>
      </header>
      {state.error ? <div className="pipeline-error">{state.error}</div> : null}
      {!state.pipeline ? <div className="rail-note">reading the pipeline…</div> : null}
      {stages.map((stage) => {
        const finished = stage.steps.filter((s) => ["done", "cached", "skipped"].includes(s.status));
        const seconds = stage.steps.reduce((t, s) => t + (s.seconds ?? 0), 0);
        return (
          <section key={stage.id} className="pipeline-stage">
            <header>
              <span>{stage.label}</span>
              <span className="count">
                {finished.length}/{stage.steps.length}
                {finished.length === stage.steps.length && seconds > 0 ? ` · ${fmtTime(seconds)}` : ""}
              </span>
            </header>
            {stage.steps.map((step) => (
              <StepRow
                key={step.id}
                step={step}
                elapsed={
                  state.started.has(step.id) ? (now - state.started.get(step.id)!) / 1000 : null
                }
                steps={state.steps}
                open={open.has(step.id)}
                openGroups={openGroups}
                focus={focus}
                state={state}
                onToggle={() => {
                  // Opening a step shows what it made; closing one only closes it.
                  if (!open.has(step.id)) onStep(step);
                  toggle(step.id);
                }}
                onToggleGroup={toggleGroup}
                onGroup={onGroup}
                onEntity={onEntity}
              />
            ))}
          </section>
        );
      })}
    </nav>
  );
}

function StepRow(props: {
  step: StepRun;
  elapsed: number | null;
  steps: Map<string, StepRun>;
  open: boolean;
  openGroups: Set<string>;
  focus: Focus | null;
  state: PipelineState;
  onToggle: () => void;
  onToggleGroup: (id: string) => void;
  onGroup: (group: Group, step: StepRun) => void;
  onEntity: (entity: EntitySummary) => void;
}) {
  const { step, focus } = props;
  const focused = focus?.kind === "step" && focus.step === step.id;
  return (
    <div className="step" data-status={step.status} data-open={props.open} data-focus={focused}>
      <button className="step-head" onClick={props.onToggle} title={step.detail || step.label}>
        <i className="dot" />
        <span className="step-label">{step.label}</span>
        <span className="step-time">{stepTime(step, props.elapsed)}</span>
      </button>
      {!props.open && step.detail ? <div className="step-line">{step.detail}</div> : null}
      {props.open ? (
        <div className="step-body">
          {step.detail ? <div className="step-detail">{step.detail}</div> : null}
          {step.inputs.length ? (
            <div className="io">
              <span className="io-tag">in</span>
              <div className="io-chips">
                {step.inputs.map((input) => {
                  const from = props.steps.get(input.step);
                  return (
                    <button
                      key={input.key}
                      className="chip-in"
                      data-empty={input.count === 0}
                      title={from ? `from ${from.label}` : undefined}
                      onClick={() => from && props.onGroup(input, from)}
                    >
                      <b>{input.count.toLocaleString("en-GB")}</b> {input.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}
          {step.outputs.length ? (
            <div className="io">
              <span className="io-tag">out</span>
              <div className="io-groups">
                {step.outputs.map((group) => {
                  const id = `${step.id}/${group.key}`;
                  const isOpen = props.openGroups.has(id);
                  const groupFocused =
                    focus?.kind === "group" && focus.group?.key === group.key && focus.step === step.id;
                  return (
                    <div key={group.key} className="out-group" data-focus={groupFocused}>
                      <button
                        className="out-head"
                        onClick={() => {
                          if (!isOpen) props.onGroup(group, step);
                          props.onToggleGroup(id);
                        }}
                      >
                        <span className="caret">{isOpen ? "▾" : "▸"}</span>
                        <span className="out-label">{group.label}</span>
                        <span className="count">{group.count.toLocaleString("en-GB")}</span>
                      </button>
                      {isOpen ? (
                        <Members group={group} state={props.state} focus={focus} onEntity={props.onEntity} />
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : step.status === "pending" || step.status === "running" ? null : (
            <div className="io">
              <span className="io-tag">out</span>
              <span className="dim">nothing</span>
            </div>
          )}
          {step.warnings.length ? (
            <details className="step-warn">
              <summary>
                {step.warnings.length} warning{step.warnings.length === 1 ? "" : "s"}
              </summary>
              {step.warnings.map((w, i) => (
                <div key={i}>{w}</div>
              ))}
            </details>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

const FIRST = 60;

function Members({
  group,
  state,
  focus,
  onEntity,
}: {
  group: Group;
  state: PipelineState;
  focus: Focus | null;
  onEntity: (entity: EntitySummary) => void;
}) {
  const [members, setMembers] = useState<EntitySummary[] | null>(null);
  const [all, setAll] = useState(false);
  const read = state.members;
  useEffect(() => {
    let live = true;
    read(group)
      .then((found) => live && setMembers(found))
      .catch(() => live && setMembers([]));
    return () => {
      live = false;
    };
  }, [group, read]);
  if (!members) return <div className="members dim">reading…</div>;
  const shown = all ? members : members.slice(0, FIRST);
  return (
    <div className="members">
      {shown.map((e) => (
        <EntityRow key={e.id} entity={e} focused={focus?.entity === e.id} onClick={() => onEntity(e)} />
      ))}
      {members.length > shown.length ? (
        <button className="more" onClick={() => setAll(true)}>
          all {members.length.toLocaleString("en-GB")}
        </button>
      ) : null}
    </div>
  );
}

export function EntityRow({
  entity,
  focused,
  onClick,
}: {
  entity: EntitySummary;
  focused: boolean;
  onClick: () => void;
}) {
  return (
    <button className="entity-row" data-focus={focused} data-status={entity.status} onClick={onClick} title={entity.id}>
      <i className="origin" data-origin={entity.origin} title={ORIGIN_WORDS[entity.origin]} />
      <span className="entity-label">{entity.label}</span>
      {entity.status !== "ok" ? <span className="entity-status">{entity.status}</span> : null}
    </button>
  );
}

function stepTime(step: StepRun, elapsed: number | null): string {
  if (step.status === "running") return elapsed !== null && elapsed >= 1 ? `${fmtTime(elapsed)} …` : "…";
  if (step.status === "pending") return "";
  if (step.status === "skipped") return "skipped";
  if (step.status === "failed") return "failed";
  if (step.status === "cached") return "read back";
  return step.seconds === null ? "" : fmtTime(step.seconds);
}

export function fmtTime(seconds: number): string {
  if (seconds < 1) return `${seconds.toFixed(1)} s`;
  if (seconds < 60) return `${seconds.toFixed(0)} s`;
  return `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} s`;
}
