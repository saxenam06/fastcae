/**
 * Say what you want: the engineer's words, with the faces selected, go to the agent, which reads the
 * part and writes the study. The study card shows what changed, and waits for Accept or Undo.
 *
 * Nothing is decided here, and nothing the card shows is said again. This shows what was said,
 * what the agent is doing while it reads, and its answer: when it filled the card, only the few
 * lines it asked the engineer to look at - with faces as chips that show them on the part.
 */

import { useCallback, useEffect, useState } from "react";

import { api, type AgentEvent, type AgentMessage } from "../api/client";
import { Said, Written } from "./shared";

// What each of the agent's tools is doing, as the engineer would say it.
const DOING: Record<string, string> = {
  read_study: "reading the study",
  edit_study: "writing the study",
  find: "looking for entities",
  describe: "reading entities",
  relate: "relating them to the part",
  measure: "measuring",
  search_drawing: "reading the drawing",
  skill: "reading a skill",
};

interface SayWhatProps {
  /** The faces selected on the part: they go with what is said. */
  selection: number[];
  /** The agent filled the card: read it again, and show it. */
  onCardChanged: () => void;
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

export function SayWhat({ selection, onCardChanged, onShow }: SayWhatProps) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState<string | null>(null);
  const [answer, setAnswer] = useState<Answer>(NOTHING);
  const [doing, setDoing] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  // The last exchange, as the conversation kept it: the pane comes and goes with the tab.
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

  return (
    <section className="section say-what">
      <header>
        Say what you want
        <button className="link" onClick={() => void fresh()} disabled={busy}>
          new conversation
        </button>
      </header>
      <div className="body">
        <textarea
          value={text}
          rows={3}
          disabled={busy}
          placeholder="What to add, where, and what must hold - the faces selected go with it"
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) void send();
          }}
        />
        <div className="actions">
          <button onClick={() => void send()} disabled={busy || !text.trim()}>
            {busy ? "Reading…" : "Send"}
          </button>
          <span className="dim">
            {selection.length ? `${selection.length} faces selected` : "no faces selected"} ·
            Ctrl+Enter sends
          </span>
        </div>
        {said ? <div className="said-line">&ldquo;{said}&rdquo;</div> : null}
        {doing.length ? <div className="card-note">{doing.join(" · ")}</div> : null}
        <AnswerView answer={answer} busy={busy} onShow={onShow} />
        {error ? <div className="warn">{error}</div> : null}
      </div>
    </section>
  );
}

/** The agent's answer. When it filled the card, the card says what changed: only what it asked
 * the engineer to look at is said here. */
function AnswerView(props: { answer: Answer; busy: boolean; onShow: (refs: string[]) => void }) {
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
          <div className="dim">Wrote the study: what changed is marked on the study card.</div>
        )}
        {answer.needed.length ? (
          <div className="dim">Still needed: {answer.needed.join(", ")}.</div>
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
