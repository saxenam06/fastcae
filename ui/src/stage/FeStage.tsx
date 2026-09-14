/**
 * A finite-element view on the stage: the renderer's lifetime, camera input, hover.
 *
 * Two views share a camera through a link: moving either moves both, which is all a side-by-side
 * comparison needs. What is drawn arrives as props and reaches the renderer through explicit calls.
 */

import { useEffect, useRef } from "react";
import type { Values } from "../api/simulate";
import type { Camera, ColourMode, GlyphData, GlyphLabel, Pick, Skin } from "../render/fe";
import { FeRenderer, newCamera } from "../render/fe";

/** A camera two views can share, and who to tell when it moves. */
export class CameraLink {
  camera: Camera = newCamera();
  framed: string | null = null;
  private listeners = new Set<() => void>();
  listen(fn: () => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }
  changed(): void {
    for (const fn of this.listeners) fn();
  }
}

export interface Hovered {
  pick: Pick;
  name: string;
  detail: string;
}

interface Props {
  skin: Skin | null;
  glyphs?: GlyphData | null;
  values?: Values | null;
  mode: ColourMode;
  range?: [number, number];
  groupColours?: ([number, number, number] | null)[];
  edges?: boolean;
  showGlyphs?: boolean;
  deform?: number;
  link: CameraLink;
  bbox?: number[] | null;
  /** Named so a change of subject reframes the camera and nothing else does. */
  frameKey?: string;
  hoveredGroup?: number | null;
  onHover?: (hovered: Hovered | null) => void;
  caption?: React.ReactNode;
}

export function FeStage(props: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<FeRenderer | null>(null);
  const dirty = useRef(true);
  const propsRef = useRef(props);
  propsRef.current = props;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const renderer = new FeRenderer(canvas, props.link.camera);
    rendererRef.current = renderer;
    let frame = 0;
    const loop = () => {
      if (dirty.current) {
        dirty.current = false;
        renderer.render();
      }
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);
    const sized = new ResizeObserver(() => (dirty.current = true));
    sized.observe(canvas);
    const unlisten = props.link.listen(() => (dirty.current = true));
    return () => {
      cancelAnimationFrame(frame);
      sized.disconnect();
      unlisten();
      renderer.dispose();
      rendererRef.current = null;
    };
  }, [props.link]);

  useEffect(() => {
    const r = rendererRef.current;
    if (!r) return;
    r.setSkin(props.skin);
    if (props.skin && props.bbox && props.link.framed !== (props.frameKey ?? "")) {
      r.frame(props.bbox);
      props.link.framed = props.frameKey ?? "";
      props.link.changed();
    }
    dirty.current = true;
  }, [props.skin, props.bbox, props.frameKey, props.link]);

  useEffect(() => {
    const r = rendererRef.current;
    if (!r) return;
    r.setValues(props.values?.values ?? null, props.values?.vectors ?? null);
    dirty.current = true;
  }, [props.values, props.skin]);

  useEffect(() => {
    const r = rendererRef.current;
    if (!r) return;
    r.setGlyphs(props.glyphs ?? null);
    dirty.current = true;
  }, [props.glyphs]);

  useEffect(() => {
    const r = rendererRef.current;
    if (!r) return;
    r.setGroupColours(props.groupColours ?? []);
    dirty.current = true;
  }, [props.groupColours, props.skin]);

  useEffect(() => {
    const r = rendererRef.current;
    if (!r) return;
    r.mode = props.mode;
    r.range = props.range ?? [0, 1];
    r.edges = props.edges ?? true;
    r.showGlyphs = props.showGlyphs ?? true;
    r.deform = props.deform ?? 0;
    r.hoveredGroup = props.hoveredGroup ?? -1;
    dirty.current = true;
  }, [props.mode, props.range, props.edges, props.showGlyphs, props.deform, props.hoveredGroup]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let dragging: "orbit" | "pan" | null = null;
    let lastX = 0;
    let lastY = 0;
    let timer = 0;
    const down = (e: PointerEvent) => {
      canvas.setPointerCapture(e.pointerId);
      dragging = e.button === 1 || e.button === 2 || e.shiftKey ? "pan" : "orbit";
      lastX = e.clientX;
      lastY = e.clientY;
    };
    const move = (e: PointerEvent) => {
      const r = rendererRef.current;
      if (!r) return;
      if (dragging) {
        const dx = e.clientX - lastX;
        const dy = e.clientY - lastY;
        lastX = e.clientX;
        lastY = e.clientY;
        if (dragging === "orbit") r.orbit(dx, dy);
        else r.pan(dx, dy);
        propsRef.current.link.changed();
        return;
      }
      if (timer) return;
      timer = requestAnimationFrame(() => {
        timer = 0;
        const rect = canvas.getBoundingClientRect();
        const pick = r.pick(e.clientX - rect.left, e.clientY - rect.top);
        const onHover = propsRef.current.onHover;
        if (!onHover) return;
        if (!pick) return onHover(null);
        if (pick.kind === "group") {
          const name = propsRef.current.skin?.groupNames[pick.index] ?? "?";
          onHover({ pick, name, detail: "" });
        } else {
          const label: GlyphLabel | undefined = r.labels[pick.index];
          onHover(label ? { pick, name: label.name, detail: label.detail } : null);
        }
      });
    };
    const up = (e: PointerEvent) => {
      canvas.releasePointerCapture(e.pointerId);
      dragging = null;
    };
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      rendererRef.current?.zoom(e.deltaY);
      propsRef.current.link.changed();
    };
    const leave = () => propsRef.current.onHover?.(null);
    const menu = (e: Event) => e.preventDefault();
    canvas.addEventListener("pointerdown", down);
    canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerup", up);
    canvas.addEventListener("pointerleave", leave);
    canvas.addEventListener("wheel", wheel, { passive: false });
    canvas.addEventListener("contextmenu", menu);
    return () => {
      canvas.removeEventListener("pointerdown", down);
      canvas.removeEventListener("pointermove", move);
      canvas.removeEventListener("pointerup", up);
      canvas.removeEventListener("pointerleave", leave);
      canvas.removeEventListener("wheel", wheel);
      canvas.removeEventListener("contextmenu", menu);
      if (timer) cancelAnimationFrame(timer);
    };
  }, []);

  return (
    <div className="fe-view">
      <canvas ref={canvasRef} />
      {props.caption ? <div className="fe-caption">{props.caption}</div> : null}
    </div>
  );
}
