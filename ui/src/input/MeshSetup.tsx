/**
 * Input → Mesh & setup: the deck's mesh, and every support, coupling and load where the deck puts
 * it, under the deck's own names. Nothing here is fastcae's: it is what the engineer's deck says,
 * read and drawn.
 */

import { useMemo, useState } from "react";
import type { DeckGroup } from "../api/simulate";
import { FE_COLOURS } from "../render/fe";
import { CameraLink, FeStage } from "../stage/FeStage";
import type { Hovered } from "../stage/FeStage";
import type { DeckState } from "./useDeck";
import { Provenance, fmtCount, fmtNumber } from "./shared";

export interface MeshView {
  link: CameraLink;
  edges: boolean;
  setEdges: (v: boolean) => void;
  glyphs: boolean;
  setGlyphs: (v: boolean) => void;
  patches: boolean;
  setPatches: (v: boolean) => void;
  hovered: Hovered | null;
  setHovered: (h: Hovered | null) => void;
  focus: string | null;
  setFocus: (g: string | null) => void;
}

export function useMeshView(): MeshView {
  const link = useMemo(() => new CameraLink(), []);
  const [edges, setEdges] = useState(true);
  const [glyphs, setGlyphs] = useState(true);
  const [patches, setPatches] = useState(true);
  const [hovered, setHovered] = useState<Hovered | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  return { link, edges, setEdges, glyphs, setGlyphs, patches, setPatches, hovered, setHovered, focus, setFocus };
}

const ROLE_ORDER = ["distributing coupling", "rigid coupling", "held", "loaded", "signal"];

function roleColour(roles: string[]): string {
  if (roles.includes("distributing coupling")) return rgb(FE_COLOURS.distributing);
  if (roles.includes("rigid coupling")) return rgb(FE_COLOURS.rigid);
  if (roles.includes("held") || roles.includes("rigid coupling reference")) return rgb(FE_COLOURS.support);
  if (roles.includes("loaded") || roles.includes("distributing coupling reference")) return rgb(FE_COLOURS.x);
  return "transparent";
}

function rgb(c: number[]): string {
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export function MeshRail({ state, view }: { state: DeckState; view: MeshView }) {
  const { deck } = state;
  if (!deck) return <div className="rail-note">{state.loading ? "reading the deck…" : state.error ?? ""}</div>;
  if (!deck.present) return <MissingDeck files={deck.files} />;
  const setup = deck.setup!;
  const groups = (deck.groups ?? []).filter((g) => g.roles.length);
  const others = (deck.groups ?? []).filter((g) => !g.roles.length);
  const byRole = (g: DeckGroup) => Math.min(...g.roles.map((r) => (ROLE_ORDER.indexOf(r) + 100) % 100));
  groups.sort((a, b) => byRole(a) - byRole(b) || a.name.localeCompare(b.name));
  const sets = [...new Set([...setup.held, ...setup.rigid, ...setup.distributing, ...setup.nodal_loads].map((x) => x.load_set))];
  return (
    <>
      <section className="section">
        <header>
          Solver deck <Provenance kind="imported" />
        </header>
        <div className="deck-files">
          {deck.files.map((f) => (
            <div key={`${f.role}${f.name}`} className="deck-file" data-present={f.present}>
              <span className="mono">{f.name ?? "—"}</span>
              <span className="dim">{f.present ? f.role : `no ${f.role}`}</span>
            </div>
          ))}
        </div>
      </section>
      <section className="section">
        <header>Mesh</header>
        <dl className="kv body">
          {Object.entries(deck.mesh!.cells).map(([kind, count]) => (
            <FragmentRow key={kind} label={kind} value={fmtCount(count)} />
          ))}
          <FragmentRow label="nodes" value={fmtCount(deck.mesh!.nodes)} />
          {deck.mesh!.unknowns ? <FragmentRow label="unknowns" value={fmtCount(deck.mesh!.unknowns)} derived /> : null}
        </dl>
      </section>
      <section className="section">
        <header>
          Material <span className="count">{setup.materials.length}</span>
        </header>
        <dl className="kv body">
          {setup.materials.map((m) => (
            <FragmentRow
              key={m.name}
              label={m.name}
              value={`E ${fmtNumber(m.young)} · ν ${m.poisson}${m.density ? ` · ρ ${m.density}` : ""} → ${m.groups.join(", ") || "all"}`}
            />
          ))}
        </dl>
      </section>
      <section className="section">
        <header>
          Groups acted on <span className="count">{groups.length}</span>
        </header>
        <div className="layers">
          {groups.map((g) => (
            <button
              key={g.name}
              data-on={view.focus === null || view.focus === g.name}
              onMouseEnter={() => view.setFocus(g.name)}
              onMouseLeave={() => view.setFocus(null)}
              title={g.roles.join(", ")}
            >
              <span className="swatch" style={{ background: roleColour(g.roles) }} />
              <span className="mono">{g.name}</span>
              <span className="detail">
                {g.roles[0]} · {fmtCount(g.count)}
              </span>
            </button>
          ))}
        </div>
        {others.length ? <div className="body dim">and {others.length} groups the setup does not use</div> : null}
      </section>
      <section className="section">
        <header>
          Load sets <span className="count">{sets.length}</span>
        </header>
        <div className="body load-sets">
          {sets.map((name) => {
            const held = setup.held.filter((x) => x.load_set === name);
            const rigid = setup.rigid.filter((x) => x.load_set === name);
            const dist = setup.distributing.filter((x) => x.load_set === name);
            const loads = setup.nodal_loads.filter((x) => x.load_set === name);
            const active = !setup.analysis || setup.analysis.load_sets.includes(name);
            return (
              <div key={name} className="load-set" data-active={active}>
                <div className="mono load-set-name">{name}</div>
                <div className="dim">
                  {[
                    held.length ? `${held.reduce((n, h) => n + h.groups.length, 0)} held` : "",
                    rigid.length ? `${rigid.length} rigid` : "",
                    dist.length ? `${dist.length} distributing` : "",
                    loads.length ? `${loads.length} nodal loads` : "",
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                  {active ? "" : " · not applied"}
                </div>
                {loads.map((l) => (
                  <div key={l.group} className="load-row num">
                    <span>{l.group}</span>
                    <span>
                      {Object.entries(l.values)
                        .filter(([, v]) => v)
                        .map(([k, v]) => `${k} ${fmtNumber(v)}`)
                        .join("  ")}
                    </span>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </section>
      <section className="section">
        <header>
          Signals the deck reads <span className="count">{setup.outputs.length}</span>
        </header>
        <div className="body">
          {setup.outputs.map((o) => (
            <div key={o.name} className="load-row num">
              <span>{o.name}</span>
              <span className="dim">
                {o.field} {o.components ? o.components.join(" ") : "all"} at {o.group}
              </span>
            </div>
          ))}
        </div>
      </section>
      <section className="section">
        <header>Analysis</header>
        <dl className="kv body">
          <FragmentRow label="kind" value={setup.analysis?.kind ?? "—"} />
          <FragmentRow label="solver" value={String(setup.analysis?.solver?.METHODE ?? "—")} />
          <FragmentRow label="fields" value={(setup.analysis?.written ?? []).join(" ")} />
        </dl>
        {[...(deck.skipped ?? []), ...setup.not_read, ...(deck.warnings ?? [])].length ? (
          <div className="body warn-list">
            {[...(deck.skipped ?? []), ...setup.not_read].map((line) => (
              <div key={line}>not read: {line}</div>
            ))}
            {(deck.warnings ?? []).map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>
        ) : null}
      </section>
    </>
  );
}

function FragmentRow({ label, value, derived }: { label: string; value: string; derived?: boolean }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>
        {value} {derived ? <Provenance kind="derived" small /> : null}
      </dd>
    </>
  );
}

export function MissingDeck({ files }: { files: { role: string; name: string | null; present: boolean }[] }) {
  return (
    <section className="section">
      <header>Solver deck</header>
      <div className="body">
        <p className="dim">
          Not provided. Put the baseline's Code_Aster deck in the project folder - its .export, .comm and
          MED mesh - and the results it wrote (.rmed), then extract again.
        </p>
        {files.map((f) => (
          <div key={f.role} className="deck-file" data-present={f.present}>
            <span className="mono">{f.name ?? "—"}</span>
            <span className="dim">{f.present ? f.role : `no ${f.role}`}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

export function MeshStage({ state, view }: { state: DeckState; view: MeshView }) {
  const { deck, skin } = state;
  const focusIndex = view.focus && skin ? skin.groupNames.indexOf(view.focus) : -1;
  const hoveredIndex = view.hovered?.pick.kind === "group" ? view.hovered.pick.index : focusIndex;
  if (!deck?.present) {
    return <div className="stage-page"><div className="later"><h2>Mesh &amp; setup</h2><p>No solver deck in this project.</p></div></div>;
  }
  return (
    <>
      <FeStage
        skin={skin}
        glyphs={state.glyphs}
        mode={view.patches ? "patches" : "plain"}
        groupColours={state.colours}
        edges={view.edges}
        showGlyphs={view.glyphs}
        link={view.link}
        bbox={deck.mesh?.bbox_mm}
        frameKey="deck"
        hoveredGroup={hoveredIndex}
        onHover={view.setHovered}
        caption={
          <>
            <b>{deck.files.find((f) => f.role === "mesh")?.name}</b> <Provenance kind="imported" />
          </>
        }
      />
      <div className="overlay">
        <button data-active={view.edges} onClick={() => view.setEdges(!view.edges)}>
          edges
        </button>
        <button data-active={view.patches} onClick={() => view.setPatches(!view.patches)}>
          groups
        </button>
        <button data-active={view.glyphs} onClick={() => view.setGlyphs(!view.glyphs)}>
          supports · couplings · loads
        </button>
      </div>
      <div className="fe-key">
        <span><i style={{ background: rgb(FE_COLOURS.distributing) }} /> distributing coupling</span>
        <span><i style={{ background: rgb(FE_COLOURS.rigid) }} /> rigid coupling</span>
        <span><i style={{ background: rgb(FE_COLOURS.spokes) }} /> spokes</span>
        <span><i style={{ background: rgb(FE_COLOURS.support) }} /> held</span>
        <span><i style={{ background: rgb(FE_COLOURS.x) }} /><i style={{ background: rgb(FE_COLOURS.y) }} /><i style={{ background: rgb(FE_COLOURS.z) }} /> force X Y Z</span>
      </div>
      <div className="fe-readout">
        {view.hovered ? (
          <>
            <b className="mono">{view.hovered.name}</b>{" "}
            <span className="dim">{view.hovered.detail || state.roleOf(view.hovered.name).join(", ")}</span>
          </>
        ) : (
          <span className="dim">drag orbit · shift-drag pan · wheel zoom · hover a patch or glyph</span>
        )}
      </div>
    </>
  );
}
