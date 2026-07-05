import type { BacktestData } from "../types";
import ProfitChart from "./ProfitChart";

export default function TrackRecord({ data }: { data: BacktestData }) {
  const series = [
    { name: "Flat", color: "#2a78d6", points: data.schemes.flat.curve },
    { name: "Kelly", color: "#1baf7a", points: data.schemes.kelly.curve },
  ];
  return (
    <section>
      <h2>The bot's running profit over time</h2>
      <p className="section-lede">
        Betting across the <b>Top-5 European leagues</b> — England, Spain, Germany, Italy, France —
        matchday after matchday. Two staking styles run side by side: a <b>flat</b> stake and a
        bankroll-adjusted <b>Kelly</b> stake. Both fall below break-even and stay there.
      </p>
      <ProfitChart series={series} />
      <p className="caption">
        Cumulative profit in units · {data.date_range[0]} → {data.date_range[1]} · walk-forward, model
        refit on past results only (no lookahead). A rising line would mean it beat the market.
      </p>
    </section>
  );
}
