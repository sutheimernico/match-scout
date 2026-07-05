import { useEffect, useState } from "react";
import Disclaimer from "./components/Disclaimer";
import HonestHarness from "./components/HonestHarness";
import TipsBoard from "./components/TipsBoard";
import type { BacktestData, Meta, TipsData } from "./types";

// Vite serves public/ at BASE_URL; fetch the static JSON relative to it so it works both
// locally and under the GitHub Pages sub-path.
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
      <header>
        <h1>match-scout</h1>
        <p className="tagline">
          Honest football prediction &amp; betting-slip simulation — no edge promise.
        </p>
      </header>
      {meta && <Disclaimer text={meta.disclaimer} />}
      {backtest && <HonestHarness data={backtest} />}
      {tips && <TipsBoard data={tips} />}
      {meta && (
        <footer>
          Generated {new Date(meta.generated_at).toLocaleString()} · paper-only · MIT
        </footer>
      )}
    </div>
  );
}
