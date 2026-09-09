/**
 * The card vocabulary. Every panel is built from these.
 *
 * Each card renders one *kind of thing the platform knows about*, never one kind of part. If a
 * card would be meaningless for a bracket, it belongs somewhere else.
 *
 * Evidence state is carried by line pattern as well as colour, so it survives greyscale,
 * screenshots and colour-vision differences rather than depending on a hue.
 */

import type { Callout, Evidence, EvidenceState, Fact, Feature, Step } from "../api/client";

export function StateChip({ state }: { state: EvidenceState }) {
  return (
    <span className="state" data-state={state}>
      {state}
    </span>
  );
}

export function EvidenceRow({ evidence }: { evidence: Evidence }) {
  return (
    <div className="evidence" data-kind={evidence.kind}>
      <div className="locator">
        {evidence.kind} &middot; {evidence.locator}
      </div>
      <div className="method">
        via {evidence.method}
        {evidence.confidence < 1 ? ` (confidence ${evidence.confidence.toFixed(2)})` : ""}
      </div>
      {evidence.detail ? <div className="method">{evidence.detail}</div> : null}
    </div>
  );
}

/** A value and every source behind it. */
export function FactCard({ label, fact }: { label: string; fact: Fact }) {
  return (
    <div className="card">
      <div className="card-head">
        <span className="card-title">{label}</span>
        <span className="mono">{show(fact.value)}</span>
        <StateChip state={fact.state} />
      </div>
      {fact.note ? <div className="card-note">{fact.note}</div> : null}
      {fact.evidence.map((evidence, index) => (
        <EvidenceRow key={index} evidence={evidence} />
      ))}
    </div>
  );
}

/** One stage of the deterministic pipeline: what it did, or precisely why it did not. */
export function StepCard({ step }: { step: Step }) {
  const produced = Object.entries(step.produced).filter(
    ([, value]) => typeof value !== "object" || value === null,
  );
  return (
    <div className="card" data-status={step.status}>
      <div className="card-head">
        <span className={`status status-${step.status}`}>{step.status}</span>
        <span className="card-title">{step.label}</span>
        {step.seconds > 0.05 ? <span className="mono dim">{step.seconds.toFixed(1)}s</span> : null}
      </div>
      <div className="card-note">{step.detail}</div>
      {produced.length ? (
        <dl className="kv compact">
          {produced.map(([key, value]) => (
            <Row key={key} label={key.replace(/_/g, " ")} value={show(value)} />
          ))}
        </dl>
      ) : null}
      {step.warnings.map((warning, index) => (
        <div key={index} className="warn">
          {warning}
        </div>
      ))}
    </div>
  );
}

/** A detected geometric feature. */
export function FeatureRow({
  feature,
  onSelect,
  selected,
}: {
  feature: Feature;
  onSelect: (feature: Feature) => void;
  selected: boolean;
}) {
  return (
    <button className="row" data-selected={selected} onClick={() => onSelect(feature)}>
      <span className="kind">{feature.kind.replace(/_/g, " ")}</span>
      <span className="name mono">{feature.id.split(":").pop()}</span>
      <span className="detail">
        {feature.diameter_mm !== null ? `⌀${feature.diameter_mm.toFixed(1)} ` : ""}
        {feature.count > 1 ? `×${feature.count} ` : ""}
        {area(feature.area_mm2)}
      </span>
      {feature.controlled ? <StateChip state={feature.controlled.state} /> : null}
    </button>
  );
}

/** One claim read off a drawing, with the literal text it came from. */
export function CalloutRow({ callout }: { callout: Callout }) {
  return (
    <div className="callout">
      <span className="kind">p{callout.page}</span>
      <span className="mono">
        {callout.count ? `${callout.count}× ` : ""}
        {callout.is_diameter ? "⌀" : ""}
        {callout.nominal !== null ? callout.nominal.toFixed(callout.tolerance ? 3 : 2) : ""}
        {callout.tolerance ? ` ±${callout.tolerance.toFixed(3)}` : ""}
        {callout.through ? " THRU" : ""}
        {!callout.nominal && callout.text ? callout.text : ""}
      </span>
      <span className="raw">{callout.raw}</span>
    </div>
  );
}

/** A measured quantity with its unit. The smallest card, and the most reused. */
export function Metric({
  label,
  value,
  unit,
  tone,
}: {
  label: string;
  value: string | number | null;
  unit?: string;
  tone?: "ok" | "warn" | "bad";
}) {
  return (
    <div className="metric" data-tone={tone}>
      <div className="metric-value mono">
        {value === null ? "—" : typeof value === "number" ? value.toLocaleString() : value}
        {unit && value !== null ? <span className="metric-unit">{unit}</span> : null}
      </div>
      <div className="metric-label">{label}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  );
}

function show(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

function area(mm2: number): string {
  return mm2 >= 1e6 ? `${(mm2 / 1e6).toFixed(2)} m²` : `${Math.round(mm2).toLocaleString()} mm²`;
}
