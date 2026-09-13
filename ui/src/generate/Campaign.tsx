/**
 * Generate, Campaign: many designs at once, with the whole pipeline in the open.
 *
 * What varies is the design space as Design a variant (on CAD) has it - every block, what it adds,
 * where, what its settings may take - and what must hold: the rules of each block and of the study,
 * the part's interfaces, the screening checks every design passes before it is kept, and the rules
 * of thumb they rest on, each with its source. How designs are spread over it and the stages each
 * one goes through are said too.
 *
 * Any block, rule or check can be switched off for one campaign without touching the study: the run
 * keeps the version it used and what was off beside its designs, and a campaign with other switches
 * is a run of its own. The part's interfaces stay closed whatever is switched off.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import type {
  CampaignOff,
  CampaignPipeline,
  GoAlone,
  GoProgress,
  KeptRun,
  StudyBlockView,
  StudyDraft,
  StudyRule,
} from "../api/client";
import { api } from "../api/client";
import { plain } from "../panel/shared";

const NONE_OFF: CampaignOff = { blocks: [], rules: [], checks: [] };

/** What a launched campaign has said so far. */
export interface Launched {
  run: string;
  version: number;
  n: number;
  budget: number;
  waiting: string[];
  off: CampaignOff;
}

export interface Campaign {
  pipeline: CampaignPipeline | null;
  draft: StudyDraft | null;
  off: CampaignOff;
  toggle: (kind: keyof CampaignOff, id: string) => void;
  allOn: () => void;
  n: string;
  setN: (n: string) => void;
  seed: string;
  setSeed: (seed: string) => void;
  going: string | null;
  launched: Launched | null;
  alone: GoAlone[];
  progress: GoProgress | null;
  kept: number;
  masses: [number, number] | null;
  finished: string | null;
  problem: string | null;
  launch: () => Promise<void>;
}

/** A campaign's state: read whenever the tab is opened, since the card may have changed since. */
export function useCampaign(active: boolean, project: string | null): Campaign {
  const [pipeline, setPipeline] = useState<CampaignPipeline | null>(null);
  const [draft, setDraft] = useState<StudyDraft | null>(null);
  const [off, setOff] = useState<CampaignOff>(NONE_OFF);
  const [n, setN] = useState("4000");
  const [seed, setSeed] = useState("");
  const [going, setGoing] = useState<string | null>(null);
  const [launched, setLaunched] = useState<Launched | null>(null);
  const [alone, setAlone] = useState<GoAlone[]>([]);
  const [progress, setProgress] = useState<GoProgress | null>(null);
  const [kept, setKept] = useState(0);
  const [masses, setMasses] = useState<[number, number] | null>(null);
  const [finished, setFinished] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    setPipeline(null);
    setDraft(null);
    setOff(NONE_OFF);
    setLaunched(null);
    setFinished(null);
  }, [project]);

  const read = useCallback(() => {
    Promise.all([api.campaign(), api.studyDraft()])
      .then(([found, card]) => {
        setPipeline(found);
        setDraft(card.draft);
      })
      .catch((caught) => setProblem(plain(caught)));
  }, []);

  useEffect(() => {
    if (active && project && going === null) read();
  }, [active, project, going, read]);

  const toggle = useCallback((kind: keyof CampaignOff, id: string) => {
    setOff((was) => ({
      ...was,
      [kind]: was[kind].includes(id) ? was[kind].filter((x) => x !== id) : [...was[kind], id],
    }));
  }, []);

  const allOn = useCallback(() => setOff(NONE_OFF), []);

  const launch = useCallback(async () => {
    const count = Number(n);
    const from = seed.trim() === "" ? null : Number(seed);
    // Only what the card still has: a switch left over from a block since taken out is dropped.
    const known = knownIds(draft, pipeline);
    const sent: CampaignOff = {
      blocks: off.blocks.filter((id) => known.blocks.has(id)),
      rules: off.rules.filter((id) => known.rules.has(id)),
      checks: off.checks.filter((id) => known.checks.has(id)),
    };
    setProblem(null);
    setLaunched(null);
    setAlone([]);
    setProgress(null);
    setKept(0);
    setMasses(null);
    setFinished(null);
    setGoing("Accepting the card if it changed, and trying each block alone.");
    // Thousands of designs come one by one: only how many, and what they weigh, is kept here - the
    // designs themselves are read from the run, on Designs.
    let low = Infinity;
    let high = -Infinity;
    let made = 0;
    // What the stream said, read once it ends: kept in an object the handler writes to.
    const ended: { run: string | null; failed: boolean } = { run: null, failed: false };
    try {
      await api.go(
        { n: Number.isInteger(count) && count > 0 ? count : null, seed: from, off: sent },
        (event) => {
          if (event.type === "started") {
            ended.run = event.run;
            setLaunched(event);
            setGoing(
              `Trying each block alone, then ${event.n.toLocaleString()} designs from study ` +
                `v${event.version} - at most ${event.budget.toLocaleString()} tried.`,
            );
          } else if (event.type === "block") setAlone((was) => [...was, event]);
          else if (event.type === "design") {
            made += 1;
            low = Math.min(low, event.mass_kg);
            high = Math.max(high, event.mass_kg);
          } else if (event.type === "progress" || event.type === "done") {
            setProgress(event);
            setKept(made);
            if (made) setMasses([low, high]);
          } else if (event.type === "error") {
            ended.failed = true;
            setProblem(event.message);
          }
        },
      );
      if (ended.run && !ended.failed) setFinished(ended.run);
    } catch (caught) {
      setProblem(plain(caught));
    } finally {
      setGoing(null);
    }
  }, [n, seed, off, draft, pipeline]);

  return {
    pipeline,
    draft,
    off,
    toggle,
    allOn,
    n,
    setN,
    seed,
    setSeed,
    going,
    launched,
    alone,
    progress,
    kept,
    masses,
    finished,
    problem,
    launch,
  };
}

/** The ids the card has now, of blocks and rules, and the names of the checks. */
function knownIds(draft: StudyDraft | null, pipeline: CampaignPipeline | null) {
  const blocks = new Set((draft?.blocks ?? []).map((b) => b.id));
  const rules = new Set<string>();
  for (const block of draft?.blocks ?? []) {
    for (const rule of [...block.rules, ...block.keep_clear]) rules.add(rule.id);
  }
  for (const rule of draft?.rules ?? []) rules.add(rule.id);
  const checks = new Set((pipeline?.checks ?? []).map((c) => c.name));
  return { blocks, rules, checks };
}

// --- the pipeline, in the open ------------------------------------------------------------------

/** What each rule of thumb is, in words. */
const KNOWLEDGE: Record<string, [string, string]> = {
  rib_to_wall: ["a rib no thicker than", "× the wall it stands on"],
  root_gap: ["ribs in the open at least", "× the thinner one apart"],
  hole_ligament: ["between a hole and a rib at least", "× the plate's thickness of metal"],
  min_wall_mm: ["no wall thinner than", "mm, where the material says nothing"],
};

/** The pipeline, top to bottom: what varies, what must hold, how designs are screened and on what
 * rules of thumb, how they are spread, and the stages each one goes through. */
export function CampaignPipelineView(props: {
  campaign: Campaign;
  onOpenCard: () => void;
}) {
  const { pipeline, draft, off, toggle } = props.campaign;
  const locked = props.campaign.going !== null;
  if (!pipeline || !draft) {
    return (
      <div className="campaign-doc">
        <p className="card-note">{props.campaign.problem ?? "Reading the pipeline…"}</p>
      </div>
    );
  }
  return (
    <div className="campaign-doc">
      <section className="campaign-section">
        <h2>
          What varies
          <span className="dim">
            {" "}
            - the design space as{" "}
            <button className="link" onClick={props.onOpenCard}>
              Design a variant
            </button>{" "}
            on CAD has it
            {draft.accepted !== null ? `, study v${draft.accepted}` : ""}
          </span>
        </h2>
        {draft.refused ? (
          <div className="card-note warn">
            The card's draft cannot be written - {draft.cannot}. No campaign can start until it can.
          </div>
        ) : draft.differs ? (
          <div className="card-note warn">
            The card has changes not accepted yet: launching accepts them as v
            {(draft.accepted ?? 0) + 1} first.
          </div>
        ) : null}
        {!draft.blocks.length ? (
          <div className="card-note">
            Nothing varies yet: add blocks on Design a variant, on CAD - or say what you want to the
            agent at the top.
          </div>
        ) : null}
        {draft.blocks.map((block) => (
          <BlockRow
            key={block.id}
            block={block}
            names={draft.names}
            off={off}
            locked={locked}
            onToggle={toggle}
          />
        ))}
      </section>

      <section className="campaign-section">
        <h2>
          What must hold <span className="dim">- for every block</span>
        </h2>
        {draft.rules.length ? (
          draft.rules.map((rule) => (
            <RuleSwitch key={rule.id} rule={rule} off={off} locked={locked} onToggle={toggle} />
          ))
        ) : (
          <div className="card-note">No rules for the whole study.</div>
        )}
        {draft.interfaces.length ? (
          <details className="study-fold">
            <summary>
              The part's {draft.interfaces.length} interfaces are kept as they are - always, whatever
              is switched off
            </summary>
            <ul className="study-lines">
              {draft.interfaces.map((rule) => (
                <li key={rule.id}>{rule.says}</li>
              ))}
            </ul>
          </details>
        ) : null}
      </section>

      <section className="campaign-section">
        <h2>
          Screening <span className="dim">- every design, before it is kept, in milliseconds</span>
        </h2>
        <p className="card-note">
          A check switched off lets through what it would have screened out. A design is checked in
          full only when its field is built.
        </p>
        {pipeline.checks.map((check) => (
          <label key={check.name} className="switch-row" data-off={off.checks.includes(check.name)}>
            <input
              type="checkbox"
              checked={!off.checks.includes(check.name)}
              disabled={locked}
              onChange={() => toggle("checks", check.name)}
            />
            <b>{check.name}</b>
            <span>{check.rule}</span>
            <span className="dim"> · {check.source}</span>
          </label>
        ))}
      </section>

      <section className="campaign-section">
        <h2>
          How ribs, pads and holes are placed{" "}
          <span className="dim">- for every design, before it is screened</span>
        </h2>
        {pipeline.placement.map((rule) => (
          <div key={rule.name} className="knowledge-row">
            <span>
              <b>{rule.name}</b> {rule.says}
            </span>
            <span className="mono">{rule.value ?? ""}</span>
          </div>
        ))}
        <div className="knowledge-row">
          <span>
            <b>interfaces</b> the part's holes and bores are kept as they are, whatever is switched
            off, this many mm clear
          </span>
          <span className="mono">{pipeline.interfaces_clear_mm}</span>
        </div>
      </section>

      <section className="campaign-section">
        <h2>
          Rules of thumb <span className="dim">- what the checks and the blocks rest on</span>
        </h2>
        {pipeline.knowledge.map((rule) => {
          const [before, after] = KNOWLEDGE[rule.name] ?? [rule.name, ""];
          return (
            <div key={rule.name} className="knowledge-row">
              <span>
                {before} <b className="mono">{rule.value}</b> {after}
              </span>
              <span className="dim">{rule.source}</span>
            </div>
          );
        })}
        <details className="study-fold">
          <summary>
            The materials the catalogue holds ({pipeline.materials.length}) - a part is cast in one,
            which its designs do not change
          </summary>
          <table className="materials">
            <thead>
              <tr>
                <th>material</th>
                <th>density</th>
                <th>least wall</th>
                <th>source</th>
              </tr>
            </thead>
            <tbody>
              {pipeline.materials.map((m) => (
                <tr key={m.id}>
                  <td>{m.name}</td>
                  <td className="mono">{m.density_kg_m3.toLocaleString()} kg/m³</td>
                  <td className="mono">{m.min_wall_mm} mm</td>
                  <td className="dim">{m.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </section>

      <section className="campaign-section">
        <h2>How designs are spread</h2>
        <p className="card-note">
          {capital(pipeline.sampler.says)}. Each block alone tries {pipeline.sampler.pool.least} to{" "}
          {pipeline.sampler.pool.most.toLocaleString()} points; together, up to{" "}
          {pipeline.sampler.tries_per_design} tries a design kept. Two designs that come out alike
          are kept once.
        </p>
      </section>

      <section className="campaign-section">
        <h2>What each design goes through</h2>
        <div className="stage-list">
          {pipeline.stages.map((stage) => (
            <div key={stage.key} className="stage-list-row" data-built={stage.built}>
              <span className="stage-badge" data-state={stage.built ? "done" : "none"}>
                {stage.key}
              </span>
              <b>{stage.label}</b>
              <span>{stage.says}</span>
              <span className="dim">{stage.built ? "" : " · not built yet"}</span>
            </div>
          ))}
        </div>
        <p className="card-note">
          A campaign places and screens its designs; a design's field is built on Designs, one at a
          time. Meshing, solver setup and results come next.
        </p>
        <details className="study-fold">
          <summary>
            What a design is checked for when its field is built ({pipeline.full_checks.length})
          </summary>
          {pipeline.full_checks.map((check) => (
            <div key={check.name} className="knowledge-row">
              <span>
                <b>{check.name}</b> {check.rule}
              </span>
            </div>
          ))}
        </details>
      </section>
    </div>
  );
}

/** One block: in this campaign or not; what it adds, where, what its settings may take - and its
 * rules, each switched on or off. */
function BlockRow(props: {
  block: StudyBlockView;
  names: Record<string, string>;
  off: CampaignOff;
  locked: boolean;
  onToggle: (kind: keyof CampaignOff, id: string) => void;
}) {
  const { block, off } = props;
  const gone = off.blocks.includes(block.id);
  const where = block.stand_on.refs;
  const rules = [...block.keep_clear, ...block.rules];
  return (
    <div className="campaign-block" data-off={gone}>
      <label className="switch-row block-switch">
        <input
          type="checkbox"
          checked={!gone}
          disabled={props.locked}
          onChange={() => props.onToggle("blocks", block.id)}
        />
        <b>
          {block.id} · adds {block.add}
        </b>
        {where.length ? (
          <span className="dim" title={where.map((r) => props.names[r] ?? r).join("\n")}>
            {block.add === "thicken" ? "moving " : block.add === "holes" ? "through " : "on "}
            {where.slice(0, 3).join(", ")}
            {where.length > 3 ? ` +${where.length - 3}` : ""}
          </span>
        ) : null}
        {block.cannot ? <span className="warn"> · {block.cannot}</span> : null}
      </label>
      {!gone ? (
        <div className="campaign-block-body">
          {block.settings.map((setting) => (
            <div key={setting.name} className="campaign-setting">
              <span className="tag" data-fixed={setting.fixed}>
                {setting.fixed ? "fixed" : "varies"}
              </span>
              <span className="setting-label">{setting.label}</span> {setting.says}
            </div>
          ))}
          {rules.map((rule) => (
            <RuleSwitch
              key={rule.id}
              rule={rule}
              off={off}
              locked={props.locked}
              onToggle={props.onToggle}
            />
          ))}
        </div>
      ) : (
        <div className="card-note">Switched off for this campaign: nothing of it is made.</div>
      )}
    </div>
  );
}

/** A rule switched on or off for this campaign - or, the platform's, always on. */
function RuleSwitch(props: {
  rule: StudyRule;
  off: CampaignOff;
  locked: boolean;
  onToggle: (kind: keyof CampaignOff, id: string) => void;
}) {
  const { rule } = props;
  const platform = rule.by === "platform";
  const isOff = props.off.rules.includes(rule.id);
  return (
    <label className="switch-row rule-switch" data-off={isOff} title={rule.basis || undefined}>
      <input
        type="checkbox"
        checked={!isOff}
        disabled={props.locked || platform}
        onChange={() => props.onToggle("rules", rule.id)}
      />
      <span className="chip" data-strength={rule.strength}>
        {rule.strength}
      </span>
      <span>{rule.says}</span>
      {platform ? <span className="dim"> · the platform's, always on</span> : null}
      {!rule.enforced ? <span className="dim"> · not enforced yet</span> : null}
    </label>
  );
}

// --- launching, and what came of it -------------------------------------------------------------

/** Launch: how many, from which seed, what is switched off - and the campaign as it runs. */
export function CampaignLaunch(props: {
  campaign: Campaign;
  onOpenRun: (run: string) => void;
  onCollapse: () => void;
}) {
  const c = props.campaign;
  const offCount = c.off.blocks.length + c.off.rules.length + c.off.checks.length;
  const buildable = (c.draft?.blocks ?? []).some(
    (b) => !c.off.blocks.includes(b.id) && !b.cannot && !b.needed.length && !b.problems.length,
  );
  const rejected = Object.entries(c.progress?.rejected ?? {}).sort((a, b) => b[1] - a[1]);
  const ruleSays = useMemo(() => {
    const out: Record<string, string> = {};
    for (const block of c.draft?.blocks ?? []) {
      for (const rule of [...block.rules, ...block.keep_clear]) out[rule.id] = rule.says;
    }
    for (const rule of c.draft?.rules ?? []) out[rule.id] = rule.says;
    return out;
  }, [c.draft]);
  return (
    <div className="rib-card launch-card">
      <header className="rib-card-head">
        <span className="card-title">Launch a campaign</span>
        <button className="icon pane-fold" onClick={props.onCollapse} aria-label="Fold away">
          ›
        </button>
      </header>
      <div className="rib-slots">
        <section className="rib-slot">
          <div className="launch-line">
            <label>
              designs to keep{" "}
              <input
                className="num"
                value={c.n}
                disabled={c.going !== null}
                onChange={(e) => c.setN(e.target.value)}
                aria-label="designs to keep"
              />
            </label>
            <label>
              seed{" "}
              <input
                className="num"
                value={c.seed}
                placeholder="study's"
                disabled={c.going !== null}
                onChange={(e) => c.setSeed(e.target.value)}
                aria-label="seed"
              />
            </label>
          </div>
          <div className="launch-off">
            {offCount ? (
              <>
                <span className="dim">switched off for this campaign:</span>
                {c.off.blocks.map((id) => (
                  <OffChip key={`b${id}`} label={`block ${id}`} onOn={() => c.toggle("blocks", id)} />
                ))}
                {c.off.rules.map((id) => (
                  <OffChip
                    key={`r${id}`}
                    label={ruleSays[id] ?? id}
                    onOn={() => c.toggle("rules", id)}
                  />
                ))}
                {c.off.checks.map((name) => (
                  <OffChip key={`c${name}`} label={name} onOn={() => c.toggle("checks", name)} />
                ))}
                <button className="link" onClick={c.allOn} disabled={c.going !== null}>
                  switch all back on
                </button>
              </>
            ) : (
              <span className="dim">
                Nothing switched off: the design space as the card has it, every rule and check on.
                Switch any of them off in the pipeline for this campaign alone.
              </span>
            )}
          </div>
          <div className="actions">
            <button
              className="primary"
              onClick={() => void c.launch()}
              disabled={c.going !== null || !buildable || Boolean(c.draft?.refused)}
              title="Accept the card if it changed, then make this many designs over what it leaves free - each screened, every one kept written beside the project"
            >
              {c.going ? "Running…" : "Launch"}
            </button>
          </div>
        </section>

        {c.going || c.launched || c.problem ? (
          <section className="rib-slot go-designs">
            {c.launched ? (
              <div className="dim">
                run <b className="mono">{c.launched.run}</b>
                {c.launched.waiting.length ? ` - waiting: ${c.launched.waiting.join("; ")}` : ""}
              </div>
            ) : null}
            {c.going ? <div className="card-note busy-note">{c.going}</div> : null}
            {c.alone.length ? (
              <div className="go-alone">
                {c.alone.map((block) => (
                  <div key={block.block} className="dim">
                    {block.block} alone: {block.kept} of {block.tried} points make something
                    {Object.keys(block.rejected).length
                      ? ` - the rest: ${Object.entries(block.rejected)
                          .map(([why, n]) => `${why} ${n}`)
                          .join(", ")}`
                      : ""}
                  </div>
                ))}
              </div>
            ) : null}
            {c.progress ? (
              <div className="go-progress">
                <b>{c.progress.made.toLocaleString()}</b> kept of{" "}
                {c.progress.tried.toLocaleString()} tried together in {c.progress.seconds} s
                {rejected.length
                  ? ` - screened out: ${rejected.map(([why, n]) => `${why} ${n}`).join(", ")}`
                  : ""}
                {c.masses ? (
                  <span className="dim">
                    {" "}
                    · {Math.round(c.masses[0]).toLocaleString()} to{" "}
                    {Math.round(c.masses[1]).toLocaleString()} kg
                  </span>
                ) : null}
              </div>
            ) : null}
            {c.finished && !c.going ? (
              <div className="actions">
                <button onClick={() => props.onOpenRun(c.finished as string)}>
                  Open its designs
                </button>
              </div>
            ) : null}
            {c.problem ? <div className="card-note warn">{c.problem}</div> : null}
          </section>
        ) : null}
      </div>
    </div>
  );
}

function OffChip(props: { label: string; onOn: () => void }) {
  return (
    <span className="off-chip">
      {props.label}
      <button className="icon" onClick={props.onOn} title="Switch it back on">
        ×
      </button>
    </span>
  );
}

/** Every run kept for the project, newest first: its study and version, what it switched off,
 * how many designs of how many tried, how many built - each opened on Designs. */
export function CampaignRuns(props: {
  runs: KeptRun[];
  going: string | null;
  onOpenRun: (run: string) => void;
}) {
  return (
    <nav className="index">
      <section className="section">
        <header>
          Runs kept <span className="count">{props.runs.length}</span>
        </header>
        {props.going ? <div className="body card-note busy-note">A campaign is running.</div> : null}
        {!props.runs.length ? (
          <div className="body card-note">
            No campaign has run yet. Launch one on the right: its designs are kept in
            _archived_designs beside the project.
          </div>
        ) : null}
        {props.runs.map((run) => (
          <button key={run.run} className="row run-row" onClick={() => props.onOpenRun(run.run)}>
            <span className="run-name mono">{run.run}</span>
            <span className="run-detail">
              {run.study} v{run.version} · {run.made.toLocaleString()} designs of{" "}
              {run.tried.toLocaleString()} tried · {Math.round(run.seconds / 60)} min
              {run.built ? ` · ${run.built} built` : ""}
            </span>
            {offSaid(run.off) ? <span className="run-detail dim">{offSaid(run.off)}</span> : null}
          </button>
        ))}
      </section>
    </nav>
  );
}

function offSaid(off: Partial<CampaignOff>): string {
  const parts = [];
  if (off.blocks?.length) parts.push(`blocks ${off.blocks.join(", ")} off`);
  if (off.rules?.length) parts.push(`${off.rules.length} rules off`);
  if (off.checks?.length) parts.push(`${off.checks.join(", ")} off`);
  return parts.join(" · ");
}

function capital(text: string): string {
  return text ? text[0].toUpperCase() + text.slice(1) : text;
}
