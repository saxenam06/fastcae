/**
 * The rail for the Generate tab: the spec the rib card wrote from what the engineer set, the design
 * made from it, and that design's verdict.
 *
 * Nothing here decides anything. The spec is written from the card, in the engineer's words and
 * selections; this shows it and makes designs from it. Every verdict lists the engineer's
 * constraints first, each citing the words it came from, then the checks the platform holds every
 * rib to - with any threshold nobody confirmed marked assumed.
 */

import type { SpecInfo, Verdict, VerdictRow } from "../api/client";

export interface GenerateLayers {
  /** The part as its CAD describes it. */
  geometry: boolean;
  /** The design's new surfaces: ribs and fillets. */
  design: boolean;
}

export const GENERATE_COLOURS: Record<keyof GenerateLayers, string> = {
  geometry: "#a5a9a4",
  design: "#0e6e74",
};

const GENERATE_LABELS: Record<keyof GenerateLayers, string> = {
  geometry: "Part",
  design: "Ribs and fillets",
};

interface GenerateIndexProps {
  layers: GenerateLayers;
  onLayers: (layers: GenerateLayers) => void;
  spec: SpecInfo | null;
  verdict: Verdict | null;
  onDesign: (fidelity: "preview" | "full") => void;
  busy: string | null;
  error: string | null;
}

export function GenerateIndex(props: GenerateIndexProps) {
  const { spec, verdict } = props;
  const working = props.busy !== null;
  const current = spec?.current;

  return (
    <nav className="index">
      <section className="section">
        <header>Layers</header>
        <div className="layers">
          {(Object.keys(GENERATE_LABELS) as (keyof GenerateLayers)[]).map((name) => (
            <button
              key={name}
              data-on={props.layers[name]}
              onClick={() => props.onLayers({ ...props.layers, [name]: !props.layers[name] })}
            >
              <span className="swatch" style={{ background: GENERATE_COLOURS[name] }} />
              {GENERATE_LABELS[name]}
            </button>
          ))}
        </div>
      </section>

      <section className="section">
        <header>
          The spec
          {current ? (
            <span className="detail">
              {" "}
              {spec?.spec} · version {current.version}
            </span>
          ) : null}
        </header>
        <div className="body">
          {!current ? (
            <div className="card-note">
              No spec yet. Start the rib card from faces on the part and make a design from it:
              the card is written as the spec first, and designs are made only from that.
            </div>
          ) : (
            <>
              <div className="words">
                {current.words.map((word) => (
                  <p key={word.id}>
                    <span className="mono dim">{word.id}</span> &ldquo;{word.text}&rdquo;
                  </p>
                ))}
              </div>
              {current.placements.map((placement) => (
                <PlacementCard key={String(placement.id)} placement={placement} />
              ))}
              {current.levers.length ? (
                <div className="card-note">
                  Levers:{" "}
                  {current.levers
                    .map((lever) => `${lever.path} ${lever.low}–${lever.high}`)
                    .join(", ")}
                </div>
              ) : null}
              {current.note ? <div className="card-note">{current.note}</div> : null}
            </>
          )}
        </div>
      </section>

      <section className="section">
        <header>Design</header>
        <div className="body">
          <div className="card-note">
            Preview is the same design on a coarser grid, for looking. A design is accepted only
            at full.
          </div>
          <div className="actions">
            <button onClick={() => props.onDesign("preview")} disabled={!current || working}>
              Preview
            </button>
            <button onClick={() => props.onDesign("full")} disabled={!current || working}>
              Full
            </button>
          </div>
          {props.busy ? <div className="card-note busy-note">{props.busy}</div> : null}
          {props.error ? <div className="warn">{props.error}</div> : null}
        </div>
      </section>

      {verdict ? <VerdictCard verdict={verdict} /> : null}
    </nav>
  );
}

function PlacementCard({ placement }: { placement: Record<string, unknown> }) {
  const layout = placement.layout as Record<string, unknown> | undefined;
  const section = placement.section as Record<string, unknown> | undefined;
  const host = (placement.host as string[] | undefined) ?? [];
  const supports = (placement.supports as string[] | undefined) ?? [];
  const keep = (placement.keep_out as Record<string, unknown>[] | undefined) ?? [];
  const cites = (placement.cites as string[] | undefined) ?? [];
  return (
    <div className="approval">
      <div className="card-head">
        <span className="card-title">Placement {String(placement.id)}</span>
        <span className="mono dim">{cites.join(" ")}</span>
      </div>
      <dl className="kv compact">
        <dt>on</dt>
        <dd className="mono">{host.join(", ")}</dd>
        <dt>between</dt>
        <dd className="mono">{supports.length ? supports.join(", ") : "the host's edges"}</dd>
        {keep.length ? (
          <>
            <dt>clear of</dt>
            <dd>
              {keep
                .map(
                  (k) =>
                    `${[...((k.features as string[]) ?? []), ...((k.kinds as string[]) ?? []).map((kind) => `every ${kind}`)].join(", ")}` +
                    ` by ${k.clearance_mm} mm`,
                )
                .join("; ")}
            </dd>
          </>
        ) : null}
        <dt>layout</dt>
        <dd>{layout ? describeLayout(layout) : ""}</dd>
        <dt>section</dt>
        <dd>
          {section
            ? `${section.thickness_mm} mm thick, R${section.root_fillet_mm} root` +
              (section.edge_round_mm ? `, R${section.edge_round_mm} edges` : "") +
              (section.draft_deg ? `, ${section.draft_deg}° draft` : "")
            : ""}
        </dd>
      </dl>
    </div>
  );
}

function describeLayout(layout: Record<string, unknown>): string {
  if (layout.kind === "radial") {
    return `${layout.count} spokes about ${layout.centre}`;
  }
  const families = (layout.families as Record<string, unknown>[] | undefined) ?? [];
  return families
    .map(
      (f) =>
        `${f.count ? `${f.count} paths` : `every ${f.spacing_mm} mm`} at ${f.angle_deg ?? 0}°`,
    )
    .join(" + ");
}

function VerdictCard({ verdict }: { verdict: Verdict }) {
  return (
    <section className="section">
      <header>
        This design <span className="chip" data-outcome={verdict.outcome}>{verdict.outcome}</span>
        <span className="detail">
          {" "}
          {verdict.fidelity} · spec v{verdict.spec_version}
        </span>
      </header>
      <div className="body">
        <dl className="kv compact">
          <dt>ribs</dt>
          <dd>{verdict.ribs}</dd>
          <dt>added</dt>
          <dd>{verdict.added_cm3.toLocaleString(undefined, { maximumFractionDigits: 0 })} cm³</dd>
          <dt>made in</dt>
          <dd>{verdict.seconds} s</dd>
        </dl>
        <div className="verdict-part">Your constraints</div>
        <div className="findings">
          {verdict.constraints.map((row) => (
            <Row key={row.check} row={row} />
          ))}
        </div>
        <div className="verdict-part">Checks</div>
        <div className="findings">
          {verdict.checks.map((row) => (
            <Row key={row.check} row={row} />
          ))}
        </div>
      </div>
    </section>
  );
}

function Row({ row }: { row: VerdictRow }) {
  return (
    <div className="finding" data-outcome={row.outcome} title={row.rule}>
      <span className="mark">{row.outcome}</span>
      <span className="what">
        <b>{row.check}</b> {row.reason}
        {row.cites?.length ? <span className="mono dim"> · {row.cites.join(" ")}</span> : null}
        {row.assumed ? <span className="assumed"> · assumed rule</span> : null}
      </span>
    </div>
  );
}
