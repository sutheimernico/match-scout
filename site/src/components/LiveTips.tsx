import { useState } from "react";
import type { Tip, UpcomingData } from "../types";

const pct = (x: number) => `${Math.round(x * 100)}%`;
const first = (name: string) => name.split(" ")[0];

function TipCard({ t, cup }: { t: Tip; cup: boolean }) {
  return (
    <article className="card">
      <div className="card-top">
        <span className="teams">
          {t.home} <em>v</em> {t.away}
        </span>
        <span className="pick-chip">{t.tip_1x2}</span>
      </div>
      <div className="prob-bar" aria-hidden="true">
        <span className="seg h" style={{ width: pct(t.p_H) }} />
        <span className="seg d" style={{ width: pct(t.p_D) }} />
        <span className="seg a" style={{ width: pct(t.p_A) }} />
      </div>
      <div className="prob-legend">
        <span>
          <i className="dot h" />H {pct(t.p_H)}
        </span>
        <span>
          <i className="dot d" />D {pct(t.p_D)}
        </span>
        <span>
          <i className="dot a" />A {pct(t.p_A)}
        </span>
      </div>
      <dl className="mkt">
        {cup && (
          <div>
            <dt>Advance</dt>
            <dd>
              {first(t.home)} {pct(t.p_home_adv)} · {first(t.away)} {pct(t.p_away_adv)}
            </dd>
          </div>
        )}
        <div>
          <dt>Over 2.5</dt>
          <dd>{pct(t.p_over25)}</dd>
        </div>
        <div>
          <dt>BTTS</dt>
          <dd>{pct(t.p_btts)}</dd>
        </div>
        <div>
          <dt>Likely score</dt>
          <dd>{t.most_likely_score}</dd>
        </div>
      </dl>
    </article>
  );
}

export default function LiveTips({ data }: { data: UpcomingData }) {
  const [sel, setSel] = useState(0);
  const comps = data.competitions ?? [];

  if (!comps.length) {
    return (
      <section>
        <h2>What the bot is betting now</h2>
        <p className="section-lede">
          Nothing scheduled right now — the bot is between rounds. Tips appear automatically when the
          next competition kicks off; no part of this page is wired to one specific tournament.
        </p>
      </section>
    );
  }

  const comp = comps[Math.min(sel, comps.length - 1)];
  const cup = comp.kind === "cup";

  return (
    <section>
      <h2>What the bot is betting now</h2>
      {comps.length > 1 && (
        <div className="tabs" role="tablist">
          {comps.map((c, i) => (
            <button
              key={c.code}
              role="tab"
              aria-selected={i === sel}
              className={`tab ${i === sel ? "on" : ""}`}
              onClick={() => setSel(i)}
            >
              {c.name} <span className="tab-n">{c.n_scheduled}</span>
            </button>
          ))}
        </div>
      )}
      <p className="section-lede">
        {comp.name} · shadow-mode: predictions only, no odds for these fixtures, so no stake.
        {cup && " Knockout — “Advance” is the qualify market (extra time + penalties), different from the 90-minute result."}{" "}
        Fit on {comp.n_trained_on} played matches — treat as directional, not gospel.
      </p>
      <div className="cards">
        {comp.tips.map((t) => (
          <TipCard key={t.match_id} t={t} cup={cup} />
        ))}
      </div>
      {comp.combo && comp.combo.n_legs > 0 && (
        <p className="combo">
          <b>Combo idea</b> (illustrative — accumulators are −EV):{" "}
          {comp.combo.legs.map((l) => `${l.pick} in ${l.match}`).join("  +  ")} →{" "}
          {pct(comp.combo.combined_prob)} combined.
        </p>
      )}
    </section>
  );
}
