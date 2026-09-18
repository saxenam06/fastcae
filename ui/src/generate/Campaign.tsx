/**
 * Generate, Campaign: a card in three steps, with the whole pipeline in the open.
 *
 * **Compose** - its name, and the variants it takes from the library, each with how many designs
 * it allows. **Check** - every rule each variant holds, what holds between variants, the part's
 * interfaces held always, the screening checks - each switchable for this campaign - the checks a
 * design's field is held to, and the pipeline: what each stage takes and gives. **Sample & launch**
 * - how designs are drawn, how many, from which seed, whether to keep the most different of more;
 * how many designs the variants allow; a hundred screened in half a minute, and how long the launch
 * will take; then the launch, and what it came to.
 *
 * A campaign never narrows a variant: to hold a lever fixed, change the variant on CAD. Every
 * launch is a campaign of its own, kept whole beside the project.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import type {
  CampaignCard,
  CampaignEstimate,
  CampaignPipeline,
  CampaignScreen,
  GoProgress,
  LaunchedCampaign,
  StudySetting,
  VariantRow,
  VariantShown,
} from "../api/client";
import { api } from "../api/client";
import { PATTERN_NAMES, matters, plain } from "../panel/shared";

const FRESH: CampaignCard = {
  name: "",
  variants: [],
  checks_off: [],
  method: "even",
  n: 20,
  seed: 0,
  diverse: 0,
};

/** What a launched campaign has said so far. */
interface Started {
  run: string;
  name: string;
  n: number;
  count: number | null;
}

interface Alone {
  variant: string;
  label: string;
  kept: number;
  tried: number;
  rejected: Record<string, number>;
}

export interface Campaign {
  pipeline: CampaignPipeline | null;
  library: VariantRow[];
  shown: Record<string, VariantShown>;
  /** Variants chosen that could not be read, and why. */
  unread: Record<string, string>;
  readAgain: () => void;
  card: CampaignCard;
  update: (change: Partial<CampaignCard>) => void;
  toggleVariant: (id: string) => void;
  toggleCheck: (name: string) => void;
  estimate: CampaignEstimate | null;
  screen: CampaignScreen | null;
  screening: boolean;
  runScreen: () => Promise<void>;
  going: string | null;
  started: Started | null;
  alone: Alone[];
  progress: (GoProgress & { repaired?: number }) | null;
  kept: number;
  finished: string | null;
  problem: string | null;
  launch: () => Promise<void>;
  launched: LaunchedCampaign[];
  refresh: () => void;
}

/** A campaign card's state: the library and the pipeline read whenever the tab is opened - a
 * variant may have been authored since - and what a launch says as it runs. */
export function useCampaign(active: boolean, project: string | null): Campaign {
  const [pipeline, setPipeline] = useState<CampaignPipeline | null>(null);
  const [library, setLibrary] = useState<VariantRow[]>([]);
  const [shown, setShown] = useState<Record<string, VariantShown>>({});
  const [unread, setUnread] = useState<Record<string, string>>({});
  const [again, setAgain] = useState(0);
  const [launched, setLaunched] = useState<LaunchedCampaign[]>([]);
  const [card, setCard] = useState<CampaignCard>(FRESH);
  const [estimate, setEstimate] = useState<CampaignEstimate | null>(null);
  const [screen, setScreen] = useState<CampaignScreen | null>(null);
  const [screening, setScreening] = useState(false);
  const [going, setGoing] = useState<string | null>(null);
  const [started, setStarted] = useState<Started | null>(null);
  const [alone, setAlone] = useState<Alone[]>([]);
  const [progress, setProgress] = useState<(GoProgress & { repaired?: number }) | null>(null);
  const [kept, setKept] = useState(0);
  const [finished, setFinished] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [stamp, setStamp] = useState(0);

  useEffect(() => {
    setPipeline(null);
    setLibrary([]);
    setShown({});
    setUnread({});
    setLaunched([]);
    setCard(FRESH);
    setEstimate(null);
    setScreen(null);
    setStarted(null);
    setFinished(null);
    setProblem(null);
  }, [project]);

  useEffect(() => {
    if (!active || !project || going !== null) return;
    let live = true;
    Promise.all([api.campaign(), api.variants(), api.campaigns()])
      .then(([found, listed, runs]) => {
        if (!live) return;
        setPipeline(found);
        setLibrary(listed.variants);
        setLaunched(runs);
        // A variant since taken out of the library is out of the card too.
        const ids = new Set(listed.variants.map((v) => v.id));
        setCard((was) => ({ ...was, variants: was.variants.filter((id) => ids.has(id)) }));
        setShown({});
      })
      .catch((caught) => live && setProblem(plain(caught)));
    return () => {
      live = false;
    };
  }, [active, project, going, stamp]);

  // Each variant chosen, read in full once: what it may vary and every rule it holds - or why it
  // could not be, beside it, to try again.
  useEffect(() => {
    const missing = card.variants.filter((id) => !shown[id]);
    if (!missing.length) {
      setUnread({});
      return;
    }
    let live = true;
    void Promise.allSettled(missing.map((id) => api.variant(id))).then((found) => {
      if (!live) return;
      const read: Record<string, VariantShown> = {};
      const failed: Record<string, string> = {};
      found.forEach((result, i) => {
        if (result.status === "fulfilled") read[missing[i]] = result.value;
        else failed[missing[i]] = plain(result.reason);
      });
      setUnread(failed);
      if (Object.keys(read).length) setShown((was) => ({ ...was, ...read }));
    });
    return () => {
      live = false;
    };
  }, [card.variants, shown, again]);

  // How many designs the card's variants allow, counted again as the card changes.
  useEffect(() => {
    setScreen(null);
    if (!card.variants.length) {
      setEstimate(null);
      return;
    }
    let live = true;
    const timer = window.setTimeout(() => {
      api
        .estimateCampaign(card)
        .then((found) => live && setEstimate(found))
        .catch((caught) => live && setProblem(plain(caught)));
    }, 250);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [card]);

  const update = useCallback((change: Partial<CampaignCard>) => {
    setCard((was) => ({ ...was, ...change }));
  }, []);

  const toggleVariant = useCallback((id: string) => {
    setCard((was) => ({
      ...was,
      variants: was.variants.includes(id)
        ? was.variants.filter((x) => x !== id)
        : [...was.variants, id],
    }));
  }, []);

  const toggleCheck = useCallback((name: string) => {
    setCard((was) => ({
      ...was,
      checks_off: was.checks_off.includes(name)
        ? was.checks_off.filter((x) => x !== name)
        : [...was.checks_off, name],
    }));
  }, []);

  const runScreen = useCallback(async () => {
    setScreening(true);
    setProblem(null);
    try {
      setScreen(await api.screenCampaign(card));
    } catch (caught) {
      setProblem(plain(caught));
    } finally {
      setScreening(false);
    }
  }, [card]);

  const launch = useCallback(async () => {
    setProblem(null);
    setStarted(null);
    setAlone([]);
    setProgress(null);
    setKept(0);
    setFinished(null);
    setGoing("Each variant alone first: points of it placed, repaired and screened.");
    let made = 0;
    const ended: { run: string | null; failed: boolean } = { run: null, failed: false };
    try {
      await api.launch(card, (event) => {
        if (event.type === "started") {
          ended.run = event.run;
          setStarted(event);
        } else if (event.type === "variant") {
          setAlone((was) => [...was, event]);
          setGoing(
            `${event.label} alone: ${event.kept} of ${event.tried} points pass. Then designs, ` +
              "each a set of the variants.",
          );
        } else if (event.type === "design") {
          made += 1;
          if (made % 5 === 0) setKept(made);
        } else if (event.type === "progress" || event.type === "done") {
          setProgress(event);
          setKept(made);
          if (event.type === "progress") {
            setGoing(`${made.toLocaleString()} designs kept of ${event.tried.toLocaleString()} tried.`);
          }
        } else if (event.type === "error") {
          ended.failed = true;
          setProblem(event.message);
        }
      });
      setKept(made);
      if (ended.run && !ended.failed) setFinished(ended.run);
    } catch (caught) {
      setProblem(plain(caught));
    } finally {
      setGoing(null);
    }
  }, [card]);

  const refresh = useCallback(() => setStamp((n) => n + 1), []);
  const readAgain = useCallback(() => {
    setUnread({});
    setAgain((n) => n + 1);
  }, []);

  return {
    pipeline,
    library,
    shown,
    unread,
    readAgain,
    card,
    update,
    toggleVariant,
    toggleCheck,
    estimate,
    screen,
    screening,
    runScreen,
    going,
    started,
    alone,
    progress,
    kept,
    finished,
    problem,
    launch,
    launched,
    refresh,
  };
}

/** The card, in three steps: compose, check, sample and launch. */
export function CampaignCardView(props: {
  campaign: Campaign;
  onOpenCard: () => void;
  onOpenRun: (run: string) => void;
}) {
  const c = props.campaign;
  const chosen = c.card.variants;
  const suggested = chosen.map((id) => c.library.find((v) => v.id === id)?.label ?? id).join(" + ");
  if (!c.pipeline) {
    return (
      <div className="campaign-card">
        <p className="card-note">{c.problem ?? "Reading the pipeline…"}</p>
      </div>
    );
  }
  return (
    <div className="campaign-card">
      <header className="campaign-card-head">
        <h1>Launch a campaign</h1>
        <p className="dim">Choose variants, check what holds, then sample and launch.</p>
      </header>
      <div className="campaign-steps">
        <section className="campaign-step">
          <h2>
            <span className="step-number">1</span> Compose
          </h2>
          <label className="campaign-name">
            <span className="dim">name</span>
            <input
              value={c.card.name}
              placeholder={suggested || "what this campaign is for"}
              disabled={c.going !== null}
              onChange={(e) => c.update({ name: e.target.value })}
              aria-label="the campaign's name"
            />
          </label>
          <div className="step-sub">variants</div>
          {!c.library.length ? (
            <div className="card-note">
              No variants yet. Author them on{" "}
              <button className="link" onClick={props.onOpenCard}>
                CAD → Design a variant
              </button>
              : one change in one place, with what it may vary.
            </div>
          ) : null}
          {c.library.map((variant) => (
            <label key={variant.id} className="variant-choice" data-on={chosen.includes(variant.id)}>
              <input
                type="checkbox"
                checked={chosen.includes(variant.id)}
                disabled={c.going !== null}
                onChange={() => c.toggleVariant(variant.id)}
              />
              <span className="mono">{variant.id}</span>
              <b>{variant.label}</b>
              <span className="tag">{variant.kind}</span>
              <span className="dim">{designsSaid(variant.combinations)}</span>
            </label>
          ))}
          {c.library.length ? (
            <button className="link" onClick={props.onOpenCard}>
              author or change a variant on CAD
            </button>
          ) : null}
        </section>

        <section className="campaign-step" data-waiting={!chosen.length}>
          <h2>
            <span className="step-number">2</span> Check
          </h2>
          {!chosen.length ? (
            <div className="card-note">Choose variants first: what they must hold is here.</div>
          ) : (
            <CheckStep campaign={c} />
          )}
        </section>

        <section className="campaign-step" data-waiting={!chosen.length}>
          <h2>
            <span className="step-number">3</span> Sample &amp; launch
          </h2>
          {!chosen.length ? (
            <div className="card-note">Choose variants first.</div>
          ) : (
            <LaunchStep campaign={c} onOpenRun={props.onOpenRun} />
          )}
        </section>
      </div>
    </div>
  );
}

/** What must hold, at a glance: what each variant varies and the rules it holds, what holds always,
 * the screening checks - each to switch off for this campaign - and the checks a built field goes
 * through. Every item is a few words; its full rule shows on hover. */
function CheckStep({ campaign: c }: { campaign: Campaign }) {
  const pipeline = c.pipeline as CampaignPipeline;
  const locked = c.going !== null;
  const on = pipeline.checks.filter((check) => !c.card.checks_off.includes(check.name)).length;
  return (
    <>
      <div className="step-sub">each variant</div>
      {c.card.variants.map((id) => (
        <VariantHeld key={id} id={id} campaign={c} />
      ))}

      <div className="step-sub">always</div>
      <ul className="held-always">
        <li>Holes keep a ligament of metal from every variant's ribs</li>
        <li>Ribs of different variants keep the root gap between them</li>
        <li>The part's holes, bores and drawing features stay {pipeline.interfaces_clear_mm} mm clear</li>
        <li title={pipeline.repair.says}>Clashes repaired by CP-SAT - the fewest pieces left out</li>
      </ul>

      <div className="step-sub">
        screening · {on} of {pipeline.checks.length} on
      </div>
      <div className="check-pills">
        {pipeline.checks.map((check) => {
          const off = c.card.checks_off.includes(check.name);
          return (
            <button
              key={check.name}
              className="check-pill"
              data-off={off}
              aria-pressed={!off}
              disabled={locked}
              onClick={() => c.toggleCheck(check.name)}
              title={`${check.rule}. Click to switch it ${off ? "on" : "off"} for this campaign.`}
            >
              {check.name}
            </button>
          );
        })}
      </div>
      <details className="field-checks">
        <summary>{pipeline.full_checks.length} more checks when a design's field is built</summary>
        <div className="check-pills">
          {pipeline.full_checks.map((check) => (
            <span key={check.name} className="check-pill fixed" title={check.rule}>
              {check.name}
            </span>
          ))}
        </div>
        <div className="dim">Mould release waits for the pull direction, which variants do not hold yet.</div>
      </details>
      <div className="dim held-hint">Hover any item for its rule in full.</div>
    </>
  );
}

/** One variant at a glance: what it varies and the rules it holds, a pill each - its full words on
 * hover - or why it could not be read, to try again. */
function VariantHeld({ id, campaign: c }: { id: string; campaign: Campaign }) {
  const variant = c.shown[id];
  const label = variant?.label ?? c.library.find((v) => v.id === id)?.label ?? id;
  const head = (
    <div className="variant-held-head">
      <span className="mono">{id}</span> <b>{label}</b>
      {variant ? <span className="tag">{variant.kind}</span> : null}
    </div>
  );
  if (!variant) {
    const why = c.unread[id];
    return (
      <div className="variant-held">
        {head}
        {why ? (
          <div className="card-note warn">
            Could not read it: {why}.{" "}
            <button className="link" onClick={c.readAgain}>
              try again
            </button>
          </div>
        ) : (
          <div className="dim">reading…</div>
        )}
      </div>
    );
  }
  const block = variant.block;
  const generator = block.settings.find((s) => s.name === "generator");
  const patterns = (generator?.domain.options ?? []).map(String);
  const varies = block.settings.filter((s) => !s.hidden && !s.fixed && matters(s.name, patterns));
  const rules = [...block.keep_clear, ...block.rules].filter((rule) => rule.enforced);
  return (
    <div className="variant-held">
      {head}
      <div className="held-line">
        <span className="held-what">varies</span>
        {varies.length ? (
          varies.map((s) => (
            <span key={s.name} className="held-pill" title={`${s.label}: ${s.says}`}>
              {s.label} <b>{brief(s)}</b>
            </span>
          ))
        ) : (
          <span className="dim">nothing - one design</span>
        )}
      </div>
      <div className="held-line">
        <span className="held-what">rules</span>
        {rules.length ? (
          rules.map((rule) => (
            <span
              key={rule.id}
              className="held-pill rule"
              data-strength={rule.strength}
              title={`${rule.says} - ${rule.strength}${rule.source ? `, from ${rule.source}` : ""}`}
            >
              {rule.says}
            </span>
          ))
        ) : (
          <span className="dim">none of its own</span>
        )}
      </div>
    </div>
  );
}

/** What a setting may take, in a few characters: 2–10, 15–25 mm, square grid · spokes, 3 choices. */
function brief(s: StudySetting): string {
  const d = s.domain;
  const unit = s.percent ? " %" : d.unit === "°" ? "°" : d.unit ? ` ${d.unit}` : "";
  const value = (v: unknown) => (s.percent ? String(Math.round(Number(v) * 100)) : String(v));
  if (d.options) {
    if (s.name === "generator") return d.options.map((p) => PATTERN_NAMES[String(p)] ?? String(p)).join(" · ");
    return d.options.length <= 3 ? `${d.options.map(value).join(" · ")}${unit}` : `${d.options.length} choices`;
  }
  // A dash after a minus sign reads as another minus: a range below zero says "to".
  const dash = Number(d.low) < 0 ? " to " : "–";
  return `${value(d.low)}${dash}${value(d.high)}${unit}`;
}

/** How designs are drawn, how many, from which seed; the count; a hundred screened; the launch,
 * and what it came to. */
function LaunchStep({ campaign: c, onOpenRun }: { campaign: Campaign; onOpenRun: (run: string) => void }) {
  const pipeline = c.pipeline as CampaignPipeline;
  const locked = c.going !== null;
  const every = Boolean(c.estimate?.every);
  const rejected = Object.entries(c.progress?.rejected ?? {}).sort((a, b) => b[1] - a[1]);
  const screened = c.screen;
  const screenedOut = Object.entries(screened?.rejected ?? {}).sort((a, b) => b[1] - a[1]);
  const [nText, setNText] = useState(String(c.card.n));
  const [seedText, setSeedText] = useState(String(c.card.seed));
  useEffect(() => setNText(String(c.card.n)), [c.card.n]);
  useEffect(() => setSeedText(String(c.card.seed)), [c.card.seed]);
  const blocked = useMemo(
    () => locked || (c.card.method === "every" && !every),
    [locked, c.card.method, every],
  );
  return (
    <>
      <div className="step-sub">how designs are drawn</div>
      {pipeline.methods.map((method) => {
        const off = method.key === "every" && !every;
        return (
          <label key={method.key} className="method-row" data-off={off}>
            <input
              type="radio"
              name="method"
              checked={c.card.method === method.key}
              disabled={locked || off}
              onChange={() => c.update({ method: method.key })}
            />
            <b>{method.label}</b> <span className="dim">{method.says}</span>
          </label>
        );
      })}
      <div className="launch-line">
        <label>
          designs to keep{" "}
          <input
            className="num"
            value={nText}
            disabled={locked}
            onChange={(e) => {
              setNText(e.target.value);
              const n = Number(e.target.value);
              if (Number.isInteger(n) && n >= 1 && n <= 20000) c.update({ n });
            }}
            aria-label="designs to keep"
          />
        </label>
        <label>
          seed{" "}
          <input
            className="num"
            value={seedText}
            disabled={locked}
            onChange={(e) => {
              setSeedText(e.target.value);
              const seed = Number(e.target.value);
              if (Number.isInteger(seed) && seed >= 0) c.update({ seed });
            }}
            aria-label="seed"
          />
        </label>
      </div>
      <label className="method-row">
        <input
          type="checkbox"
          checked={c.card.diverse >= 2}
          disabled={locked}
          onChange={(e) => c.update({ diverse: e.target.checked ? 2 : 0 })}
        />
        <b>keep the most different</b>
        <span className="dim"> of </span>
        <select
          value={Math.max(c.card.diverse, 2)}
          disabled={locked || c.card.diverse < 2}
          onChange={(e) => c.update({ diverse: Number(e.target.value) })}
          aria-label="how many times as many to draw"
        >
          {[2, 3, 4, 5].map((k) => (
            <option key={k} value={k}>
              {k} times as many
            </option>
          ))}
        </select>
        <span className="dim"> drawn - placing takes as many times as long</span>
      </label>

      <div className="step-sub">how many</div>
      <div className="estimate-line">
        {c.estimate
          ? c.estimate.count === null
            ? "The variants allow no end of designs - free layouts among them."
            : `The variants allow ${c.estimate.count.toLocaleString()} designs: every set of them at every point of each.`
          : "Counting…"}
      </div>
      <div className="actions">
        <button onClick={() => void c.runScreen()} disabled={locked || c.screening}>
          {c.screening ? "Screening…" : "Screen 100"}
        </button>
      </div>
      {screened ? (
        <div className="screen-said">
          <b>{screened.passed}</b> of {screened.tried} pass
          {screened.repaired ? ` - ${screened.repaired} of them after repair` : ""} ·{" "}
          {screened.seconds_per_design} s a design
          {screenedOut.length
            ? ` · the rest: ${screenedOut.map(([why, n]) => `${why} ${n}`).join(", ")}`
            : ""}
          <div className="dim">
            {c.card.n.toLocaleString()} designs would take about {durationSaid(screened.estimate_seconds)}.
          </div>
        </div>
      ) : null}

      <div className="actions launch-actions">
        <button
          className="primary"
          onClick={() => void c.launch()}
          disabled={blocked}
          title="Make the designs: each variant pooled alone, then designs drawn together, repaired, screened and kept"
        >
          {c.going ? "Running…" : `Launch ${c.card.n.toLocaleString()} designs`}
        </button>
      </div>

      {c.going || c.started || c.problem ? (
        <div className="go-designs">
          {c.started ? (
            <div className="dim">
              campaign <b className="mono">{c.started.run}</b>
            </div>
          ) : null}
          {c.going ? <div className="card-note busy-note">{c.going}</div> : null}
          {c.alone.map((a) => (
            <div key={a.variant} className="dim">
              {a.label} alone: {a.kept} of {a.tried} points pass
              {Object.keys(a.rejected).length
                ? ` - the rest: ${Object.entries(a.rejected)
                    .map(([why, n]) => `${why} ${n}`)
                    .join(", ")}`
                : ""}
            </div>
          ))}
          {c.progress ? (
            <div className="go-progress">
              <b>{c.kept.toLocaleString()}</b> kept of {c.progress.tried.toLocaleString()} tried in{" "}
              {c.progress.seconds} s
              {c.progress.repaired ? ` · ${c.progress.repaired} repaired` : ""}
              {rejected.length
                ? ` - not kept: ${rejected.map(([why, n]) => `${why} ${n}`).join(", ")}`
                : ""}
            </div>
          ) : null}
          {c.finished && !c.going ? (
            <div className="actions">
              <button onClick={() => onOpenRun(c.finished as string)}>Open its designs</button>
            </div>
          ) : null}
          {c.problem ? <div className="card-note warn">{c.problem}</div> : null}
        </div>
      ) : null}
    </>
  );
}

/** Every campaign launched for the project, newest first - each chosen to watch its designs
 * solved, or the card to compose another. */
export function CampaignRuns(props: {
  launched: LaunchedCampaign[];
  going: string | null;
  onOpenRun: (run: string) => void;
  selected?: string | null;
  onNew?: () => void;
}) {
  return (
    <nav className="index">
      <section className="section">
        <header>
          Campaigns <span className="count">{props.launched.length}</span>
        </header>
        {props.onNew ? (
          <div className="body">
            <button data-active={!props.selected} onClick={props.onNew}>
              New campaign
            </button>
          </div>
        ) : null}
        {props.going ? <div className="body card-note busy-note">A campaign is running.</div> : null}
        {!props.launched.length ? (
          <div className="body card-note">
            No campaign launched yet. Compose one on the card: its designs are kept in
            _archived_designs beside the project.
          </div>
        ) : null}
        {props.launched.map((run) => (
          <button
            key={run.run}
            className="row run-row"
            data-selected={props.selected === run.run}
            onClick={() => props.onOpenRun(run.run)}
            disabled={run.state !== "done"}
            title={run.state === "done" ? "Its designs, solved" : "It did not finish"}
          >
            <span className="run-name" title={run.name}>
              <span className="mono dim">{run.id}</span> <b>{run.name}</b>
            </span>
            <span className="run-detail">
              {run.state === "done"
                ? `${(run.made ?? 0).toLocaleString()} designs of ${(run.tried ?? 0).toLocaleString()} tried · ${durationSaid(run.seconds ?? 0)}`
                : "unfinished"}
              {run.built ? ` · ${run.built} built` : ""}
            </span>
            <span className="run-detail dim" title={run.variants.map((v) => v.label).join("\n")}>
              {run.variants.length} variant{run.variants.length === 1 ? "" : "s"} · {run.card.method}
            </span>
          </button>
        ))}
      </section>
    </nav>
  );
}

function designsSaid(count: number | null): string {
  return count === null ? "no end of designs" : `${count.toLocaleString()} designs`;
}

function durationSaid(seconds: number): string {
  if (seconds < 90) return `${Math.max(1, Math.round(seconds))} s`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} min`;
  return `${(seconds / 3600).toFixed(1)} h`;
}
