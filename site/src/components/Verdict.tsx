import type { BacktestData } from "../types";

export default function Verdict({ data }: { data: BacktestData }) {
  const flat = data.schemes.flat.summary;
  const deltaPct = flat.yield * 100;
  const negative = flat.yield < 0;
  return (
    <section className="verdict-block">
      <p className="kicker">The result · {flat.n_bets} paper bets</p>
      <div className="verdict-headline">
        <span className={`big-num ${negative ? "down" : "up"}`}>
          {deltaPct > 0 ? "+" : ""}
          {deltaPct.toFixed(1)}%
        </span>
        <p className="verdict-lede">
          Starting at {data.start_bankroll} units, the bot's bankroll ended at{" "}
          <b>{Math.round(flat.final_bankroll)}</b> — a {negative ? "loss" : "gain"} over{" "}
          {data.league} {data.seasons.join(" & ")}.
        </p>
      </div>
      <p className="verdict-line">{data.headline_verdict}</p>
    </section>
  );
}
