import type { BacktestData } from "../types";
import BankrollChart from "./BankrollChart";

export default function TrackRecord({ data }: { data: BacktestData }) {
  const series = [
    { name: "Flat", color: "#2a78d6", points: data.schemes.flat.curve },
    { name: "Kelly", color: "#1baf7a", points: data.schemes.kelly.curve },
  ];
  return (
    <section>
      <h2>The bot's track record over time</h2>
      <p className="section-lede">
        It placed a paper bet whenever its model disagreed with the price — matchday after matchday.
        Two staking styles run side by side: a <b>flat</b> stake and a bankroll-adjusted{" "}
        <b>Kelly</b> stake. Both drift below the {data.start_bankroll}-unit start and never recover.
      </p>
      <BankrollChart series={series} start={data.start_bankroll} />
      <p className="caption">
        {data.date_range[0]} → {data.date_range[1]} · walk-forward, model refit on past results only
        (no lookahead). A rising line would mean it beat the market.
      </p>
    </section>
  );
}
