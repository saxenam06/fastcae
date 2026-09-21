/**
 * The shell.
 *
 * Starts empty. There is no model until something has been extracted, and nothing on screen is
 * derived from anything but the files in that project's folder.
 *
 * Four tabs, in the order the work happens: Input - what the engineer brought, read by the pipeline
 * into typed entities, and the design space; Generate - designs made in that space and every design
 * followed through its stages; Learn and Optimize. On Input the left rail is the pipeline itself -
 * every step, what it read and what it made - the canvases show whatever is in focus, and the card
 * on the right shows it in full. The project's name comes from its folder, so a
 * `DEEPJEB_Bracket/` folder renames the whole application without a code change.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type {
  Callout,
  FaceDetail,
  Mesh,
  ProjectRow,
  SessionState,
  Step,
  Summary,
} from "../api/client";
import type { EntitySummary, Group, StepRun } from "../api/pipeline";
import { AgentBar } from "../panel/AgentBar";
import { Splitter } from "../panel/Splitter";
import {
  CampaignPage,
  CampaignRail,
  DesignCard,
  DesignFe,
  DesignOverlay,
  DesignsRail,
  onPart,
  tabsFor,
  useCampaigns,
  useDesign,
  useDesignCanvas,
} from "../designs/Designs";
import type { DesignTab } from "../designs/Designs";
import { DrawingStage } from "../stage/DrawingStage";
import { UploadStage } from "../stage/UploadStage";
import { Stage as GeometryStage } from "../stage/Stage";
import { HoverCard } from "../stage/HoverCard";
import { DESIGN_PICK } from "../render/renderer";
import type { ColourMode } from "../render/renderer";
import { MeshStage, useMeshView } from "../input/MeshSetup";
import { ResultsStage } from "../input/Results";
import { useSolveView } from "../input/Solve";
import { useDeck } from "../input/useDeck";
import { EntityCard } from "../pipeline/EntityCard";
import { PipelineRail } from "../pipeline/PipelineRail";
import type { Focus } from "../pipeline/focus";
import { merged, stepFocus } from "../pipeline/focus";
import { SPACE_TINT, useDesignSpace } from "../pipeline/spaceLayers";
import { useVolumes } from "../volumes/useVolumes";
import { VolumesPanel } from "../volumes/VolumesPanel";
import { SPACE_STEP, usePipeline } from "../pipeline/usePipeline";
import type { CadView, DeckView, GenerateTab, InputTab, View } from "./product";
import {
  ART,
  CAD_VIEWS,
  DECK_VIEWS,
  GENERATE_TABS,
  INPUT_TABS,
  PRODUCT,
  VENDOR,
  VIEWS,
} from "./product";

interface Model {
  summary: Summary;
  steps: Step[];
  mesh: Mesh;
  callouts: Callout[];
  controlled: Set<number>;
}

/** The right-hand panes that fold away to the edge, one a place. */
type Pane = "entity" | "designs";

/** A step's outputs are shown together only while there are few enough to mean something. */
const SHOWN_TOGETHER = 60;

export function App() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [projects, setProjects] = useState<ProjectRow[]>([]);
  const [model, setModel] = useState<Model | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [view, setView] = useState<View>("input");
  const [inputTab, setInputTab] = useState<InputTab>("cad");
  const [cadView, setCadView] = useState<CadView>("part");
  const [deckView, setDeckView] = useState<DeckView>("setup");
  const [generateTab, setGenerateTab] = useState<GenerateTab>("campaign");
  // A design is looked at stage by stage; its optimisation at any iteration, the last by default.
  const [designTab, setDesignTab] = useState<DesignTab>("optimise");
  const [designIteration, setDesignIteration] = useState(-1);
  const [designShowSpace, setDesignShowSpace] = useState(false);
  const [designShowPlanes, setDesignShowPlanes] = useState(false);

  // What is in focus - an entity, a group, a step - and so what every canvas highlights.
  const [focus, setFocus] = useState<Focus | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const [cardFace, setCardFace] = useState<FaceDetail | null>(null);
  const faceCache = useRef(new Map<number, FaceDetail>());
  const [colourMode, setColourMode] = useState<ColourMode>("surface");
  // The design-space view's switches, as the deck's view has its own: the part, the design space,
  // and the design space coloured by where metal helps. Everything drawn opaque.
  const [spaceShow, setSpaceShow] = useState({ part: true, space: true, heat: false });
  // The design-volume view's switches: the part, and the volumes over it.
  const [volumeShow, setVolumeShow] = useState({ part: true, volumes: true });
  const [showPart, setShowPart] = useState(true);

  // Pane widths, remembered between sessions. Losing them on every reload is a small annoyance
  // that never stops being annoying.
  const [railWidth, setRailWidth] = useState(() => remembered("fastcae.rail", 320));
  const [cardWidth, setCardWidth] = useState(() => remembered("fastcae.card", 380));
  const [open, setOpen] = useState<Record<Pane, boolean>>({ entity: true, designs: true });

  useEffect(() => {
    try {
      localStorage.setItem("fastcae.rail", String(railWidth));
      localStorage.setItem("fastcae.card", String(cardWidth));
    } catch {
      // Private windows and blocked site data. A forgotten width is not worth an error.
    }
  }, [railWidth, cardWidth]);

  const project = session?.project?.name ?? null;
  const opened = session?.stage === "model" && model !== null;
  const pipeline = usePipeline(opened ? project : null);
  const campaigns = useCampaigns(view === "generate", project);
  const design = useDesign(view === "generate" ? campaigns.design : null);
  const onDeck = view === "input" && inputTab === "mesh";
  const deck = useDeck(onDeck, project);
  const meshView = useMeshView();
  const resultsView = useSolveView();

  const loadModel = useCallback(async () => {
    const [summary, steps, mesh, callouts, controlled] = await Promise.all([
      api.summary(),
      api.steps(),
      api.mesh(),
      api.callouts(),
      api.controlled(),
    ]);
    setModel({ summary, steps, mesh, callouts, controlled: new Set(controlled.face_ids) });
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [state, found] = await Promise.all([api.state(), api.projects()]);
        setSession(state);
        setProjects(found);
        // A project already open - the page reloaded - is shown again, not asked for.
        if (state.stage === "model") await loadModel();
      } catch (caught) {
        setError(String(caught));
      }
    })();
  }, [loadModel]);

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

  // Reading the same files again, on purpose. Everything read from a project is kept on disk and
  // keyed on what those files contain, so opening one is instant after the first time; this is the
  // way to say "read them anyway" - the design space with them.
  const reextract = useCallback(async () => {
    if (!session?.project) return;
    const paths = session.project.artifacts.map((a) => a.path);
    setFocus(null);
    await extract(session.project, paths, false);
    await pipeline.run(false);
  }, [session, extract, pipeline]);

  const selectDesign = campaigns.selectDesign;
  const openDesign = useCallback(
    (id: string) => {
      selectDesign(id);
      setDesignIteration(-1);
      setView("generate");
      setGenerateTab("designs");
    },
    [selectDesign],
  );

  const reset = useCallback(async () => {
    setSession(await api.reset());
    setModel(null);
    setFocus(null);
    setView("input");
    setInputTab("cad");
  }, []);

  // --- focus: what the rail, the card or a canvas picked, shown on the canvas that shows it ------

  const setMeshFocus = meshView.setFocus;
  const show = useCallback(
    (next: Focus) => {
      setFocus(next);
      setOpen((was) => ({ ...was, entity: true }));
      const { canvas, layers, group } = next.show;
      if (canvas === "none") return;
      setView("input");
      if (canvas === "drawing") setInputTab("drawing");
      else if (canvas === "mesh") {
        setInputTab("mesh");
        setDeckView("setup");
        setMeshFocus(group);
      } else {
        // On the CAD: the design space shown - or asked for - opens the design-space view with it
        // on; faces alone are shown on whichever view is up.
        setInputTab("cad");
        if (canvas === "space" || layers.length) {
          setCadView("space");
          setSpaceShow((was) => ({ ...was, space: true }));
        }
      }
    },
    [setMeshFocus],
  );

  const onEntity = useCallback(
    (entity: EntitySummary, look = true) =>
      show({
        kind: "entity",
        step: entity.step,
        group: null,
        entity: entity.id,
        show: entity.show,
        look,
      }),
    [show],
  );

  const readEntity = pipeline.entity;
  const onEntityId = useCallback(
    async (id: string, look = true) => {
      const found = await readEntity(id).catch(() => null);
      if (found) onEntity(found, look);
    },
    [readEntity, onEntity],
  );

  const readMembers = pipeline.members;
  const onGroup = useCallback(
    async (group: Group, step: StepRun) => {
      const members = await readMembers(group).catch(() => []);
      const fallback = step.id === SPACE_STEP ? "space" : "none";
      show({ kind: "group", step: step.id, group, entity: null, show: merged(members, fallback) });
    },
    [readMembers, show],
  );

  const onStep = useCallback(
    async (step: StepRun) => {
      const total = step.outputs.reduce((n, g) => n + g.count, 0);
      const members =
        total <= SHOWN_TOGETHER
          ? (await Promise.all(step.outputs.map((g) => readMembers(g).catch(() => [])))).flat()
          : [];
      show(stepFocus(step, members));
    },
    [readMembers, show],
  );

  // What the agent showed: one entity is focused as any is; several, together, as a group.
  const showIds = useCallback(
    async (ids: string[]) => {
      if (ids.length === 1) {
        await onEntityId(ids[0]);
        return;
      }
      const found = (await Promise.all(ids.map((id) => readEntity(id).catch(() => null)))).filter(
        (e): e is NonNullable<typeof e> => e !== null,
      );
      if (!found.length) return;
      const group: Group = {
        key: "shown",
        label: "Shown by the agent",
        count: found.length,
        kind: "",
        ids: found.map((e) => e.id),
        step: "",
      };
      show({ kind: "group", step: null, group, entity: null, show: merged(found), look: true });
    },
    [onEntityId, readEntity, show],
  );

  const refreshPipeline = pipeline.refresh;
  const agentChanged = useCallback(
    (what: string[]) => {
      if (what.length) void refreshPipeline().catch(() => undefined);
    },
    [refreshPipeline],
  );

  // What goes to the agent with the engineer's words: what is in focus.
  const focusIds = useMemo(
    () => (focus?.entity ? [focus.entity] : (focus?.group?.ids ?? []).slice(0, 40)),
    [focus],
  );

  // A face clicked on the part is the face entity: its card says what else lies on it.
  const pick = useCallback(
    (faceId: number | null) => {
      if (faceId === null) {
        setFocus(null);
        return;
      }
      if (faceId === DESIGN_PICK || view !== "input") return;
      void onEntityId(`face:${faceId}`, false);
    },
    [onEntityId, view],
  );

  // How many pages the drawing had, from the step that read it.
  const pages = useMemo(() => {
    const step = model?.steps.find((s) => s.id === "drawing.read");
    const value = step?.produced?.pages;
    return typeof value === "number" ? value : null;
  }, [model]);

  const focusFaces = useMemo(() => new Set(focus?.show.faces ?? []), [focus]);

  // What is picked from the rail or a card, or shown by the agent, is looked at: the camera moves
  // to its faces once, and stays where it is put.
  const focusBox = useMemo(() => {
    if (!model || !focus?.look || !focus.show.faces.length) return null;
    return lookAt(model.mesh, new Set(focus.show.faces), model.summary.bbox_mm ?? null);
  }, [focus, model]);

  useEffect(() => {
    faceCache.current.clear();
    setCardFace(null);
  }, [model]);

  useEffect(() => {
    if (hovered === null || hovered === DESIGN_PICK) return;
    const known = faceCache.current.get(hovered);
    if (known) {
      setCardFace(known);
      return;
    }
    // A short wait, so sweeping the cursor across a part does not ask about every face it crosses.
    const timer = window.setTimeout(() => {
      api
        .face(hovered)
        .then((detail) => {
          faceCache.current.set(hovered, detail);
          setCardFace(detail);
        })
        .catch(() => undefined);
    }, 60);
    return () => window.clearTimeout(timer);
  }, [hovered]);

  // The design space on the CAD, once it has been read.
  const spaceStep = pipeline.steps.get(SPACE_STEP);
  const spaceReady =
    !pipeline.running && (spaceStep?.status === "done" || spaceStep?.status === "cached");
  const onSpace = view === "input" && inputTab === "cad" && cadView === "space";
  // Design volumes: faces picked on the CAD, and the volumes they bound, see-through over it.
  const onVolumes = view === "input" && inputTab === "cad" && cadView === "volumes";
  const volumes = useVolumes(onVolumes);
  const designSpace = useDesignSpace(
    onSpace && spaceShow.space,
    pipeline.version,
    spaceShow.heat,
    spaceReady,
  );
  // A design's stages that are drawn on the part's canvas, over the part - and the design space
  // under the optimisation, asked for.
  const designOnPart = view === "generate" && generateTab === "designs" && onPart(designTab);
  // the tabs a campaign's designs are looked at in are its own stages: when the campaign changes
  // to one made in other stages, the tab in hand may not exist there - start it at the first
  const designTabs = tabsFor(campaigns.campaign);
  useEffect(() => {
    if (!designTabs.some((t) => t.id === designTab)) setDesignTab(designTabs[0]?.id ?? "optimise");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaigns.campaign?.id]);
  const spaceUnderDesign = useDesignSpace(
    designOnPart && designShowSpace,
    pipeline.version,
    false,
    spaceReady,
  );
  const designCanvas = useDesignCanvas(
    design,
    designTab,
    designIteration,
    designShowSpace,
    spaceUnderDesign.layers,
    designShowPlanes,
  );

  if (error && !session) return <div className="error">{error}</div>;
  if (!session) return <div className="loading">starting&hellip;</div>;

  const title = session.project?.title ?? "no project";

  const onInput = view === "input";
  const onDrawing = onInput && inputTab === "drawing";
  const onCad = onInput && inputTab === "cad";
  const onMesh = onInput && inputTab === "mesh";
  const onCampaign = view === "generate" && generateTab === "campaign";
  const onDesigns = view === "generate" && generateTab === "designs";

  const pane: Pane | null = onInput && focus ? "entity" : onDesigns ? "designs" : null;
  const hasRail = onInput || view === "generate";
  const paneWidth = pane === null ? 0 : open[pane] ? cardWidth : 30;

  // The part in 3D is kept alive on the CAD and on Designs, so going back and forth costs nothing;
  // what is drawn over it depends on the tab: a design's metal, its plates, its CAD's new faces.
  const overlay = designOnPart ? designCanvas.overlay : null;
  const lines = designOnPart ? designCanvas.lines : null;
  const partShown = designOnPart ? showPart : true;
  const layersShown = onSpace ? designSpace.layers : designOnPart ? designCanvas.layers : NO_LAYERS;
  // The part is what is looked at on the CAD and on a design's stages drawn over it; elsewhere it
  // stays loaded under the page that covers it.
  const geometryInView = onCad || designOnPart;
  const mode: ColourMode = onSpace ? "surface" : onCad ? colourMode : "surface";

  return (
    <div
      className="shell"
      data-open={opened}
      // Only while a project is open: the upload screen is one column, and an inline three-column
      // template would override the rule that makes it so.
      style={
        opened
          ? {
              gridTemplateColumns: `${hasRail ? railWidth : 0}px minmax(0, 1fr) ${paneWidth}px`,
            }
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
        {opened ? (
          <nav className="stages main-tabs">
            {VIEWS.map((entry) => (
              <button
                key={entry.id}
                data-active={view === entry.id}
                data-ready={entry.ready}
                onClick={() => setView(entry.id)}
                title={entry.summary}
              >
                {entry.label}
              </button>
            ))}
          </nav>
        ) : null}
        <span className="spacer" />
        {opened ? (
          <>
            <button
              onClick={reextract}
              disabled={busy !== null || pipeline.running}
              title="Read the artifacts again, and derive the design space again, instead of using what was kept"
            >
              {busy ? "Reading…" : "Re-extract"}
            </button>
            <button onClick={reset} title="Close this project and start again">
              Close
            </button>
          </>
        ) : null}
      </header>

      {opened && model ? (
        <>
          <AgentBar focus={focusIds} onShow={(ids) => void showIds(ids)} onChanged={agentChanged} />
          {hasRail ? (
            <div className="rail">
              <div className="rail-scroll">
                {onInput ? (
                  <PipelineRail
                    state={pipeline}
                    focus={focus}
                    onStep={onStep}
                    onGroup={onGroup}
                    onEntity={onEntity}
                  />
                ) : onCampaign ? (
                  <CampaignRail state={campaigns} onNew={() => campaigns.selectCampaign("new")} />
                ) : (
                  <DesignsRail state={campaigns} />
                )}
              </div>
              <Splitter side="right" onResize={(d) => setRailWidth((w) => clampPane(w + d))} />
            </div>
          ) : null}

          <div className="stage">
            {onInput ? (
              <nav className="stage-tabs">
                {INPUT_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    data-active={inputTab === tab.id}
                    onClick={() => setInputTab(tab.id)}
                    title={tab.summary}
                  >
                    {tab.label}
                  </button>
                ))}
                <span className="stage-tabs-spacer" />
                {onCad ? (
                  <span className="segmented stage-toggle">
                    {CAD_VIEWS.map((v) => (
                      <button key={v.id} data-active={cadView === v.id} onClick={() => setCadView(v.id)}>
                        {v.label}
                      </button>
                    ))}
                  </span>
                ) : null}
                {onMesh ? (
                  <span className="segmented stage-toggle">
                    {DECK_VIEWS.map((v) => (
                      <button key={v.id} data-active={deckView === v.id} onClick={() => setDeckView(v.id)}>
                        {v.label}
                      </button>
                    ))}
                  </span>
                ) : null}
              </nav>
            ) : null}
            {view === "generate" ? (
              <nav className="stage-tabs">
                {GENERATE_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    data-active={generateTab === tab.id}
                    onClick={() => setGenerateTab(tab.id)}
                    title={tab.summary}
                  >
                    {tab.label}
                  </button>
                ))}
                <span className="stage-tabs-spacer" />
                {onDesigns ? (
                  <span className="segmented stage-toggle">
                    {designTabs.map((t) => (
                      <button key={t.id} data-active={designTab === t.id} onClick={() => setDesignTab(t.id)}>
                        {t.label}
                      </button>
                    ))}
                  </span>
                ) : null}
              </nav>
            ) : null}
            <div className="stage-body">
              {onDrawing ? (
                <DrawingStage
                  all={model.callouts}
                  callouts={
                    focus?.kind === "group" && focus.group?.kind === "callout"
                      ? model.callouts.filter((c) => c.kind === focus.group!.key)
                      : model.callouts
                  }
                  steps={model.steps}
                  filter={focus?.kind === "group" && focus.group?.kind === "callout" ? focus.group.key : null}
                  pages={pages}
                  focus={focus?.show.canvas === "drawing" ? focus.show : null}
                />
              ) : null}
              {!onDrawing ? (
                <>
                  <GeometryStage
                    mesh={model.mesh}
                    faceCount={model.summary.faces ?? 0}
                    bbox={model.summary.bbox_mm ?? [0, 0, 0, 1, 1, 1]}
                    showSurface={onSpace ? spaceShow.part : onVolumes ? volumeShow.part : partShown}
                    showOverlay
                    showVoxels={layersShown.length > 0}
                    overlay={overlay}
                    hidden={EMPTY}
                    sectionControl={onCad || (designOnPart && !!design)}
                    overlayAlpha={1.0}
                    overlayTint={DESIGN_TINT}
                    overlayPick={overlay ? "design" : "none"}
                    voxels={null}
                    voxelLayers={layersShown}
                    focusBox={onCad ? focusBox : null}
                    lines={lines}
                    selected={onVolumes ? volumes.selected : onCad ? focusFaces : EMPTY}
                    ghosts={onVolumes && volumeShow.volumes ? volumes.ghosts : undefined}
                    frozen={model.controlled}
                    exterior={EMPTY}
                    hovered={hovered}
                    colourMode={mode}
                    onHover={setHovered}
                    onPick={
                      onVolumes
                        ? (faceId, event) => {
                            if (faceId === null || faceId === DESIGN_PICK) return;
                            volumes.pick(faceId, event.ctrlKey || event.metaKey || event.shiftKey);
                          }
                        : pick
                    }
                  />
                  {onCad && cadView === "part" ? (
                    <div className="overlay">
                      <button
                        data-active={colourMode === "frozen"}
                        onClick={() => setColourMode(colourMode === "frozen" ? "surface" : "frozen")}
                        title="Faces the drawing controls"
                      >
                        drawing controls
                      </button>
                    </div>
                  ) : null}
                  {onSpace ? (
                    <SpaceOverlay
                      show={spaceShow}
                      onShow={setSpaceShow}
                      step={spaceStep ?? null}
                      running={pipeline.running}
                      error={designSpace.error}
                    />
                  ) : null}
                  {onVolumes ? (
                    <>
                      <div className="overlay">
                        <button
                          data-active={volumeShow.part}
                          onClick={() => setVolumeShow({ ...volumeShow, part: !volumeShow.part })}
                        >
                          part
                        </button>
                        <button
                          data-active={volumeShow.volumes}
                          onClick={() => setVolumeShow({ ...volumeShow, volumes: !volumeShow.volumes })}
                        >
                          <i className="swatch" style={{ background: "rgb(31,148,140)" }} /> design volumes
                        </button>
                      </div>
                      <VolumesPanel state={volumes} />
                    </>
                  ) : null}
                  {designOnPart && design ? (
                    <DesignOverlay
                      design={design}
                      tab={designTab}
                      iteration={designIteration}
                      onIteration={setDesignIteration}
                      showSpace={designShowSpace}
                      onShowSpace={setDesignShowSpace}
                      showPart={showPart}
                      onShowPart={setShowPart}
                      showPlanes={designShowPlanes}
                      onShowPlanes={setDesignShowPlanes}
                      fins={designCanvas.fins}
                    />
                  ) : null}
                  {designOnPart && !design ? (
                    <div className="stage-page">
                      <div className="later">
                        <h2>Designs</h2>
                        <p>Pick a design on the left, or plan a campaign on Campaign.</p>
                      </div>
                    </div>
                  ) : null}
                  {geometryInView ? (
                    <>
                      <HoverCard
                        target={hovered === DESIGN_PICK ? "design" : hovered}
                        face={cardFace}
                        pinned={false}
                        onRelease={() => undefined}
                      />
                      <div className="hint">
                        {onSpace && pipeline.running ? "reading the design space · " : ""}
                        drag orbit &middot; shift-drag pan &middot; wheel zoom &middot; click a face
                        for its card
                      </div>
                    </>
                  ) : null}
                </>
              ) : null}
              {onMesh ? (
                <div className="fe-page">
                  {deckView === "setup" ? (
                    <MeshStage state={deck} view={meshView} />
                  ) : (
                    <ResultsStage state={deck} view={resultsView} />
                  )}
                </div>
              ) : null}
              {onCampaign ? (
                <div className="stage-page">
                  <CampaignPage state={campaigns} onOpen={openDesign} />
                </div>
              ) : null}
              {onDesigns && (designTab === "mesh" || designTab === "solve") ? (
                design ? (
                  <DesignFe design={design} tab={designTab} />
                ) : (
                  <div className="stage-page">
                    <div className="later">
                      <h2>Designs</h2>
                      <p>Pick a design on the left, or plan a campaign on Campaign.</p>
                    </div>
                  </div>
                )
              ) : null}
              {view === "learn" || view === "optimize" ? (
                <div className="stage-page">
                  <Later view={view} />
                </div>
              ) : null}
            </div>
          </div>

          {pane !== null ? (
            <div className="card-pane">
              {open[pane] ? (
                <>
                  <Splitter side="left" onResize={(d) => setCardWidth((w) => clampPane(w - d))} />
                  {pane === "entity" && focus ? (
                    <EntityCard
                      state={pipeline}
                      focus={focus}
                      onEntity={onEntityId}
                      onStep={onStep}
                      onGroup={onGroup}
                      onCollapse={() => setOpen((was) => ({ ...was, entity: false }))}
                    />
                  ) : (
                    <DesignCard
                      design={design}
                      onCollapse={() => setOpen((was) => ({ ...was, designs: false }))}
                    />
                  )}
                </>
              ) : (
                <button
                  className="pane-strip"
                  onClick={() => setOpen((was) => ({ ...was, [pane]: true }))}
                  title="Open it again"
                >
                  <span>{PANE_NAMES[pane]}</span>
                </button>
              )}
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
const NO_LAYERS: never[] = [];

/** What a folded pane says on its strip. */
const PANE_NAMES: Record<Pane, string> = {
  entity: "Card",
  designs: "The design",
};

/** The design's new surfaces: teal, a colour nothing else uses - selection is blue. */
const DESIGN_TINT: [number, number, number] = [0.055, 0.431, 0.455];

/**
 * Where to look at some of the part's faces from: the box round them, and the side they are seen
 * from - their outward normal where they face one way, as a flat face does; down their axis from the
 * end away from the part's middle where they turn about one, as a bore does.
 */
function lookAt(
  mesh: Mesh,
  faces: Set<number>,
  partBox: number[] | null,
): { box: number[]; from: number[] | null } | null {
  let x0 = Infinity;
  let y0 = Infinity;
  let z0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  let z1 = -Infinity;
  const mean = [0, 0, 0];
  // The normals' second moments: the axis a round face turns about is the direction no normal has.
  const moment = [0, 0, 0, 0, 0, 0];
  let count = 0;
  const { positions, normals, faceIds, vertexCount } = mesh;
  for (let v = 0; v < vertexCount; v++) {
    if (!faces.has(faceIds[v])) continue;
    const x = positions[v * 3];
    const y = positions[v * 3 + 1];
    const z = positions[v * 3 + 2];
    if (x < x0) x0 = x;
    if (y < y0) y0 = y;
    if (z < z0) z0 = z;
    if (x > x1) x1 = x;
    if (y > y1) y1 = y;
    if (z > z1) z1 = z;
    const nx = normals[v * 4] / 127;
    const ny = normals[v * 4 + 1] / 127;
    const nz = normals[v * 4 + 2] / 127;
    mean[0] += nx;
    mean[1] += ny;
    mean[2] += nz;
    moment[0] += nx * nx;
    moment[1] += ny * ny;
    moment[2] += nz * nz;
    moment[3] += nx * ny;
    moment[4] += nx * nz;
    moment[5] += ny * nz;
    count++;
  }
  if (!count) return null;
  const box = [x0, y0, z0, x1, y1, z1];
  const m = mean.map((v) => v / count);
  if (Math.hypot(m[0], m[1], m[2]) > 0.35) return { box, from: m };
  // A face that turns about an axis: the eigenvector of the smallest moment, by power iteration on
  // (trace - moment), then from the end away from the part's middle.
  const [xx, yy, zz, xy, xz, yz] = moment.map((v) => v / count);
  const t = xx + yy + zz;
  let axis = [1, 0.7, 0.3];
  for (let i = 0; i < 60; i++) {
    const next = [
      (t - xx) * axis[0] - xy * axis[1] - xz * axis[2],
      -xy * axis[0] + (t - yy) * axis[1] - yz * axis[2],
      -xz * axis[0] - yz * axis[1] + (t - zz) * axis[2],
    ];
    const length = Math.hypot(next[0], next[1], next[2]) || 1;
    axis = next.map((v) => v / length);
  }
  if (partBox) {
    const out = [0, 1, 2].map((i) => (box[i] + box[i + 3]) / 2 - (partBox[i] + partBox[i + 3]) / 2);
    if (out[0] * axis[0] + out[1] * axis[1] + out[2] * axis[2] < 0) axis = axis.map((v) => -v);
  }
  return { box, from: axis };
}

/**
 * The design-space view's switches, as the deck's view has its own - the part, the design space,
 * where metal helps - with what the design space holds beside them, and what is happening while it
 * is read or defined.
 */
function SpaceOverlay({
  show,
  onShow,
  step,
  running,
  error,
}: {
  show: { part: boolean; space: boolean; heat: boolean };
  onShow: (show: { part: boolean; space: boolean; heat: boolean }) => void;
  step: StepRun | null;
  running: boolean;
  error: string | null;
}) {
  const swatch = `rgb(${SPACE_TINT.map((c) => Math.round(c * 255)).join(",")})`;
  return (
    <>
      <div className="overlay">
        <button data-active={show.part} onClick={() => onShow({ ...show, part: !show.part })}>
          part
        </button>
        <button data-active={show.space} onClick={() => onShow({ ...show, space: !show.space })}>
          <i className="swatch" style={{ background: swatch }} /> design space
        </button>
        <button
          data-active={show.heat}
          disabled={!show.space}
          onClick={() => onShow({ ...show, heat: !show.heat })}
          title="The design space coloured by how much load metal there would carry"
        >
          <i className="swatch heat" /> where metal helps
        </button>
      </div>
      <div className="space-readout">
        {running ? (
          <span className="dim">{step?.detail || "reading the design space…"}</span>
        ) : step?.status === "done" || step?.status === "cached" ? (
          <span>{step.detail}</span>
        ) : (
          <span className="dim">no design space yet</span>
        )}
        {error ? <span className="fe-error">{error}</span> : null}
      </div>
    </>
  );
}

/** Learn and Optimize, not built yet: what each will do, and what it waits for. */
function Later({ view }: { view: "learn" | "optimize" }) {
  return (
    <div className="later">
      {view === "learn" ? (
        <>
          <h2>Learn - not built yet</h2>
          <p>
            Surrogates trained on the designs Generate solved - each made as its own CAD, meshed and
            solved as the deck solves the part - with how far they can be believed on designs they
            were not trained on.
          </p>
        </>
      ) : (
        <>
          <h2>Optimize - not built yet</h2>
          <p>
            The search run on the surrogates: candidates proposed in the design space, the ones worth
            solving confirmed by the solver.
          </p>
        </>
      )}
      <p className="dim">It waits for solved designs from Generate.</p>
    </div>
  );
}

const MIN_PANE = 220;
const MAX_PANE = 900;

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
