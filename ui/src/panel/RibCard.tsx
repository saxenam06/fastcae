/**
 * The rib card: every slot a group of ribs needs, set by the engineer or filled from the part.
 *
 * Start it from faces selected on the part. Each slot shows its value and where that came from -
 * you, selected, the drawing, measured, a default, or needed - and is set in place: faces added
 * from the selection or taken out, numbers stepped, choices picked from a list, or words typed with
 * faces in them as ids. Words the card cannot read are kept and flagged, never guessed at. When
 * nothing is needed and nothing is wrong, make a design: the card is written as a new version of
 * the spec, and the design is made from that.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  CardEdit,
  CardPart,
  CardPaths,
  CardSlot,
  RibCardData,
  Source,
  Verdict,
  VerdictRow,
} from "../api/client";
import { api } from "../api/client";
import type { LineSet } from "../render/renderer";

interface RibCardProps {
  /** The project the card is about. A new one starts the pane afresh. */
  project: string | null;
  /** The faces selected on the part now. */
  selection: number[];
  /** Show these faces and features on the part. */
  onShow: (refs: string[]) => void;
  /** A design was made from the card. */
  onDesign: (verdict: Verdict) => void;
  /** Draw these lines on the part - where the card would put ribs - or none. */
  onPaths: (lines: LineSet | null) => void;
}

/** What became of a stretch of path, by its colour on the part. */
const OUTCOMES: Record<string, { colour: [number, number, number]; label: string }> = {
  rib: { colour: [0.0, 0.62, 0.62], label: "becomes a rib" },
  keep_out: { colour: [0.93, 0.55, 0.1], label: "stops at something to keep clear of" },
  ended_elsewhere: { colour: [0.85, 0.2, 0.2], label: "ends on something not named" },
  too_short: { colour: [0.6, 0.35, 0.8], label: "too short" },
  no_height: { colour: [0.6, 0.35, 0.8], label: "no room for its height" },
  missed: { colour: [0.55, 0.55, 0.55], label: "misses where ribs stand" },
};

function toLines(paths: CardPaths): LineSet {
  const positions = new Float32Array(paths.lines.length * 6);
  const colours = new Float32Array(paths.lines.length * 6);
  paths.lines.forEach((line, index) => {
    positions.set([...line.a, ...line.b], index * 6);
    const colour = (OUTCOMES[line.outcome] ?? OUTCOMES.missed).colour;
    colours.set([...colour, ...colour], index * 6);
  });
  return { positions, colours };
}

const SOURCE_LABEL: Record<Source, string> = {
  you: "you",
  selected: "selected",
  drawing: "drawing",
  measured: "measured",
  default: "default",
  needed: "needed",
};

/** A face or feature id, as the card and the words write it - to find them all, and to ask
 * whether there is one (a global pattern remembers where it last matched). */
const REFERENCE = /\b[a-z_]+:\d+\b/g;
const HAS_REFERENCE = /\b[a-z_]+:\d+\b/;

/** How many faces a row lists before the rest fold away. */
const FOLD = 8;

export function RibCard({ project, selection, onShow, onDesign, onPaths }: RibCardProps) {
  const [card, setCard] = useState<RibCardData | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  // Whether the card has changed since the design the verdict is for.
  const [changed, setChanged] = useState(false);
  // Where the card would put ribs, drawn on the part, redrawn as the card changes.
  const [showPaths, setShowPaths] = useState(false);
  const [paths, setPaths] = useState<CardPaths | null>(null);
  const [pathsNote, setPathsNote] = useState<string | null>(null);

  useEffect(() => {
    setCard(null);
    setVerdict(null);
    setProblem(null);
    setShowPaths(false);
    if (!project) return;
    api
      .card()
      .then((reply) => setCard(reply.card))
      .catch((caught) => setProblem(plain(caught)));
  }, [project]);

  useEffect(() => {
    if (!showPaths || !card?.ready) {
      onPaths(null);
      setPaths(null);
      setPathsNote(showPaths ? "Nothing to draw until the card is ready." : null);
      return;
    }
    let live = true;
    setPathsNote("Placing the ribs to draw them: seconds, or about 2 minutes the first time.");
    const timer = window.setTimeout(() => {
      api
        .cardPaths()
        .then((drawn) => {
          if (!live) return;
          setPaths(drawn);
          setPathsNote(null);
          onPaths(toLines(drawn));
        })
        .catch((caught) => {
          if (live) setPathsNote(plain(caught));
        });
    }, 250);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [showPaths, card, onPaths]);

  // Lines drawn for this card go when it does.
  useEffect(() => () => onPaths(null), [onPaths]);

  const edit = useCallback(async (edits: CardEdit[]) => {
    setProblem(null);
    try {
      setCard((await api.editCard(edits)).card);
      setChanged(true);
    } catch (caught) {
      setProblem(plain(caught));
    }
  }, []);

  const start = useCallback(async () => {
    const set = card?.slots.some((slot) => slot.line || slot.unread);
    const again = selection.length
      ? "Start the card again from the faces selected now? What you set on it is forgotten."
      : "Clear the card? What you set on it is forgotten.";
    if (set && !window.confirm(again)) return;
    setProblem(null);
    setVerdict(null);
    try {
      setCard((await api.startCard(selection)).card);
    } catch (caught) {
      setProblem(plain(caught));
    }
  }, [card, selection]);

  const design = useCallback(
    async (fidelity: "preview" | "full") => {
      setBusy(
        fidelity === "preview"
          ? "Making a preview: writing the spec, placing the ribs, joining them, checking."
          : "Making the full design. Minutes on a large part the first time.",
      );
      setProblem(null);
      try {
        const made = await api.cardDesign(fidelity);
        setVerdict(made.verdict);
        setChanged(false);
        onDesign(made.verdict);
      } catch (caught) {
        setProblem(plain(caught));
      } finally {
        setBusy(null);
      }
    },
    [onDesign],
  );

  if (!project) {
    return (
      <div className="rib-card">
        <div className="card-note">Open a project to put ribs on it.</div>
      </div>
    );
  }

  const faces = selection.length;
  const needed = card?.needed.length ?? 0;
  const wrong = card?.problems.length ?? 0;

  return (
    <div className="rib-card">
      <header className="rib-card-head">
        <span className="card-title">Rib card</span>
        <button
          onClick={start}
          disabled={busy !== null || (!faces && !card?.started)}
          title={
            faces
              ? "Fill the card from the faces selected now: where ribs stand, and what they run between"
              : "Clear the card"
          }
        >
          {faces ? `Start from ${faces} selected` : "Clear"}
        </button>
      </header>

      {!card?.started ? (
        <div className="card-note">
          Select the flat faces ribs stand on - with what they run between, if you like - and
          start the card from them. It fills in what the part and the drawing say, and marks what
          only you can say. Set anything it has wrong: faces, values, or words.
        </div>
      ) : (
        <div className="rib-slots">
          {card.slots.map((slot) => (
            <SlotRow
              key={slot.key}
              slot={slot}
              names={card.names}
              selection={selection}
              disabled={busy !== null}
              onEdit={edit}
              onShow={onShow}
            />
          ))}
        </div>
      )}

      {problem ? <div className="card-note warn">{problem}</div> : null}

      {card?.started ? (
        <footer className="rib-card-foot">
          <div className="rib-card-status" data-ready={card.ready}>
            {card.ready
              ? "ready to make ribs"
              : [needed ? `${needed} needed` : "", wrong ? `${wrong} to fix` : ""]
                  .filter(Boolean)
                  .join(" · ")}
          </div>
          <div className="actions">
            <button
              data-active={showPaths}
              onClick={() => setShowPaths((was) => !was)}
              disabled={!card.ready && !showPaths}
              title="Draw where the ribs would go on the part, before making anything"
            >
              {showPaths ? "Hide paths" : "Show paths"}
            </button>
            <button
              onClick={() => design("preview")}
              disabled={!card.ready || busy !== null}
              title="Write the card as a new version of the spec and make the design on a coarse grid"
            >
              Preview
            </button>
            <button
              onClick={() => design("full")}
              disabled={!card.ready || busy !== null}
              title="The same design at full resolution - what a design is accepted at"
            >
              Full
            </button>
          </div>
          {showPaths ? <PathsKey paths={paths} note={pathsNote} /> : null}
          {busy ? <div className="card-note busy-note">{busy}</div> : null}
          {verdict && !busy ? (
            <>
              {changed ? (
                <div className="card-note">This design is from the card before your last change.</div>
              ) : null}
              <VerdictView verdict={verdict} />
            </>
          ) : null}
        </footer>
      ) : null}
    </div>
  );
}

/** One slot: its label and where its value came from, its controls, and anything wrong. */
function SlotRow(props: {
  slot: CardSlot;
  names: Record<string, string>;
  selection: number[];
  disabled: boolean;
  onEdit: (edits: CardEdit[]) => void;
  onShow: (refs: string[]) => void;
}) {
  const { slot } = props;
  const [typing, setTyping] = useState<string | null>(null);
  const change = (edit: Omit<CardEdit, "slot">) => props.onEdit([{ slot: slot.key, ...edit }]);
  const said = slot.line.startsWith(`${slot.label}: `)
    ? slot.line.slice(slot.label.length + 2)
    : slot.line;
  const others = slot.problems.filter((p) => !p.startsWith("could not read"));

  return (
    <section className="rib-slot" data-source={slot.source}>
      <header>
        <span className="slot-label">{slot.label}</span>
        <span className="chip" data-source={slot.source}>
          {SOURCE_LABEL[slot.source]}
        </span>
        <span className="spacer" />
        <button
          className="icon"
          disabled={props.disabled}
          onClick={() => setTyping(slot.unread ?? (said || slot.words))}
          title="Say it in words - faces as face:N"
        >
          words
        </button>
        {slot.line || slot.unread ? (
          <button
            className="icon"
            disabled={props.disabled}
            onClick={() => change({ reset: true })}
            title="Forget what you set here: back to what the part and the drawing say"
          >
            reset
          </button>
        ) : null}
      </header>

      <div className="slot-parts">
        {slot.parts.map((part, index) => (
          <Part
            key={`${part.type}-${"field" in part ? part.field : index}`}
            part={part}
            names={props.names}
            selection={props.selection}
            disabled={props.disabled}
            onChange={change}
            onShow={props.onShow}
          />
        ))}
      </div>

      {typing !== null ? (
        <WordsLine
          initial={typing}
          names={props.names}
          selection={props.selection}
          onShow={props.onShow}
          onCancel={() => setTyping(null)}
          onDone={(words) => {
            setTyping(null);
            change({ words });
          }}
        />
      ) : slot.typed && slot.line && !slot.unread ? (
        <div className="slot-said" title="Your words, as the spec will quote them">
          &ldquo;
          <Said text={said} names={props.names} onShow={props.onShow} />
          &rdquo;
        </div>
      ) : null}

      {slot.unread ? (
        <div className="slot-problem">
          could not read &ldquo;{slot.unread}&rdquo; - set it with the controls, or say it with a
          value and faces
        </div>
      ) : null}
      {others.map((text) => (
        <div key={text} className="slot-problem">
          {text}
        </div>
      ))}
      {slot.note && slot.source !== "you" ? <div className="slot-note">{slot.note}</div> : null}
    </section>
  );
}

function Part(props: {
  part: CardPart;
  names: Record<string, string>;
  selection: number[];
  disabled: boolean;
  onChange: (edit: Omit<CardEdit, "slot">) => void;
  onShow: (refs: string[]) => void;
}) {
  const { part } = props;
  if (part.type === "faces") return <FacesPart {...props} part={part} />;
  if (part.type === "list") {
    return (
      <div className="part" data-type="list">
        <span className="part-label">{part.label}</span>
        <Refs refs={part.refs} names={props.names} onShow={props.onShow} />
        {part.refs.length ? (
          <button className="link" onClick={() => props.onShow(part.refs)}>
            show
          </button>
        ) : (
          <span className="dim">nothing</span>
        )}
      </div>
    );
  }
  if (part.type === "number") return <NumberPart {...props} part={part} />;
  if (part.type === "choice") {
    const current = part.value === null ? "" : String(part.value);
    return (
      <label className="part" data-type="choice">
        {part.label ? <span className="part-label">{part.label}</span> : null}
        <select
          value={current}
          disabled={props.disabled}
          onChange={(event) => {
            const option = part.options.find((o) => String(o.value) === event.target.value);
            if (option) props.onChange({ field: part.field, value: option.value });
          }}
        >
          {current === "" ? <option value="">-</option> : null}
          {part.options.map((option) => (
            <option key={String(option.value)} value={String(option.value)}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
    );
  }
  return (
    <label className="part" data-type="toggle">
      <input
        type="checkbox"
        checked={part.value}
        disabled={props.disabled}
        onChange={(event) => props.onChange({ field: part.field, value: event.target.checked })}
      />
      <span>{part.label}</span>
    </label>
  );
}

/** Faces in a slot: each one shown on the part by a click, taken out by its cross; the faces
 * selected now added, or put in place of them. */
function FacesPart(props: {
  part: Extract<CardPart, { type: "faces" }>;
  names: Record<string, string>;
  selection: number[];
  disabled: boolean;
  onChange: (edit: Omit<CardEdit, "slot">) => void;
  onShow: (refs: string[]) => void;
}) {
  const { part, selection } = props;
  const set = part.refs.length > 0;
  const refs = set ? part.refs : (part.shown ?? []);
  const picked = selection.map((f) => `face:${f}`);
  const count = selection.length;
  if (part.single && part.options) {
    // One face out of what it could be: a list, and the selection as another way to say it.
    const current = refs[0] ?? "";
    return (
      <div className="part" data-type="faces">
        {part.label ? <span className="part-label">{part.label}</span> : null}
        <select
          value={current}
          disabled={props.disabled}
          onChange={(event) => {
            const picked = event.target.value;
            if (!picked) return;
            props.onChange({ field: part.field, replace: [picked] });
            // Seen on the part as it is picked: a name in a list means little on its own.
            props.onShow([picked]);
          }}
        >
          {current ? null : (
            <option value="">
              {part.options.length ? "pick one…" : "none found - select one, then use selected"}
            </option>
          )}
          {part.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {current ? (
          <button className="link" onClick={() => props.onShow([current])} title="Show it">
            show
          </button>
        ) : null}
        <button
          className="link"
          disabled={props.disabled || count !== 1}
          onClick={() => props.onChange({ field: part.field, replace: picked, selected: true })}
          title={count === 1 ? "Use the face selected now" : "Select one face on the part"}
        >
          use selected
        </button>
      </div>
    );
  }
  return (
    <div className="part" data-type="faces" data-default={!set && refs.length > 0}>
      {part.label ? <span className="part-label">{part.label}</span> : null}
      <Refs
        refs={refs}
        names={props.names}
        onShow={props.onShow}
        onRemove={
          props.disabled || (part.single && !set)
            ? undefined
            : (ref) => props.onChange({ field: part.field, remove: [ref] })
        }
      />
      {!refs.length ? <span className="dim">none</span> : null}
      <span className="part-actions">
        {part.single ? (
          <button
            className="link"
            disabled={props.disabled || count !== 1}
            onClick={() =>
              props.onChange({ field: part.field, replace: picked, selected: true })
            }
            title={count === 1 ? "Use the face selected now" : "Select one face on the part"}
          >
            use selected
          </button>
        ) : (
          <>
            <button
              className="link"
              disabled={props.disabled || !count}
              onClick={() => props.onChange({ field: part.field, add: picked, selected: true })}
              title={`Add the ${count} faces selected now to ${part.label || "these"}`}
            >
              {count ? `add the ${count} selected` : "add selected"}
            </button>
            {refs.length ? (
              <button
                className="link"
                disabled={props.disabled || !count}
                onClick={() =>
                  props.onChange({ field: part.field, replace: picked, selected: true })
                }
                title="Put the faces selected now in place of these"
              >
                {count ? `replace with the ${count}` : "replace"}
              </button>
            ) : null}
            {refs.length > 1 ? (
              <button className="link" onClick={() => props.onShow(refs)} title="Show them all">
                show
              </button>
            ) : null}
          </>
        )}
      </span>
    </div>
  );
}

/** Ids as chips: a click shows one on the part, its cross takes it out. Long lists fold. */
function Refs(props: {
  refs: string[];
  names: Record<string, string>;
  onShow: (refs: string[]) => void;
  onRemove?: (ref: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const shown = open ? props.refs : props.refs.slice(0, FOLD);
  return (
    <span className="refs">
      {shown.map((ref) => (
        <span key={ref} className="ref-chip">
          <button onClick={() => props.onShow([ref])} title={props.names[ref] ?? ref}>
            {ref}
          </button>
          {props.onRemove ? (
            <button className="remove" onClick={() => props.onRemove?.(ref)} title="Take it out">
              ×
            </button>
          ) : null}
        </span>
      ))}
      {props.refs.length > FOLD ? (
        <button className="link" onClick={() => setOpen((was) => !was)}>
          {open ? "fewer" : `+${props.refs.length - FOLD} more`}
        </button>
      ) : null}
    </span>
  );
}

/** A number with its unit, stepped up and down by the arrows or the keys, or typed. Blank clears
 * it where it may be left out. */
function NumberPart(props: {
  part: Extract<CardPart, { type: "number" }>;
  disabled: boolean;
  onChange: (edit: Omit<CardEdit, "slot">) => void;
}) {
  const { part } = props;
  const [text, setText] = useState(format(part.value));
  const [editing, setEditing] = useState(false);
  useEffect(() => {
    if (!editing) setText(format(part.value));
  }, [part.value, editing]);

  const send = (value: number | null) => {
    if (value === part.value) return;
    props.onChange({ field: part.field, value });
  };
  const commit = () => {
    setEditing(false);
    const trimmed = text.trim();
    if (!trimmed) {
      if (part.value !== null) send(null);
      return;
    }
    const value = Number(trimmed.replace(",", "."));
    if (Number.isFinite(value)) send(clamp(value, part.min));
    else setText(format(part.value));
  };
  const step = (sense: 1 | -1) => {
    const from = part.value ?? part.min ?? 0;
    const next = Math.round((from + sense * part.step) / part.step) * part.step;
    send(clamp(Number(next.toFixed(3)), part.min));
  };

  return (
    <label className="part" data-type="number" data-active={part.active}>
      {part.label ? <span className="part-label">{part.label}</span> : null}
      <span className="stepper">
        <input
          value={text}
          disabled={props.disabled}
          inputMode="decimal"
          onFocus={() => setEditing(true)}
          onChange={(event) => setText(event.target.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === "Enter") (event.target as HTMLInputElement).blur();
            if (event.key === "Escape") {
              setText(format(part.value));
              setEditing(false);
            }
            if (event.key === "ArrowUp" || event.key === "ArrowDown") {
              event.preventDefault();
              step(event.key === "ArrowUp" ? 1 : -1);
            }
          }}
        />
        <span className="arrows">
          <button tabIndex={-1} disabled={props.disabled} onClick={() => step(1)} title="Up">
            ▴
          </button>
          <button tabIndex={-1} disabled={props.disabled} onClick={() => step(-1)} title="Down">
            ▾
          </button>
        </span>
      </span>
      {part.unit ? <span className="unit">{part.unit}</span> : null}
    </label>
  );
}

/** Words for one slot, kept as typed. Faces go in as ids - typed, or put in from the selection. */
function WordsLine(props: {
  initial: string;
  names: Record<string, string>;
  selection: number[];
  onShow: (refs: string[]) => void;
  onDone: (words: string) => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState(props.initial);
  const box = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const input = box.current;
    if (!input) return;
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
  }, []);

  const putSelection = () => {
    const input = box.current;
    if (!input || !props.selection.length) return;
    const ids = props.selection.map((f) => `face:${f}`).join(", ");
    const at = input.selectionStart ?? text.length;
    const end = input.selectionEnd ?? at;
    const before = text.slice(0, at);
    const after = text.slice(end);
    const lead = before && !/\s$/.test(before) ? " " : "";
    const tail = after && !/^[\s,.]/.test(after) ? " " : "";
    const next = `${before}${lead}${ids}${tail}${after}`;
    setText(next);
    const caret = (before + lead + ids).length;
    requestAnimationFrame(() => {
      input.focus();
      input.setSelectionRange(caret, caret);
    });
  };

  return (
    <div className="words-line">
      <div className="words-edit">
        <input
          ref={box}
          value={text}
          placeholder="say it in words - faces as face:N"
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") props.onDone(text);
            if (event.key === "Escape") props.onCancel();
          }}
        />
        <button
          className="link"
          disabled={!props.selection.length}
          onMouseDown={(event) => event.preventDefault()}
          onClick={putSelection}
          title="Put the faces selected now into the words, where the cursor is"
        >
          + {props.selection.length || ""} selected
        </button>
        <button onClick={() => props.onDone(text)}>Set</button>
        <button className="icon" onClick={props.onCancel} title="Leave it as it was">
          ×
        </button>
      </div>
      {HAS_REFERENCE.test(text) ? (
        <div className="slot-said">
          <Said text={text} names={props.names} onShow={props.onShow} />
        </div>
      ) : null}
    </div>
  );
}

/** Words with the faces in them as chips. */
function Said(props: { text: string; names: Record<string, string>; onShow: (refs: string[]) => void }) {
  const pieces: (string | { ref: string })[] = [];
  let last = 0;
  for (const match of props.text.matchAll(REFERENCE)) {
    const at = match.index ?? 0;
    if (at > last) pieces.push(props.text.slice(last, at));
    pieces.push({ ref: match[0] });
    last = at + match[0].length;
  }
  if (last < props.text.length) pieces.push(props.text.slice(last));
  return (
    <>
      {pieces.map((piece, index) =>
        typeof piece === "string" ? (
          <span key={index}>{piece}</span>
        ) : (
          <button
            key={index}
            className="ref-inline"
            onClick={() => props.onShow([piece.ref])}
            title={props.names[piece.ref] ?? piece.ref}
          >
            {piece.ref}
          </button>
        ),
      )}
    </>
  );
}

/** What the lines on the part mean, with how many of each, and the count in words. */
function PathsKey({ paths, note }: { paths: CardPaths | null; note: string | null }) {
  if (note || !paths) return <div className="card-note">{note}</div>;
  const counts = new Map<string, number>();
  for (const line of paths.lines) counts.set(line.outcome, (counts.get(line.outcome) ?? 0) + 1);
  return (
    <div className="paths-key">
      <div className="verdict-line">{paths.summary}</div>
      {[...counts.entries()].map(([outcome, count]) => {
        const known = OUTCOMES[outcome] ?? OUTCOMES.missed;
        const [r, g, b] = known.colour.map((c) => Math.round(c * 255));
        return (
          <span key={outcome} className="paths-key-item">
            <span className="swatch" style={{ background: `rgb(${r}, ${g}, ${b})` }} />
            {count} {known.label}
          </span>
        );
      })}
    </div>
  );
}

/** What the design came out as: the outcome, and whatever did not pass. The rest folds away; the
 * Generate tab has it all. */
function VerdictView({ verdict }: { verdict: Verdict }) {
  const [open, setOpen] = useState(false);
  const rows = [...verdict.constraints, ...verdict.checks];
  // How many paths became ribs, and why the rest did not, is always worth reading.
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
        cm³ · {verdict.fidelity} · spec v{verdict.spec_version} · {verdict.seconds} s
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

function format(value: number | null): string {
  return value === null ? "" : String(Number(value.toFixed(3)));
}

function clamp(value: number, least: number | null): number {
  return least === null ? value : Math.max(value, least);
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
