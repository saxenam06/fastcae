/**
 * A draggable edge between two panes.
 *
 * Pointer events are taken on the window rather than the handle, so a fast drag that outruns the
 * cursor does not drop the gesture halfway across the screen - which on a four-pixel target is
 * most of them.
 */

import { useCallback } from "react";

interface SplitterProps {
  /** Called with how far the edge moved, in pixels, as it moves. */
  onResize: (delta: number) => void;
  side: "left" | "right";
}

export function Splitter(props: SplitterProps) {
  const { onResize } = props;

  const begin = useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault();
      let last = event.clientX;
      const move = (moved: PointerEvent) => {
        onResize(moved.clientX - last);
        last = moved.clientX;
      };
      const end = () => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", end);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", end);
      // Held on the body for the length of the drag: without it the cursor flickers back to a
      // caret every time it leaves the handle, and text on either side selects as you drag.
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [onResize],
  );

  return (
    <div
      className="splitter"
      data-side={props.side}
      onPointerDown={begin}
      role="separator"
      aria-orientation="vertical"
    />
  );
}
