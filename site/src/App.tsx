import { useEffect, useState } from "react";
import Disclaimer from "./components/Disclaimer";
import ForwardRecord from "./components/ForwardRecord";
import HowItWorks from "./components/HowItWorks";
import Insight from "./components/Insight";
import LeagueBreakdown from "./components/LeagueBreakdown";
import LiveTips from "./components/LiveTips";
import TrackRecord from "./components/TrackRecord";
import Verdict from "./components/Verdict";
import type { BacktestData, ForwardData, Meta, UpcomingData } from "./types";

// Vite serves public/ at BASE_URL; fetch the static JSON relative to it so it works both locally
// (root) and under the GitHub Pages sub-path.
const base = import.meta.env.BASE_URL;

export default function App() {
  const [upcoming, setUpcoming] = useState<UpcomingData | null>(null);
  const [backtest, setBacktest] = useState<BacktestData | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [forward, setForward] = useState<ForwardData | null>(null);

  useEffect(() => {
    fetch(`${base}data/upcoming.json`).then((r) => r.json()).then(setUpcoming).catch(() => {});
    fetch(`${base}data/backtest.json`).then((r) => r.json()).then(setBacktest).catch(() => {});
    fetch(`${base}data/meta.json`).then((r) => r.json()).then(setMeta).catch(() => {});
    fetch(`${base}data/forward.json`).then((r) => r.json()).then(setForward).catch(() => {});
  }, []);

  const liveCount = upcoming?.competitions?.length ?? 0;

  return (
    <div className="page">
      <header className="masthead">
        <p className="kicker">match-scout · a systematic football betting lab, measured honestly</p>
        <h1>
          A bot placed{" "}
          {backtest ? backtest.schemes.flat.summary.n_bets.toLocaleString() : "thousands of"} paper
          bets across Europe's top leagues.
          <br />
          Did it beat the bookmakers?
        </h1>
        <p className="dek">
          A systematic model predicts every match, finds where it disagrees with the price, and
          places paper bets — then we measure, honestly, whether it comes out ahead. The number below
          is the answer; the live board shows whatever it would bet today.
        </p>
        <div className="status">
          <span className="paper-chip">● paper-only · no real money</span>
          {upcoming && (
            <span className="live-note">
              {liveCount > 0
                ? `live: ${liveCount} competition${liveCount > 1 ? "s" : ""} with fixtures`
                : "live: nothing scheduled right now"}
              {meta && ` · updated ${new Date(meta.generated_at).toLocaleDateString()}`}
            </span>
          )}
        </div>
      </header>

      {backtest && <Verdict data={backtest} />}
      {backtest && <TrackRecord data={backtest} />}
      {backtest && <LeagueBreakdown data={backtest} />}
      {backtest && <Insight data={backtest} />}
      {forward && <ForwardRecord data={forward} base={base} />}
      {upcoming && <LiveTips data={upcoming} />}
      <HowItWorks />
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
