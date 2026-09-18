/**
 * The pipeline as the interface holds it: the steps of both stages, merged with what a run in
 * progress has reported so far, and the entities they produced, read on demand and kept.
 *
 * Opening a project shows the Read stage at once - extraction ran it - and starts the design-space
 * stage straight away. The server reads the space back when nothing it depends on has changed, so
 * that costs a second; otherwise each step is shown starting and finishing as it runs.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  EntityDetail,
  EntitySummary,
  Group,
  Pipeline,
  PipelineEvent,
  RunStatus,
  StepRun,
} from "../api/pipeline";
import { pipelineApi } from "../api/pipeline";

interface LiveStep {
  status: RunStatus;
  seconds?: number;
  detail?: string;
}

export interface PipelineState {
  pipeline: Pipeline | null;
  /** Every step by id, with a run's live status laid over what the server last said. */
  steps: Map<string, StepRun>;
  /** When each running step was first seen running, in this page's clock. */
  started: Map<string, number>;
  running: boolean;
  error: string | null;
  /** Bumped whenever the design space changes, so whatever shows it reads it again. */
  version: number;
  /** Answers recorded since the space was last derived: they apply on the next run. */
  unapplied: number;
  run: (reuse?: boolean) => Promise<void>;
  /** Follow a run something else started - the agent - until it ends. */
  follow: (starting?: boolean) => Promise<void>;
  /** Read the pipeline again: something else changed it. */
  refresh: () => Promise<Pipeline>;
  answer: (question: string, value: string | null) => Promise<void>;
  entity: (id: string) => Promise<EntityDetail>;
  members: (group: Group) => Promise<EntitySummary[]>;
}

export function usePipeline(project: string | null): PipelineState {
  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [live, setLive] = useState<Record<string, LiveStep>>({});
  const [running, setRunning] = useState(false);
  // A run this page started and is streaming, as opposed to one it follows by asking.
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [unapplied, setUnapplied] = useState(0);
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
    async (reuse = true) => {
      setRunning(true);
      setStreaming(true);
      setError(null);
      setLive({});
      // The space shown so far is on its way out: whatever shows layers reads the run's instead.
      setVersion((v) => v + 1);
      try {
        await pipelineApi.run({ reuse }, (event: PipelineEvent) => {
          if (event.type === "step") {
            setLive((was) => ({
              ...was,
              [event.id]: { status: event.status, seconds: event.seconds, detail: event.detail },
            }));
          } else if (event.type === "error") {
            setError(event.message);
          }
        });
        setUnapplied(0);
      } catch (caught) {
        setError(String(caught));
      } finally {
        await refresh().catch(() => undefined);
        setLive({});
        setStreaming(false);
        setRunning(false);
        setVersion((v) => v + 1);
      }
    },
    [refresh],
  );

  // A run this page did not start - it was reloaded mid-run, or the agent started it - is followed
  // by asking again until it ends; the server's pipeline carries each step's live status. One
  // about to start is waited for a few seconds first.
  const follow = useCallback(async (starting = false) => {
    setRunning(true);
    try {
      let seen = !starting;
      for (let asked = 0; ; asked++) {
        await new Promise((r) => setTimeout(r, 1500));
        const found = await refresh();
        if (found.running) seen = true;
        else if (seen || asked > 6) break;
      }
    } catch (caught) {
      setError(String(caught));
    } finally {
      setRunning(false);
      setVersion((v) => v + 1);
    }
  }, [refresh]);

  // A project opened: its pipeline, and the design space derived - or read back - if it is not
  // held yet.
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
        const space = found.stages.find((s) => s.id === "space");
        const idle = space?.steps.every((s) => s.status === "pending") ?? false;
        if (found.running) void follow();
        else if (idle) void run(true);
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
        // While a run streams, a design-space step is what the run has said about it - its outputs
        // arrive with the space when the run ends.
        const now = streaming && stage.id === "space" ? live[step.id] : undefined;
        out.set(
          step.id,
          streaming && stage.id === "space"
            ? {
                ...step,
                status: now?.status ?? "pending",
                seconds: now?.seconds ?? null,
                detail: now?.detail ?? "",
                outputs: [],
              }
            : step,
        );
      }
    }
    return out;
  }, [pipeline, live, streaming]);

  // A step's clock starts when it is first seen running - from the stream or from asking.
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

  const answer = useCallback(
    async (question: string, value: string | null) => {
      await pipelineApi.answer(question, value);
      details.current.delete(question);
      setUnapplied((n) => n + 1);
      await refresh();
    },
    [refresh],
  );

  return {
    pipeline,
    steps,
    started,
    running,
    error,
    version,
    unapplied,
    run,
    follow,
    refresh,
    answer,
    entity,
    members,
  };
}
