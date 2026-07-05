const STEPS = [
  {
    n: "1",
    t: "Predict",
    d: "A Dixon-Coles goal model, refit before every matchday on past results only.",
  },
  {
    n: "2",
    t: "Find value",
    d: "Compare the model's probability to the bookmaker's price; bet only when the edge is positive.",
  },
  {
    n: "3",
    t: "Place paper bets",
    d: "Stake flat — and separately a bankroll-adjusted Kelly stake. No real money, ever.",
  },
  {
    n: "4",
    t: "Settle honestly",
    d: "Settle at the price taken, measure closing-line value, and report the result even when negative.",
  },
];

export default function HowItWorks() {
  return (
    <section>
      <h2>How the bot works</h2>
      <ol className="steps">
        {STEPS.map((s) => (
          <li key={s.n}>
            <span className="step-n">{s.n}</span>
            <div>
              <b>{s.t}</b>
              <p>{s.d}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="caption">
        A LightGBM machine-learning challenger was also tried — it overfit the thin data and lost to
        the simpler model. Reported, not hidden.
      </p>
    </section>
  );
}
