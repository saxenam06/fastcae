/**
 * The agent, above every tab: the engineer's words - with what is in focus on the screen - go to
 * it; it reads the pipeline, its entities and the part, shows what it talks about, and records an
 * answer only when the engineer's words give it. One conversation, whichever tab is open.
 *
 * One line to say something; under it a drawer with what was said, what the agent is doing while it
 * reads, and its answer - opened when something is sent, closed at a click. Entity ids in the answer
 * are chips: a click brings one into focus.
 */

import { useCallback, useEffect, useState } from "react";

import { api, type AgentEvent, type AgentMessage } from "../api/client";

// What each of the agent's tools is doing, as the engineer would say it.
const DOING: Record<string, string> = {
  pipeline: "reading the pipeline",
  entities: "looking for entities",
  entity: "reading an entity",
  show: "showing you",
  answer: "recording your answer",
  derive: "deriving the design space again",
  find: "looking at the part",
  describe: "reading the part",
  relate: "relating it to the part",
  measure: "measuring",
  search_drawing: "reading the drawing",
};

/** An entity's id as the pipeline names it: ``interface:bore:196``, ``group:BORE_MAIN_S2``. */
const ENTITY_ID = /\b[a-z_]+(?::[A-Za-z0-9_.-]*[A-Za-z0-9_])+/g;

interface AgentBarProps {
  /** The entities in focus on the screen: they go with what is said. */
  focus: string[];
  /** Bring these entities into focus, on their canvases. */
  onShow: (ids: string[]) => void;
  /** The agent is deriving the design space again: follow it on the pipeline. */
  onDerive: () => void;
  /** The agent changed something - answers, the space: read it again. */
  onChanged: (what: string[]) => void;
}

export function AgentBar(props: AgentBarProps) {
  const { focus, onShow, onDerive, onChanged } = props;
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
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
    setAnswer("");
    setDoing([]);
    setError(null);
    try {
      await api.chat(message, focus, (event: AgentEvent) => {
        if (event.type === "token") setAnswer((before) => before + event.text);
        else if (event.type === "tool_start") {
          setDoing((before) => [...before, DOING[event.name] ?? event.name]);
          if (event.name === "derive") onDerive();
        } else if (event.type === "tool_result" && event.summary.startsWith("refused"))
          setDoing((before) => [...before, event.summary]);
        else if (event.type === "show" && event.ids.length) onShow(event.ids);
        else if (event.type === "changed" && event.what.length) onChanged(event.what);
        else if (event.type === "error") setError(event.message);
      });
    } catch (caught) {
      setError(String(caught));
    } finally {
      setBusy(false);
    }
  }, [text, busy, focus, onShow, onDerive, onChanged]);

  const fresh = useCallback(async () => {
    await api.newChat().catch(() => undefined);
    setSaid(null);
    setAnswer("");
    setDoing([]);
    setError(null);
  }, []);

  const something = Boolean(said || answer || error);

  return (
    <section className="agent-bar" data-open={open && something}>
      <div className="agent-line">
        <span className="agent-label" title="Reads the pipeline and the part, and settles what the files leave open">
          Agent
        </span>
        <input
          value={text}
          disabled={busy}
          placeholder="Ask what was read, why a face is frozen, where metal may go - or answer a question in your words."
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") void send();
          }}
        />
        <button onClick={() => void send()} disabled={busy || !text.trim()}>
          {busy ? "Reading…" : "Send"}
        </button>
        <span className="dim agent-selected" title={focus.join(", ")}>
          {focus.length ? `${focus[0]}${focus.length > 1 ? ` +${focus.length - 1}` : ""} in focus` : "nothing in focus"}
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
          {answer ? (
            <div className="agent-reply">
              {answer
                .replace(/\*\*|__|`/g, "")
                .split("\n")
                .filter((line) => line.trim())
                .map((line, index) => (
                  <p key={index}>
                    <WithIds text={line} onShow={onShow} />
                  </p>
                ))}
            </div>
          ) : null}
          {error ? <div className="warn">{error}</div> : null}
        </div>
      ) : null}
    </section>
  );
}

/** A line of the answer with every entity id in it as a chip that brings it into focus. */
function WithIds({ text, onShow }: { text: string; onShow: (ids: string[]) => void }) {
  const pieces: (string | { id: string })[] = [];
  let last = 0;
  for (const match of text.matchAll(ENTITY_ID)) {
    const at = match.index ?? 0;
    if (at > last) pieces.push(text.slice(last, at));
    pieces.push({ id: match[0] });
    last = at + match[0].length;
  }
  if (last < text.length) pieces.push(text.slice(last));
  return (
    <>
      {pieces.map((piece, index) =>
        typeof piece === "string" ? (
          <span key={index}>{piece}</span>
        ) : (
          <button
            key={index}
            className="ref-inline"
            onClick={() => onShow([piece.id])}
            title={`show ${piece.id}`}
          >
            {piece.id}
          </button>
        ),
      )}
    </>
  );
}

/** The engineer's last words in a conversation, and what came back to them. */
function lastExchange(messages: AgentMessage[]): [string | null, string] {
  let at = -1;
  messages.forEach((message, index) => {
    if (message.role === "engineer") at = index;
  });
  if (at < 0) return [null, ""];
  const said = (messages[at] as { text: string }).text.split("\n\n(in focus on the screen")[0];
  let answer = "";
  for (const message of messages.slice(at + 1)) {
    if (message.role === "agent") answer = message.text;
  }
  return [said, answer];
}
