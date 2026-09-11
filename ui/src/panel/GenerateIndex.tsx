/**
 * The rail for the Generate tab: approve where ribs may go, pick a formation, set its levers,
 * generate, and see what came out.
 *
 * Nothing is preloaded and nothing is decided here. Zones and protected areas arrive as proposals
 * and a person approves them; levers exist only for an approved zone; every design comes back with
 * each check's verdict and the rule it used, so an assumed threshold never reads as a confirmed one.
 *
 * No part's vocabulary: zones, formations, levers and rules are all labelled by the server.
 */

import type {
  FindingRow,
  Formations,
  MadeDesign,
  SpaceInfo,
  ZoneSettings,
  ZonesInfo,
} from "../api/client";

export interface GenerateLayers {
  /** The part as its CAD describes it. */
  geometry: boolean;
  /** The design's new surfaces: ribs and fillets. */
  design: boolean;
}

export const GENERATE_COLOURS: Record<keyof GenerateLayers, string> = {
  geometry: "#a5a9a4",
  design: "#0f3d91",
};

const GENERATE_LABELS: Record<keyof GenerateLayers, string> = {
  geometry: "Part",
  design: "Ribs and fillets",
};

interface GenerateIndexProps {
  layers: GenerateLayers;
  onLayers: (layers: GenerateLayers) => void;

  zones: ZonesInfo | null;
  onApproveZone: (id: string, approved: boolean) => void;
  onApproveProtected: (approved: boolean) => void;

  space: SpaceInfo | null;
  onOpen: () => void;

  formations: Formations | null;
  settings: Record<string, ZoneSettings>;
  onSettings: (zoneId: string, settings: ZoneSettings) => void;
  onGenerate: () => void;

  made: MadeDesign | null;
  busy: string | null;
  error: string | null;
}

export function GenerateIndex(props: GenerateIndexProps) {
  const { zones, space, formations, made } = props;
  const approved = zones?.zones.filter((z) => z.status === "approved") ?? [];
  const working = props.busy !== null;

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
          <span className="step">1</span> Approve where ribs may go
        </header>
        <div className="body">
          {!zones ? (
            <div className="card-note">Reading the project&hellip;</div>
          ) : zones.zones.length === 0 ? (
            <div className="card-note">
              No zones yet. Where ribs may go comes from what you ask for: the faces they stand on,
              what they run between, and what they keep away from.
            </div>
          ) : (
            zones.zones.map((zone) => (
              <div key={zone.id} className="approval">
                <div className="card-head">
                  <span className="card-title">{zone.label}</span>
                  <span className="chip" data-state={zone.status}>
                    {zone.status}
                  </span>
                </div>
                <div className="card-note">{zone.summary}</div>
                <div className="actions">
                  <button
                    onClick={() => props.onApproveZone(zone.id, zone.status !== "approved")}
                    disabled={working}
                  >
                    {zone.status === "approved" ? "Withdraw" : "Approve"}
                  </button>
                </div>
              </div>
            ))
          )}

          {zones ? (
            <div className="approval">
              <div className="card-head">
                <span className="card-title">Protected areas</span>
                <span className="chip" data-state={zones.protected.status}>
                  {zones.protected.status}
                </span>
              </div>
              <div className="card-note">
                Every {zones.protected.kinds.map((k) => k.replace("_", " ")).join(", ")} face, and{" "}
                {zones.protected.clearance_mm} mm around it. Ribs and fillets that reach them are
                cut back, and the surface there stays exactly as it was.
              </div>
              <div className="actions">
                <button
                  onClick={() => props.onApproveProtected(zones.protected.status !== "approved")}
                  disabled={working}
                >
                  {zones.protected.status === "approved" ? "Withdraw" : "Approve"}
                </button>
              </div>
            </div>
          ) : null}

        </div>
      </section>

      <section className="section">
        <header>
          <span className="step">2</span> Open for designing
        </header>
        <div className="body">
          {space ? (
            <dl className="kv compact">
              <dt>grid</dt>
              <dd>{space.spacing_mm} mm</dd>
              <dt>part</dt>
              <dd>{space.base_volume_cm3.toLocaleString()} cm³</dd>
              <dt>root fillet</dt>
              <dd>R{space.radius_mm}</dd>
            </dl>
          ) : (
            <div className="card-note">
              Builds or reads the part&rsquo;s field, its contour, and each approved zone&rsquo;s
              window. Minutes the first time on a large part, seconds after.
            </div>
          )}
          <div className="actions">
            <button onClick={props.onOpen} disabled={approved.length === 0 || working}>
              {space ? "Open again" : "Open"}
            </button>
          </div>
        </div>
      </section>

      {space && formations ? (
        <section className="section">
          <header>
            <span className="step">3</span> Set the levers
          </header>
          {space.zones.map((zone) => {
            const chosen = props.settings[zone.id];
            const formation = formations.formations.find((f) => f.name === chosen?.formation);
            return (
              <div key={zone.id} className="parameter">
                <div className="card-head">
                  <span className="card-title">{zone.label}</span>
                  <select
                    value={chosen?.formation ?? ""}
                    onChange={(event) => {
                      const next = formations.formations.find((f) => f.name === event.target.value);
                      if (next) props.onSettings(zone.id, defaults(next));
                    }}
                  >
                    {formations.formations.map((f) => (
                      <option key={f.name} value={f.name}>
                        {f.label}
                      </option>
                    ))}
                  </select>
                </div>
                {formation && chosen
                  ? formation.levers.map((lever) => (
                      <label key={lever.name} className="slider">
                        {lever.label.toLowerCase()}
                        <input
                          type="range"
                          min={lever.low}
                          max={lever.high}
                          step={lever.step}
                          value={chosen.values[lever.name] ?? lever.low}
                          onChange={(event) =>
                            props.onSettings(zone.id, {
                              ...chosen,
                              values: { ...chosen.values, [lever.name]: Number(event.target.value) },
                            })
                          }
                        />
                        <span className="mono">
                          {format(chosen.values[lever.name] ?? lever.low, lever.step)}
                          {lever.unit === "mm" || lever.unit === "deg"
                            ? ` ${lever.unit === "deg" ? "°" : "mm"}`
                            : ""}
                        </span>
                      </label>
                    ))
                  : null}
              </div>
            );
          })}
          <div className="body">
            <div className="card-note">
              Every rib shares R{formations.fixed.root_fillet_mm} root fillets, R
              {formations.fixed.edge_round_mm} rounded free edges and {formations.fixed.draft_deg}
              &deg; draft, from the casting rules. Rules marked assumed are defaults nobody has
              confirmed.
            </div>
            <div className="actions">
              <button onClick={props.onGenerate} disabled={working}>
                {props.busy === "generating" ? "Generating…" : "Generate"}
              </button>
            </div>
          </div>
        </section>
      ) : null}

      {made ? <DesignResult made={made} /> : null}

      {props.busy && props.busy !== "generating" ? (
        <div className="card-note busy-note">{props.busy}</div>
      ) : null}
      {props.error ? <div className="warn">{props.error}</div> : null}
    </nav>
  );
}

function DesignResult({ made }: { made: MadeDesign }) {
  const { stats } = made;
  const addedMass =
    stats.mass_kg !== null && stats.base_mass_kg !== null ? stats.mass_kg - stats.base_mass_kg : null;
  return (
    <section className="section">
      <header>
        This design <span className="chip" data-outcome={made.outcome}>{made.outcome}</span>
      </header>
      <div className="body">
        <dl className="kv compact">
          <dt>ribs</dt>
          <dd>
            {stats.ribs}
            {stats.dropped ? ` · ${stats.dropped} pieces too short, dropped` : ""}
          </dd>
          <dt>mass</dt>
          <dd>
            {stats.mass_kg === null
              ? "no density given"
              : `${stats.mass_kg.toFixed(1)} kg` +
                (addedMass === null ? "" : ` (${addedMass >= 0 ? "+" : ""}${addedMass.toFixed(1)} kg)`)}
          </dd>
          <dt>added</dt>
          <dd>{stats.added_cm3.toLocaleString(undefined, { maximumFractionDigits: 0 })} cm³</dd>
          <dt>smallest fillet</dt>
          <dd>{stats.smallest_fillet_mm === null ? "not measured" : `R${stats.smallest_fillet_mm}`}</dd>
          <dt>made in</dt>
          <dd>
            {Object.values(stats.seconds)
              .reduce((a, b) => a + b, 0)
              .toFixed(1)}{" "}
            s
          </dd>
        </dl>
        <div className="findings">
          {made.findings.map((finding) => (
            <Finding key={finding.check} finding={finding} />
          ))}
        </div>
        <div className="card-note mono dim">{made.digest.slice(0, 19)}</div>
      </div>
    </section>
  );
}

function Finding({ finding }: { finding: FindingRow }) {
  return (
    <div className="finding" data-outcome={finding.outcome} title={finding.rule}>
      <span className="mark">{finding.outcome}</span>
      <span className="what">
        <b>{finding.check}</b> {finding.reason}
        {finding.assumed ? <span className="assumed"> · assumed rule</span> : null}
      </span>
    </div>
  );
}


/** A formation's levers set to the middle of their ranges, snapped to their steps. */
export function defaults(formation: {
  name: string;
  levers: { name: string; low: number; high: number; step: number }[];
}): ZoneSettings {
  const values: Record<string, number> = {};
  for (const lever of formation.levers) {
    const middle = (lever.low + lever.high) / 2;
    values[lever.name] = Number((Math.round(middle / lever.step) * lever.step).toFixed(6));
  }
  return { formation: formation.name, values };
}

function format(value: number, step: number): string {
  const places = step >= 1 ? 0 : Math.min(3, Math.ceil(-Math.log10(step)));
  return value.toFixed(places);
}
