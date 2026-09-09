/**
 * The shell.
 *
 * Starts empty. There is no model until something has been extracted, and nothing on screen is derived
 * from anything but the files in that project's folder.
 *
 * The chrome describes the **product** - six stages, always shown - and the project's name comes
 * from its folder, so a `DEEPJEB_Bracket/` folder renames the whole application without a code
 * change.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type {
  Axis,
  Callout,
  FaceDetail,
  Feature,
  Mesh,
  ProjectRow,
  Selection,
  SessionState,
  Step,
  Summary,
} from "../api/client";
import { ModelIndex } from "../panel/ModelIndex";
import { Inspector } from "../panel/Inspector";
import { PipelineStage } from "../stage/PipelineStage";
import { UploadStage } from "../stage/UploadStage";
import { Stage as GeometryStage } from "../stage/Stage";
import type { ColourMode } from "../render/renderer";
import { ART, PRODUCT, STAGES, VENDOR } from "./product";

interface Model {
  summary: Summary;
  steps: Step[];
  mesh: Mesh;
  features: Feature[];
  kinds: { kind: string; count: number; controlled: number }[];
  axes: Axis[];
  callouts: Callout[];
  controlled: Set<number>;
}

export function App() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [projects, setProjects] = useState<ProjectRow[]>([]);
  const [model, setModel] = useState<Model | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [view, setView] = useState<"pipeline" | "geometry">("pipeline");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [face, setFace] = useState<FaceDetail | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const [colourMode, setColourMode] = useState<ColourMode>("surface");
  const [growAngle, setGrowAngle] = useState(40);
  const [kindFilter, setKindFilter] = useState<string | null>(null);
  const [ofKind, setOfKind] = useState<Feature[] | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [state, found] = await Promise.all([api.state(), api.projects()]);
        setSession(state);
        setProjects(found);
      } catch (caught) {
        setError(String(caught));
      }
    })();
  }, []);

  const loadModel = useCallback(async () => {
    const [summary, steps, mesh, features, kinds, axes, callouts, controlled] =
      await Promise.all([
        api.summary(),
        api.steps(),
        api.mesh(),
        api.features(),
        api.featureKinds(),
        api.axes(),
        api.callouts(),
        api.controlled(),
      ]);
    setModel({
      summary, steps, mesh, features, kinds, axes, callouts,
      controlled: new Set(controlled.face_ids),
    });
  }, []);

  const extract = useCallback(
    async (project: ProjectRow, paths: string[]) => {
      setBusy(project.name);
      setError(null);
      try {
        const state = await api.extract(project.name, paths);
        setSession(state);
        if (state.stage === "model") await loadModel();
      } catch (caught) {
        setError(String(caught));
      } finally {
        setBusy(null);
      }
    },
    [loadModel],
  );

  const reset = useCallback(async () => {
    setSession(await api.reset());
    setModel(null);
    setSelection(null);
    setFace(null);
    setView("pipeline");
  }, []);

  // Filtering by kind is a server query, not a filter over what was already fetched. The features
  // route returns the largest few hundred across every kind, so filtering that list client-side
  // would show whichever members of a kind happened to be big enough to make the cut.
  useEffect(() => {
    if (!kindFilter) {
      setOfKind(null);
      return;
    }
    let live = true;
    api.features(kindFilter).then((found) => {
      if (live) setOfKind(found);
    });
    return () => {
      live = false;
    };
  }, [kindFilter]);

  const selectedFaces = useMemo(() => new Set(selection?.face_ids ?? []), [selection]);

  // The selection is measured by the server, never assembled here. A picked face has an area and
  // may be controlled; inventing zeros for both put two panels on screen contradicting each other
  // about the same face.
  const pick = useCallback(
    async (faceId: number | null, event: MouseEvent) => {
      if (faceId === null) {
        setSelection(null);
        setFace(null);
        return;
      }
      const additive = event.ctrlKey || event.metaKey;
      const next = new Set(additive ? (selection?.face_ids ?? []) : []);
      if (next.has(faceId)) next.delete(faceId);
      else next.add(faceId);

      setFace(await api.face(faceId));
      setSelection(next.size ? await api.selectFaces([...next]) : null);
    },
    [selection],
  );

  const grow = useCallback(async () => {
    const seed = selection?.face_ids.length ? selection.face_ids : face ? [face.face_id] : [];
    if (!seed.length) return;
    setSelection(await api.grow(seed, growAngle));
  }, [selection, face, growAngle]);

  const similar = useCallback(async () => {
    if (!face) return;
    setSelection(await api.similar(face.face_id));
  }, [face]);

  const selectFeature = useCallback(async (feature: Feature) => {
    setSelection(await api.selectFeature(feature.id));
    if (feature.face_ids.length) setFace(await api.face(feature.face_ids[0]));
    setView("geometry");
  }, []);

  if (error && !session) return <div className="error">{error}</div>;
  if (!session) return <div className="loading">starting&hellip;</div>;

  const open = session.stage === "model" && model !== null;
  const title = session.project?.title ?? "no project";

  return (
    <div className="shell" data-open={open}>
      <header className="topbar">
        <img className="mark" src={ART.mark} alt="" aria-hidden="true" />
        <span className="lockup">
          <b>{VENDOR.name}</b>
          <em>{VENDOR.tagline}</em>
        </span>
        <span className="divider" />
        <span className="lockup">
          <b>{PRODUCT.name}</b>
        </span>
        <span className="divider" />
        <span className="lockup">
          <b>{title}</b>
          <em>{session.project ? `${session.project.artifacts.length} artifacts` : "not extracted"}</em>
        </span>
        <span className="spacer" />
        {open ? (
          <button onClick={reset} title="Close this project and start again">
            Close
          </button>
        ) : null}
        <nav className="stages">
          {STAGES.map((entry) => (
            <button
              key={entry.id}
              data-active={entry.id === (open ? "model" : "extract")}
              data-reached={entry.id === "extract" || (open && entry.id === "model")}
              disabled
              title={entry.summary}
            >
              {entry.label}
            </button>
          ))}
        </nav>
      </header>

      {open ? (
        <>
          <ModelIndex
            features={ofKind ?? model.features}
            kinds={model.kinds}
            axes={model.axes}
            selectedFaces={selectedFaces}
            kindFilter={kindFilter}
            onKindFilter={setKindFilter}
            onSelectFeature={selectFeature}
            view={view}
            onView={setView}
          />

          <div className="stage">
            {view === "pipeline" ? (
              <PipelineStage
                summary={model.summary}
                steps={model.steps}
                callouts={model.callouts}
              />
            ) : (
              <>
                <GeometryStage
                  mesh={model.mesh}
                  faceCount={model.summary.faces ?? 0}
                  bbox={model.summary.bbox_mm ?? [0, 0, 0, 1, 1, 1]}
                  selected={selectedFaces}
                  frozen={model.controlled}
                  exterior={EMPTY}
                  hovered={hovered}
                  colourMode={colourMode}
                  onHover={setHovered}
                  onPick={pick}
                />
                <div className="overlay">
                  {(["surface", "frozen"] as ColourMode[]).map((mode) => (
                    <button
                      key={mode}
                      data-active={colourMode === mode}
                      onClick={() => setColourMode(mode)}
                    >
                      {mode === "frozen" ? "controlled" : mode}
                    </button>
                  ))}
                </div>
                <div className="hint">
                  drag orbit &middot; shift-drag pan &middot; wheel zoom &middot; click select
                  {hovered !== null ? ` · face ${hovered}` : ""}
                </div>
              </>
            )}
          </div>

          <Inspector
            face={face}
            selection={selection}
            onGrow={grow}
            onSimilar={similar}
            onSelectFeature={selectFeature}
            onClear={() => {
              setSelection(null);
              setFace(null);
            }}
            growAngle={growAngle}
            onGrowAngle={setGrowAngle}
          />

          <footer className="titleblock">
            <span>{session.project?.path}</span>
            <span>
              {model.summary.faces} faces &middot; {model.summary.features} features
            </span>
            <span
              style={{ color: model.summary.watertight ? "var(--measured)" : "var(--conflict)" }}
            >
              {model.summary.watertight ? "watertight" : "NOT WATERTIGHT"}
            </span>
            <span style={{ marginLeft: "auto" }}>
              {model.summary.controlled_faces} controlled
            </span>
          </footer>
        </>
      ) : (
        <UploadStage projects={projects} busy={busy} error={error} onExtract={extract} />
      )}
    </div>
  );
}

const EMPTY = new Set<number>();
