/**
 * The study card: the one structured view of the study - the draft of its next version.
 *
 * Every block says what it adds, what its ribs stand on, what they end on and what they keep clear
 * of - each a set of the part's named entities, or another block's ribs, as chips that show them on
 * the part - then its settings, fixed or what they may vary over and who said so, and its rules.
 * Blocks grow and entities are added as the engineer says more; what the draft changes is marked,
 * nothing is written until they accept it, and Undo reads the study back. What a block still needs,
 * and what cannot be built yet, stays on it.
 *
 * Go makes many designs from the study at once: each is listed, drawn on the part at a click, and
 * any one made into a design.
 */

import { Fragment, useCallback, useEffect, useState } from "react";
import type {
  CardPaths,
  GoDesign,
  StudyBlockView,
  StudyDraft,
  StudyEntities,
  StudyRule,
  StudySetting,
  Verdict,
  VerdictRow,
} from "../api/client";
import { api } from "../api/client";
import type { LineSet } from "../render/renderer";
import { PathsKey, Said, toLines } from "./shared";

interface StudyCardProps {
  /** The project the study is about. A new one starts the pane afresh. */
  project: string | null;
  /** Read the draft again when this changes: the agent changed it. */
  refresh: number;
  /** Show these faces and features on the part. */
  onShow: (refs: string[]) => void;
  /** A design was made from the study. */
  onDesign: (verdict: Verdict) => void;
  /** The study has a new version. */
  onStudyChanged: () => void;
  /** Draw these lines on the part - where ribs would go - or none. */
  onPaths: (lines: LineSet | null) => void;
}

const SOURCE: Record<string, string> = {
  you: "you",
  selected: "selected",
  words: "your words",
  drawing: "drawing",
  measured: "measured",
  default: "default",
  cad: "the part",
  rejection: "rejection",
};

/** How many entities a row lists before the rest fold away. */
const FOLD = 8;
/** How many designs Go makes at a press. */
const GO = 24;

export function StudyCard(props: StudyCardProps) {
  const { project, refresh, onShow, onDesign, onStudyChanged, onPaths } = props;
  const [draft, setDraft] = useState<StudyDraft | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [designs, setDesigns] = useState<GoDesign[]>([]);
  const [going, setGoing] = useState<string | null>(null);
  // What is drawn on the part: the draft's suggested design, or one Go made.
  const [drawn, setDrawn] = useState<number | "draft" | null>(null);
  const [paths, setPaths] = useState<CardPaths | null>(null);
  const [pathsNote, setPathsNote] = useState<string | null>(null);

  useEffect(() => {
    setDraft(null);
    setVerdict(null);
    setDesigns([]);
    setDrawn(null);
    setProblem(null);
  }, [project]);

  useEffect(() => {
    if (!project) return;
    api
      .studyDraft()
      .then((reply) => setDraft(reply.draft))
      .catch((caught) => setProblem(plain(caught)));
  }, [project, refresh]);

  // Where ribs would go, drawn on the part: redrawn as the draft changes.
  useEffect(() => {
    if (drawn === null) {
      onPaths(null);
      setPaths(null);
      setPathsNote(null);
      return;
    }
    let live = true;
    setPathsNote("Placing the ribs to draw them: seconds, or about 2 minutes the first time.");
    const which = drawn === "draft" ? {} : { design: drawn };
    api
      .studyPaths(which)
      .then((reply) => {
        if (!live) return;
        setPaths(reply);
        setPathsNote(null);
        onPaths(toLines(reply));
      })
      .catch((caught) => live && setPathsNote(plain(caught)));
    return () => {
      live = false;
    };
  }, [drawn, draft, onPaths]);

  useEffect(() => () => onPaths(null), [onPaths]);

  const run = useCallback(async (label: string, action: () => Promise<void>) => {
    setBusy(label);
    setProblem(null);
    try {
      await action();
    } catch (caught) {
      setProblem(plain(caught));
    } finally {
      setBusy(null);
    }
  }, []);

  const accept = useCallback(
    () =>
      run("Writing the study.", async () => {
        setDraft((await api.acceptStudy()).draft);
        onStudyChanged();
      }),
    [run, onStudyChanged],
  );

  const undo = useCallback(
    () => run("Reading the study back.", async () => setDraft((await api.undoStudy()).draft)),
    [run],
  );

  const drop = useCallback(
    (id: string) =>
      run("Taking it out.", async () => setDraft((await api.dropRule(id)).draft)),
    [run],
  );

  const make = useCallback(
    (fidelity: "preview" | "full", design?: number) =>
      run(
        fidelity === "preview"
          ? "Making a preview: placing the ribs, joining them, checking."
          : "Making the full design. Minutes on a large part the first time.",
        async () => {
          const made = await api.studyDesign(fidelity, design);
          setVerdict(made);
          setDraft((await api.studyDraft()).draft);
          onDesign(made);
          onStudyChanged();
        },
      ),
    [run, onDesign, onStudyChanged],
  );

  const goNow = useCallback(async () => {
    setDesigns([]);
    setDrawn(null);
    setProblem(null);
    setGoing("Accepting the study and placing its designs.");
    try {
      await api.go(GO, (event) => {
        if (event.type === "accepted") onStudyChanged();
        else if (event.type === "started")
          setGoing(`Placing ${event.n} designs from study v${event.version}.`);
        else if (event.type === "design") setDesigns((was) => [...was, event]);
        else if (event.type === "error") setProblem(event.message);
      });
      setDraft((await api.studyDraft()).draft);
    } catch (caught) {
      setProblem(plain(caught));
    } finally {
      setGoing(null);
    }
  }, [onStudyChanged]);

  if (!project) {
    return (
      <div className="rib-card">
        <div className="card-note">Open a project to add ribs to it.</div>
      </div>
    );
  }

  const refused = Boolean(draft?.refused);
  const blocks = draft?.blocks ?? [];
  const waiting = blocks.some((b) => b.needed.length || b.problems.length);
  const buildable = blocks.some((b) => !b.cannot && !b.needed.length && !b.problems.length);

  return (
    <div className="rib-card study-card">
      <header className="rib-card-head">
        <span className="card-title">Study</span>
        {draft ? <VersionChip draft={draft} /> : null}
      </header>

      {draft && (draft.differs || refused) ? (
        <DraftBar
          draft={draft}
          disabled={busy !== null || going !== null}
          onAccept={accept}
          onUndo={undo}
          onShow={onShow}
        />
      ) : null}

      <div className="rib-slots">
        {!blocks.length && !refused ? (
          <div className="card-note">
            Nothing asked for yet. Say what you want in the rail - where, between what, clear of
            what - with faces selected on the part if you like. Each thing asked for becomes a block
            here, in the part's named entities; what you leave open is read off the part.
          </div>
        ) : null}
        {blocks.map((block) => (
          <BlockView
            key={block.id}
            block={block}
            names={draft?.names ?? {}}
            disabled={busy !== null}
            onDrop={drop}
            onShow={onShow}
          />
        ))}
        {draft ? (
          <StudyRest draft={draft} disabled={busy !== null} onDrop={drop} onShow={onShow} />
        ) : null}
        {designs.length || going ? (
          <Designs
            designs={designs}
            going={going}
            drawn={drawn}
            disabled={busy !== null}
            onDraw={(index) => setDrawn((was) => (was === index ? null : index))}
            onMake={(index) => make("preview", index)}
          />
        ) : null}
      </div>

      {problem ? <div className="card-note warn">{problem}</div> : null}

      <footer className="rib-card-foot">
        <div className="rib-card-status" data-ready={buildable && !waiting}>
          {refused
            ? "the draft cannot be written"
            : !blocks.length
              ? "nothing to make yet"
              : waiting
                ? "something is needed - see the block"
                : buildable
                  ? "ready to make ribs"
                  : "nothing here can be built yet"}
        </div>
        <div className="actions">
          <button
            data-active={drawn === "draft"}
            onClick={() => setDrawn((was) => (was === "draft" ? null : "draft"))}
            disabled={(!buildable || refused) && drawn !== "draft"}
            title="Draw where the suggested design would put ribs, before anything is made"
          >
            {drawn === "draft" ? "Hide paths" : "Show paths"}
          </button>
          <button
            onClick={() => void goNow()}
            disabled={!buildable || refused || busy !== null || going !== null}
            title={`Accept the study if it changed, and place ${GO} designs spread over what it leaves free`}
          >
            Go
          </button>
          <button
            onClick={() => make("preview")}
            disabled={!buildable || refused || busy !== null || going !== null}
            title="Accept the study if it changed, and make its suggested design on a coarse grid"
          >
            Preview
          </button>
          <button
            onClick={() => make("full")}
            disabled={!buildable || refused || busy !== null || going !== null}
            title="The same design at full resolution - what a design is accepted at"
          >
            Full
          </button>
        </div>
        {drawn !== null ? <PathsKey paths={paths} note={pathsNote} /> : null}
        {busy ? <div className="card-note busy-note">{busy}</div> : null}
        {verdict && !busy ? <VerdictView verdict={verdict} /> : null}
      </footer>
    </div>
  );
}

/** Where the draft stands against the study: the version it was read from, or that it has none. */
function VersionChip({ draft }: { draft: StudyDraft }) {
  if (draft.accepted === null) {
    return <span className="chip draft-chip">no study yet</span>;
  }
  if (draft.differs === null) {
    return (
      <span className="chip draft-chip" title={draft.cannot ?? undefined}>
        cannot be written
      </span>
    );
  }
  return (
    <span className="chip draft-chip" data-differs={Boolean(draft.differs)}>
      {draft.differs ? `changed from v${draft.accepted}` : `study v${draft.accepted}`}
    </span>
  );
}

/** The draft, waiting for the engineer: what it changes, and Accept or Undo - or why a check
 * refused it. */
function DraftBar(props: {
  draft: StudyDraft;
  disabled: boolean;
  onAccept: () => void;
  onUndo: () => void;
  onShow: (refs: string[]) => void;
}) {
  const { draft } = props;
  const refused = draft.refused;
  return (
    <div className="draft-bar" data-refused={refused}>
      <div className="draft-line">
        {refused ? (
          <>
            The draft cannot be written: <Said text={draft.cannot ?? ""} onShow={props.onShow} />
          </>
        ) : draft.accepted === null ? (
          "Not written yet: accepting makes it the study's first version."
        ) : (
          "Marked below: not written until accepted."
        )}
      </div>
      {!refused && draft.changes.length && draft.accepted !== null ? (
        <details className="study-fold">
          <summary>What changes ({draft.changes.length})</summary>
          <ul className="study-lines">
            {draft.changes.map((line) => (
              <li key={line}>
                <Said text={line} onShow={props.onShow} />
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      <div className="actions">
        {!refused ? (
          <button onClick={props.onAccept} disabled={props.disabled}>
            Accept as v{(draft.accepted ?? 0) + 1}
          </button>
        ) : null}
        {draft.accepted !== null || refused ? (
          <button onClick={props.onUndo} disabled={props.disabled}>
            Undo
          </button>
        ) : null}
      </div>
    </div>
  );
}

/** One block: what it adds; what its ribs stand on, end on and keep clear of, as entities; its
 * settings and rules; and anything it needs or waits for. */
function BlockView(props: {
  block: StudyBlockView;
  names: Record<string, string>;
  disabled: boolean;
  onDrop: (id: string) => void;
  onShow: (refs: string[]) => void;
}) {
  const { block, names, onShow } = props;
  return (
    <section className="rib-slot study-block" data-changed={block.changed}>
      <header>
        <span className="slot-label">
          {block.id} · add {block.add}
        </span>
      </header>
      <dl className="kv compact block-where">
        <dt>stand on</dt>
        <dd data-changed={block.stand_on.changed}>
          {!block.stand_on.refs.length && block.note.webs ? (
            <span className="dim">
              nothing - webs that <Said text={block.note.webs} names={names} onShow={onShow} />
            </span>
          ) : (
            <EntityChips group={block.stand_on} names={names} onShow={onShow} none="nothing - they hang" />
          )}
        </dd>
        <dt>end on</dt>
        <dd data-changed={block.end_on.changed}>
          <EntityChips group={block.end_on} names={names} onShow={onShow} none="nothing named" />
        </dd>
        {block.keep_clear.length ? (
          <>
            <dt>keep clear</dt>
            <dd>
              {block.keep_clear.map((rule) => (
                <KeepClear
                  key={rule.id}
                  rule={rule}
                  names={names}
                  disabled={props.disabled}
                  onDrop={props.onDrop}
                  onShow={onShow}
                />
              ))}
            </dd>
          </>
        ) : null}
      </dl>
      <div className="slot-study">
        {block.settings.map((setting) => (
          <SettingLine key={setting.name} setting={setting} names={names} onShow={onShow} />
        ))}
        {block.rules.map((rule) => (
          <RuleLine
            key={rule.id}
            rule={rule}
            names={names}
            disabled={props.disabled}
            onDrop={props.onDrop}
            onShow={onShow}
          />
        ))}
      </div>
      {block.needed.map((what) => (
        <div key={what} className="slot-problem">
          needed: {what} - only you can say
        </div>
      ))}
      {block.problems.map((what) => (
        <div key={what} className="slot-problem">
          <Said text={what} names={names} onShow={onShow} />
        </div>
      ))}
      {block.cannot ? <div className="slot-note waits">{block.cannot}</div> : null}
    </section>
  );
}

/** Entities as chips: a click shows one on the part; many fold; read off the part says so. */
function EntityChips(props: {
  group: StudyEntities;
  names: Record<string, string>;
  onShow: (refs: string[]) => void;
  none: string;
}) {
  const { group } = props;
  const [open, setOpen] = useState(false);
  if (!group.refs.length) return <span className="dim">{props.none}</span>;
  const shown = open ? group.refs : group.refs.slice(0, FOLD);
  return (
    <span className="refs">
      {shown.map((ref) => (
        <Chip key={ref} ref_={ref} names={props.names} onShow={props.onShow} />
      ))}
      {group.refs.length > FOLD ? (
        <button className="link" onClick={() => setOpen((was) => !was)}>
          {open ? "fewer" : `+${group.refs.length - FOLD} more`}
        </button>
      ) : null}
      {group.refs.length > 1 ? (
        <button className="link" onClick={() => props.onShow(group.refs)} title="Show them all">
          show
        </button>
      ) : null}
      {group.read_off ? <span className="tag">read off the part</span> : null}
    </span>
  );
}

/** One entity. Another block's ribs are named like any entity, but are not on the part. */
function Chip(props: { ref_: string; names: Record<string, string>; onShow: (refs: string[]) => void }) {
  const ref = props.ref_;
  if (ref.startsWith("ribs:")) {
    return (
      <span className="ref-chip ribs-chip" title={`the ribs of ${ref.slice(5)}`}>
        <span>{ref}</span>
      </span>
    );
  }
  return (
    <span className="ref-chip">
      <button onClick={() => props.onShow([ref])} title={props.names[ref] ?? ref}>
        {ref}
      </button>
    </span>
  );
}

/** A keep-clear rule: how far, from what - each entity a chip - and whose rule it is. */
function KeepClear(props: {
  rule: StudyRule;
  names: Record<string, string>;
  disabled: boolean;
  onDrop: (id: string) => void;
  onShow: (refs: string[]) => void;
}) {
  const { rule } = props;
  const clearance = Number(rule.params.clearance_mm ?? 0);
  return (
    <div className="keep-clear" data-changed={rule.changed} title={rule.basis || undefined}>
      <span className="chip" data-strength={rule.strength}>
        {rule.strength}
      </span>
      <EntityChips
        group={{ refs: rule.refs, read_off: false }}
        names={props.names}
        onShow={props.onShow}
        none="nothing"
      />
      <span className="dim">
        {" "}
        · {clearance ? `${clearance} mm clear` : "not crossing"} · {whose(rule)}
      </span>
      {rule.by !== "platform" ? (
        <button
          className="icon"
          disabled={props.disabled}
          onClick={() => props.onDrop(rule.id)}
          title="Take this out"
        >
          ×
        </button>
      ) : null}
    </div>
  );
}

function SettingLine(props: {
  setting: StudySetting;
  names: Record<string, string>;
  onShow: (refs: string[]) => void;
}) {
  const { setting } = props;
  return (
    <div className="study-setting" data-changed={setting.changed} title={setting.basis || undefined}>
      <span className="tag" data-fixed={setting.fixed}>
        {setting.fixed ? "fixed" : "varies"}
      </span>
      <span className="setting-label">{setting.label}</span>{" "}
      <Said text={setting.says} names={props.names} onShow={props.onShow} />
      <span className="dim"> · {SOURCE[setting.source] ?? setting.source}</span>
    </div>
  );
}

/** A rule: how firmly it holds, in words with its entities as chips, whose it is, and - when
 * nothing enforces it yet - until when. */
function RuleLine(props: {
  rule: StudyRule;
  names: Record<string, string>;
  disabled?: boolean;
  onDrop?: (id: string) => void;
  onShow: (refs: string[]) => void;
}) {
  const { rule } = props;
  return (
    <div className="study-rule" data-enforced={rule.enforced} data-changed={rule.changed}>
      <span className="chip" data-strength={rule.strength}>
        {rule.strength}
      </span>
      <Said text={rule.says} names={props.names} onShow={props.onShow} />
      <span className="dim"> · {whose(rule)}</span>
      {props.onDrop && rule.by !== "platform" ? (
        <button
          className="icon"
          disabled={props.disabled}
          onClick={() => props.onDrop?.(rule.id)}
          title="Take this out"
        >
          ×
        </button>
      ) : null}
      {rule.until ? <div className="rule-until">not enforced yet: {rule.until}</div> : null}
    </div>
  );
}

function whose(rule: StudyRule): string {
  if (rule.by === "words") return "your words";
  if (rule.by === "part") return rule.source === "drawing" ? "the drawing" : "suggested by the part";
  if (rule.by === "platform") return "the platform";
  return SOURCE[rule.source] ?? rule.source;
}

/** The rest of the study: rules for every block, what makes a design better, the pull, how many
 * designs - and the part's interfaces, closed by the platform. */
function StudyRest(props: {
  draft: StudyDraft;
  disabled: boolean;
  onDrop: (id: string) => void;
  onShow: (refs: string[]) => void;
}) {
  const { draft, onShow } = props;
  const rest = draft.rest;
  if (!rest && !draft.rules.length && !draft.interfaces.length) return null;
  return (
    <section className="rib-slot study-extra">
      {draft.rules.length ? (
        <>
          <header>
            <span className="slot-label">for every block</span>
          </header>
          <div className="study-rules">
            {draft.rules.map((rule) => (
              <RuleLine
                key={rule.id}
                rule={rule}
                names={draft.names}
                disabled={props.disabled}
                onDrop={props.onDrop}
                onShow={onShow}
              />
            ))}
          </div>
        </>
      ) : null}
      {rest ? (
        <dl className="kv compact">
          <dt>pull</dt>
          <dd title={rest.pull?.basis || undefined}>
            {rest.pull ? <Said text={rest.pull.says} onShow={onShow} /> : "not given"}
          </dd>
          <dt>designs</dt>
          <dd>{rest.target.says}</dd>
          {rest.prefer.map((item) => (
            <Fragment key={item.id}>
              <dt>prefer</dt>
              <dd>
                <Said text={item.says} onShow={onShow} />
              </dd>
            </Fragment>
          ))}
          {rest.objectives.map((item) => (
            <Fragment key={item.id}>
              <dt>better</dt>
              <dd>
                <Said text={item.says} onShow={onShow} />
                {item.physical ? <span className="dim"> · waits for simulation</span> : null}
              </dd>
            </Fragment>
          ))}
        </dl>
      ) : null}
      {draft.interfaces.length ? (
        <details className="study-fold">
          <summary>
            The part's interfaces, kept as they are ({draft.interfaces.length}) - from the part and
            the drawing
          </summary>
          <div className="study-rules">
            {draft.interfaces.map((rule) => (
              <RuleLine key={rule.id} rule={rule} names={draft.names} onShow={onShow} />
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}

/** What Go made: one row a design - how many ribs, what it is - drawn on the part at a click, and
 * made at Make. */
function Designs(props: {
  designs: GoDesign[];
  going: string | null;
  drawn: number | "draft" | null;
  disabled: boolean;
  onDraw: (index: number) => void;
  onMake: (index: number) => void;
}) {
  return (
    <section className="rib-slot go-designs">
      <header>
        <span className="slot-label">designs ({props.designs.length})</span>
      </header>
      {props.going ? <div className="card-note busy-note">{props.going}</div> : null}
      {props.designs.map((design) => (
        <div key={design.index} className="go-design" data-drawn={props.drawn === design.index}>
          <button className="link" onClick={() => props.onDraw(design.index)} title="Draw it on the part">
            #{design.index + 1} · {design.ribs} ribs
          </button>
          <span className="dim">
            {" "}
            {Object.entries(design.about)
              .map(([block, about]) => `${block}: ${about}`)
              .join(" · ")}
          </span>
          <button
            className="icon"
            disabled={props.disabled}
            onClick={() => props.onMake(design.index)}
            title="Make this design, on the preview grid"
          >
            make
          </button>
        </div>
      ))}
    </section>
  );
}

/** What the design came out as: the outcome, and whatever did not pass. */
function VerdictView({ verdict }: { verdict: Verdict }) {
  const [open, setOpen] = useState(false);
  const rows = [...verdict.constraints, ...verdict.checks];
  const shown = (row: VerdictRow) => row.outcome !== "pass" || row.check.startsWith("supports");
  const notPassed = rows.filter(shown);
  const passed = rows.filter((row) => !shown(row));
  return (
    <div className="rib-verdict">
      <div className="verdict-line">
        <span className="chip" data-outcome={verdict.outcome}>
          {verdict.outcome}
        </span>{" "}
        {verdict.ribs} ribs · +{verdict.added_cm3.toLocaleString(undefined, { maximumFractionDigits: 0 })}{" "}
        cm³ · {verdict.fidelity} · study v{verdict.study_version ?? verdict.spec_version} ·{" "}
        {verdict.seconds} s
      </div>
      {notPassed.map((row) => (
        <FindingLine key={row.check} row={row} />
      ))}
      {passed.length ? (
        <button className="link" onClick={() => setOpen((was) => !was)}>
          {open ? "hide what passed" : `${passed.length} passed`}
        </button>
      ) : null}
      {open ? passed.map((row) => <FindingLine key={row.check} row={row} />) : null}
    </div>
  );
}

function FindingLine({ row }: { row: VerdictRow }) {
  return (
    <div className="finding" data-outcome={row.outcome} title={row.rule}>
      <span className="mark">{row.outcome}</span>
      <span className="what">
        <b>{row.check}</b> {row.reason}
      </span>
    </div>
  );
}

/** An error from the server, as the sentence it carries. */
function plain(caught: unknown): string {
  const text = String(caught instanceof Error ? caught.message : caught);
  const body = text.indexOf("{");
  if (body >= 0) {
    try {
      const detail = (JSON.parse(text.slice(body)) as { detail?: unknown }).detail;
      if (typeof detail === "string") return detail;
    } catch {
      // Not JSON after all: say it as it came.
    }
  }
  return text;
}
