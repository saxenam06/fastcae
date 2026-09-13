/**
 * The agent, above every tab: the engineer's words - with the faces selected on the part - go to it,
 * it reads the drawing and the part, and it writes the design space on the variant card, which waits
 * there for Accept or Undo. One conversation, whichever tab is open.
 *
 * One line to say something; under it a drawer with what was said, what the agent is doing while it
 * reads, and its answer - opened when something is sent, closed at a click. When it filled the card,
 * only the few lines it asked the engineer to look at are said here, with faces as chips that show
 * them on the part.
 */

import { useCallback, useEffect, useState } from "react";

import { api, type AgentEvent, type AgentMessage } from "../api/client";
import { Said, Written } from "./shared";

// What each of the agent's tools is doing, as the engineer would say it.
const DOING: Record<string, string> = {
  read_study: "reading the design space",
  edit_study: "writing the design space",
  find: "looking for entities",
  describe: "reading entities",
  relate: "relating them to the part",
  measure: "measuring",
  search_drawing: "reading the drawing",
  skill: "reading a skill",
};

interface AgentBarProps {
  /** The faces selected on the part: they go with what is said. */
  selection: number[];
  /** The agent changed the variant card: read it again. */
  onCardChanged: () => void;
  /** Open the variant card, where what the agent wrote waits. */
  onOpenCard: () => void;
  /** Whether the variant card is in view: if not, the answer says where to find it. */
  cardInView: boolean;
  /** Show these faces and features on the part. */
  onShow: (refs: string[]) => void;
}

/** What the agent answered: the lines it asked the engineer to look at, when it filled the card;
 * or what it wrote, when it did not. */
interface Answer {
  filled: boolean;
  attention: string[];
  needed: string[];
  text: string;
}

const NOTHING: Answer = { filled: false, attention: [], needed: [], text: "" };

export function AgentBar(props: AgentBarProps) {
  const { selection, onCardChanged, onShow } = props;
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState<string | null>(null);
  const [answer, setAnswer] = useState<Answer>(NOTHING);
  const [doing, setDoing] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  // The last exchange, as the conversation kept it.
  useEffect(() => {
    api
      .agentHistory()
      .then((history) => {
        const [lastSaid, lastAnswer] = lastExchange(history.messages);
        setSaid(lastSaid);
        setAnswer(lastAnswer);
      })
      .catch(() => undefined);
  }, []);

  const send = useCallback(async () => {
    const message = text.trim();
    if (!message || busy) return;
    setBusy(true);
    setOpen(true);
    setSaid(message);
    setText("");
    setAnswer(NOTHING);
    setDoing([]);
    setError(null);
    try {
      await api.chat(message, selection, (event: AgentEvent) => {
        if (event.type === "token")
          setAnswer((before) => ({ ...before, text: before.text + event.text }));
        else if (event.type === "tool_start")
          setDoing((before) => [...before, DOING[event.name] ?? event.name]);
        else if (event.type === "tool_result" && event.summary.startsWith("refused"))
          setDoing((before) => [...before, event.summary]);
        else if (event.type === "draft")
          setAnswer((before) => ({
            ...before,
            filled: true,
            attention: event.attention,
            needed: event.needed,
          }));
        else if (event.type === "changed" && event.what.includes("draft")) onCardChanged();
        else if (event.type === "error") setError(event.message);
      });
    } catch (caught) {
      setError(String(caught));
    } finally {
      setBusy(false);
    }
  }, [text, busy, selection, onCardChanged]);

  const fresh = useCallback(async () => {
    await api.newChat().catch(() => undefined);
    setSaid(null);
    setAnswer(NOTHING);
    setDoing([]);
    setError(null);
  }, []);

  const something = Boolean(said || answer.text || answer.filled || error);

  return (
    <section className="agent-bar" data-open={open && something}>
      <div className="agent-line">
        <span className="agent-label" title="Reads the drawing and the part, and writes the design space">
          Agent
        </span>
        <input
          value={text}
          disabled={busy}
          placeholder="Say what you want - what to add, where, what must hold. The faces selected go with it."
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void send();
          }}
        />
        <button onClick={() => void send()} disabled={busy || !text.trim()}>
          {busy ? "Reading…" : "Send"}
        </button>
        <span className="dim agent-selected">
          {selection.length ? `${selection.length} faces selected` : "no faces selected"}
        </span>
        {something ? (
          <button
            className="quiet"
            onClick={() => setOpen((was) => !was)}
            title={open ? "Fold the answer away" : "Show the last answer"}
          >
            {open ? "▴ hide" : busy ? "▾ reading…" : "▾ answer"}
          </button>
        ) : null}
        <button className="quiet" onClick={() => void fresh()} disabled={busy}>
          new conversation
        </button>
      </div>
      {open && something ? (
        <div className="agent-drawer">
          {said ? <div className="said-line">&ldquo;{said}&rdquo;</div> : null}
          {doing.length ? <div className="card-note">{doing.join(" · ")}</div> : null}
          <AnswerView
            answer={answer}
            onShow={onShow}
            cardInView={props.cardInView}
            onOpenCard={props.onOpenCard}
          />
          {error ? <div className="warn">{error}</div> : null}
        </div>
      ) : null}
    </section>
  );
}

/** The agent's answer. When it filled the card, the card says what changed: only what it asked
 * the engineer to look at is said here - and where the card is, when it is not in view. */
function AnswerView(props: {
  answer: Answer;
  onShow: (refs: string[]) => void;
  cardInView: boolean;
  onOpenCard: () => void;
}) {
  const { answer, onShow } = props;
  if (answer.filled) {
    return (
      <div className="agent-reply attention">
        {answer.attention.length ? (
          <ul className="written-list">
            {answer.attention.map((line) => (
              <li key={line}>
                <Said text={line} onShow={onShow} />
              </li>
            ))}
          </ul>
        ) : (
          <div className="dim">Wrote the design space: what changed is marked on the variant card.</div>
        )}
        {answer.needed.length ? (
          <div className="dim">Still needed: {answer.needed.join(", ")}.</div>
        ) : null}
        {!props.cardInView ? (
          <button className="link" onClick={props.onOpenCard}>
            open the variant card, on CAD
          </button>
        ) : null}
      </div>
    );
  }
  if (!answer.text) return null;
  return (
    <div className="agent-reply">
      <Written text={answer.text} onShow={onShow} />
    </div>
  );
}

/** The engineer's last words in a conversation, and what came back to them. */
function lastExchange(messages: AgentMessage[]): [string | null, Answer] {
  let at = -1;
  messages.forEach((message, index) => {
    if (message.role === "engineer") at = index;
  });
  if (at < 0) return [null, NOTHING];
  const said = (messages[at] as { text: string }).text.split("\n\n(selected on the part")[0];
  let answer: Answer = NOTHING;
  for (const message of messages.slice(at + 1)) {
    if (message.role === "draft")
      answer = { ...answer, filled: true, attention: message.attention, needed: message.needed };
    else if (message.role === "agent") answer = { ...answer, text: message.text };
  }
  return [said, answer];
}
