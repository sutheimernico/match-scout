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
          Flat 10-unit stakes across the <b>Top-5 European leagues</b> ({data.seasons.join(" & ")})
          {" "}left a net {negative ? "loss" : "gain"} of{" "}
          <b>{Math.abs(Math.round(flat.profit))} units</b> on {Math.round(flat.total_staked)} staked.
        </p>
      </div>
      <p className="verdict-line">{data.headline_verdict}</p>
    </section>
  );
}
