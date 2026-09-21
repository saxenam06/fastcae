/**
 * The pipeline as the interface holds it: the steps that read the engineer's files, the design
 * space last, and the entities they produced, read on demand and kept.
 *
 * Opening a project shows the steps extraction ran, and reads the design space from the project's
 * folder - a second or two. Where there is none yet, the rules define it and the step says what
 * they are doing as they go.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { EntityDetail, EntitySummary, Group, Pipeline, PipelineEvent, StepRun } from "../api/pipeline";
import { pipelineApi } from "../api/pipeline";

/** The design space's step: the last of the pipeline. */
export const SPACE_STEP = "space";

export interface PipelineState {
  pipeline: Pipeline | null;
  /** Every step by id, the design space's with what a run in progress has said laid over it. */
  steps: Map<string, StepRun>;
  /** When each running step was first seen running, in this page's clock. */
  started: Map<string, number>;
  running: boolean;
  error: string | null;
  /** Bumped whenever the design space changes, so whatever shows it reads it again. */
  version: number;
  /** Read the design space - or, ``again``, define it anew by the rules. */
  run: (again?: boolean) => Promise<void>;
  /** Follow a run something else started until it ends. */
  follow: () => Promise<void>;
  /** Read the pipeline again: something else changed it. */
  refresh: () => Promise<Pipeline>;
  entity: (id: string) => Promise<EntityDetail>;
  members: (group: Group) => Promise<EntitySummary[]>;
}

export function usePipeline(project: string | null): PipelineState {
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [said, setSaid] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const details = useRef(new Map<string, EntityDetail>());
  const opened = useRef<string | null>(null);
  const [started, setStarted] = useState(() => new Map<string, number>());

  const refresh = useCallback(async () => {
    const found = await pipelineApi.pipeline();
    details.current.clear();
    setPipeline(found);
    return found;
  }, []);

  const run = useCallback(
    async (again = false) => {
      setRunning(true);
      setError(null);
      setSaid(null);
      try {
        await refresh().catch(() => undefined);
        await pipelineApi.run({ again }, (event: PipelineEvent) => {
          if (event.type === "say") setSaid(event.detail);
          else if (event.type === "error") setError(event.message);
        });
      } catch (caught) {
        setError(String(caught));
      } finally {
        await refresh().catch(() => undefined);
        setSaid(null);
        setRunning(false);
        setVersion((v) => v + 1);
      }
    },
    [refresh],
  );

  // A run this page did not start - it was reloaded mid-run - is followed by asking again until
  // it ends.
  const follow = useCallback(async () => {
    setRunning(true);
    try {
      for (;;) {
        await new Promise((r) => setTimeout(r, 1500));
        const found = await refresh();
        if (!found.running) break;
      }
    } catch (caught) {
      setError(String(caught));
    } finally {
      setRunning(false);
      setVersion((v) => v + 1);
    }
  }, [refresh]);

  // A project opened: its pipeline, and its design space read - or defined - if it is not held yet.
  useEffect(() => {
    if (!project) {
      setPipeline(null);
      opened.current = null;
      return;
    }
    let live = true;
    refresh()
      .then((found) => {
        if (!live || opened.current === project) return;
        opened.current = project;
        const space = found.stages.flatMap((s) => s.steps).find((s) => s.id === SPACE_STEP);
        if (found.running) void follow();
        else if (space?.status === "pending") void run(false);
      })
      .catch((caught) => live && setError(String(caught)));
    return () => {
      live = false;
    };
  }, [project, refresh, run, follow]);

  const steps = useMemo(() => {
    const out = new Map<string, StepRun>();
    for (const stage of pipeline?.stages ?? []) {
      for (const step of stage.steps) {
        // While the design space is read or defined, its step says what the rules last said.
        out.set(
          step.id,
          step.id === SPACE_STEP && running
            ? { ...step, status: "running", detail: said ?? step.detail, outputs: [] }
            : step,
        );
      }
    }
    return out;
  }, [pipeline, said, running]);

  // A step's clock starts when it is first seen running.
  useEffect(() => {
    setStarted((was) => {
      const next = new Map<string, number>();
      for (const [id, step] of steps) {
        if (step.status === "running") next.set(id, was.get(id) ?? Date.now());
      }
      const same = next.size === was.size && [...next].every(([id, t]) => was.get(id) === t);
      return same ? was : next;
    });
  }, [steps]);

  const entity = useCallback(async (id: string) => {
    const known = details.current.get(id);
    if (known) return known;
    const found = await pipelineApi.entity(id);
    details.current.set(id, found);
    return found;
  }, []);

  const members = useCallback(async (group: Group) => {
    if (group.ids.length) {
      const found = await pipelineApi.entities({ ids: group.ids, limit: group.ids.length });
      return found.entities;
    }
    const found = await pipelineApi.entities({ kind: group.kind, step: group.step, limit: 5000 });
    return found.entities;
  }, []);

  return { pipeline, steps, started, running, error, version, run, follow, refresh, entity, members };
}
