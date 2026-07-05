import type { BacktestData } from "../types";

export default function Insight({ data }: { data: BacktestData }) {
  const beat = Math.round(data.clv_beat_rate * 100);
  return (
    <section className="insight">
      <div className="insight-num">{beat}%</div>
      <div className="insight-body">
        <h2>Why it loses — and how we know that's honest</h2>
        <p className="section-lede">
          Only <b>{beat}%</b> of the bot's “value” bets got a better price than the market's{" "}
          <b>closing line</b> — the sharpest signal in football. The bot bets against it, and the
          market is right the other {100 - beat}% of the time. This closing-line-value check is
          leak-resistant: it agrees with the falling bankroll, so the negative result is real, not a
          quirk of one lucky or unlucky run.
        </p>
      </div>
    </section>
  );
}
