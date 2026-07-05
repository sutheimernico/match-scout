// Hand-rolled SVG line chart (no chart library — grid-scout pattern): points are linearly scaled
// into a fixed viewBox; SVG y grows downward, so the value axis is inverted.
export default function BankrollChart({ points, start = 1000 }: { points: number[]; start?: number }) {
  const w = 640;
  const h = 180;
  const pad = 6;
  if (points.length < 2) return null;

  const min = Math.min(start, ...points);
  const max = Math.max(start, ...points);
  const span = max - min || 1;
  const x = (i: number) => pad + (i / (points.length - 1)) * (w - 2 * pad);
  const y = (v: number) => pad + (1 - (v - min) / span) * (h - 2 * pad);

  const path = points.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last = points[points.length - 1];
  const up = last >= start;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="chart" preserveAspectRatio="none" aria-label="bankroll curve">
      <line x1={pad} y1={y(start)} x2={w - pad} y2={y(start)} className="baseline" />
      <path d={path} className={`curve ${up ? "up" : "down"}`} />
    </svg>
  );
}
