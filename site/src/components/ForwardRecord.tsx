import type { ForwardData } from "../types";
import ProfitChart from "./ProfitChart";

const pct = (x: number | null, d = 1) =>
  x === null ? "–" : `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x * 100).toFixed(d)}%`;

// Live paper record. Unlike the backtest above, every bet here was written down before its
// kickoff, so nothing in it can be hindsight. Small-n is shown, never smoothed over.
export default function ForwardRecord({ data, base }: { data: ForwardData; base: string }) {
  const b = data.bets;
  const cal = data.calibration;
  return (
    <section>
      <h2>Live paper record{data.since ? ` since ${data.since}` : ""}</h2>
      <p className="section-lede">
        The same frozen model, now betting <b>forward</b>: every bet is logged with its timestamp
        before kickoff and settled after the final whistle. Expectation from the backtest: it loses
        to the market. This is where that expectation is tested on matches nobody has seen yet.
      </p>
      {data.state === "empty" && (
        <p className="combo">No forward bets or predictions yet — the first run logs them.</p>
      )}
      {data.state === "pending" && (
        <p className="combo">
          {b.n_pending} paper bet{b.n_pending === 1 ? "" : "s"} placed, none settled yet. No result
          is claimed before the matches are played.
        </p>
      )}
      {data.state === "settled" && (
        <>
          <dl className="mkt">
            <div>
              <dt>settled bets</dt>
              <dd>
                {b.n_bets} ({b.n_won} won, {b.n_pending} open)
              </dd>
            </div>
            <div>
              <dt>yield · 95% CI</dt>
              <dd>
                {pct(b.yield)} · [{pct(b.yield_ci?.[0] ?? null, 0)}, {pct(b.yield_ci?.[1] ?? null, 0)}]
              </dd>
            </div>
            <div>
              <dt>beat the closing line</dt>
              <dd>
                {pct(b.clv_beat_rate, 0)} (vs. {Object.keys(b.clv_books).join(", ") || "–"})
              </dd>
            </div>
            {cal.n > 0 && (
              <div>
                <dt>Brier model / market · n={cal.n}</dt>
                <dd>
                  {cal.brier_model?.toFixed(3)} / {cal.brier_market?.toFixed(3)}
                </dd>
              </div>
            )}
          </dl>
          <p className="verdict-line">{b.verdict}</p>
          <ProfitChart series={[{ name: "Forward", color: "#2a78d6", points: b.curve }]} />
        </>
      )}
      <div className="disclaimer" role="note">
        ⚠️ Simulation, paper stakes only. Expectation from the backtest: a loss against the market.
      </div>
      <p className="caption">
        Matchday view in German, with every fixture's model-vs-market probabilities:{" "}
        <a href={`${base}spieltag.html`}>Spieltag page</a>.
      </p>
    </section>
  );
}
