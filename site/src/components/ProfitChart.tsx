// Hand-rolled SVG time-series chart (no chart library). One value axis (cumulative profit in
// units), an emphasised break-even line at 0, recessive gridlines, two direct-labelled series.
// SVG y grows downward, so the value axis is inverted; profit can be negative.

interface Series {
  name: string;
  color: string;
  points: { date: string; profit: number }[];
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const shortDate = (iso: string) => {
  const [y, m] = iso.split("-");
  return `${MONTHS[Number(m) - 1]} ’${y.slice(2)}`;
};
const signed = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(Math.round(v))}`;

export default function ProfitChart({ series }: { series: Series[] }) {
  const W = 760;
  const H = 320;
  const pad = { t: 18, r: 116, b: 38, l: 64 };
  const n = Math.max(...series.map((s) => s.points.length));
  if (n < 2) return null;

  const values = series.flatMap((s) => s.points.map((p) => p.profit)).concat(0);
  const lo = Math.floor(Math.min(...values) / 500) * 500;
  const hi = Math.ceil(Math.max(...values) / 500) * 500;

  const x = (i: number) => pad.l + (i / (n - 1)) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - (v - lo) / (hi - lo)) * (H - pad.t - pad.b);

  const yTicks = [0, 1, 2, 3, 4].map((k) => lo + ((hi - lo) * k) / 4);
  const xTickIdx = [0, Math.round((n - 1) / 3), Math.round((2 * (n - 1)) / 3), n - 1];
  const dates = series[0].points;
  const line = (pts: Series["points"]) =>
    pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.profit).toFixed(1)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="cumulative profit over time">
      {yTicks.map((v) => (
        <g key={v}>
          <line x1={pad.l} y1={y(v)} x2={W - pad.r} y2={y(v)} className="grid" />
          <text x={pad.l - 10} y={y(v) + 4} className="ax-y" textAnchor="end">
            {signed(v)}
          </text>
        </g>
      ))}
      {/* break-even */}
      <line x1={pad.l} y1={y(0)} x2={W - pad.r} y2={y(0)} className="baseline" />
      <text x={W - pad.r + 6} y={y(0) + 4} className="ax-note">
        break-even
      </text>
      {xTickIdx.map((i) => (
        <text key={i} x={x(i)} y={H - pad.b + 20} className="ax-x" textAnchor="middle">
          {shortDate(dates[Math.min(i, dates.length - 1)].date)}
        </text>
      ))}
      {series.map((s) => {
        const last = s.points[s.points.length - 1];
        return (
          <g key={s.name}>
            <path d={line(s.points)} className="series-line" style={{ stroke: s.color }} />
            <circle cx={x(s.points.length - 1)} cy={y(last.profit)} r={3.5} style={{ fill: s.color }} />
            <text
              x={x(s.points.length - 1) + 8}
              y={y(last.profit) + 4}
              className="series-label"
              style={{ fill: s.color }}
            >
              {s.name} {signed(last.profit)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
