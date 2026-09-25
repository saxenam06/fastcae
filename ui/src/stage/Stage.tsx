/**
 * The 3D stage: renderer lifetime, camera input, hover and click.
 *
 * The renderer is imperative and long-lived; React is not. So it is created once in a ref and
 * never re-created on re-render, and state reaches it through explicit calls rather than through
 * props. Recreating a WebGL context per render would re-upload 13 MB of vertices on every hover.
 */

import { useEffect, useMemo, useRef } from "react";
import type { ColourMode, Ghost, LineSet, OverlayPick, VoxelLayer } from "../render/renderer";
import { Renderer } from "../render/renderer";
import type { Mesh, VoxelCells } from "../api/client";
import { SectionControl, useSection } from "./Section";
import { outlineOf, planeKey, planeOf } from "./sectionPlane";

interface StageProps {
  mesh: Mesh;
  /**
   * A second surface drawn over the first, for comparing them, and the field's own cells.
   *
   * Passed whenever they are *loaded*, not whenever they are *shown*: whether a layer is visible
   * is a separate flag, so switching one off leaves it on the GPU rather than throwing away
   * eighty megabytes that have to be uploaded again to switch it back on.
   */
  overlay?: Mesh | null;
  voxels?: VoxelCells | null;
  /** Layers of cells over the part, each its own colour: the design space, a design's metal. */
  voxelLayers?: VoxelLayer[];
  /** Each face its own colour, for the paint colour mode: a per-face value painted on the part. */
  facePaint?: Map<number, [number, number, number]> | null;
  /** A box to look at, and the side to look at it from: the camera moves there once per box. */
  focusBox?: { box: number[]; from: number[] | null } | null;
  /** Lines over everything: where a layout would put ribs, before any design is made. */
  lines?: LineSet | null;
  overlayAlpha?: number;
  /** The overlay's colour. Ochre by default, against the steel of the main surface. */
  overlayTint?: [number, number, number];
  /** Whether the overlay can be picked, and as what. Not at all by default. */
  overlayPick?: OverlayPick;
  showSurface?: boolean;
  showOverlay?: boolean;
  showVoxels?: boolean;
  /** The part's faces left out of the picture: those a design cuts, whose own surface the overlay
   * draws instead, so a hole looks like one. */
  hidden?: Set<number>;
  /** Offer the section control: not while another page covers this canvas. */
  sectionControl?: boolean;
  /** Volumes drawn see-through over the part, each its own colour: design volumes. */
  ghosts?: Ghost[];
  faceCount: number;
  bbox: number[];
  selected: Set<number>;
  frozen: Set<number>;
  exterior: Set<number>;
  hovered: number | null;
  colourMode: ColourMode;
  onHover: (faceId: number | null) => void;
  onPick: (faceId: number | null, event: MouseEvent) => void;
}

const OCHRE: [number, number, number] = [0.541, 0.416, 0.122];
const NONE: Set<number> = new Set();
const NO_LAYERS: VoxelLayer[] = [];
const NO_GHOSTS: Ghost[] = [];

export function Stage(props: StageProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<Renderer | null>(null);
  const dirtyRef = useRef(true);
  const propsRef = useRef(props);
  propsRef.current = props;
  const { section } = useSection();
  const plane = useMemo(() => planeOf(section, props.bbox), [section, props.bbox]);
  const planeRef = useRef(plane);
  planeRef.current = plane;

  // Renderer setup, once. The dependency list is deliberately the mesh alone: everything else is
  // read through propsRef, so a hover cannot tear down the GL context.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const renderer = new Renderer(canvas, props.mesh, props.faceCount);
    renderer.showSurface = props.showSurface ?? true;
    renderer.showOverlay = props.showOverlay ?? true;
    renderer.showVoxels = props.showVoxels ?? true;
    renderer.overlayAlpha = props.overlayAlpha ?? 0.42;
    renderer.overlayTint = props.overlayTint ?? OCHRE;
    renderer.overlayPick = props.overlayPick ?? "none";
    renderer.setOverlay(props.overlay ?? null);
    renderer.setVoxels(props.voxels ?? null);
    renderer.setVoxelLayers(props.voxelLayers ?? NO_LAYERS);
    renderer.setFacePaint(props.facePaint ?? null);
    renderer.setLines(props.lines ?? null);
    renderer.setHidden(props.hidden ?? NONE);
    renderer.setGhosts(props.ghosts ?? NO_GHOSTS);
    renderer.frame(props.bbox);
    const cut = planeRef.current;
    renderer.setSection(cut, cut ? outlineOf(cut, props.bbox) : null);
    rendererRef.current = renderer;
    dirtyRef.current = true;

    let frame = 0;
    const loop = () => {
      if (dirtyRef.current) {
        dirtyRef.current = false;
        renderer.render();
      }
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);

    // The canvas changes size with the window, and with every pane that opens, folds or is dragged
    // beside it: redrawn whenever it does, or the picture stretches until something else moves.
    const sized = new ResizeObserver(() => {
      dirtyRef.current = true;
    });
    sized.observe(canvas);

    return () => {
      cancelAnimationFrame(frame);
      sized.disconnect();
      renderer.dispose();
      rendererRef.current = null;
    };
  }, [props.mesh, props.faceCount]);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    renderer.setOverlay(props.overlay ?? null);
    dirtyRef.current = true;
  }, [props.overlay]);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    renderer.setVoxels(props.voxels ?? null);
    dirtyRef.current = true;
  }, [props.voxels]);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    renderer.setVoxelLayers(props.voxelLayers ?? NO_LAYERS);
    dirtyRef.current = true;
  }, [props.voxelLayers]);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    renderer.setFacePaint(props.facePaint ?? null);
    dirtyRef.current = true;
  }, [props.facePaint]);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer || !props.focusBox) return;
    renderer.focusBox(props.focusBox.box, props.focusBox.from);
    dirtyRef.current = true;
  }, [props.focusBox]);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    renderer.setLines(props.lines ?? null);
    dirtyRef.current = true;
  }, [props.lines]);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    renderer.setHidden(props.hidden ?? NONE);
    dirtyRef.current = true;
  }, [props.hidden]);

  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    renderer.setGhosts(props.ghosts ?? NO_GHOSTS);
    dirtyRef.current = true;
  }, [props.ghosts]);

  // The section, as the one plane every view shares.
  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    renderer.setSection(plane, plane ? outlineOf(plane, props.bbox) : null);
    dirtyRef.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planeKey(plane), props.bbox]);

  // Cheap to change and cheap to apply, so these ride along with the face state rather than
  // rebuilding anything.
  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    renderer.showSurface = props.showSurface ?? true;
    renderer.showOverlay = props.showOverlay ?? true;
    renderer.showVoxels = props.showVoxels ?? true;
    renderer.overlayAlpha = props.overlayAlpha ?? 0.42;
    renderer.overlayTint = props.overlayTint ?? OCHRE;
    renderer.overlayPick = props.overlayPick ?? "none";
    dirtyRef.current = true;
  }, [
    props.showSurface,
    props.showOverlay,
    props.showVoxels,
    props.overlayAlpha,
    props.overlayTint,
    props.overlayPick,
  ]);

  // Face state and colour mode: cheap texture writes, so this can run on every state change.
  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer) return;
    renderer.colourMode = props.colourMode;
    renderer.setFaceState({
      selected: props.selected,
      frozen: props.frozen,
      exterior: props.exterior,
      hovered: props.hovered,
    });
    dirtyRef.current = true;
  }, [props.selected, props.frozen, props.exterior, props.hovered, props.colourMode]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let dragging: "orbit" | "pan" | null = null;
    let lastX = 0;
    let lastY = 0;
    let movedWhileDown = 0;
    let hoverTimer = 0;

    const toPixels = (event: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const ratio = canvas.width / rect.width;
      return {
        x: (event.clientX - rect.left) * ratio * 0.5,
        y: (event.clientY - rect.top) * ratio * 0.5,
      };
    };

    const onPointerDown = (event: PointerEvent) => {
      canvas.setPointerCapture(event.pointerId);
      // Middle button, or shift with the left, pans. Matching what CAD tools do rather than
      // inventing a scheme nobody has muscle memory for.
      dragging = event.button === 1 || event.shiftKey ? "pan" : "orbit";
      lastX = event.clientX;
      lastY = event.clientY;
      movedWhileDown = 0;
    };

    const onPointerMove = (event: PointerEvent) => {
      const renderer = rendererRef.current;
      if (!renderer) return;

      if (dragging) {
        const dx = event.clientX - lastX;
        const dy = event.clientY - lastY;
        lastX = event.clientX;
        lastY = event.clientY;
        movedWhileDown += Math.abs(dx) + Math.abs(dy);
        if (dragging === "orbit") renderer.orbit(dx, dy);
        else renderer.pan(dx, dy);
        dirtyRef.current = true;
        return;
      }

      // Hover picking is throttled to a frame. A pick is a full render plus a synchronous
      // readPixels, so running it per mousemove event would stall the pipeline.
      if (hoverTimer) return;
      hoverTimer = requestAnimationFrame(() => {
        hoverTimer = 0;
        const { x, y } = toPixels(event);
        propsRef.current.onHover(renderer.pick(x, y));
      });
    };

    const onPointerUp = (event: PointerEvent) => {
      const renderer = rendererRef.current;
      canvas.releasePointerCapture(event.pointerId);
      // A drag that ends is a camera move, not a click. Four pixels of slop covers a shaky hand
      // without swallowing a deliberate click.
      if (renderer && dragging === "orbit" && movedWhileDown < 4) {
        const { x, y } = toPixels(event);
        propsRef.current.onPick(renderer.pick(x, y), event);
      }
      dragging = null;
    };

    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      rendererRef.current?.zoom(event.deltaY);
      dirtyRef.current = true;
    };

    const onContextMenu = (event: Event) => event.preventDefault();

    canvas.addEventListener("pointerdown", onPointerDown);
    canvas.addEventListener("pointermove", onPointerMove);
    canvas.addEventListener("pointerup", onPointerUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("contextmenu", onContextMenu);

    return () => {
      canvas.removeEventListener("pointerdown", onPointerDown);
      canvas.removeEventListener("pointermove", onPointerMove);
      canvas.removeEventListener("pointerup", onPointerUp);
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("contextmenu", onContextMenu);
      if (hoverTimer) cancelAnimationFrame(hoverTimer);
    };
  }, []);

  return (
    <>
      <canvas ref={canvasRef} />
      {props.sectionControl ?? true ? (
        <SectionControl bbox={props.bbox} facing={() => rendererRef.current?.facing() ?? null} />
      ) : null}
    </>
  );
}
