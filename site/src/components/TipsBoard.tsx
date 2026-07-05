import type { TipsData } from "../types";

const pct = (x: number) => `${Math.round(x * 100)}%`;

export default function TipsBoard({ data }: { data: TipsData }) {
  if (!data.tips.length) {
    return (
      <section className="tips">
        <h2>{data.competition} — tips</h2>
        <p>No upcoming fixtures with known teams (between rounds / off-season).</p>
      </section>
    );
  }
  return (
    <section className="tips">
      <h2>{data.competition} — shadow-mode tips</h2>
      <p className="caption">
        Goals-only markets, no odds, no stake. Trained on {data.n_trained_on} played matches —
        overconfident on thin data, directional only. Goalscorer markets need player data (not
        available on free data).
      </p>
      <div className="cards">
        {data.tips.map((t) => (
          <article className="card" key={t.match_id}>
            <div className="fixture">
              {t.home} <span>vs</span> {t.away}
            </div>
            <div className="row">
              <b>1X2</b> <span className="pick">{t.tip_1x2}</span> · H {pct(t.p_H)} / D{" "}
              {pct(t.p_D)} / A {pct(t.p_A)}
            </div>
            <div className="row highlight">
              <b>Advance</b> {t.home} {pct(t.p_home_adv)} / {t.away} {pct(t.p_away_adv)}
            </div>
            <div className="row">
              <b>O/U</b> &gt;1.5 {pct(t.p_over15)} · &gt;2.5 {pct(t.p_over25)} · &gt;3.5{" "}
              {pct(t.p_over35)} · BTTS {pct(t.p_btts)}
            </div>
            <div className="row">
              <b>Likely</b> {t.most_likely_score} <span className="tops">({t.top_scores})</span>
            </div>
          </article>
        ))}
      </div>
      {data.combo && data.combo.n_legs > 0 && (
        <div className="combo">
          <b>Combo (illustrative, −EV):</b>{" "}
          {data.combo.legs.map((l) => `${l.match} [${l.pick} ${pct(l.p)}]`).join("  +  ")} →{" "}
          {pct(data.combo.combined_prob)} combined
        </div>
      )}
    </section>
  );
}
