/**
 * The rail for the Generate tab: what the engineer says, and why the study is what it is.
 *
 * The study card is the one structured view of the study - every block, setting and rule, what
 * changed, the designs and their verdicts - so none of that is here. Here is what the card does not
 * show: the conversation with the agent, the engineer's words the study rests on, each face in them
 * a chip that shows it on the part, and the study's versions, each with what it changed.
 */

import type { StudyInfo } from "../api/client";
import { SayWhat } from "./SayWhat";
import { Said } from "./shared";

export interface GenerateLayers {
  /** The part as its CAD describes it. */
  geometry: boolean;
  /** The design's new surfaces: ribs and fillets. */
  design: boolean;
}

export const GENERATE_COLOURS: Record<keyof GenerateLayers, string> = {
  geometry: "#a5a9a4",
  design: "#0e6e74",
};

const GENERATE_LABELS: Record<keyof GenerateLayers, string> = {
  geometry: "Part",
  design: "Ribs and fillets",
};

interface GenerateIndexProps {
  layers: GenerateLayers;
  onLayers: (layers: GenerateLayers) => void;
  study: StudyInfo | null;
  error: string | null;
  /** The faces selected on the part: they go with what the engineer says. */
  selection: number[];
  /** The agent filled the card: read it again, and show it. */
  onCardChanged: () => void;
  /** Show these faces and features on the part. */
  onShow: (refs: string[]) => void;
}

export function GenerateIndex(props: GenerateIndexProps) {
  const { study, onShow } = props;
  const current = study?.current;
  const versions = [...(study?.versions ?? [])].reverse();

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

      <SayWhat
        selection={props.selection}
        onCardChanged={props.onCardChanged}
        onShow={onShow}
      />

      <section className="section">
        <header>
          The study rests on
          {current ? (
            <span className="detail">
              {" "}
              {study?.study} · version {current.version}
            </span>
          ) : null}
        </header>
        <div className="body">
          {!current ? (
            <div className="card-note">
              No study yet. Say what you want above - with faces selected on the part if you like -
              and accept what the study card then shows.
            </div>
          ) : (
            <>
              <div className="words">
                {current.words.map((word) => (
                  <p key={word.id}>
                    <span className="mono dim">{word.id}</span> &ldquo;
                    <Said text={word.text} onShow={onShow} />
                    &rdquo;
                  </p>
                ))}
              </div>
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
                            <Said text={v.note} onShow={onShow} />
                          </>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </>
          )}
          {props.error ? <div className="warn">{props.error}</div> : null}
        </div>
      </section>
    </nav>
  );
}
