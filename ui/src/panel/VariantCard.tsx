/**
 * Design a variant: the design space, by hand - and one variant of it at a time, made and checked.
 *
 * The one structured view of the study - the draft of its next version. Every block says what it
 * adds, what its ribs stand on, what they end on and what they keep clear of - each a set of the
 * part's named entities, or another block's ribs, as chips that show them on the part - then its
 * settings, fixed or what they may vary over and who said so, and its rules.
 *
 * **Built by hand.** Blocks are added from the faces selected on the part - ribs standing on them,
 * webs between them, faces to thicken, a plate to cut holes in - or the material; what a block
 * stands on and ends on is taken from the selection; every setting is fixed, ranged, narrowed or
 * handed back to the part where it shows; a block keeps clear of what is selected; a rule the part
 * suggested is taken out or kept as the engineer's. Each is theirs, said in words in the study. The
 * agent above changes the same draft from what they write. What the draft changes is marked,
 * nothing is written until they accept it, and Undo reads the study back.
 *
 * One variant at a time: where its ribs would go drawn on the part, then made on the preview grid or
 * in full, and checked. Thousands at once are a campaign, on Generate - spread over what this card
 * leaves free.
 */

import { Fragment, useCallback, useEffect, useState } from "react";
import type {
  CardPaths,
  HandAction,
  StudyBlockView,
  StudyDraft,
  StudyEntities,
  StudyInfo,
  StudyRule,
  StudySetting,
  Verdict,
} from "../api/client";
import { api } from "../api/client";
import type { LineSet } from "../render/renderer";
import { PathsKey, Said, VerdictView, plain, toLines } from "./shared";

interface VariantCardProps {
  /** The project the study is about. A new one starts the pane afresh. */
  project: string | null;
  /** The faces selected on the part: what a block is added from, or takes by hand. */
  selection: number[];
  /** Read the draft again when this changes: the agent changed it. */
  refresh: number;
  /** Show these faces and features on the part. */
  onShow: (refs: string[]) => void;
  /** A variant was made from the study. */
  onDesign: (verdict: Verdict) => void;
  /** The study has a new version. */
  onStudyChanged: () => void;
  /** Draw these lines on the part - where ribs would go - or none. */
  onPaths: (lines: LineSet | null) => void;
  /** Fold the card away to the edge. */
  onCollapse: () => void;
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

export function VariantCard(props: VariantCardProps) {
  const { project, refresh, selection, onShow, onDesign, onStudyChanged, onPaths } = props;
  const [draft, setDraft] = useState<StudyDraft | null>(null);
  const [study, setStudy] = useState<StudyInfo | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  // Whether the suggested variant's paths are drawn on the part.
  const [drawn, setDrawn] = useState(false);
  const [paths, setPaths] = useState<CardPaths | null>(null);
  const [pathsNote, setPathsNote] = useState<string | null>(null);

  useEffect(() => {
    setDraft(null);
    setStudy(null);
    setVerdict(null);
    setDrawn(false);
    setProblem(null);
  }, [project]);

  useEffect(() => {
    if (!project) return;
    api
      .studyDraft()
      .then((reply) => setDraft(reply.draft))
      .catch((caught) => setProblem(plain(caught)));
  }, [project, refresh]);

  // What the study rests on - the engineer's words - and its versions: read again whenever the
  // draft is, since accepting it writes a version.
  useEffect(() => {
    if (!project) return;
    api
      .study()
      .then(setStudy)
      .catch(() => setStudy(null));
  }, [project, refresh, draft?.accepted]);

  // Where ribs would go, drawn on the part: redrawn as the draft changes.
  useEffect(() => {
    if (!drawn) {
      onPaths(null);
      setPaths(null);
      setPathsNote(null);
      return;
    }
    let live = true;
    setPathsNote("Placing the ribs to draw them: seconds, or about 2 minutes the first time.");
    api
      .studyPaths({})
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

  // Something done by hand: the draft as it now is, or why not.
  const byHand = useCallback(
    (action: HandAction) =>
      run("Changing the study.", async () =>
        setDraft((await api.handStudy({ ...action, selected: selection })).draft),
      ),
    [run, selection],
  );

  const make = useCallback(
    (fidelity: "preview" | "full") =>
      run(
        fidelity === "preview"
          ? "Making a preview: moving faces, placing and joining the ribs, cutting holes, checking. Minutes on a large part."
          : "Making the full variant. Minutes on a large part the first time.",
        async () => {
          const made = await api.studyDesign(fidelity);
          setVerdict(made);
          setDraft((await api.studyDraft()).draft);
          onDesign(made);
          onStudyChanged();
        },
      ),
    [run, onDesign, onStudyChanged],
  );

  if (!project) {
    return (
      <div className="rib-card">
        <div className="card-note">Open a project to design a variant of it.</div>
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
        <span className="card-title">Design a variant</span>
        {draft ? <VersionChip draft={draft} /> : null}
        <button
          className="icon pane-fold"
          onClick={props.onCollapse}
          title="Fold the card away to the edge"
          aria-label="Fold the card away"
        >
          ›
        </button>
      </header>

      {draft && (draft.differs || refused) ? (
        <DraftBar
          draft={draft}
          disabled={busy !== null}
          onAccept={accept}
          onUndo={undo}
          onShow={onShow}
        />
      ) : null}

      <div className="rib-slots">
        <AddRow selection={selection} disabled={busy !== null} onHand={byHand} />
        {!blocks.length && !refused ? (
          <div className="card-note">
            Nothing asked for yet. Select faces on the part and add a block from them above - ribs
            standing on them, webs between them, faces to thicken, a plate to cut holes in - or say
            what you want to the agent at the top. Each block is in the part's named entities; what
            you leave open is read off the part, and you can change any of it here.
          </div>
        ) : null}
        {blocks.map((block) => (
          <BlockView
            key={block.id}
            block={block}
            names={draft?.names ?? {}}
            selection={selection}
            others={blocks.filter((b) => b.id !== block.id)}
            disabled={busy !== null}
            onDrop={drop}
            onHand={byHand}
            onShow={onShow}
          />
        ))}
        {draft ? (
          <StudyRest
            draft={draft}
            disabled={busy !== null}
            onDrop={drop}
            onHand={byHand}
            onShow={onShow}
          />
        ) : null}
        <RestsOn study={study} onShow={onShow} />
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
                  ? "ready to make a variant"
                  : "nothing here can be built yet"}
        </div>
        <div className="actions">
          <button
            data-active={drawn}
            onClick={() => setDrawn((was) => !was)}
            disabled={(!buildable || refused) && !drawn}
            title="Draw where the suggested variant would put ribs, before anything is made"
          >
            {drawn ? "Hide paths" : "Show paths"}
          </button>
          <button
            onClick={() => make("preview")}
            disabled={!buildable || refused || busy !== null}
            title="Accept the study if it changed, and make its suggested variant on a coarse grid"
          >
            Preview
          </button>
          <button
            onClick={() => make("full")}
            disabled={!buildable || refused || busy !== null}
            title="The same variant at full resolution - what a variant is accepted at"
          >
            Full
          </button>
        </div>
        {drawn ? <PathsKey paths={paths} note={pathsNote} folded /> : null}
        {busy ? <div className="card-note busy-note">{busy}</div> : null}
        {verdict && !busy ? <VerdictView verdict={verdict} /> : null}
      </footer>
    </div>
  );
}

/** Blocks added by hand, from the faces selected on the part - or the material, from nothing. */
function AddRow(props: {
  selection: number[];
  disabled: boolean;
  onHand: (action: HandAction) => void;
}) {
  const none = !props.selection.length;
  const add = (what: NonNullable<HandAction["add"]>) => props.onHand({ action: "add", add: what });
  const faces = none ? "select faces on the part first" : `${props.selection.length} faces selected`;
  return (
    <div className="add-row">
      <span className="dim">add</span>
      <button disabled={props.disabled || none} onClick={() => add("ribs")} title={`Ribs standing on the faces selected - ${faces}`}>
        ribs on
      </button>
      <button disabled={props.disabled || none} onClick={() => add("webs")} title={`Webs between the faces selected, with nothing under them - ${faces}`}>
        webs between
      </button>
      <button disabled={props.disabled || none} onClick={() => add("thicken")} title={`The faces selected made thicker or thinner - ${faces}`}>
        thicken
      </button>
      <button disabled={props.disabled || none} onClick={() => add("holes")} title={`Holes through the plate selected - ${faces}`}>
        holes in
      </button>
      <button disabled={props.disabled} onClick={() => add("material")} title="What the part is cast in - one material, which its designs do not change">
        material
      </button>
      {none ? (
        <div className="add-hint">
          Ribs, webs, thickening and holes are added from faces: click one on the part - ctrl-click
          for more - and they come on. The material needs nothing selected.
        </div>
      ) : (
        <span className="dim"> · {faces}</span>
      )}
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
  selection: number[];
  others: StudyBlockView[];
  disabled: boolean;
  onDrop: (id: string) => void;
  onHand: (action: HandAction) => void;
  onShow: (refs: string[]) => void;
}) {
  const { block, names, onShow, onHand } = props;
  const ribs = block.add === "ribs";
  const faces = props.selection.length;
  const take = (action: "stand_on" | "end_on") =>
    onHand({ action, block: block.id, refs: undefined });
  const labels: Record<string, [string, string]> = {
    ribs: ["stand on", "end on"],
    thicken: ["faces moved", ""],
    holes: ["through", ""],
    material: ["", ""],
  };
  const [standLabel, endLabel] = labels[block.add] ?? ["stand on", "end on"];
  return (
    <section className="rib-slot study-block" data-changed={block.changed}>
      <header>
        <span className="slot-label">
          {block.id} · add {block.add}
        </span>
        <button
          className="icon"
          disabled={props.disabled}
          onClick={() => onHand({ action: "remove", block: block.id })}
          title={`Take ${block.id} out of the study`}
        >
          ×
        </button>
      </header>
      <dl className="kv compact block-where">
        {standLabel ? (
          <>
            <dt>{standLabel}</dt>
            <dd data-changed={block.stand_on.changed}>
              {!block.stand_on.refs.length && block.note.webs ? (
                <span className="dim">
                  nothing - webs that <Said text={block.note.webs} names={names} onShow={onShow} />
                </span>
              ) : (
                <EntityChips group={block.stand_on} names={names} onShow={onShow} none="nothing - they hang" />
              )}
              <button
                className="link"
                disabled={props.disabled || !faces}
                onClick={() => take("stand_on")}
                title={faces ? `Take the ${faces} faces selected instead` : "Select faces on the part first"}
              >
                ← selection
              </button>
            </dd>
          </>
        ) : null}
        {ribs ? (
          <>
            <dt>{endLabel}</dt>
            <dd data-changed={block.end_on.changed}>
              <EntityChips group={block.end_on} names={names} onShow={onShow} none="nothing named" />
              <button
                className="link"
                disabled={props.disabled || !faces}
                onClick={() => take("end_on")}
                title={faces ? `End on the ${faces} faces selected` : "Select faces on the part first"}
              >
                ← selection
              </button>
              {!block.end_on.read_off && block.stand_on.refs.length ? (
                <button
                  className="link"
                  disabled={props.disabled}
                  onClick={() => onHand({ action: "end_on", block: block.id, refs: [] })}
                  title="End on what rises round where they stand, read off the part"
                >
                  read off
                </button>
              ) : null}
            </dd>
          </>
        ) : null}
        {block.add === "ribs" || block.add === "holes" ? (
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
                  onHand={onHand}
                  onShow={onShow}
                />
              ))}
              <KeepClearAdd
                block={block}
                others={props.others}
                faces={faces}
                disabled={props.disabled}
                onHand={onHand}
              />
            </dd>
          </>
        ) : null}
      </dl>
      <div className="slot-study">
        {block.settings.map((setting) => (
          <SettingLine
            key={setting.name}
            block={block.id}
            setting={setting}
            names={names}
            disabled={props.disabled}
            onHand={onHand}
            onShow={onShow}
          />
        ))}
        {block.rules.map((rule) => (
          <RuleLine
            key={rule.id}
            rule={rule}
            names={names}
            disabled={props.disabled}
            onDrop={props.onDrop}
            onHand={onHand}
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

/** Keep a block clear of what is selected on the part, or of another block's ribs or holes - by
 * how much. */
function KeepClearAdd(props: {
  block: StudyBlockView;
  others: StudyBlockView[];
  faces: number;
  disabled: boolean;
  onHand: (action: HandAction) => void;
}) {
  const [clearance, setClearance] = useState("10");
  const [what, setWhat] = useState("selection");
  const made = props.others
    .filter((b) => b.add === "ribs" || b.add === "holes")
    .map((b) => `${b.add}:${b.id}`);
  const mm = Number(clearance);
  const ready = Number.isFinite(mm) && mm >= 0 && (what !== "selection" || props.faces > 0);
  return (
    <div className="keep-clear-add">
      <input
        className="num"
        value={clearance}
        onChange={(e) => setClearance(e.target.value)}
        aria-label="clearance in mm"
      />
      <span className="dim"> mm clear of </span>
      <select value={what} onChange={(e) => setWhat(e.target.value)}>
        <option value="selection">the faces selected ({props.faces})</option>
        {made.map((ref) => (
          <option key={ref} value={ref}>
            the {ref.split(":")[0]} of {ref.split(":")[1]}
          </option>
        ))}
      </select>
      <button
        className="link"
        disabled={props.disabled || !ready}
        onClick={() =>
          props.onHand({
            action: "keep_clear",
            block: props.block.id,
            clearance_mm: mm,
            refs: what === "selection" ? undefined : [what],
          })
        }
      >
        keep clear
      </button>
    </div>
  );
}

/** A keep-clear rule: how far, from what - each entity a chip - and whose rule it is. */
function KeepClear(props: {
  rule: StudyRule;
  names: Record<string, string>;
  disabled: boolean;
  onDrop: (id: string) => void;
  onHand: (action: HandAction) => void;
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
      {rule.by === "part" ? (
        <button
          className="link"
          disabled={props.disabled}
          onClick={() => props.onHand({ action: "confirm", rule: rule.id })}
          title="Keep this as yours"
        >
          keep
        </button>
      ) : null}
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
  block: string;
  setting: StudySetting;
  names: Record<string, string>;
  disabled: boolean;
  onHand: (action: HandAction) => void;
  onShow: (refs: string[]) => void;
}) {
  const { setting } = props;
  const [open, setOpen] = useState(false);
  const mine = ["you", "words", "selected"].includes(setting.source);
  return (
    <div className="study-setting" data-changed={setting.changed} title={setting.basis || undefined}>
      <span className="tag" data-fixed={setting.fixed}>
        {setting.fixed ? "fixed" : "varies"}
      </span>
      <span className="setting-label">{setting.label}</span>{" "}
      <Said text={setting.says} names={props.names} onShow={props.onShow} />
      <span className="dim"> · {SOURCE[setting.source] ?? setting.source}</span>
      <button
        className="link"
        disabled={props.disabled}
        onClick={() => setOpen((was) => !was)}
        title="Fix it, range it or narrow its choices - by hand"
      >
        {open ? "close" : "change"}
      </button>
      {mine ? (
        <button
          className="link"
          disabled={props.disabled}
          onClick={() => props.onHand({ action: "setting", block: props.block, name: setting.name })}
          title="Hand it back to the part: what it reads off for it"
        >
          back to the part
        </button>
      ) : null}
      {open ? (
        <SettingEditor
          block={props.block}
          setting={setting}
          disabled={props.disabled}
          onHand={(action) => {
            setOpen(false);
            props.onHand(action);
          }}
        />
      ) : null}
    </div>
  );
}

/** A setting by hand: choices to keep, or a range and its step - or one value. */
function SettingEditor(props: {
  block: string;
  setting: StudySetting;
  disabled: boolean;
  onHand: (action: HandAction) => void;
}) {
  const { setting } = props;
  const domain = setting.domain;
  const base = { action: "setting" as const, block: props.block, name: setting.name };
  const [chosen, setChosen] = useState<(number | string)[]>(domain.options ?? []);
  const [low, setLow] = useState(String(domain.low ?? ""));
  const [high, setHigh] = useState(String(domain.high ?? ""));
  const [step, setStep] = useState(String(domain.step ?? ""));
  const [one, setOne] = useState(String(domain.suggested ?? domain.low ?? ""));
  const [cast, setCast] = useState(String(domain.options?.[0] ?? domain.suggested ?? ""));
  if (domain.catalogue) {
    // One material the part is cast in: chosen, never varied.
    return (
      <div className="setting-editor">
        {domain.catalogue.map((option) => (
          <label key={option}>
            <input
              type="radio"
              name={`cast-${props.block}`}
              checked={cast === option}
              onChange={() => setCast(option)}
            />
            {option}
          </label>
        ))}
        <button
          disabled={props.disabled || !cast}
          onClick={() => props.onHand({ ...base, value: cast })}
          title="The part is cast in one material, which its designs do not change"
        >
          cast in this
        </button>
      </div>
    );
  }
  if (domain.options) {
    return (
      <div className="setting-editor">
        {domain.options.map((option) => (
          <label key={String(option)}>
            <input
              type="checkbox"
              checked={chosen.includes(option)}
              onChange={(e) =>
                setChosen((was) =>
                  e.target.checked ? [...was, option] : was.filter((o) => o !== option),
                )
              }
            />
            {String(option)}
          </label>
        ))}
        <button
          disabled={props.disabled || !chosen.length}
          onClick={() => props.onHand({ ...base, options: chosen })}
        >
          keep these
        </button>
      </div>
    );
  }
  const numbers = [low, high, step].map(Number);
  const ranged = numbers.every(Number.isFinite) && numbers[0] <= numbers[1] && numbers[2] > 0;
  return (
    <div className="setting-editor">
      <input className="num" value={low} onChange={(e) => setLow(e.target.value)} aria-label="low" />
      <span className="dim"> to </span>
      <input className="num" value={high} onChange={(e) => setHigh(e.target.value)} aria-label="high" />
      <span className="dim"> {domain.unit} in steps of </span>
      <input className="num" value={step} onChange={(e) => setStep(e.target.value)} aria-label="step" />
      <button
        disabled={props.disabled || !ranged}
        onClick={() => props.onHand({ ...base, low: numbers[0], high: numbers[1], step: numbers[2] })}
      >
        range
      </button>
      <span className="dim"> or fix at </span>
      <input className="num" value={one} onChange={(e) => setOne(e.target.value)} aria-label="value" />
      <button
        disabled={props.disabled || !Number.isFinite(Number(one))}
        onClick={() => props.onHand({ ...base, value: Number(one) })}
      >
        fix
      </button>
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
  onHand?: (action: HandAction) => void;
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
      {props.onHand && rule.by === "part" ? (
        <button
          className="link"
          disabled={props.disabled}
          onClick={() => props.onHand?.({ action: "confirm", rule: rule.id })}
          title="Keep this as yours"
        >
          keep
        </button>
      ) : null}
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
  if (rule.by === "words") return rule.source === "you" ? "you" : "your words";
  if (rule.by === "part") return rule.source === "drawing" ? "the drawing" : "suggested by the part";
  if (rule.by === "platform") return "the platform";
  return SOURCE[rule.source] ?? rule.source;
}

/** The rest of the study: rules for every block, what makes a design better, the pull - and the
 * part's interfaces, closed by the platform. How many designs is the campaign's to say. */
function StudyRest(props: {
  draft: StudyDraft;
  disabled: boolean;
  onDrop: (id: string) => void;
  onHand: (action: HandAction) => void;
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

/** What the study rests on: the engineer's words - said to the agent, or done by hand on this card
 * - each face in them a chip that shows it on the part; and the study's versions, each with what it
 * changed. */
function RestsOn(props: { study: StudyInfo | null; onShow: (refs: string[]) => void }) {
  const current = props.study?.current;
  if (!current) return null;
  const versions = [...(props.study?.versions ?? [])].reverse();
  return (
    <section className="rib-slot study-extra">
      <details className="study-fold">
        <summary>
          What it rests on - {current.words.length} things said · study v{current.version}
        </summary>
        <div className="words">
          {current.words.map((word) => (
            <p key={word.id}>
              <span className="mono dim">{word.id}</span> &ldquo;
              <Said text={word.text} onShow={props.onShow} />
              &rdquo;
            </p>
          ))}
        </div>
      </details>
      {versions.length ? (
        <details className="study-fold">
          <summary>Versions ({versions.length})</summary>
          <ul className="study-lines">
            {versions.map((v) => (
              <li key={v.version}>
                <span className="mono">v{v.version}</span>{" "}
                <span className="dim">{v.created.replace("T", " ").slice(0, 16)}</span>
                {v.note ? (
                  <>
                    {" "}
                    <Said text={v.note} onShow={props.onShow} />
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
