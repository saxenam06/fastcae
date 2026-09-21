/**
 * The card on the right: whatever is in focus, in full. An entity shows its typed fields, the
 * evidence behind it, what it is tied to and what is tied to it - every one of those a link that
 * moves the focus there. A step shows what it read and made; a group, its members.
 *
 * The same JSON an agent reads; the card only lays it out. Nothing here knows a kind by name.
 */

import { useEffect, useState } from "react";
import type { EntityDetail, EntitySummary, Group, StepRun } from "../api/pipeline";
import type { Focus } from "./focus";
import { EntityRow, ORIGIN_WORDS, fmtTime } from "./PipelineRail";
import type { PipelineState } from "./usePipeline";

interface Props {
  state: PipelineState;
  focus: Focus;
  onEntity: (id: string) => void;
  onStep: (step: StepRun) => void;
  onGroup: (group: Group, step: StepRun) => void;
  onCollapse: () => void;
}

export function EntityCard(props: Props) {
  const { focus, state } = props;
  const step = focus.step ? state.steps.get(focus.step) : undefined;
  return (
    <div className="entity-card">
      <div className="entity-card-bar">
        <span className="dim">{focus.kind}</span>
        <button className="icon" onClick={props.onCollapse} title="Fold the card away">
          ›
        </button>
      </div>
      <div className="entity-card-scroll">
        {focus.kind === "entity" && focus.entity ? (
          <EntityView id={focus.entity} {...props} />
        ) : focus.kind === "group" && focus.group ? (
          <GroupView group={focus.group} step={step} {...props} />
        ) : step ? (
          <StepView step={step} {...props} />
        ) : null}
      </div>
    </div>
  );
}

// --- an entity --------------------------------------------------------------------------------------

/** Fields every entity has, laid out in the card's head rather than among its own. */
const COMMON = new Set(["id", "kind", "label", "step", "origin", "show", "links", "evidence", "status", "backlinks"]);

const ROLE_WORDS: Record<string, string> = {
  on: "lies on",
  evidenced_by: "evidence",
  from: "made from",
  about: "about",
  of: "of",
  holds: "holds",
  ties: "ties",
  reads: "reads",
  round: "round",
};

const BACK_WORDS: Record<string, string> = {
  on: "on it",
  evidenced_by: "evidence for",
  from: "made into",
  about: "asked about by",
  of: "has",
  holds: "held by",
  ties: "tied by",
  reads: "read by",
  round: "has round it",
};

function EntityView({ id, state, onEntity, onStep }: Props & { id: string }) {
  const [entity, setEntity] = useState<EntityDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const read = state.entity;
  useEffect(() => {
    let live = true;
    setError(null);
    read(id)
      .then((found) => live && setEntity(found))
      .catch((caught) => live && setError(String(caught)));
    return () => {
      live = false;
    };
  }, [id, read, state.pipeline]);
  if (error) return <div className="card-error">{error}</div>;
  if (!entity || entity.id !== id) return <div className="dim card-pad">reading…</div>;
  const step = state.steps.get(entity.step);
  const fields = Object.entries(entity).filter(([k]) => !COMMON.has(k));
  return (
    <>
      <header className="entity-head">
        <div className="entity-kind">
          <span className="kind-chip">{entity.kind.replace(/_/g, " ")}</span>
          <span className="origin-pill" data-origin={entity.origin} title={ORIGIN_WORDS[entity.origin]}>
            {entity.origin}
          </span>
          {entity.status !== "ok" ? <span className="status-pill">{entity.status}</span> : null}
        </div>
        <h2 className="entity-title">{entity.label}</h2>
        <div className="entity-id mono">{entity.id}</div>
        {step ? (
          <div className="entity-made">
            made by{" "}
            <button className="link" onClick={() => onStep(step)}>
              {step.label}
            </button>
          </div>
        ) : null}
      </header>
      {fields.length ? (
        <details className="card-section" open>
          <summary>Fields</summary>
          <dl className="fields-list">
            {fields.map(([key, value]) => (
              <FieldRow key={key} name={key} value={value} />
            ))}
          </dl>
        </details>
      ) : null}
      {entity.evidence.length ? (
        <details className="card-section" open>
          <summary>
            Evidence <span className="count">{entity.evidence.length}</span>
          </summary>
          <div className="proofs">
            {entity.evidence.map((proof, index) => (
              <div key={index} className="proof" data-source={proof.source}>
                <span className="proof-source">{proof.source}</span>
                <span className="proof-detail">{proof.detail}</span>
                {proof.locator ? (
                  isEntityId(proof.locator) ? (
                    <button className="link mono" onClick={() => onEntity(proof.locator)}>
                      {proof.locator}
                    </button>
                  ) : (
                    <span className="mono dim">{proof.locator}</span>
                  )
                ) : null}
              </div>
            ))}
          </div>
        </details>
      ) : null}
      <LinkSection
        title="Tied to"
        rows={entity.links.map((l) => ({ id: l.to, role: l.role, label: l.label, kind: l.kind }))}
        words={ROLE_WORDS}
        onEntity={onEntity}
      />
      <LinkSection
        title="Tied from"
        rows={entity.backlinks.map((l) => ({ id: l.from, role: l.role, label: l.label, kind: l.kind }))}
        words={BACK_WORDS}
        onEntity={onEntity}
      />
    </>
  );
}

function isEntityId(text: string): boolean {
  return /^[a-z_]+:[^\s]+$/.test(text);
}

/** A linked entity as the card lists it. */
interface Tie {
  id: string;
  role: string;
  label: string;
  kind: string;
}

const LISTED_TIES = 8;

function LinkSection({
  title,
  rows,
  words,
  onEntity,
}: {
  title: string;
  rows: Tie[];
  words: Record<string, string>;
  onEntity: (id: string) => void;
}) {
  if (!rows.length) return null;
  const byRole = new Map<string, Tie[]>();
  for (const row of rows) byRole.set(row.role, [...(byRole.get(row.role) ?? []), row]);
  return (
    <details className="card-section" open>
      <summary>
        {title} <span className="count">{rows.length}</span>
      </summary>
      {[...byRole.entries()].map(([role, ties]) => (
        <TieGroup key={role} role={words[role] ?? role} ties={ties} onEntity={onEntity} />
      ))}
    </details>
  );
}

function TieGroup({ role, ties, onEntity }: { role: string; ties: Tie[]; onEntity: (id: string) => void }) {
  const [all, setAll] = useState(false);
  const shown = all ? ties : ties.slice(0, LISTED_TIES);
  return (
    <div className="tie-group">
      <div className="tie-role">{role}</div>
      <div className="ties">
        {shown.map((tie) => (
          <button key={tie.id} className="tie" onClick={() => onEntity(tie.id)} title={tie.id}>
            {tie.kind ? <span className="tie-kind">{tie.kind.replace(/_/g, " ")}</span> : null}
            <span>{tie.label}</span>
          </button>
        ))}
        {ties.length > shown.length ? (
          <button className="more" onClick={() => setAll(true)}>
            all {ties.length}
          </button>
        ) : null}
      </div>
    </div>
  );
}

const UNITS: [RegExp, string][] = [
  [/_mm2$/, "mm²"],
  [/_m2$/, "m²"],
  [/_cm3$/, "cm³"],
  [/_mm$/, "mm"],
  [/_L$/, "L"],
  [/_pct$/, "%"],
  [/_bytes$/, "bytes"],
];

function FieldRow({ name, value }: { name: string; value: unknown }) {
  let label = name;
  let unit = "";
  for (const [pattern, words] of UNITS) {
    if (pattern.test(name)) {
      label = name.replace(pattern, "");
      unit = words;
      break;
    }
  }
  return (
    <>
      <dt>{label.replace(/_/g, " ")}</dt>
      <dd>
        <Value value={value} />
        {unit && value !== null && value !== undefined ? <span className="unit"> {unit}</span> : null}
      </dd>
    </>
  );
}

const LISTED_VALUES = 8;

function Value({ value }: { value: unknown }) {
  const [all, setAll] = useState(false);
  if (value === null || value === undefined) return <span className="dim">–</span>;
  if (typeof value === "boolean") return <span>{value ? "yes" : "no"}</span>;
  if (typeof value === "number") return <span className="num">{fmtValue(value)}</span>;
  if (typeof value === "string") return <span>{value.replace(/_/g, " ")}</span>;
  if (Array.isArray(value)) {
    if (!value.length) return <span className="dim">none</span>;
    if (value.every((v) => typeof v === "number")) {
      const shown = all ? value : value.slice(0, LISTED_VALUES);
      return (
        <span className="num">
          {shown.map((v) => fmtValue(v as number)).join(", ")}
          {value.length > shown.length ? (
            <button className="more inline" onClick={() => setAll(true)}>
              +{value.length - shown.length}
            </button>
          ) : null}
        </span>
      );
    }
    return (
      <div className="value-list">
        {(all ? value : value.slice(0, LISTED_VALUES)).map((v, i) => (
          <div key={i}>
            <Value value={v} />
          </div>
        ))}
        {value.length > LISTED_VALUES && !all ? (
          <button className="more inline" onClick={() => setAll(true)}>
            all {value.length}
          </button>
        ) : null}
      </div>
    );
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (!entries.length) return <span className="dim">none</span>;
    return (
      <dl className="value-map">
        {entries.map(([k, v]) => (
          <div key={k}>
            <dt>{k.replace(/_/g, " ")}</dt>
            <dd>
              <Value value={v} />
            </dd>
          </div>
        ))}
      </dl>
    );
  }
  return <span>{String(value)}</span>;
}

function fmtValue(v: number): string {
  if (!Number.isFinite(v)) return "–";
  if (Number.isInteger(v)) return v.toLocaleString("en-GB");
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-3 || a >= 1e7)) return v.toExponential(3);
  return v.toLocaleString("en-GB", { maximumSignificantDigits: 4 });
}

// --- a group, a step --------------------------------------------------------------------------------

function GroupView({ group, step, state, onEntity, onStep }: Props & { group: Group; step?: StepRun }) {
  const [members, setMembers] = useState<EntitySummary[] | null>(null);
  const [all, setAll] = useState(false);
  const read = state.members;
  useEffect(() => {
    let live = true;
    read(group).then((found) => live && setMembers(found));
    return () => {
      live = false;
    };
  }, [group, read]);
  const shown = members ? (all ? members : members.slice(0, 200)) : [];
  return (
    <>
      <header className="entity-head">
        <div className="entity-kind">
          <span className="kind-chip">{group.kind.replace(/_/g, " ") || "group"}</span>
        </div>
        <h2 className="entity-title">
          {group.label} <span className="count">{group.count.toLocaleString("en-GB")}</span>
        </h2>
        {step ? (
          <div className="entity-made">
            from{" "}
            <button className="link" onClick={() => onStep(step)}>
              {step.label}
            </button>
          </div>
        ) : null}
      </header>
      <div className="members card-members">
        {members === null ? <div className="dim card-pad">reading…</div> : null}
        {shown.map((e) => (
          <EntityRow key={e.id} entity={e} focused={false} onClick={() => onEntity(e.id)} />
        ))}
        {members && members.length > shown.length ? (
          <button className="more" onClick={() => setAll(true)}>
            all {members.length.toLocaleString("en-GB")}
          </button>
        ) : null}
      </div>
    </>
  );
}

function StepView({ step, state, onGroup }: Props & { step: StepRun }) {
  const producer = (key: string) => state.steps.get(key);
  return (
    <>
      <header className="entity-head">
        <div className="entity-kind">
          <span className="kind-chip">step</span>
          <span className="status-pill" data-status={step.status}>
            {step.status === "cached" ? "read back" : step.status}
          </span>
          {step.seconds !== null && step.status === "done" ? (
            <span className="dim num">{fmtTime(step.seconds)}</span>
          ) : null}
        </div>
        <h2 className="entity-title">{step.label}</h2>
        {step.detail ? <p className="step-detail">{step.detail}</p> : null}
      </header>
      {step.inputs.length ? (
        <details className="card-section" open>
          <summary>
            Read <span className="count">{step.inputs.length}</span>
          </summary>
          {step.inputs.map((input) => {
            const from = producer(input.step);
            return (
              <button
                key={input.key}
                className="io-row"
                onClick={() => from && onGroup(input, from)}
                disabled={!from}
              >
                <b className="num">{input.count.toLocaleString("en-GB")}</b>
                <span>{input.label}</span>
                <span className="dim">{from ? `from ${from.label}` : ""}</span>
              </button>
            );
          })}
        </details>
      ) : null}
      {step.outputs.length ? (
        <details className="card-section" open>
          <summary>
            Made <span className="count">{step.outputs.reduce((n, g) => n + g.count, 0)}</span>
          </summary>
          {step.outputs.map((group) => (
            <button key={group.key} className="io-row" onClick={() => onGroup(group, step)}>
              <b className="num">{group.count.toLocaleString("en-GB")}</b>
              <span>{group.label}</span>
              <span className="dim">{group.kind.replace(/_/g, " ")}</span>
            </button>
          ))}
        </details>
      ) : null}
      {step.warnings.length ? (
        <details className="card-section">
          <summary>
            Warnings <span className="count">{step.warnings.length}</span>
          </summary>
          <div className="card-pad">
            {step.warnings.map((w, i) => (
              <div key={i} className="warn">
                {w}
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </>
  );
}
