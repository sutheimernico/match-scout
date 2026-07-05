import { useEffect, useState } from "react";
import Disclaimer from "./components/Disclaimer";
import HowItWorks from "./components/HowItWorks";
import Insight from "./components/Insight";
import TipsBoard from "./components/TipsBoard";
import TrackRecord from "./components/TrackRecord";
import Verdict from "./components/Verdict";
import type { BacktestData, Meta, TipsData } from "./types";

// Vite serves public/ at BASE_URL; fetch the static JSON relative to it so it works both locally
// (root) and under the GitHub Pages sub-path.
const base = import.meta.env.BASE_URL;

export default function App() {
  const [tips, setTips] = useState<TipsData | null>(null);
  const [backtest, setBacktest] = useState<BacktestData | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);

  useEffect(() => {
    fetch(`${base}data/tips.json`).then((r) => r.json()).then(setTips).catch(() => {});
    fetch(`${base}data/backtest.json`).then((r) => r.json()).then(setBacktest).catch(() => {});
    fetch(`${base}data/meta.json`).then((r) => r.json()).then(setMeta).catch(() => {});
  }, []);

  return (
    <div className="page">
      <header className="masthead">
        <p className="kicker">match-scout · an honest football betting lab</p>
        <h1>
          A bot bet on{" "}
          {backtest ? backtest.schemes.flat.summary.n_bets : "hundreds of"} football matches.
          <br />
          Did it beat the bookmakers?
        </h1>
        <p className="dek">
          A systematic model predicts every match, finds where it disagrees with the price, and
          places paper bets — then we measure, honestly, whether it comes out ahead. Spoiler in the
          number below.
        </p>
        <span className="paper-chip">● paper-only · no real money</span>
      </header>

      {backtest && <Verdict data={backtest} />}
      {backtest && <TrackRecord data={backtest} />}
      {backtest && <Insight data={backtest} />}
      <HowItWorks />
      {tips && <TipsBoard data={tips} />}
      {meta && <Disclaimer text={meta.disclaimer} />}
      {meta && (
        <footer>
          Generated {new Date(meta.generated_at).toLocaleDateString()} · educational simulation ·
          paper stakes only · MIT
        </footer>
      )}
    </div>
  );
}
