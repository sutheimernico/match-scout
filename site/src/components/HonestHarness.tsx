import type { BacktestData } from "../types";
import BankrollChart from "./BankrollChart";

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <span className="v">{value}</span>
      <span className="l">{label}</span>
    </div>
  );
}

export default function HonestHarness({ data }: { data: BacktestData }) {
  const s = data.summary;
  const bankroll = data.bankroll_curve.map((p) => p.bankroll);
  return (
    <section className="harness">
      <h2>Honest harness — does it beat the market?</h2>
      <p className="verdict">{data.verdict}</p>
      <div className="stats">
        <Stat label="Value bets" value={String(s.n_bets)} />
        <Stat label="Yield" value={pct(s.yield)} />
        <Stat label="Yield 95% CI" value={`${pct(s.yield_ci[0])} … ${pct(s.yield_ci[1])}`} />
        <Stat label="CLV beat-rate" value={pct(s.clv_beat_rate)} />
        <Stat label="Max drawdown" value={pct(s.max_drawdown)} />
      </div>
      <BankrollChart points={bankroll} />
      <p className="caption">
        {data.league} {data.seasons.join(" + ")} · flat stake, start 1000u · a rising curve would
        beat the market — it does not. CLV beat-rate under 50% is the leak-resistant proof of no edge.
      </p>
    </section>
  );
}
