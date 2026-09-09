/**
 * Choose what to extract.
 *
 * Paths are editable. What gets extracted is whatever is in the fields when Extract is pressed, not
 * whatever happened to be in the folder when the page loaded - so a file can be swapped, pointed
 * elsewhere, or removed without touching the filesystem.
 *
 * Each field validates as it is typed. A path that does not resolve disables Extract rather than
 * failing ten seconds into a pipeline.
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { ProjectRow } from "../api/client";

interface Row {
  id: number;
  path: string;
  label: string | null;
  exists: boolean | null;
  size: number;
}

interface UploadStageProps {
  projects: ProjectRow[];
  busy: string | null;
  error: string | null;
  onExtract: (project: ProjectRow, paths: string[]) => void;
}

export function UploadStage(props: UploadStageProps) {
  const [active, setActive] = useState<string | null>(props.projects[0]?.name ?? null);
  const [rows, setRows] = useState<Row[]>([]);

  const project = props.projects.find((p) => p.name === active) ?? null;

  useEffect(() => {
    if (!project) return;
    setRows(
      project.artifacts.map((artifact, index) => ({
        id: index,
        path: artifact.path,
        label: artifact.label,
        exists: true,
        size: artifact.size_bytes,
      })),
    );
  }, [project?.name]);

  const check = useCallback(async (id: number, path: string) => {
    if (!path.trim()) {
      setRows((current) =>
        current.map((r) => (r.id === id ? { ...r, exists: null, label: null, size: 0 } : r)),
      );
      return;
    }
    const result = await api.check(path);
    setRows((current) =>
      current.map((r) =>
        r.id === id
          ? { ...r, exists: result.exists, label: result.label, size: result.size_bytes }
          : r,
      ),
    );
  }, []);

  const usable = rows.filter((r) => r.exists && r.path.trim());
  const hasCad = usable.some((r) => r.label === "CAD");
  const broken = rows.some((r) => r.path.trim() && r.exists === false);

  return (
    <div className="upload">
      <div className="upload-inner">
        {props.projects.length > 1 ? (
          <div className="project-tabs">
            {props.projects.map((entry) => (
              <button
                key={entry.name}
                data-active={entry.name === active}
                onClick={() => setActive(entry.name)}
              >
                {entry.title}
              </button>
            ))}
          </div>
        ) : null}

        {project ? (
          <div className="panel">
            <div className="panel-head">
              <h1>{project.title}</h1>
              <span className="mono dim">{project.path}</span>
            </div>

            <div className="fields">
              {rows.map((row) => (
                <div className="field" key={row.id} data-bad={row.exists === false}>
                  <label>{row.label ?? "—"}</label>
                  <input
                    className="mono"
                    value={row.path}
                    spellCheck={false}
                    onChange={(event) => {
                      const path = event.target.value;
                      setRows((current) =>
                        current.map((r) => (r.id === row.id ? { ...r, path } : r)),
                      );
                      void check(row.id, path);
                    }}
                  />
                  <span className="mono dim size">
                    {row.exists === false ? "not found" : row.size ? size(row.size) : ""}
                  </span>
                  <button
                    className="ghost"
                    title="Remove"
                    onClick={() => setRows((c) => c.filter((r) => r.id !== row.id))}
                  >
                    ×
                  </button>
                </div>
              ))}
              <button
                className="ghost add"
                onClick={() =>
                  setRows((c) => [
                    ...c,
                    { id: Math.max(0, ...c.map((r) => r.id)) + 1, path: "", label: null, exists: null, size: 0 },
                  ])
                }
              >
                + add file
              </button>
            </div>

            {props.error ? <div className="error-inline">{props.error}</div> : null}

            <div className="panel-foot">
              <button
                className="primary"
                disabled={!hasCad || broken || props.busy !== null}
                onClick={() => props.onExtract(project, usable.map((r) => r.path))}
              >
                {props.busy ? "Extracting…" : "Extract"}
              </button>
              {!hasCad && !broken ? <span className="dim">CAD required</span> : null}
            </div>
          </div>
        ) : (
          <div className="panel empty-panel">
            No projects. Add a folder under <code>assets/</code>.
          </div>
        )}
      </div>
    </div>
  );
}

function size(bytes: number): string {
  return bytes >= 1e6 ? `${(bytes / 1e6).toFixed(1)} MB` : `${Math.round(bytes / 1e3)} kB`;
}
