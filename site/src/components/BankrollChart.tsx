// Hand-rolled SVG time-series chart (no chart library). One value axis (bankroll), a dashed
// start-baseline, recessive gridlines, two direct-labelled series (flat + Kelly). SVG y grows
// downward, so the value axis is inverted. Points are scaled into a fixed viewBox.

interface Series {
  name: string;
  color: string;
  points: { date: string; bankroll: number }[];
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function shortDate(iso: string): string {
  const [y, m] = iso.split("-");
  return `${MONTHS[Number(m) - 1]} ’${y.slice(2)}`;
}

export default function BankrollChart({ series, start }: { series: Series[]; start: number }) {
  const W = 760;
  const H = 320;
  const pad = { t: 18, r: 104, b: 38, l: 56 };
  const n = Math.max(...series.map((s) => s.points.length));
  if (n < 2) return null;

  const values = series.flatMap((s) => s.points.map((p) => p.bankroll)).concat(start);
  const lo = Math.floor(Math.min(...values) / 100) * 100;
  const hi = Math.ceil(Math.max(...values) / 100) * 100;

  const x = (i: number) => pad.l + (i / (n - 1)) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - (v - lo) / (hi - lo)) * (H - pad.t - pad.b);

  const yTicks = [0, 1, 2, 3, 4].map((k) => lo + ((hi - lo) * k) / 4);
  const xTickIdx = [0, Math.round((n - 1) / 3), Math.round((2 * (n - 1)) / 3), n - 1];
  const dates = series[0].points;

  const line = (pts: Series["points"]) =>
    pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.bankroll).toFixed(1)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="bankroll over time">
      {/* gridlines + y labels */}
      {yTicks.map((v) => (
        <g key={v}>
          <line x1={pad.l} y1={y(v)} x2={W - pad.r} y2={y(v)} className="grid" />
          <text x={pad.l - 10} y={y(v) + 4} className="ax-y" textAnchor="end">
            {v}
          </text>
        </g>
      ))}
      {/* start baseline */}
      <line x1={pad.l} y1={y(start)} x2={W - pad.r} y2={y(start)} className="baseline" />
      <text x={W - pad.r + 6} y={y(start) + 4} className="ax-note">
        start {start}
      </text>
      {/* x date labels */}
      {xTickIdx.map((i) => (
        <text key={i} x={x(i)} y={H - pad.b + 20} className="ax-x" textAnchor="middle">
          {shortDate(dates[Math.min(i, dates.length - 1)].date)}
        </text>
      ))}
      {/* series */}
      {series.map((s) => {
        const last = s.points[s.points.length - 1];
        return (
          <g key={s.name}>
            <path d={line(s.points)} className="series-line" style={{ stroke: s.color }} />
            <circle cx={x(s.points.length - 1)} cy={y(last.bankroll)} r={3.5} style={{ fill: s.color }} />
            <text
              x={x(s.points.length - 1) + 8}
              y={y(last.bankroll) + 4}
              className="series-label"
              style={{ fill: s.color }}
            >
              {s.name} {Math.round(last.bankroll)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
