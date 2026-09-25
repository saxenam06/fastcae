/**
 * A new campaign: one rib network in the kept design volumes, held to the target's metal and read
 * against it at every stage. What is chosen here is only how the network is seeded - the rules
 * that place, move and keep its fins are the same for every seeder.
 */

import { useEffect, useState } from "react";
import { getJson, postJson } from "../api/client";

interface Seeder {
  name: string;
  words: string;
}

interface Asked {
  pattern: string;
  rays: number;
  steps: number;
  polish: number;
  seed: number;
}

interface RibPlan {
  volumes: { name: string; volume_L: number | null; faces: number[] }[];
  target: { name: string; metal_L: number | null; words: string | null } | null;
  seeders: Seeder[];
  defaults: Asked;
  limits: { rays: [number, number]; steps: [number, number]; polish: [number, number] };
  deck: boolean;
}

export function RibPlanPage({ onLaunched }: { onLaunched: () => void }) {
  const [plan, setPlan] = useState<RibPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [volumes, setVolumes] = useState<Set<string>>(new Set());
  const [asked, setAsked] = useState<Asked | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getJson<RibPlan>("/api/ribs/plan")
      .then((p) => {
        setPlan(p);
        setVolumes(new Set(p.volumes.map((v) => v.name)));
        setAsked(p.defaults);
      })
      .catch((e: unknown) => setError(String(e)));
  }, []);

  if (error && !plan) return <div className="stage-page"><div className="later fe-error">{error}</div></div>;
  if (!plan || !asked) return <div className="stage-page"><div className="later">reading the design volumes…</div></div>;

  const toggle = (name: string) => {
    const next = new Set(volumes);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    setVolumes(next);
  };
  const number = (key: "rays" | "steps" | "polish", label: string, hint: string) => (
    <label>
      <span>{label}</span>
      <input
        type="number"
        min={plan.limits[key][0]}
        max={plan.limits[key][1]}
        value={asked[key]}
        onChange={(e) => setAsked({ ...asked, [key]: Number(e.target.value) })}
      />
      <span className="dim">{hint}</span>
    </label>
  );

  return (
    <div className="campaign-page rib-plan">
      <header className="campaign-head">
        <h2>New campaign</h2>
        <span className="dim">one rib network, held to the target</span>
      </header>

      <section>
        <h3>Design volumes</h3>
        {plan.volumes.length ? (
          <div className="rib-plan-chips">
            {plan.volumes.map((v) => (
              <label key={v.name} className="rib-volume" data-on={volumes.has(v.name)}>
                <input type="checkbox" checked={volumes.has(v.name)} onChange={() => toggle(v.name)} />
                {v.name} <span className="dim num">{v.volume_L?.toFixed(1)} L</span>
              </label>
            ))}
          </div>
        ) : (
          <p className="dim">No volume kept yet: pick faces on CAD → Design volumes and keep one.</p>
        )}
      </section>

      <section>
        <h3>Target</h3>
        {plan.target ? (
          <p className="rib-plan-row">
            <b>{plan.target.name}</b>{" "}
            <span className="dim num">
              {plan.target.metal_L?.toFixed(2)} L of ribs · {plan.target.words}
            </span>
            <span className="vs-pill" title="the network may add no more metal than the target, and passes only if it beats it">
              the cap and the pass line
            </span>
          </p>
        ) : (
          <p className="dim">No target solved: a network has nothing to be held to.</p>
        )}
      </section>

      <section>
        <h3>Seed</h3>
        <div className="rib-plan-chips">
          {plan.seeders.map((s) => (
            <label key={s.name} className="rib-volume" data-on={asked.pattern === s.name} title={s.words}>
              <input
                type="radio"
                name="seeder"
                checked={asked.pattern === s.name}
                onChange={() => setAsked({ ...asked, pattern: s.name })}
              />
              {s.name}
            </label>
          ))}
        </div>
        <p className="dim">{plan.seeders.find((s) => s.name === asked.pattern)?.words}</p>
      </section>

      <details className="rib-plan-more">
        <summary>Steps</summary>
        <section className="rib-plan-grid">
          {number("rays", asked.pattern === "scatter" ? "fins" : "rays", "a volume, at most")}
          {number("steps", "pass", "steps")}
          {number("polish", "polish", "steps")}
          {asked.pattern === "scatter" ? (
            <label>
              <span>scatter</span>
              <input
                type="number"
                min={0}
                value={asked.seed}
                onChange={(e) => setAsked({ ...asked, seed: Number(e.target.value) })}
              />
              <span className="dim">the same number scatters the same fins</span>
            </label>
          ) : null}
        </section>
      </details>

      {error ? <p className="fe-error">{error}</p> : null}
      <div className="campaign-actions">
        <button
          className="primary"
          disabled={busy || !volumes.size || !plan.deck || !plan.target}
          onClick={async () => {
            setBusy(true);
            setError(null);
            try {
              await postJson("/api/ribs/campaigns", { ...asked, volumes: [...volumes] });
              onLaunched();
            } catch (caught) {
              setError(String(caught));
            } finally {
              setBusy(false);
            }
          }}
        >
          Make the network
        </button>
        <span className="dim">about 15 min: seed, pass, chooser, polish, then CAD, mesh and solve</span>
      </div>
    </div>
  );
}
