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
  FieldOption,
  FieldSummary,
  ProjectRow,
  Selection,
  SessionState,
  Step,
  Summary,
  SurfaceSummary,
  VoxelCells,
  Formations,
  MadeDesign,
  SpaceInfo,
  ZoneSettings,
  ZonesInfo,
} from "../api/client";
import { ModelIndex } from "../panel/ModelIndex";
import { DrawingIndex } from "../panel/DrawingIndex";
import type { Layers } from "../panel/FieldIndex";
import { FieldIndex } from "../panel/FieldIndex";
import type { GenerateLayers } from "../panel/GenerateIndex";
import { GenerateIndex, defaults } from "../panel/GenerateIndex";
import { Inspector } from "../panel/Inspector";
import { AgentPanel } from "../panel/AgentPanel";
import { Splitter } from "../panel/Splitter";
import { DrawingStage } from "../stage/DrawingStage";
import { UploadStage } from "../stage/UploadStage";
import { Stage as GeometryStage } from "../stage/Stage";
import type { ColourMode } from "../render/renderer";
import type { View } from "./product";
import { ART, PRODUCT, STAGES, VENDOR, VIEWS } from "./product";

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

  const [view, setView] = useState<View>("drawing");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [face, setFace] = useState<FaceDetail | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const [colourMode, setColourMode] = useState<ColourMode>("surface");
  const [growAngle, setGrowAngle] = useState(20);
  const [kindFilter, setKindFilter] = useState<string | null>(null);
  const [ofKind, setOfKind] = useState<Feature[] | null>(null);

  // The field and the surface contoured out of it, kept apart from `model` because they belong to
  // Generate rather than to what the artifacts said, and because building one costs minutes.
  const [fieldInfo, setFieldInfo] = useState<FieldSummary | null>(null);
  const [fieldSurface, setFieldSurface] = useState<SurfaceSummary | null>(null);
  const [fieldMesh, setFieldMesh] = useState<Mesh | null>(null);
  const [voxels, setVoxels] = useState<VoxelCells | null>(null);
  const [fieldBusy, setFieldBusy] = useState<string | null>(null);
  const [calloutFilter, setCalloutFilter] = useState<string | null>(null);
  const [spacings, setSpacings] = useState<FieldOption[]>([]);

  // Generate: what may be designed in, the levers set for it, and the last design made. Lever
  // values live here, so moving a slider costs nothing until Generate is pressed.
  const [zonesInfo, setZonesInfo] = useState<ZonesInfo | null>(null);
  const [formations, setFormations] = useState<Formations | null>(null);
  const [space, setSpace] = useState<SpaceInfo | null>(null);
  const [settings, setSettings] = useState<Record<string, ZoneSettings>>({});
  const [made, setMade] = useState<MadeDesign | null>(null);
  const [madeMesh, setMadeMesh] = useState<Mesh | null>(null);
  const [designBusy, setDesignBusy] = useState<string | null>(null);
  const [designError, setDesignError] = useState<string | null>(null);
  const [generateLayers, setGenerateLayers] = useState<GenerateLayers>({
    geometry: true,
    design: true,
  });

  // Pane widths, remembered between sessions. Losing them on every reload is a small annoyance
  // that never stops being annoying.
  const [railWidth, setRailWidth] = useState(() => remembered("fastcae.rail", 300));
  const [agentWidth, setAgentWidth] = useState(() => remembered("fastcae.agent", 340));
  const [agentOpen, setAgentOpen] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem("fastcae.rail", String(railWidth));
      localStorage.setItem("fastcae.agent", String(agentWidth));
    } catch {
      // Private windows and blocked site data. A forgotten width is not worth an error.
    }
  }, [railWidth, agentWidth]);

  // The field's own cells are cheap and are the field itself, so they are on by default. The
  // contour is a reconstruction and costs tens of megabytes, so it is off until asked for.
  const [layers, setLayers] = useState<Layers>({
    voxels: true,
    contour: false,
    geometry: true,
  });

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
    setSpacings(await api.fieldOptions());
  }, []);

  const extract = useCallback(
    async (project: ProjectRow, paths: string[], reuse = true) => {
      setBusy(project.name);
      setError(null);
      try {
        const state = await api.extract(project.name, paths, reuse);
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

  // Reading the same files again, on purpose. Everything derived from a project is kept on disk
  // and keyed on what those files contain, so opening one is instant after the first time; this is
  // the way to say "read them anyway".
  const reextract = useCallback(async () => {
    if (!session?.project) return;
    const paths = session.project.artifacts.map((a) => a.path);
    await extract(session.project, paths, false);
  }, [session, extract]);

  // Two steps on purpose. The numbers are the comparison and cost seconds; drawing it can be
  // hundreds of megabytes, and a browser asked to hold that without warning simply stops.
  const buildField = useCallback(async (spacingMm?: number) => {
    setFieldBusy("Sampling the part into a distance field. Minutes the first time, seconds after.");
    setError(null);
    try {
      const built = await api.buildField(spacingMm);
      api.fieldOptions().then(setSpacings);
      setFieldInfo(built);
      setFieldBusy(built.from_cache ? "Reading the contour." : "Contouring the field.");
      const [surface, cells] = await Promise.all([api.fieldSurface(), api.fieldVoxels()]);
      setFieldSurface(surface);
      setVoxels(cells);
    } catch (caught) {
      setError(String(caught));
    } finally {
      setFieldBusy(null);
    }
  }, []);

  // Every Generate action runs through here: one thing at a time, and a failure said plainly.
  const act = useCallback(async (label: string, action: () => Promise<void>) => {
    setDesignBusy(label);
    setDesignError(null);
    try {
      await action();
    } catch (caught) {
      setDesignError(String(caught));
    } finally {
      setDesignBusy(null);
    }
  }, []);

  // A decision changed: whatever was opened or made under the old one no longer holds.
  const forgetDesigns = useCallback(() => {
    setSpace(null);
    setMade(null);
    setMadeMesh(null);
  }, []);

  useEffect(() => {
    if (view !== "generate" || model === null) return;
    api.zones().then(setZonesInfo).catch((caught) => setDesignError(String(caught)));
    api.formations().then(setFormations).catch((caught) => setDesignError(String(caught)));
  }, [view, model]);

  const proposeZones = useCallback(
    () =>
      act("Proposing zones from the reference. Minutes the first time, kept after.", async () => {
        setZonesInfo(await api.proposeZones());
        forgetDesigns();
      }),
    [act, forgetDesigns],
  );

  const approveZone = useCallback(
    (id: string, approved: boolean) =>
      act("Recording the decision.", async () => {
        setZonesInfo(await api.approveZone(id, approved));
        forgetDesigns();
      }),
    [act, forgetDesigns],
  );

  const approveProtected = useCallback(
    (approved: boolean) =>
      act("Recording the decision.", async () => {
        setZonesInfo(await api.approveProtected(approved));
        forgetDesigns();
      }),
    [act, forgetDesigns],
  );

  const approveCorrection = useCallback(
    (kind: string, approved: boolean) =>
      act("Recording the decision.", async () => {
        await api.approveCorrection(kind, approved);
        setZonesInfo(await api.zones());
        forgetDesigns();
      }),
    [act, forgetDesigns],
  );

  const openSpace = useCallback(
    () =>
      act(
        "Opening for designing: the part's field, its contour and each zone's window. " +
          "Minutes the first time on a large part, seconds after.",
        async () => {
          const opened = await api.openSpace();
          setSpace(opened);
          setMade(null);
          setMadeMesh(null);
          const first = formations?.formations[0];
          if (first) {
            setSettings((was) =>
              Object.fromEntries(opened.zones.map((z) => [z.id, was[z.id] ?? defaults(first)])),
            );
          }
        },
      ),
    [act, formations],
  );

  const generate = useCallback(
    () =>
      act("generating", async () => {
        const design = await api.generate(settings);
        setMade(design);
        setMadeMesh(await api.designMesh());
      }),
    [act, settings],
  );

  const forgetField = useCallback(() => {
    setFieldInfo(null);
    setFieldSurface(null);
    setFieldMesh(null);
    setVoxels(null);
  }, []);

  const loadFieldMesh = useCallback(async () => {
    setFieldBusy("Sending the contour to the browser…");
    try {
      setFieldMesh(await api.fieldMesh());
    } catch (caught) {
      setError(String(caught));
    } finally {
      setFieldBusy(null);
    }
  }, []);

  const reset = useCallback(async () => {
    setSession(await api.reset());
    setModel(null);
    setSelection(null);
    setFace(null);
    setFieldInfo(null);
    setFieldSurface(null);
    setFieldMesh(null);
    setVoxels(null);
    setZonesInfo(null);
    setSpace(null);
    setSettings({});
    setMade(null);
    setMadeMesh(null);
    setView("drawing");
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

  // How many pages the drawing had, from the step that read it - so the tab can say so without a
  // route of its own.
  const pages = useMemo(() => {
    const step = model?.steps.find((s) => s.id === "drawing.read");
    const value = step?.produced?.pages;
    return typeof value === "number" ? value : null;
  }, [model]);

  // What the deterministic rules refused to settle. The agent's job starts where these are.
  const openQuestions = useMemo(() => {
    const produced = model?.steps.find((s) => s.id === "crosscheck")?.produced ?? {};
    const count = (key: string) => (typeof produced[key] === "number" ? produced[key] : 0);
    return count("ambiguous") + count("unresolved_pairings");
  }, [model]);

  // What each layer costs to draw, every frame. The only honest answer to "why is this slow".
  const layerCost = useMemo(
    () => ({
      voxels: (voxels?.faces.length ?? 0) * 6,
      contour: (fieldSurface?.triangles ?? 0) * 3,
      geometry: (model?.summary.triangles ?? 0) * 3,
    }),
    [voxels, fieldSurface, model],
  );

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

  // Always from the face that was clicked, never from the selection grow last produced. Feeding
  // the result back in makes the angle a ratchet: it can only ever add, so lowering it appears to
  // do nothing at all. Growing from the origin every time is what makes the slider a reading of
  // one number rather than a record of how many times it was pressed.
  const grow = useCallback(async () => {
    if (!face) return;
    setSelection(await api.grow([face.face_id], growAngle));
  }, [face, growAngle]);

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
    <div
      className="shell"
      data-open={open}
      // Only while a project is open: the upload screen is one column, and an inline three-column
      // template would override the rule that makes it so.
      style={
        open
          ? { gridTemplateColumns: `${railWidth}px 1fr ${agentOpen ? agentWidth : 0}px` }
          : undefined
      }
    >
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
          <>
            <button
              className="agent-toggle"
              data-open={agentOpen}
              onClick={() => setAgentOpen((was) => !was)}
              title={agentOpen ? "Hide the agent" : "Show the agent"}
            >
              <AgentMark />
              Agent
            </button>
            <button
              onClick={reextract}
              disabled={busy !== null}
              title="Read the artifacts again instead of using what was read before"
            >
              {busy ? "Reading…" : "Re-extract"}
            </button>
            <button onClick={reset} title="Close this project and start again">
              Close
            </button>
          </>
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
          <div className="rail">
            {view === "drawing" ? (
              <DrawingIndex
              steps={model.steps}
              callouts={model.callouts}
              pages={pages}
              filter={calloutFilter}
              onFilter={setCalloutFilter}
            />
          ) : view === "generate" ? (
            <GenerateIndex
              layers={generateLayers}
              onLayers={setGenerateLayers}
              zones={zonesInfo}
              onPropose={proposeZones}
              onApproveZone={approveZone}
              onApproveProtected={approveProtected}
              onApproveCorrection={approveCorrection}
              space={space}
              onOpen={openSpace}
              formations={formations}
              settings={settings}
              onSettings={(zoneId, next) => setSettings((was) => ({ ...was, [zoneId]: next }))}
              onGenerate={generate}
              made={made}
              busy={designBusy}
              error={designError}
            />
          ) : view === "field" ? (
            <FieldIndex
              field={fieldInfo}
              surface={fieldSurface}
              layers={layers}
              onLayers={setLayers}
              contourLoaded={fieldMesh !== null}
              voxelsLoaded={voxels !== null}
              cost={layerCost}
              onSpacing={forgetField}
            />
          ) : (
            <ModelIndex
              summary={model.summary}
              steps={model.steps}
              features={ofKind ?? model.features}
              kinds={model.kinds}
              axes={model.axes}
              selectedFaces={selectedFaces}
              kindFilter={kindFilter}
              onKindFilter={setKindFilter}
              onSelectFeature={selectFeature}
              />
            )}

            {/* The selection belongs beside the features it was made from, and it applies to two
                tabs of the three - a pane that is empty on the third is a pane in the wrong place. */}
            {view === "geometry" && (selection || face) ? (
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
            ) : null}

            <Splitter side="right" onResize={(d) => setRailWidth((w) => clampPane(w + d))} />
          </div>

          <div className="stage">
            {/* What you are looking at. The rail follows from this rather than the other way
                round, so a tab and its own detail never disagree about the subject. */}
            <nav className="stage-tabs">
              {VIEWS.map((entry) => (
                <button
                  key={entry.id}
                  data-active={view === entry.id}
                  onClick={() => setView(entry.id)}
                  title={entry.summary}
                >
                  {entry.label}
                </button>
              ))}
            </nav>

            <div className="stage-body">
              {view === "drawing" ? (
                <DrawingStage
                  all={model.callouts}
                  callouts={
                    calloutFilter
                      ? model.callouts.filter((c) => c.kind === calloutFilter)
                      : model.callouts
                  }
                  steps={model.steps}
                  filter={calloutFilter}
                  pages={pages}
                />
              ) : view === "field" && !fieldInfo ? (
                <div className="empty-stage">
                  {fieldBusy ? (
                    <p className="card-note">{fieldBusy}</p>
                  ) : (
                    <>
                      <p>
                        The distance field is the representation a design is edited in. Building it
                        samples the part onto a fixed grid. A finer voxel holds smaller features and
                        costs more of everything.
                      </p>
                      <div className="actions">
                        {spacings.map((option) => (
                          <button
                            key={option.spacing_mm}
                            onClick={() => buildField(option.spacing_mm)}
                            title={
                              option.field_ready
                                ? "Already built - opens straight away"
                                : "Not built yet - this samples the whole part"
                            }
                          >
                            {option.spacing_mm} mm
                            <span className="detail">
                              {option.field_ready ? "ready" : "minutes"}
                            </span>
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              ) : (
                <>
                  <GeometryStage
                    mesh={model.mesh}
                    faceCount={model.summary.faces ?? 0}
                    bbox={model.summary.bbox_mm ?? [0, 0, 0, 1, 1, 1]}
                    showSurface={
                      view === "field"
                        ? layers.geometry
                        : view === "generate"
                          ? generateLayers.geometry
                          : true
                    }
                    showOverlay={
                      view === "generate" ? generateLayers.design : view === "field" && layers.contour
                    }
                    showVoxels={view === "field" && layers.voxels}
                    overlay={view === "generate" ? madeMesh : fieldMesh}
                    overlayAlpha={view === "generate" ? 1.0 : layers.geometry ? 0.42 : 1.0}
                    overlayTint={view === "generate" ? DESIGN_TINT : undefined}
                    voxels={view === "generate" ? null : voxels}
                    selected={selectedFaces}
                    frozen={model.controlled}
                    exterior={EMPTY}
                    hovered={hovered}
                    colourMode={colourMode}
                    onHover={setHovered}
                    onPick={pick}
                  />
                  <div className="overlay">
                    {view === "field" ? (
                      layers.contour && !fieldMesh ? (
                        <button onClick={loadFieldMesh} disabled={fieldBusy !== null}>
                          {fieldBusy
                            ? fieldBusy
                            : `Load the contour (${megabytes(fieldSurface?.vertices ?? 0, fieldSurface?.triangles ?? 0)} MB)`}
                        </button>
                      ) : null
                    ) : view === "generate" ? null : (
                      (["surface", "frozen"] as ColourMode[]).map((mode) => (
                        <button
                          key={mode}
                          data-active={colourMode === mode}
                          onClick={() => setColourMode(mode)}
                        >
                          {mode === "frozen" ? "controlled" : mode}
                        </button>
                      ))
                    )}
                  </div>
                  <div className="hint">
                    {view === "field" && voxels ? (
                      <>
                        {voxels.faces.length.toLocaleString()} visible cell faces at {voxels.size}{" "}
                        mm
                        {fieldSurface
                          ? ` · ${fieldSurface.shell_cells.toLocaleString()} cells on the surface` +
                            ` · contour off by ${fieldSurface.volume_error_pct}%`
                          : ""}
                      </>
                    ) : (
                      <>
                        drag orbit &middot; shift-drag pan &middot; wheel zoom &middot; click select
                        {hovered !== null ? ` · face ${hovered}` : ""}
                      </>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>

          {agentOpen ? (
            <div className="agent">
              <Splitter side="left" onResize={(d) => setAgentWidth((w) => clampPane(w - d))} />
              <AgentPanel session={session} view={view} openQuestions={openQuestions} />
            </div>
          ) : null}

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
            <span>
              {session.from_cache ? "opened from cache" : `read in ${session.seconds ?? 0}s`}
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

/** The design's new surfaces, in the Generate layer's blue, against the grey of the part. */
const DESIGN_TINT: [number, number, number] = [0.059, 0.239, 0.569];

/** A four-point spark. A mark rather than a word, so the bar stays readable at any width. */
function AgentMark() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M8 0.6 L9.7 6.3 L15.4 8 L9.7 9.7 L8 15.4 L6.3 9.7 L0.6 8 L6.3 6.3 Z"
        fill="currentColor"
      />
    </svg>
  );
}

const MIN_PANE = 220;
const MAX_PANE = 640;

function clampPane(width: number): number {
  return Math.min(Math.max(width, MIN_PANE), MAX_PANE);
}

function remembered(key: string, fallback: number): number {
  try {
    const stored = Number(localStorage.getItem(key));
    return Number.isFinite(stored) && stored > 0 ? clampPane(stored) : fallback;
  } catch {
    return fallback;
  }
}

/**
 * What a surface costs to send, indexed: a position, a packed normal and a face id per vertex,
 * plus three indices per triangle. Vertices are shared wherever they agree about which way the
 * surface faces, so this is a close lower bound rather than an exact figure.
 */
function megabytes(vertices: number, triangles: number): number {
  return Math.round((vertices * 20 + triangles * 12) / 1e6);
}
