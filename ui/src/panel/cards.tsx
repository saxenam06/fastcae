/**
 * The card vocabulary: what a panel shows of a measured quantity.
 *
 * A card renders one *kind of thing the platform knows about*, never one kind of part. If a card
 * would be meaningless for a bracket, it belongs somewhere else.
 */

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
