/**
 * The rail for the Generate tab: the study the rib card wrote from what the engineer set, the design
 * made from it, and that design's verdict.
 *
 * Nothing here decides anything. The study is written from the card, in the engineer's words and
 * selections: what may vary and over what range, what must hold - how firmly, and where each rule
 * came from - what nothing enforces yet, and what nobody confirmed. This shows it and makes designs
 * from it. Every verdict lists the engineer's constraints first, each citing the words it came
 * from, then the checks the platform holds every rib to.
 */

import { Fragment } from "react";

import type { StudyBlock, StudyConstraint, StudyInfo, Verdict, VerdictRow } from "../api/client";

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
  study: StudyInfo | null;
  verdict: Verdict | null;
  onDesign: (fidelity: "preview" | "full") => void;
  busy: string | null;
  error: string | null;
}

export function GenerateIndex(props: GenerateIndexProps) {
  const { study, verdict } = props;
  const working = props.busy !== null;
  const current = study?.current;

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
          The study
          {current ? (
            <span className="detail">
              {" "}
              {study?.study} · version {current.version}
            </span>
          ) : null}
        </header>
        <div className="body">
          {!current ? (
            <div className="card-note">
              No study yet. Start the rib card from faces on the part and make a design from it:
              the card is written as the study first, and designs are made only from that.
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
              {current.blocks.map((block) => (
                <BlockCard key={block.id} block={block} said={study?.shown?.free[block.id] ?? {}} />
              ))}
              <div className="verdict-part">Must hold</div>
              <div className="study-rules">
                {current.constraints.map((constraint) => (
                  <ConstraintRow
                    key={constraint.id}
                    constraint={constraint}
                    said={study?.shown?.constraints[constraint.id] ?? constraint.kind}
                  />
                ))}
              </div>
              <Lines title="Not enforced yet" lines={study?.open ?? []} />
              <Lines title="Assumed - confirm, lock or narrow" lines={study?.assumed ?? []} />
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

// The free settings of a block of ribs, as the engineer would name them.
const SETTING: Record<string, string> = {
  generator: "patterns",
  centre: "spokes about",
  spread: "spokes",
  angle_deg: "angle",
  spacing_mm: "spacing",
  count: "count",
  thickness_mm: "thickness",
  root_fillet_mm: "root fillet",
  edge_round_mm: "edge round",
  draft_deg: "draft",
  top: "top",
  height_fraction: "height",
};

/** One group of features to add: where, and each setting with what it may take and who said so. */
function BlockCard({ block, said }: { block: StudyBlock; said: Record<string, string> }) {
  const anchors = block.where.anchors;
  return (
    <div className="approval">
      <div className="card-head">
        <span className="card-title">
          Add {block.add} · {block.id}
        </span>
        <span className="mono dim">{block.cites.join(" ")}</span>
      </div>
      <dl className="kv compact">
        <dt>on</dt>
        <dd className="mono">{block.where.support.join(", ") || "nothing - they hang"}</dd>
        <dt>between</dt>
        <dd>{anchors.length ? `${anchors.length} faces` : "the edges of where they stand"}</dd>
        {Object.entries(block.free).map(([name, domain]) => (
          <Fragment key={name}>
            <dt>{SETTING[name] ?? name}</dt>
            <dd>
              {said[name] ?? ""} <span className="dim">· {domain.source}</span>
            </dd>
          </Fragment>
        ))}
      </dl>
    </div>
  );
}

/** A rule every design must satisfy: how firmly - hard, assumed, learned - and where it came from. */
function ConstraintRow({ constraint, said }: { constraint: StudyConstraint; said: string }) {
  const from = constraint.basis ? `${constraint.source}: ${constraint.basis}` : constraint.source;
  return (
    <div className="study-rule" title={from}>
      <span className="chip" data-strength={constraint.strength}>
        {constraint.strength}
      </span>
      <span className="mono dim">{constraint.id}</span> {said}
      {constraint.cites.length ? (
        <span className="mono dim"> · {constraint.cites.join(" ")}</span>
      ) : (
        <span className="dim"> · {constraint.source}</span>
      )}
    </div>
  );
}

function Lines({ title, lines }: { title: string; lines: string[] }) {
  if (!lines.length) return null;
  return (
    <>
      <div className="verdict-part">{title}</div>
      <ul className="study-lines">
        {lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </>
  );
}

function VerdictCard({ verdict }: { verdict: Verdict }) {
  return (
    <section className="section">
      <header>
        This design <span className="chip" data-outcome={verdict.outcome}>{verdict.outcome}</span>
        <span className="detail">
          {" "}
          {verdict.fidelity} · study v{verdict.study_version ?? verdict.spec_version}
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
        <Lines title="Not checked - nothing enforces these yet" lines={verdict.open ?? []} />
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
