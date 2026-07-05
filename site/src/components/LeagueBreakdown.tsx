import type { BacktestData } from "../types";

const pct = (x: number) => `${x > 0 ? "+" : ""}${(x * 100).toFixed(1)}%`;

export default function LeagueBreakdown({ data }: { data: BacktestData }) {
  const worst = Math.min(...data.per_league.map((l) => l.yield), -0.001);
  return (
    <section>
      <h2>Every league tells the same story</h2>
      <p className="section-lede">
        The identical strategy, run across all five leagues independently. Every one loses — some far
        worse than others, none profitable. Breadth doesn't rescue it.
      </p>
      <div className="leagues">
        {data.per_league.map((l) => (
          <div className="league-row" key={l.league}>
            <span className="lg-name">{l.league}</span>
            <span className="lg-track">
              <span className="lg-fill" style={{ width: `${Math.min(100, (l.yield / worst) * 100)}%` }} />
            </span>
            <span className="lg-yield">{pct(l.yield)}</span>
            <span className="lg-meta">
              {l.n_bets} bets · {Math.round(l.clv_beat_rate * 100)}% CLV
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
