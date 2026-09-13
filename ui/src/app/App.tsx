/**
 * The shell.
 *
 * Starts empty. There is no model until something has been extracted, and nothing on screen is derived
 * from anything but the files in that project's folder.
 *
 * Five tabs, in the order the work happens: the Drawing as read; the CAD, where variants - one
 * change in one place, with what it may vary and every rule it holds - are authored by hand on
 * Design a variant; Generate, where a campaign composed of variants makes thousands of designs and
 * every design is followed through its stages; Learn and Optimize. The project's name comes from
 * its folder, so a `DEEPJEB_Bracket/` folder renames the whole application without a code change.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type {
  Axis,
  Callout,
  FaceDetail,
  Feature,
  Mesh,
  ProjectRow,
  Seed,
  Selection,
  SessionState,
  Step,
  Summary,
} from "../api/client";
import { ModelIndex } from "../panel/ModelIndex";
import { DrawingIndex } from "../panel/DrawingIndex";
import { Inspector } from "../panel/Inspector";
import { VariantCard } from "../panel/VariantCard";
import { Splitter } from "../panel/Splitter";
import { CampaignCardView, CampaignRuns, useCampaign } from "../generate/Campaign";
import { DesignReadout, DesignStage, DesignTabs, DesignsRail, useDesigns } from "../generate/Designs";
import { DrawingStage } from "../stage/DrawingStage";
import { UploadStage } from "../stage/UploadStage";
import { Stage as GeometryStage } from "../stage/Stage";
import { HoverCard } from "../stage/HoverCard";
import { SelectionBar } from "../stage/SelectionBar";
import { DESIGN_PICK } from "../render/renderer";
import type { ColourMode, LineSet } from "../render/renderer";
import type { View } from "./product";
import { ART, PRODUCT, VENDOR, VIEWS } from "./product";

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

/** Generate's two halves: launching campaigns, and the designs they kept. */
type GenerateTab = "campaign" | "designs";

/** The right-hand panes that fold away to the edge, one a place. */
type Pane = "cad" | "designs";

export function App() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [projects, setProjects] = useState<ProjectRow[]>([]);
  const [model, setModel] = useState<Model | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [view, setView] = useState<View>("drawing");
  const [generateTab, setGenerateTab] = useState<GenerateTab>("campaign");
  const [selection, setSelection] = useState<Selection | null>(null);
  const [face, setFace] = useState<FaceDetail | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  // The card under the stage: the hovered face, or the one a click pinned. Faces are read once and
  // kept, so moving back over a face costs nothing.
  const [pinned, setPinned] = useState<number | null>(null);
  const [cardFace, setCardFace] = useState<FaceDetail | null>(null);
  const faceCache = useRef(new Map<number, FaceDetail>());
  const [colourMode, setColourMode] = useState<ColourMode>("surface");
  // The faces clicked, each grown by its own angle - or not at all - and the one the grow control
  // is on: the last clicked, or one picked from the list.
  const [seeds, setSeeds] = useState<Seed[]>([]);
  const [activeSeed, setActiveSeed] = useState<number | null>(null);
  const [kindFilter, setKindFilter] = useState<string | null>(null);
  const [ofKind, setOfKind] = useState<Feature[] | null>(null);
  const [calloutFilter, setCalloutFilter] = useState<string | null>(null);

  // CAD: where the variant being authored puts its ribs and holes, drawn on the part.
  const [cardLines, setCardLines] = useState<LineSet | null>(null);
  const [showPart, setShowPart] = useState(true);

  // Pane widths, remembered between sessions. Losing them on every reload is a small annoyance
  // that never stops being annoying.
  const [railWidth, setRailWidth] = useState(() => remembered("fastcae.rail", 300));
  const [cardWidth, setCardWidth] = useState(() => remembered("fastcae.card", 380));
  const [open, setOpen] = useState<Record<Pane, boolean>>({ cad: true, designs: true });

  useEffect(() => {
    try {
      localStorage.setItem("fastcae.rail", String(railWidth));
      localStorage.setItem("fastcae.card", String(cardWidth));
    } catch {
      // Private windows and blocked site data. A forgotten width is not worth an error.
    }
  }, [railWidth, cardWidth]);

  const project = session?.project?.name ?? null;
  const campaign = useCampaign(view === "generate" && generateTab === "campaign", project);
  const designs = useDesigns(view === "generate" && generateTab === "designs", project);

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

  // Reading the same files again, on purpose. Everything derived from a project is kept on disk
  // and keyed on what those files contain, so opening one is instant after the first time; this is
  // the way to say "read them anyway".
  const reextract = useCallback(async () => {
    if (!session?.project) return;
    const paths = session.project.artifacts.map((a) => a.path);
    await extract(session.project, paths, false);
  }, [session, extract]);

  const openCard = useCallback(() => {
    setView("cad");
    setOpen((was) => ({ ...was, cad: true }));
  }, []);

  const openRun = useCallback(
    (run: string) => {
      setView("generate");
      setGenerateTab("designs");
      designs.openRun(run);
    },
    [designs],
  );

  const reset = useCallback(async () => {
    setSession(await api.reset());
    setModel(null);
    setSeeds([]);
    setActiveSeed(null);
    setFace(null);
    setCardLines(null);
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

  const selectedFaces = useMemo(() => new Set(selection?.face_ids ?? []), [selection]);

  useEffect(() => {
    faceCache.current.clear();
    setPinned(null);
    setCardFace(null);
  }, [model]);

  const cardTarget = pinned ?? hovered;
  useEffect(() => {
    if (cardTarget === null || cardTarget === DESIGN_PICK) return;
    const known = faceCache.current.get(cardTarget);
    if (known) {
      setCardFace(known);
      return;
    }
    // A short wait, so sweeping the cursor across a part does not ask about every face it crosses.
    const timer = window.setTimeout(() => {
      api
        .face(cardTarget)
        .then((detail) => {
          faceCache.current.set(cardTarget, detail);
          setCardFace(detail);
        })
        .catch(() => undefined);
    }, 60);
    return () => window.clearTimeout(timer);
  }, [cardTarget]);

  // The faces clicked are the seeds, each grown across every edge shallower than its own angle -
  // recomputed from the seeds whenever one changes, never from the last result. Feeding a grown
  // selection back in makes the angle a ratchet that can only add. The selection itself is
  // measured by the server, never assembled here.
  useEffect(() => {
    if (!seeds.length) {
      setSelection(null);
      return;
    }
    let live = true;
    const timer = window.setTimeout(() => {
      api
        .selectSeeds(seeds)
        .then((selected) => {
          if (live) setSelection(selected);
        })
        .catch(() => undefined);
    }, 120);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [seeds]);

  // A click selects a face alone; ctrl-click adds it, or takes it out again. Either way the face
  // clicked is the one the grow control is on, and it starts ungrown - an angle set for one click
  // is never carried to the next.
  const pick = useCallback(async (faceId: number | null, event: MouseEvent) => {
    setPinned(faceId);
    if (faceId === null) {
      setSeeds([]);
      setActiveSeed(null);
      setFace(null);
      return;
    }
    if (faceId === DESIGN_PICK) return;
    const additive = event.ctrlKey || event.metaKey;
    setSeeds((was) => {
      if (!additive) return [{ face: faceId, angle: 0 }];
      return was.some((s) => s.face === faceId)
        ? was.filter((s) => s.face !== faceId)
        : [...was, { face: faceId, angle: 0 }];
    });
    setActiveSeed(faceId);
    setFace(await api.face(faceId));
  }, []);

  const activeAngle = seeds.find((s) => s.face === activeSeed)?.angle ?? 0;
  const setActiveAngle = useCallback(
    (angle: number) => {
      setSeeds((was) => was.map((s) => (s.face === activeSeed ? { ...s, angle } : s)));
    },
    [activeSeed],
  );

  const grow = useCallback(() => {
    setSeeds((was) =>
      was.map((s) => (s.face === activeSeed && s.angle === 0 ? { ...s, angle: 20 } : s)),
    );
  }, [activeSeed]);

  const clearSelection = useCallback(() => {
    setSeeds([]);
    setActiveSeed(null);
    setFace(null);
  }, []);

  // Faces named somewhere - a card, a feature - become the selection, ungrown.
  const selectFaces = useCallback((faces: number[]) => {
    setSeeds([...new Set(faces)].map((face) => ({ face, angle: 0 })));
    setActiveSeed(null);
  }, []);

  // Show on the part what the card or the study names: every face of them, in one call.
  const selectRefs = useCallback(
    async (refs: string[]) => {
      if (!refs.length) return;
      const found = await api.selectRefs(refs).catch(() => null);
      if (found) selectFaces(found.face_ids);
    },
    [selectFaces],
  );

  const similar = useCallback(async () => {
    if (!face) return;
    const found = await api.similar(face.face_id);
    selectFaces(found.face_ids);
  }, [face, selectFaces]);

  const selectFeature = useCallback(
    async (feature: Feature) => {
      selectFaces([...feature.face_ids]);
      if (feature.face_ids.length) setFace(await api.face(feature.face_ids[0]));
      setView("cad");
    },
    [selectFaces],
  );

  if (error && !session) return <div className="error">{error}</div>;
  if (!session) return <div className="loading">starting&hellip;</div>;

  const opened = session.stage === "model" && model !== null;
  const title = session.project?.title ?? "no project";

  // What each tab lays out: a rail on the left, a pane on the right - and which pane.
  const pane: Pane | null =
    view === "cad" ? "cad" : view === "generate" && generateTab === "designs" ? "designs" : null;
  const hasRail = view === "drawing" || view === "cad" || view === "generate";
  const paneWidth = pane === null ? 0 : open[pane] ? cardWidth : 30;

  // The part in 3D is kept alive on every tab but the drawing, so going back and forth costs
  // nothing; what is drawn over it depends on the tab.
  const onDesigns = view === "generate" && generateTab === "designs";
  const designField = onDesigns && designs.tab === "field";
  const designPaths = onDesigns && designs.tab === "paths";
  const overlay = designField ? designs.overlay : null;
  const lines = view === "cad" ? cardLines : designPaths ? designs.lines : null;
  const voxels = designField && designs.showCells ? designs.cells : null;
  const partShown = designField ? showPart : true;
  const pageOver =
    view === "learn" ||
    view === "optimize" ||
    (view === "generate" && generateTab === "campaign") ||
    (onDesigns && !designField && !designPaths);

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
      </header>

      {opened ? (
        <>
          {/* The agent is paused while variants and campaigns are built by hand: its bar is
              kept, and comes back once it writes variants. */}
          {hasRail ? (
            <div className="rail">
              <div className="rail-scroll">
                {view === "drawing" ? (
                  <DrawingIndex
                    steps={model.steps}
                    callouts={model.callouts}
                    pages={pages}
                    filter={calloutFilter}
                    onFilter={setCalloutFilter}
                  />
                ) : view === "generate" ? (
                  <>
                    <nav className="segmented generate-tabs">
                      <button
                        data-active={generateTab === "campaign"}
                        onClick={() => setGenerateTab("campaign")}
                        title="Launch campaigns, with the whole pipeline in the open"
                      >
                        Campaign
                      </button>
                      <button
                        data-active={generateTab === "designs"}
                        onClick={() => setGenerateTab("designs")}
                        title="Every design a campaign kept, and how far each has got"
                      >
                        Designs
                      </button>
                    </nav>
                    {generateTab === "campaign" ? (
                      <CampaignRuns
                        launched={campaign.launched}
                        going={campaign.going}
                        onOpenRun={openRun}
                      />
                    ) : (
                      <DesignsRail designs={designs} />
                    )}
                  </>
                ) : (
                  <>
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
                    {/* The selection belongs beside the features it was made from. */}
                    {selection || face ? (
                      <Inspector
                        face={face}
                        selection={selection}
                        onGrow={grow}
                        onSimilar={similar}
                        onSelectFeature={selectFeature}
                        onClear={clearSelection}
                        growAngle={activeAngle}
                        onGrowAngle={setActiveAngle}
                      />
                    ) : null}
                  </>
                )}
              </div>
              <Splitter side="right" onResize={(d) => setRailWidth((w) => clampPane(w + d))} />
            </div>
          ) : null}

          <div className="stage">
            {onDesigns ? <DesignTabs designs={designs} /> : null}
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
              ) : (
                <>
                  <GeometryStage
                    mesh={model.mesh}
                    faceCount={model.summary.faces ?? 0}
                    bbox={model.summary.bbox_mm ?? [0, 0, 0, 1, 1, 1]}
                    showSurface={partShown}
                    showOverlay
                    showVoxels={voxels !== null}
                    overlay={overlay}
                    overlayAlpha={1.0}
                    overlayTint={DESIGN_TINT}
                    overlayPick={overlay ? "design" : "none"}
                    voxels={voxels}
                    lines={lines}
                    selected={selectedFaces}
                    frozen={model.controlled}
                    exterior={EMPTY}
                    hovered={hovered}
                    colourMode={colourMode}
                    onHover={setHovered}
                    onPick={pick}
                  />
                  {view === "cad" ? (
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
                  ) : null}
                  {onDesigns ? (
                    <DesignStage designs={designs} showPart={showPart} onPart={setShowPart} />
                  ) : null}
                  {!pageOver ? (
                    <>
                      <SelectionBar
                        count={selection?.count ?? 0}
                        seeds={seeds}
                        active={activeSeed}
                        onActive={setActiveSeed}
                        onAngle={setActiveAngle}
                        onRemove={(faceId) => {
                          setSeeds((was) => was.filter((s) => s.face !== faceId));
                          if (faceId === activeSeed) setActiveSeed(null);
                        }}
                        onClear={clearSelection}
                      />
                      <HoverCard
                        target={cardTarget === DESIGN_PICK ? "design" : cardTarget}
                        face={cardFace}
                        pinned={pinned !== null}
                        onRelease={() => setPinned(null)}
                      />
                      <div className="hint">
                        {voxels
                          ? `${voxels.faces.length.toLocaleString()} visible cell faces of new metal at ${voxels.size} mm · `
                          : ""}
                        drag orbit &middot; shift-drag pan &middot; wheel zoom &middot; click pins a
                        face
                      </div>
                    </>
                  ) : null}
                  {view === "generate" && generateTab === "campaign" ? (
                    <div className="stage-page">
                      <CampaignCardView
                        campaign={campaign}
                        onOpenCard={openCard}
                        onOpenRun={openRun}
                      />
                    </div>
                  ) : null}
                  {view === "learn" || view === "optimize" ? (
                    <div className="stage-page">
                      <Later view={view} />
                    </div>
                  ) : null}
                </>
              )}
            </div>
          </div>

          {pane !== null ? (
            <div className="card-pane">
              {open[pane] ? (
                <>
                  <Splitter side="left" onResize={(d) => setCardWidth((w) => clampPane(w - d))} />
                  {pane === "cad" ? (
                    <VariantCard
                      project={project}
                      selection={selection?.face_ids ?? []}
                      refresh={0}
                      onShow={selectRefs}
                      onPaths={setCardLines}
                      onCollapse={() => setOpen((was) => ({ ...was, cad: false }))}
                      onLibrary={campaign.refresh}
                    />
                  ) : (
                    <DesignReadout
                      designs={designs}
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

/** What a folded pane says on its strip. */
const PANE_NAMES: Record<Pane, string> = {
  cad: "Design a variant",
  designs: "The design",
};

/** The design's new surfaces: teal, a colour nothing else uses - selection is blue. */
const DESIGN_TINT: [number, number, number] = [0.055, 0.431, 0.455];

/** A tab not built yet: what it will do, and what it waits for. */
function Later({ view }: { view: "learn" | "optimize" }) {
  return view === "learn" ? (
    <div className="later">
      <h2>Learn - not built yet</h2>
      <p>
        Learn trains surrogates on a campaign's results - what each design's solve gave back - and
        says how far they can be believed on designs they were not trained on.
      </p>
      <p className="dim">
        It waits for designs with results: on Generate → Designs, a design goes from its paths (P)
        to its field (F), mesh (M), solver setup (S) and results (R). Fields are built today;
        meshing, setup and results come next.
      </p>
    </div>
  ) : (
    <div className="later">
      <h2>Optimize - not built yet</h2>
      <p>
        Optimize searches the surrogate for designs that do better on the study's objectives,
        proposes candidates, and verifies the ones worth solving - each a design of the same design
        space, held to the same rules.
      </p>
      <p className="dim">It waits for a surrogate from Learn.</p>
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
