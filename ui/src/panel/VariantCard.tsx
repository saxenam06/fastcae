/**
 * Design a variant: one change in one place, authored by hand and kept in the project's library.
 *
 * A variant is ribs standing on faces, webs between them, faces made thicker or thinner, or holes
 * through a plate - with what it may vary and every rule it holds. Each variant kept is a tab at the
 * top; the last tab starts a new one.
 *
 * **Built by hand.** Select faces on the part and choose what to add; what it stands on and ends on
 * is taken from the selection - webs run from the faces they were added between to the faces added
 * as the other side, never within one side; every setting is fixed, ranged in steps or narrowed to
 * some choices where it shows - the part suggests each, in steps of five; a rule is added from the
 * kinds the pipeline checks, or one the part suggested is taken out. The card counts how many
 * designs the variant allows.
 *
 * **Seen before it is kept.** Show paths draws it at its suggested point, Another sample at a point
 * drawn at random - every choice as likely as the next - each placed alone, repaired and screened,
 * and saying how it was drawn; what repair left out is drawn as left out. Create, at the bottom,
 * keeps it once one of its points passes; a variant kept is changed and saved again - campaigns
 * keep the copy they were launched with.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { ChangeEvent, FocusEvent, KeyboardEvent } from "react";
import type {
  HandAction,
  OfferedRule,
  StudyBlockView,
  StudyDraft,
  StudyEntities,
  StudyRule,
  StudySetting,
  VariantInfo,
  VariantRow,
  VariantSample,
} from "../api/client";
import { api } from "../api/client";
import type { LineSet } from "../render/renderer";
import { HAS_REFERENCE, PATTERN_NAMES, PathsKey, Said, matters, plain, toLines } from "./shared";

interface VariantCardProps {
  /** The project the variants are of. A new one starts the pane afresh. */
  project: string | null;
  /** The faces selected on the part: what a variant is added from, or takes by hand. */
  selection: number[];
  /** Read the variant again when this changes. */
  refresh: number;
  /** Show these faces and features on the part. */
  onShow: (refs: string[]) => void;
  /** Draw these lines on the part - where the variant's ribs and holes go - or none. */
  onPaths: (lines: LineSet | null) => void;
  /** Fold the card away to the edge. */
  onCollapse: () => void;
  /** The library changed: a variant kept, changed, copied or taken out. */
  onLibrary?: () => void;
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

/** What each kind of variant is called where it is added. */
const KINDS: { add: NonNullable<HandAction["add"]>; label: string; says: string }[] = [
  { add: "ribs", label: "ribs on", says: "Ribs standing on the faces selected" },
  { add: "webs", label: "webs between", says: "Webs between the faces selected, nothing under them" },
  { add: "thicken", label: "thicken", says: "The faces selected made thicker or thinner" },
  { add: "holes", label: "holes in", says: "Holes through the plate selected" },
];

/** How many entities a row lists before the rest fold away. */
const FOLD = 8;

export function VariantCard(props: VariantCardProps) {
  const { project, refresh, selection, onShow, onPaths, onLibrary } = props;
  const [library, setLibrary] = useState<VariantRow[]>([]);
  const [draft, setDraft] = useState<StudyDraft | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [name, setName] = useState("");
  // The sample drawn on the part: its suggested point, or another drawn at random.
  const [drawn, setDrawn] = useState<"suggested" | "another" | null>(null);
  const [seed, setSeed] = useState(1);
  const [sample, setSample] = useState<VariantSample | null>(null);
  const [sampleNote, setSampleNote] = useState<string | null>(null);

  const variant = draft?.variant ?? null;

  useEffect(() => {
    setLibrary([]);
    setDraft(null);
    setDrawn(null);
    setProblem(null);
  }, [project]);

  useEffect(() => {
    if (!project) return;
    let live = true;
    Promise.all([api.variants(), api.variantDraft()])
      .then(([listed, reply]) => {
        if (!live) return;
        setLibrary(listed.variants);
        setDraft(reply.draft);
      })
      .catch((caught) => live && setProblem(plain(caught)));
    return () => {
      live = false;
    };
  }, [project, refresh]);

  // Its name, as kept or suggested - until the engineer types another.
  useEffect(() => {
    setName(variant?.label ?? "");
  }, [variant?.id, variant?.label]);

  // The sample drawn again whenever the variant changes.
  useEffect(() => {
    if (!drawn) {
      onPaths(null);
      setSample(null);
      setSampleNote(null);
      return;
    }
    let live = true;
    setSampleNote(
      "Placing it, repairing and screening: seconds - or a few minutes the first time the part " +
        "is opened on its grid.",
    );
    api
      .sampleVariant(drawn === "another", drawn === "another" ? seed : undefined)
      .then((reply) => {
        if (!live) return;
        setSample(reply);
        setSampleNote(null);
        onPaths(toLines(reply));
      })
      .catch((caught) => {
        if (!live) return;
        setSample(null);
        setSampleNote(plain(caught));
        onPaths(null);
      });
    return () => {
      live = false;
    };
  }, [drawn, seed, draft, onPaths]);

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

  const open = useCallback(
    (id: string) =>
      run("Reading the variant.", async () => {
        setDrawn(null);
        // The library again too: campaigns launched since say they used it.
        const [opened, listed] = await Promise.all([api.openVariant(id), api.variants()]);
        setDraft(opened.draft);
        setLibrary(listed.variants);
      }),
    [run],
  );

  const fresh = useCallback(
    () =>
      run("Starting a new variant.", async () => {
        setDrawn(null);
        setDraft((await api.newVariant()).draft);
      }),
    [run],
  );

  // Something done by hand: the variant as it now is, or why not.
  const byHand = useCallback(
    (action: HandAction) =>
      run("Changing the variant.", async () =>
        setDraft((await api.handVariant({ ...action, selected: selection })).draft),
      ),
    [run, selection],
  );

  // Several things done by hand, one after another - a rule taken out and put back changed.
  const byHands = useCallback(
    (actions: HandAction[]) =>
      run("Changing the variant.", async () => {
        let last: StudyDraft | null = null;
        for (const action of actions) {
          last = (await api.handVariant({ ...action, selected: selection })).draft;
        }
        if (last) setDraft(last);
      }),
    [run, selection],
  );

  const drop = useCallback((id: string) => byHand({ action: "drop", rule: id }), [byHand]);

  const save = useCallback(
    () =>
      run(
        variant?.kept
          ? "Saving the variant: a point of it placed and screened first."
          : "Creating the variant: a point of it placed and screened first.",
        async () => {
          const reply = await api.saveVariant(name.trim() || null);
          setDraft(reply.draft);
          setLibrary(reply.variants);
          onLibrary?.();
        },
      ),
    [run, name, variant?.kept, onLibrary],
  );

  const discard = useCallback(
    () =>
      run("Reading the variant back.", async () => {
        setDraft((await api.discardVariant()).draft);
      }),
    [run],
  );

  const duplicate = useCallback(
    () =>
      run("Copying the variant.", async () => {
        if (!variant) return;
        const reply = await api.duplicateVariant(variant.id);
        setLibrary(reply.variants);
        setDraft((await api.openVariant(reply.id)).draft);
        onLibrary?.();
      }),
    [run, variant, onLibrary],
  );

  const remove = useCallback(() => {
    if (!variant) return;
    const said = `Take ${variant.id} · ${variant.label} out of the library? Campaigns that used it keep their copy.`;
    if (!window.confirm(said)) return;
    void run("Taking the variant out.", async () => {
      const reply = await api.deleteVariant(variant.id);
      setLibrary(reply.variants);
      setDrawn(null);
      setDraft((await api.variantDraft()).draft);
      onLibrary?.();
    });
  }, [run, variant, onLibrary]);

  if (!project) {
    return (
      <div className="rib-card">
        <div className="card-note">Open a project to design a variant of it.</div>
      </div>
    );
  }

  const refused = Boolean(draft?.refused);
  const block = draft?.blocks[0] ?? null;
  const waiting = Boolean(block && (block.needed.length || block.problems.length));
  const ready = Boolean(block && !block.cannot && !waiting && !refused);
  const kept = Boolean(variant?.kept);
  const changed = Boolean(draft?.differs);
  const renamed = kept && name.trim() !== "" && name.trim() !== variant?.label;
  const usedBy = library.find((row) => row.id === variant?.id)?.used_in ?? [];

  return (
    <div className="rib-card study-card variant-card">
      <header className="rib-card-head">
        <span className="card-title">Design a variant</span>
        <button
          className="icon pane-fold"
          onClick={props.onCollapse}
          title="Fold the card away to the edge"
          aria-label="Fold the card away"
        >
          ›
        </button>
      </header>

      <nav className="variant-tabs" aria-label="Variants">
        {library.map((row) => (
          <button
            key={row.id}
            className="variant-tab"
            data-active={variant?.id === row.id}
            disabled={busy !== null}
            onClick={() => open(row.id)}
            title={`${row.kind} · ${combinationsSaid(row.combinations)}`}
          >
            <span className="mono">{row.id}</span> {row.label}
          </button>
        ))}
        <button
          className="variant-tab new"
          data-active={Boolean(variant && !kept)}
          disabled={busy !== null}
          onClick={fresh}
          title="Start a new variant"
        >
          + New variant
        </button>
      </nav>

      <div className="rib-slots">
        {variant ? (
          <div className="variant-id">
            <span className="mono">{variant.id}</span>
            <span className="dim">
              {" "}
              · {kept ? (changed ? "changed - not saved yet" : "kept") : "new - not created yet"}
            </span>
          </div>
        ) : null}
        {kept && usedBy.length ? (
          <div className="dim variant-used">
            Used by{" "}
            {usedBy
              .map((use) => `${use.name}${use.changed_since ? " (changed since)" : ""}`)
              .join(", ")}
            . Each campaign keeps the copy it was launched with.
          </div>
        ) : null}
        {refused ? (
          <div className="card-note warn">
            <Said text={draft?.cannot ?? ""} onShow={onShow} />
          </div>
        ) : null}
        {!block ? (
          <AddRow selection={selection} disabled={busy !== null} onHand={byHand} />
        ) : (
          <BlockView
            block={block}
            draft={draft as StudyDraft}
            variant={variant}
            selection={selection}
            disabled={busy !== null}
            onDrop={drop}
            onHand={byHand}
            onHands={byHands}
            onShow={onShow}
          />
        )}
      </div>

      {problem ? <div className="card-note warn">{problem}</div> : null}

      <footer className="rib-card-foot variant-foot">
        {block ? (
          <div className="variant-look">
            <div className="actions">
              <button
                data-active={drawn === "suggested"}
                onClick={() => setDrawn((was) => (was === "suggested" ? null : "suggested"))}
                disabled={!ready && drawn !== "suggested"}
                title="Draw it at its suggested point: placed alone, repaired and screened"
              >
                {drawn === "suggested" ? "Hide paths" : "Show paths"}
              </button>
              <button
                data-active={drawn === "another"}
                onClick={() => {
                  setSeed((was) => was + 1);
                  setDrawn("another");
                }}
                disabled={!ready}
                title="Draw it at another point, drawn at random from what it allows - every choice as likely as the next"
              >
                Another sample
              </button>
            </div>
            {drawn ? (
              <>
                {variant?.kind === "thicken" && sample ? (
                  // Faces moved draw no lines: how many move, and how far, is said - the faces
                  // shown on the part on demand.
                  <div className="card-note">
                    {sample.summary}
                    {block.stand_on.refs.length ? (
                      <>
                        {" "}
                        <button
                          className="link"
                          onClick={() => onShow(block.stand_on.refs)}
                          title="Show the faces it moves on the part"
                        >
                          show them
                        </button>
                      </>
                    ) : null}
                  </div>
                ) : (
                  <PathsKey paths={sample} note={sampleNote} quiet />
                )}
                {sample?.drawn ? <div className="dim sample-drawn">{sample.drawn}</div> : null}
                {sample?.about ? <div className="dim sample-about">{sample.about}</div> : null}
                {sample?.left_out_said ? (
                  <div className="card-note">{sample.left_out_said}</div>
                ) : null}
                {sample?.findings.map((f) => (
                  <div key={`${f.check}-${f.reason}`} className="card-note">
                    {f.check}: {f.reason}
                  </div>
                ))}
              </>
            ) : null}
          </div>
        ) : null}
        {block ? (
          <div className="variant-keep">
            <label className="variant-name">
              <span className="dim">name</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="what it changes and where"
                aria-label="the variant's name"
              />
            </label>
            <div className="actions">
              {kept ? (
                <>
                  <button
                    className="primary"
                    onClick={save}
                    disabled={busy !== null || (!changed && !renamed) || (changed && !ready)}
                    title="Keep these changes - after a point of it is placed and passes"
                  >
                    Save changes
                  </button>
                  <button onClick={discard} disabled={busy !== null || !changed}>
                    Discard
                  </button>
                  <button onClick={duplicate} disabled={busy !== null}>
                    Duplicate
                  </button>
                  <button className="danger" onClick={remove} disabled={busy !== null}>
                    Delete
                  </button>
                </>
              ) : (
                <button
                  className="primary"
                  onClick={save}
                  disabled={busy !== null || !ready}
                  title="Keep it in the library - after a point of it is placed and passes"
                >
                  Create variant
                </button>
              )}
            </div>
            <div className="rib-card-status" data-ready={ready}>
              {refused
                ? "it cannot be kept as it is"
                : waiting
                  ? "something is needed - see above"
                  : block.cannot
                    ? "nothing here can be built yet"
                    : kept
                      ? changed
                        ? "changed: save to keep it"
                        : "kept in the library"
                      : "ready: look at it, then create it"}
            </div>
          </div>
        ) : null}
        {busy ? <div className="card-note busy-note">{busy}</div> : null}
      </footer>
    </div>
  );
}

function combinationsSaid(count: number | null): string {
  return count === null ? "no end to its designs" : `${count.toLocaleString()} designs`;
}

/** What a variant adds, from the faces selected on the part. */
function AddRow(props: {
  selection: number[];
  disabled: boolean;
  onHand: (action: HandAction) => void;
}) {
  const none = !props.selection.length;
  const named = props.selection.slice(0, 3).map((face) => `face:${face}`).join(", ");
  const more = props.selection.length > 3 ? ` and ${props.selection.length - 3} more` : "";
  const faces = none ? "select faces on the part first" : `${named}${more} selected`;
  return (
    <div className="add-row">
      <span className="dim">add</span>
      {KINDS.map((kind) => (
        <button
          key={kind.add}
          disabled={props.disabled || none}
          onClick={() => props.onHand({ action: "add", add: kind.add })}
          title={`${kind.says} - ${faces}`}
        >
          {kind.label}
        </button>
      ))}
      {none ? (
        <div className="add-hint">
          A variant is one change in one place. Click a face on the part - ctrl-click for more - and
          choose what to add there: ribs standing on it, webs between faces, the faces made thicker
          or thinner, or holes through a plate.
        </div>
      ) : (
        <span className="dim"> · {faces}</span>
      )}
    </div>
  );
}

/** The settings that decide a design, shown first; the rest fold away under More settings. */
const KEY: Record<string, string[]> = {
  ribs: ["generator", "thickness_mm", "spacing_mm", "count", "height_fraction"],
  holes: ["pattern", "diameter_mm", "pitch_mm"],
  thicken: ["offset_mm"],
};
/** What each kind of change is called at the top of its variant. */
const KIND_TITLES: Record<string, string> = {
  ribs: "Ribs",
  webs: "Webs",
  thicken: "Faces thicker or thinner",
  holes: "Holes",
};

/** The one change: a sentence saying what it adds and where - its entities to change on demand -
 * the settings that decide its designs, the rest folded, and its rules. */
function BlockView(props: {
  block: StudyBlockView;
  draft: StudyDraft;
  variant: VariantInfo | null;
  selection: number[];
  disabled: boolean;
  onDrop: (id: string) => void;
  onHand: (action: HandAction) => void;
  onHands: (actions: HandAction[]) => void;
  onShow: (refs: string[]) => void;
}) {
  const { block, draft, onShow, onHand } = props;
  const [where, setWhere] = useState(false);
  const [adding, setAdding] = useState(false);
  const names = draft.names;
  const webs = block.add === "ribs" && !block.stand_on.refs.length && props.variant?.kind === "webs";
  const kind = webs ? "webs" : block.add;
  // Webs with nothing to run to yet: where they go opens, to add the other side.
  const sideless = webs && !block.other_side?.refs.length;
  useEffect(() => {
    if (sideless) setWhere(true);
  }, [sideless]);
  // Every rule the variant holds - its block's, and those said for every block, such as the
  // drawing's smallest radius, which a variant of one block holds as its own. Only what the
  // pipeline checks: a rule nothing holds a design to is not the variant's.
  const rules = [...block.rules, ...draft.rules].filter((rule) => rule.enforced);
  const visible = block.settings.filter((s) => !s.hidden);
  const generator = visible.find((s) => s.name === "generator");
  const patterns = generator
    ? (generator.domain.options ?? [generator.domain.suggested]).map((p) => String(p))
    : [];
  const shown = visible.filter((s) => matters(s.name, patterns));
  const keyNames = KEY[block.add] ?? [];
  const key = keyNames.map((n) => shown.find((s) => s.name === n)).filter((s): s is StudySetting => !!s);
  const rest = shown.filter((s) => !keyNames.includes(s.name));
  const row = (setting: StudySetting) => (
    <SettingRow
      key={setting.name}
      block={block.id}
      setting={setting}
      names={names}
      selection={props.selection}
      disabled={props.disabled}
      onHand={onHand}
      onShow={onShow}
    />
  );
  return (
    <section
      className="variant-block study-block"
      // What changed is marked only on a variant already kept: on a new one, everything is.
      data-kept={Boolean(props.variant?.kept)}
      data-changed={Boolean(props.variant?.kept) && block.changed}
    >
      <header className="variant-block-head">
        <span className="variant-kind">{KIND_TITLES[kind] ?? kind}</span>
        <button
          className="icon"
          disabled={props.disabled}
          onClick={() => onHand({ action: "remove", block: block.id })}
          title="Take this out and start the variant again"
        >
          ×
        </button>
      </header>
      {block.needed.map((what) => (
        <div key={what} className="slot-problem">
          needed: {what} - only you can say
          {what === "smallest radius" ? " (add the rule “no radius under” in Rules)" : ""}
        </div>
      ))}
      {block.problems.map((what) => (
        <div key={what} className="slot-problem">
          <Said text={what} names={names} onShow={onShow} />
        </div>
      ))}
      {block.cannot ? <div className="slot-note waits">{block.cannot}</div> : null}

      <WhereSummary
        block={block}
        kind={kind}
        others={props.variant?.others ?? []}
        names={names}
        open={where}
        onToggle={() => setWhere((was) => !was)}
        onShow={onShow}
      />
      {where ? (
        <WhereDetails
          block={block}
          webs={webs}
          variant={props.variant}
          names={names}
          selection={props.selection}
          disabled={props.disabled}
          onDrop={props.onDrop}
          onHand={onHand}
          onHands={props.onHands}
          onShow={onShow}
        />
      ) : null}

      <div className="variant-section">
        <div className="section-title">Shape</div>
        {key.map(row)}
        {rest.length ? (
          <details className="more-settings">
            <summary>
              More settings ({rest.length})
              {rest.some((s) => ["you", "words", "selected"].includes(s.source)) ? (
                <span className="mine-dot" title="Some of them are yours" />
              ) : null}
            </summary>
            {rest.map(row)}
          </details>
        ) : null}
        <div className="variant-count">
          {props.variant?.combinations === null
            ? "Free lines among its patterns: no end to the designs it allows."
            : `It allows ${(props.variant?.combinations ?? 0).toLocaleString()} distinct designs.`}
        </div>
      </div>

      <div className="variant-section">
        <div className="section-title">Rules</div>
        {rules.length ? null : <div className="dim">no rules of its own yet</div>}
        {rules.map((rule) => (
          <RuleRow
            key={rule.id}
            rule={rule}
            names={names}
            disabled={props.disabled}
            onDrop={props.onDrop}
            onHand={onHand}
            onShow={onShow}
          />
        ))}
        {block.add === "ribs" ? (
          adding ? (
            <RuleAdd
              block={block.id}
              offered={draft.offered}
              faces={props.selection.length}
              disabled={props.disabled}
              onHand={(action) => {
                setAdding(false);
                onHand(action);
              }}
              onCancel={() => setAdding(false)}
            />
          ) : (
            <button className="link add-rule" disabled={props.disabled} onClick={() => setAdding(true)}>
              + add a rule
            </button>
          )
        ) : null}
        {draft.interfaces.length ? (
          <details className="study-fold interfaces-fold">
            <summary>
              The part's holes, bores and drawing features stay clear - held for every variant
            </summary>
            <div className="study-rules">
              {draft.interfaces.map((rule) => (
                <RuleLine key={rule.id} rule={rule} names={names} onShow={onShow} />
              ))}
            </div>
          </details>
        ) : null}
      </div>
    </section>
  );
}

/** Where the change goes, in a sentence: what it stands on, what it ends on, what it keeps clear
 * of - each group a few chips, or a count to show on the part. */
function WhereSummary(props: {
  block: StudyBlockView;
  kind: string;
  others: VariantInfo["others"];
  names: Record<string, string>;
  open: boolean;
  onToggle: () => void;
  onShow: (refs: string[]) => void;
}) {
  const { block, onShow } = props;
  const labels = Object.fromEntries(props.others.map((o) => [o.id, o.label]));
  const refs = (group: string[], many: string) => (
    <Refs refs={group} many={many} names={props.names} labels={labels} onShow={onShow} />
  );
  const ends = block.end_on;
  const other = block.other_side?.refs ?? [];
  return (
    <div className="where-summary">
      <span>
        {props.kind === "webs" ? (
          <>
            from {refs(ends.refs, "faces")} to{" "}
            {other.length ? refs(other, "faces") : <span className="dim">the other side - not added yet</span>}
          </>
        ) : props.kind === "thicken" ? (
          <>{refs(block.stand_on.refs, "faces")} moved along their normal</>
        ) : props.kind === "holes" ? (
          <>through {refs(block.stand_on.refs, "faces")}</>
        ) : (
          <>
            on {refs(block.stand_on.refs, "faces")}
            {ends.refs.length ? (
              <>
                , ending on{" "}
                {ends.read_off ? (
                  <>
                    what rises round it{" "}
                    <button className="link" onClick={() => onShow(ends.refs)} title="Show them on the part">
                      ({ends.refs.length})
                    </button>
                  </>
                ) : (
                  refs(ends.refs, "things")
                )}
              </>
            ) : null}
          </>
        )}
        {block.keep_clear.map((rule) => (
          <span key={rule.id}>
            ; {Number(rule.params.clearance_mm ?? 0) ? `${Number(rule.params.clearance_mm)} mm ` : ""}
            clear of {refs(rule.refs, "things")}
          </span>
        ))}
      </span>
      <button className="link where-edit" onClick={props.onToggle}>
        {props.open ? "done" : "change where"}
      </button>
    </div>
  );
}

/** A group of entities in words: one or two as chips, more as a count to show on the part. */
function Refs(props: {
  refs: string[];
  many: string;
  names: Record<string, string>;
  labels: Record<string, string>;
  onShow: (refs: string[]) => void;
}) {
  const { refs } = props;
  if (!refs.length) return <span className="dim">nothing</span>;
  if (refs.length <= 2) {
    return (
      <>
        {refs.map((ref, i) => (
          <span key={ref}>
            {i ? " and " : ""}
            <Chip ref_={ref} names={props.names} labels={props.labels} onShow={props.onShow} />
          </span>
        ))}
      </>
    );
  }
  const holes = refs.every((ref) => ref.startsWith("hole:"));
  return (
    <button className="link" onClick={() => props.onShow(refs)} title="Show them on the part">
      {refs.length} {holes ? "holes" : props.many}
    </button>
  );
}

/** What the change stands on, ends on and keeps clear of, entity by entity, to change: from the
 * faces selected, read off the part, or kept clear of by so much. */
function WhereDetails(props: {
  block: StudyBlockView;
  webs: boolean;
  variant: VariantInfo | null;
  names: Record<string, string>;
  selection: number[];
  disabled: boolean;
  onDrop: (id: string) => void;
  onHand: (action: HandAction) => void;
  onHands: (actions: HandAction[]) => void;
  onShow: (refs: string[]) => void;
}) {
  const { block, webs, names, selection, onShow, onHand } = props;
  const faces = selection.length;
  const ribs = block.add === "ribs";
  // Entities one by one: an × takes one out, + add adds the faces selected on the part.
  const edit = (action: "stand_on" | "end_on" | "other_side", refs: string[]) =>
    onHand({ action, block: block.id, refs });
  // The two sides of webs: a face is on one side only - one already on a side stays there, to be
  // taken off it first.
  const other = block.other_side ?? { refs: [], read_off: false };
  const fresh = (mine: string[], theirs: string[]) =>
    selection.filter((face) => ![...mine, ...theirs].includes(`face:${face}`));
  const fromFresh = fresh(block.end_on.refs, other.refs);
  const toFresh = fresh(other.refs, block.end_on.refs);
  const onASide = faces
    ? "The faces selected are on a side already - take one off with its × to move it"
    : undefined;
  const labels: Record<string, [string, string]> = {
    ribs: ["stand on", "end on"],
    thicken: ["faces moved", ""],
    holes: ["through", ""],
  };
  const [standLabel, endLabel] = labels[block.add] ?? ["stand on", "end on"];
  return (
    <div className="where-details">
      <dl className="kv compact block-where">
        {standLabel && !webs ? (
          <>
            <dt>{standLabel}</dt>
            <dd data-changed={block.stand_on.changed}>
              <EntityChips
                group={block.stand_on}
                names={names}
                onShow={onShow}
                none="nothing"
                onRemove={(ref) => edit("stand_on", block.stand_on.refs.filter((r) => r !== ref))}
                onAdd={() => edit("stand_on", adding(block.stand_on.refs, selection))}
                selected={faces}
                disabled={props.disabled}
              />
            </dd>
          </>
        ) : null}
        {webs ? (
          <>
            <dt title="The webs run from these faces to the other side - never between two of these">
              from
            </dt>
            <dd data-changed={block.end_on.changed}>
              <EntityChips
                group={block.end_on}
                names={names}
                onShow={onShow}
                none="nothing named"
                onRemove={(ref) => edit("end_on", block.end_on.refs.filter((r) => r !== ref))}
                onAdd={() => edit("end_on", adding(block.end_on.refs, fromFresh))}
                selected={fromFresh.length}
                idle={onASide}
                disabled={props.disabled}
              />
            </dd>
            <dt title="What the webs run to - never between two of these either">to</dt>
            <dd data-changed={other.changed}>
              <EntityChips
                group={other}
                names={names}
                onShow={onShow}
                none="nothing yet - select the faces the webs run to on the part, then add them"
                onRemove={(ref) => edit("other_side", other.refs.filter((r) => r !== ref))}
                empty
                onAdd={() => edit("other_side", adding(other.refs, toFresh))}
                selected={toFresh.length}
                idle={onASide}
                disabled={props.disabled}
              />
            </dd>
          </>
        ) : ribs ? (
          <>
            <dt>{endLabel}</dt>
            <dd data-changed={block.end_on.changed}>
              <EntityChips
                group={block.end_on}
                names={names}
                onShow={onShow}
                none="nothing named"
                onRemove={(ref) => edit("end_on", block.end_on.refs.filter((r) => r !== ref))}
                empty
                onAdd={() => edit("end_on", adding(block.end_on.refs, selection))}
                selected={faces}
                disabled={props.disabled}
              />
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
        {ribs || block.add === "holes" ? (
          <>
            <dt>keep clear</dt>
            <dd>
              {block.keep_clear.map((rule) => (
                <KeepClear
                  key={rule.id}
                  block={block.id}
                  rule={rule}
                  names={names}
                  labels={Object.fromEntries((props.variant?.others ?? []).map((o) => [o.id, o.label]))}
                  selection={selection}
                  disabled={props.disabled}
                  onDrop={props.onDrop}
                  onHand={onHand}
                  onHands={props.onHands}
                  onShow={onShow}
                />
              ))}
              <KeepClearAdd
                block={block}
                others={props.variant?.others ?? []}
                faces={faces}
                disabled={props.disabled}
                onHand={onHand}
              />
            </dd>
          </>
        ) : null}
      </dl>
    </div>
  );
}

/** Entities as chips: a click shows one on the part; many fold; read off the part says so. With
 * ``onRemove`` each has an × that takes it out - but the last, where one must stay - and with
 * ``onAdd`` the faces selected on the part are added. */
function EntityChips(props: {
  group: StudyEntities;
  names: Record<string, string>;
  onShow: (refs: string[]) => void;
  none: string;
  labels?: Record<string, string>;
  onRemove?: (ref: string) => void;
  /** Whether the last one may go too. */
  empty?: boolean;
  onAdd?: () => void;
  /** How many faces are selected, to add. */
  selected?: number;
  /** Why there is nothing to add, when faces are selected but none of them can be. */
  idle?: string;
  disabled?: boolean;
}) {
  const { group } = props;
  const [open, setOpen] = useState(false);
  const shown = open ? group.refs : group.refs.slice(0, FOLD);
  const removable = props.onRemove && (props.empty || group.refs.length > 1);
  return (
    <span className="refs">
      {group.refs.length ? null : <span className="dim">{props.none}</span>}
      {shown.map((ref) => (
        <Chip
          key={ref}
          ref_={ref}
          names={props.names}
          labels={props.labels}
          onShow={props.onShow}
          onRemove={removable && !props.disabled ? () => props.onRemove?.(ref) : undefined}
        />
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
      {props.onAdd ? (
        <button
          className="link"
          disabled={props.disabled || !props.selected}
          onClick={props.onAdd}
          title={
            props.selected
              ? "Add the faces selected on the part"
              : (props.idle ?? "Select faces on the part first")
          }
        >
          + add{props.selected ? ` ${props.selected} selected` : ""}
        </button>
      ) : null}
      {group.read_off ? <span className="tag">read off the part</span> : null}
    </span>
  );
}

/** One entity - with an × to take it out, when it may go. Another variant's ribs or holes are
 * named like any entity, but are not on the part. */
function Chip(props: {
  ref_: string;
  names: Record<string, string>;
  labels?: Record<string, string>;
  onShow: (refs: string[]) => void;
  onRemove?: () => void;
}) {
  const ref = props.ref_;
  const made = ref.match(/^(ribs|holes):(.+)$/);
  const remove = props.onRemove ? (
    <button className="chip-x" onClick={props.onRemove} title={`Take ${ref} out`}>
      ×
    </button>
  ) : null;
  if (made) {
    const label = props.labels?.[made[2]];
    return (
      <span className="ref-chip ribs-chip" title={`the ${made[1]} of variant ${made[2]}`}>
        <span>
          the {made[1]} of {made[2]}
          {label ? ` · ${label}` : ""}
        </span>
        {remove}
      </span>
    );
  }
  return (
    <span className="ref-chip">
      <button onClick={() => props.onShow([ref])} title={props.names[ref] ?? ref}>
        {ref}
      </button>
      {remove}
    </span>
  );
}

/** The faces selected on the part, as refs, added to ``refs`` - each once. */
function adding(refs: string[], selection: number[]): string[] {
  return [...new Set([...refs, ...selection.map((face) => `face:${face}`)])];
}

/** Keep the variant clear of what is selected on the part, or of another variant's ribs or holes
 * - by how much. */
function KeepClearAdd(props: {
  block: StudyBlockView;
  others: VariantInfo["others"];
  faces: number;
  disabled: boolean;
  onHand: (action: HandAction) => void;
}) {
  const [clearance, setClearance] = useState("10");
  const [what, setWhat] = useState("selection");
  const made = props.others
    .filter((o) => o.kind === "ribs" || o.kind === "webs" || o.kind === "holes")
    .map((o) => ({ ref: `${o.kind === "holes" ? "holes" : "ribs"}:${o.id}`, label: o.label, kind: o.kind }));
  const mm = Number(clearance);
  const ready = Number.isFinite(mm) && mm >= 0 && (what !== "selection" || props.faces > 0);
  return (
    <div className="keep-clear-add">
      <span className="dim">also keep </span>
      <input
        className="num"
        value={clearance}
        onChange={(e) => setClearance(e.target.value)}
        aria-label="clearance in mm"
      />
      <span className="dim"> mm clear of </span>
      <select value={what} onChange={(e) => setWhat(e.target.value)}>
        <option value="selection">the faces selected ({props.faces})</option>
        {made.map((o) => (
          <option key={o.ref} value={o.ref}>
            the {o.kind === "holes" ? "holes" : "ribs"} of {o.label}
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
        add
      </button>
    </div>
  );
}

/** A keep-clear rule: how far, from what - each entity a chip, with an × to take it out and + add
 * for the faces selected - and whose rule it is. A rule changed so is the engineer's. */
function KeepClear(props: {
  block: string;
  rule: StudyRule;
  names: Record<string, string>;
  labels: Record<string, string>;
  selection: number[];
  disabled: boolean;
  onDrop: (id: string) => void;
  onHand: (action: HandAction) => void;
  onHands: (actions: HandAction[]) => void;
  onShow: (refs: string[]) => void;
}) {
  const { rule } = props;
  const clearance = Number(rule.params.clearance_mm ?? 0);
  // The rule as it was, taken out, and put back with what it keeps clear of changed.
  const rewrite = (refs: string[]) =>
    props.onHands([
      { action: "drop", rule: rule.id },
      ...(refs.length
        ? [{ action: "keep_clear" as const, block: props.block, refs, clearance_mm: clearance }]
        : []),
    ]);
  const editable = rule.by !== "platform";
  return (
    <div className="keep-clear" data-changed={rule.changed} title={rule.basis || undefined}>
      <EntityChips
        group={{ refs: rule.refs, read_off: false }}
        names={props.names}
        labels={props.labels}
        onShow={props.onShow}
        none="nothing"
        onRemove={editable ? (ref) => rewrite(rule.refs.filter((r) => r !== ref)) : undefined}
        empty
        onAdd={editable ? () => rewrite(adding(rule.refs, props.selection)) : undefined}
        selected={props.selection.length}
        disabled={props.disabled}
      />
      <span className="dim"> {clearance ? `${clearance} mm clear` : "not crossing"} </span>
      {rule.by === "part" ? (
        <button
          className="rule-tag"
          disabled={props.disabled}
          onClick={() => props.onHand({ action: "confirm", rule: rule.id })}
          title="Suggested by the part - click to make it yours"
        >
          suggested
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

/** One setting: its name, what it may take - its choices as chips to switch on and off, or a
 * range or one value to change in place - and, when it is yours, a way back to what the part
 * suggests. Where the part's suggestion comes from is in the name's tooltip. */
function SettingRow(props: {
  block: string;
  setting: StudySetting;
  names: Record<string, string>;
  selection: number[];
  disabled: boolean;
  onHand: (action: HandAction) => void;
  onShow: (refs: string[]) => void;
}) {
  const { setting } = props;
  const [open, setOpen] = useState(false);
  const mine = ["you", "words", "selected"].includes(setting.source);
  const choices = setting.domain.options !== null;
  // Choices that are faces - what spokes turn about: each with an × to take it out, and + add
  // for the faces selected on the part.
  const faces = (setting.domain.options ?? []).map(String);
  const ofFaces = faces.length > 0 && faces.every((option) => HAS_REFERENCE.test(option));
  const choose = (options: string[]) =>
    props.onHand({ action: "setting", block: props.block, name: setting.name, options });
  return (
    <div className="setting-row" data-mine={mine} data-changed={setting.changed}>
      <span
        className="setting-name setting-label"
        title={[HINTS[setting.name], setting.basis || SOURCE[setting.source] || setting.source]
          .filter(Boolean)
          .join("\n")}
      >
        {setting.label}
        {mine ? <span className="mine-dot" title="Yours" /> : null}
      </span>
      <span className="setting-value">
        {ofFaces ? (
          <EntityChips
            group={{ refs: faces, read_off: false }}
            names={props.names}
            onShow={props.onShow}
            none="nothing"
            onRemove={(ref) => choose(faces.filter((f) => f !== ref))}
            onAdd={() => choose(adding(faces, props.selection))}
            selected={props.selection.length}
            disabled={props.disabled}
          />
        ) : choices ? (
          <ChoiceChips {...props} />
        ) : open ? null : (
          <>
            <Said text={setting.says} names={props.names} onShow={props.onShow} />{" "}
            <button
              className="link"
              disabled={props.disabled}
              onClick={() => setOpen(true)}
              title="A range in steps, or one value"
            >
              change
            </button>
          </>
        )}
        {mine ? (
          <button
            className="link reset"
            disabled={props.disabled}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              setOpen(false);
              props.onHand({ action: "setting", block: props.block, name: setting.name });
            }}
            title="Back to what the part suggests"
          >
            reset
          </button>
        ) : null}
      </span>
      {open ? (
        <SettingEditor
          block={props.block}
          setting={setting}
          disabled={props.disabled}
          onHand={(action) => {
            setOpen(false);
            props.onHand(action);
          }}
          onDone={() => setOpen(false)}
        />
      ) : null}
    </div>
  );
}

/** A setting's choices as chips: those allowed filled, the others the part offers open - a click
 * switches one on or off, at once. Every one of them on is the part's own choice again. */
function ChoiceChips(props: {
  block: string;
  setting: StudySetting;
  names: Record<string, string>;
  disabled: boolean;
  onHand: (action: HandAction) => void;
  onShow: (refs: string[]) => void;
}) {
  const { setting } = props;
  const domain = setting.domain;
  const all = domain.choices?.length ? domain.choices : (domain.options ?? []);
  const kept = domain.options ?? [];
  const has = (list: (number | string)[], option: number | string) =>
    list.some((o) => String(o) === String(option));
  const unit = typeof all[0] === "number" ? domain.unit : "";
  const toggle = (option: number | string) => {
    const next = all.filter((o) => (String(o) === String(option) ? !has(kept, o) : has(kept, o)));
    if (!next.length) return;
    props.onHand(
      next.length === all.length
        ? { action: "setting", block: props.block, name: setting.name }
        : { action: "setting", block: props.block, name: setting.name, options: next },
    );
  };
  return (
    <span className="choice-chips">
      {all.map((option) => {
        const on = has(kept, option);
        const alone = on && kept.length === 1;
        const text =
          setting.name === "generator" ? (PATTERN_NAMES[String(option)] ?? String(option)) : String(option);
        return (
          <button
            key={String(option)}
            className="choice"
            data-on={on}
            disabled={props.disabled || alone}
            onClick={() => toggle(option)}
            title={
              alone
                ? "The only one left: allow another first"
                : `${on ? "Leave this out" : "Allow this too"}${props.names[String(option)] ? ` - ${props.names[String(option)]}` : ""}`
            }
          >
            {text}
            {unit === "°" ? "°" : ""}
          </button>
        );
      })}
      {unit && unit !== "°" ? <span className="dim">{unit}</span> : null}
      {all.some((option) => HAS_REFERENCE.test(String(option))) ? (
        // Faces or features to choose among - what spokes turn about: shown on the part.
        <button
          className="link"
          onClick={() => props.onShow(all.map(String).filter((o) => HAS_REFERENCE.test(o)))}
          title="Show them on the part"
        >
          show
        </button>
      ) : null}
    </span>
  );
}

/** What a setting does, where its name alone does not say it - for every pattern. */
const HINTS: Record<string, string> = {
  count:
    "How many: the most lines each way for parallel ribs and grids, the most spokes, the number of free lines - round the middle of the floor",
  spacing_mm:
    "How far apart: between lines of parallel ribs and grids, between spokes where they end, between the places free lines may cross",
};

/** A number by hand: a range and its step - five unless you say - or one value, a height in
 * percent, the one or the other chosen at its head. What it shows is kept on Enter, on done, or
 * when the editor is left for anything else, once anything in it was touched - the choice between
 * range and one value included; a range from a value to itself is that value. Escape leaves it as
 * it was. */
function SettingEditor(props: {
  block: string;
  setting: StudySetting;
  disabled: boolean;
  onHand: (action: HandAction) => void;
  onDone: () => void;
}) {
  const { setting } = props;
  const domain = setting.domain;
  const scale = setting.percent ? 100 : 1;
  const unit = setting.percent ? "%" : domain.unit;
  const shown = (value: number | string | null) =>
    typeof value === "number" ? String(Math.round(value * scale * 1000) / 1000) : String(value ?? "");
  const base = { action: "setting" as const, block: props.block, name: setting.name };
  const fixed = domain.low !== null && domain.low === domain.high;
  const [low, setLow] = useState(shown(domain.low));
  const [high, setHigh] = useState(shown(domain.high));
  const [step, setStep] = useState(domain.step === null || fixed ? "5" : shown(domain.step));
  const [one, setOne] = useState(shown(domain.suggested ?? domain.low));
  // A range, or one value - as it is now, until the engineer picks the other.
  const [mode, setMode] = useState<"range" | "one">(fixed ? "one" : "range");
  // Whether anything in it was touched: an editor opened and left alone changes nothing.
  const [touched, setTouched] = useState(false);
  // All of it as it is this instant: a key pressed straight after typing is read against what
  // was typed, not against what was last drawn.
  const now = useRef({ low, high, step, one, mode, touched: false });

  const read = () => {
    const { low: l, high: h, step: s, one: o } = now.current;
    const numbers = [l, h, s].map(Number);
    return {
      numbers,
      ranged: numbers.every(Number.isFinite) && numbers[0] <= numbers[1] && numbers[2] > 0,
      fixable: o.trim() !== "" && Number.isFinite(Number(o)),
      value: Number(o),
    };
  };
  // Done with it: what it shows kept, when anything was touched - unless it is no range or value,
  // which stays to be put right - else closed as it was.
  const done = () => {
    if (props.disabled) return;
    if (!now.current.touched) {
      props.onDone();
      return;
    }
    const { numbers, ranged, fixable, value } = read();
    if (now.current.mode === "one") {
      if (fixable) props.onHand({ ...base, value: value / scale });
    } else if (ranged) {
      props.onHand(
        numbers[0] === numbers[1]
          ? { ...base, value: numbers[0] / scale }
          : { ...base, low: numbers[0] / scale, high: numbers[1] / scale, step: numbers[2] / scale },
      );
    }
  };
  const touch = (change: Partial<typeof now.current>) => {
    now.current = { ...now.current, ...change, touched: true };
    setTouched(true);
  };
  const typing = (set: (value: string) => void, field: "low" | "high" | "step" | "one") =>
    (e: ChangeEvent<HTMLInputElement>) => {
      touch({ [field]: e.target.value });
      set(e.target.value);
    };
  const choose = (next: "range" | "one") => {
    touch({ mode: next });
    setMode(next);
  };
  const { ranged, fixable } = read();
  const wrong = touched && (mode === "one" ? !fixable : !ranged);
  return (
    <div
      className="setting-editor"
      data-typed={touched}
      onBlur={(e: FocusEvent<HTMLDivElement>) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) done();
      }}
      onKeyDown={(e: KeyboardEvent<HTMLDivElement>) => {
        if (e.key === "Enter") done();
        if (e.key === "Escape") props.onDone();
      }}
    >
      <span className="choice-chips editor-mode">
        <button className="choice" data-on={mode === "range"} onClick={() => choose("range")}>
          range
        </button>
        <button className="choice" data-on={mode === "one"} onClick={() => choose("one")}>
          one value
        </button>
      </span>
      {mode === "range" ? (
        <>
          <input className="num" value={low} onChange={typing(setLow, "low")} aria-label="low" autoFocus />
          <span className="dim"> to </span>
          <input className="num" value={high} onChange={typing(setHigh, "high")} aria-label="high" />
          <span className="dim"> {unit} in steps of </span>
          <input className="num" value={step} onChange={typing(setStep, "step")} aria-label="step" />
        </>
      ) : (
        <>
          <input className="num" value={one} onChange={typing(setOne, "one")} aria-label="value" autoFocus />
          <span className="dim"> {unit}</span>
        </>
      )}
      <button disabled={props.disabled || wrong} onClick={done} title="Keep it">
        done
      </button>
      {touched ? (
        <div className="setting-unkept">
          {wrong
            ? mode === "range"
              ? "a range runs from low to high, in steps above nothing"
              : "one value: a number"
            : `not kept yet - Enter, done, or clicking elsewhere keeps ${mode === "range" ? "the range" : "the one value"}; Esc leaves it as it was`}
        </div>
      ) : null}
    </div>
  );
}

/** A rule of a kind the pipeline checks, added to the variant: its kind, what it needs, and the
 * faces selected when it names some. */
function RuleAdd(props: {
  block: string;
  offered: OfferedRule[];
  faces: number;
  disabled: boolean;
  onHand: (action: HandAction) => void;
  onCancel?: () => void;
}) {
  const kinds = props.offered.filter((o) => o.kind !== "keep_clear_of");
  const [kind, setKind] = useState(kinds[0]?.kind ?? "");
  const [values, setValues] = useState<Record<string, string>>({});
  const chosen = kinds.find((o) => o.kind === kind);
  if (!chosen) return null;
  const params = Object.fromEntries(chosen.needs.map((need) => [need, Number(values[need])]));
  const ready =
    chosen.needs.every((need) => Number.isFinite(params[need]) && values[need] !== undefined && values[need] !== "") &&
    (!chosen.names || props.faces > 0);
  return (
    <div className="rule-add">
      <span className="dim">add a rule: </span>
      <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="kind of rule">
        {kinds.map((o) => (
          <option key={o.kind} value={o.kind}>
            {o.says.replace(/\{[^}]+\}/g, "…")}
          </option>
        ))}
      </select>
      {chosen.needs.map((need) => (
        <input
          key={need}
          className="num"
          placeholder={need.replace("_mm", " mm").replace("_", " ")}
          value={values[need] ?? ""}
          onChange={(e) => setValues((was) => ({ ...was, [need]: e.target.value }))}
          aria-label={need}
        />
      ))}
      {chosen.names ? <span className="dim"> · the faces selected ({props.faces})</span> : null}
      <button
        className="link"
        disabled={props.disabled || !ready}
        onClick={() =>
          props.onHand({
            action: "rule",
            block: props.block,
            kind,
            params: chosen.needs.length ? params : undefined,
            refs: undefined,
          })
        }
      >
        add
      </button>
      {props.onCancel ? (
        <button className="link" onClick={props.onCancel}>
          cancel
        </button>
      ) : null}
    </div>
  );
}

/** One of the variant's rules in words, its entities as chips: suggested by the part - a click on
 * the tag makes it yours - or from the drawing; taken out with ×. */
function RuleRow(props: {
  rule: StudyRule;
  names: Record<string, string>;
  disabled: boolean;
  onDrop: (id: string) => void;
  onHand: (action: HandAction) => void;
  onShow: (refs: string[]) => void;
}) {
  const { rule } = props;
  const drawing = rule.source === "drawing";
  return (
    <div className="rule-row" data-changed={rule.changed} title={rule.basis || undefined}>
      <span className="rule-text">
        <Said text={rule.says} names={props.names} onShow={props.onShow} />
      </span>
      {rule.by === "part" && !drawing ? (
        <button
          className="rule-tag"
          disabled={props.disabled}
          onClick={() => props.onHand({ action: "confirm", rule: rule.id })}
          title="Suggested by the part - click to make it yours"
        >
          suggested
        </button>
      ) : drawing ? (
        <span className="rule-tag" title="From the drawing">
          drawing
        </span>
      ) : null}
      {rule.by !== "platform" ? (
        <button
          className="icon"
          disabled={props.disabled}
          onClick={() => props.onDrop(rule.id)}
          title="Take this rule out"
        >
          ×
        </button>
      ) : null}
    </div>
  );
}

/** A rule: how firmly it holds, in words with its entities as chips, and whose it is. */
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
