import type { TipsData } from "../types";

const pct = (x: number) => `${Math.round(x * 100)}%`;
const first = (name: string) => name.split(" ")[0];

export default function TipsBoard({ data }: { data: TipsData }) {
  if (!data.tips.length) {
    return (
      <section>
        <h2>What the bot would bet today</h2>
        <p className="section-lede">No upcoming fixtures with known teams right now (between rounds).</p>
      </section>
    );
  }
  return (
    <section>
      <h2>What the bot would bet today — {data.competition}</h2>
      <p className="section-lede">
        Shadow-mode: predictions only, no odds for these fixtures, so no stake. Trained on{" "}
        {data.n_trained_on} matches — thin data, so treat as directional. Goalscorer bets need
        player data we don't have.
      </p>
      <div className="cards">
        {data.tips.map((t) => (
          <article className="card" key={t.match_id}>
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
              <div>
                <dt>Advance</dt>
                <dd>
                  {first(t.home)} {pct(t.p_home_adv)} · {first(t.away)} {pct(t.p_away_adv)}
                </dd>
              </div>
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
        ))}
      </div>
      {data.combo && data.combo.n_legs > 0 && (
        <p className="combo">
          <b>Combo idea</b> (illustrative — accumulators are −EV):{" "}
          {data.combo.legs.map((l) => `${l.pick} in ${l.match}`).join("  +  ")} →{" "}
          {pct(data.combo.combined_prob)} combined.
        </p>
      )}
    </section>
  );
}
