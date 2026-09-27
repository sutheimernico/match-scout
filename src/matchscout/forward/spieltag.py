"""The German "Spieltag" page: next fixtures per league, model vs. market, and the forward record.

One self-contained HTML file (inline CSS, no JS, no external requests), written into
`site/public/` so the existing dashboard serves it and it also opens straight from disk.
Everything on it is read from the committed forward logs — nothing is fetched or refitted here,
so the page can only show what the loop actually recorded before kickoff.

Paper stakes only. The disclaimer is part of the page body, not a dismissible banner.
"""

from __future__ import annotations

import html
from typing import Any

import pandas as pd

from matchscout.forward.ledger import PENDING, SETTLED
from matchscout.forward.predictions import PREDICTED
from matchscout.forward.report import MIN_N

LEAGUES = {  # display order: the one Nico follows first
    "D1": "Bundesliga",
    "E0": "Premier League",
    "SP1": "La Liga",
    "I1": "Serie A",
    "F1": "Ligue 1",
}
SELECTION = {
    "H": "1 (Heim)",
    "D": "X (Remis)",
    "A": "2 (Gast)",
    "over": "Über 2,5 Tore",
    "under": "Unter 2,5 Tore",
}
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
BOOKS = {"PS": "Pinnacle", "Avg": "Marktschnitt", "B365": "Bet365"}

DISCLAIMER = (
    "Simulation mit Papier-Einsätzen — keine Wettempfehlung, kein Echtgeld. "
    "Erwartung laut Backtest: Verlust gegen den Markt."
)


def backtest_line(backtest: dict[str, Any] | None) -> str:
    """One sentence from the committed `backtest.json`, so the page quotes it, not a copy."""
    if not backtest:
        return ""
    flat = backtest["schemes"]["flat"]["summary"]
    lo, hi = flat["yield_ci"]
    seasons = " und ".join(f"20{s[:2]}/{s[2:]}" for s in backtest.get("seasons", []))
    return (
        f"Backtest {seasons}: {_num(flat['n_bets'], 0)} Papier-Wetten, Rendite "
        f"{_pct(flat['yield'], 1, True)} (95-%-Intervall {_pct(lo, 1, True)} bis "
        f"{_pct(hi, 1, True)})."
    )

CSS = """
:root{--page:#f9f9f7;--surface:#fff;--ink:#111;--ink-2:#52514e;--muted:#898781;--hair:#e5e4de;
--up:#0a7a2f;--down:#c0392b;--accent:#2a78d6;--warn-bg:#fff4e5;--warn-ink:#7a4a00}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--page:#141414;--surface:#1c1c1c;
--ink:#eee;--ink-2:#b5b3ad;--muted:#8a8883;--hair:#2e2e2c;--up:#4cc26f;--down:#ff6b5e;
--accent:#6aa8ff;--warn-bg:#2d2414;--warn-ink:#f0c27a}}
:root[data-theme="dark"]{--page:#141414;--surface:#1c1c1c;--ink:#eee;--ink-2:#b5b3ad;
--muted:#8a8883;--hair:#2e2e2c;--up:#4cc26f;--down:#ff6b5e;--accent:#6aa8ff;--warn-bg:#2d2414;
--warn-ink:#f0c27a}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:1.6rem;margin:.2em 0}h2{font-size:1.2rem;margin:1.6em 0 .4em}
h3{font-size:1rem;margin:1.2em 0 .3em;color:var(--ink-2)}
.kicker{color:var(--muted);font-size:.85rem;margin:0}
.warn{background:var(--warn-bg);color:var(--warn-ink);border-radius:8px;padding:10px 14px;
font-size:.9rem}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}
.tile{background:var(--surface);border:1px solid var(--hair);border-radius:8px;padding:10px 12px}
.tile b{display:block;font-size:1.35rem}.tile span{color:var(--ink-2);font-size:.85rem}
.verdict{color:var(--ink-2);font-size:.9rem;margin:.6em 0 0}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.88rem;background:var(--surface)}
th,td{padding:6px 8px;border-bottom:1px solid var(--hair);text-align:left;white-space:nowrap}
th{color:var(--muted);font-weight:600;font-size:.78rem}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.up{color:var(--up)}.down{color:var(--down)}.muted{color:var(--muted)}
.bet{font-weight:600;color:var(--accent)}
footer{margin-top:32px;color:var(--muted);font-size:.8rem}
"""


def _e(value: Any) -> str:
    return html.escape(str(value))


def _num(x: float, digits: int = 1) -> str:
    """German number format with a real minus sign."""
    text = f"{abs(x):,.{digits}f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"−{text}" if x < 0 else text


def _pct(x: float | None, digits: int = 0, signed: bool = False) -> str:
    if x is None or pd.isna(x):
        return "–"
    sign = "+" if signed and x > 0 else ""
    return f"{sign}{_num(x * 100, digits)} %"


def _teams(match_id: str) -> tuple[str, str]:
    parts = match_id.split(":")
    return parts[3], parts[4]


def _kickoff_de(kickoff: str | None, date: str) -> str:
    """Source kickoff is UK local time; Germany is always exactly one hour ahead of it.

    (The UK and the EU switch daylight saving at the same instant, so the offset never changes.)
    """
    stamp = pd.Timestamp(kickoff) if kickoff and kickoff != "NaT" else None
    if stamp is None or stamp.hour == 0 and stamp.minute == 0:
        day = pd.Timestamp(date)
        return f"{WEEKDAYS[day.weekday()]} {day:%d.%m.}"
    local = stamp + pd.Timedelta(hours=1)
    return f"{WEEKDAYS[local.weekday()]} {local:%d.%m. %H:%M}"


def _record_tiles(record: dict[str, Any]) -> str:
    bets, cal = record["bets"], record["calibration"]
    n = bets.get("n_bets", 0)
    tiles = []
    if n:
        lo, hi = bets["yield_ci"]
        profit = bets["profit"]
        cls = "up" if profit > 0 else "down"
        books = ", ".join(BOOKS.get(b, b) for b in sorted(bets.get("clv_books", {}))) or "–"
        tiles += [
            f'<div class="tile"><b>{n}</b><span>abgerechnete Papier-Wetten '
            f'({bets["n_won"]} gewonnen, {bets["n_pending"]} offen)</span></div>',
            f'<div class="tile"><b class="{cls}">{_num(profit, 0)} E</b>'
            f"<span>Ergebnis bei 10 Einheiten je Wette</span></div>",
            f'<div class="tile"><b class="{cls}">{_pct(bets["yield"], 1, True)}</b>'
            f"<span>Rendite · 95-%-Intervall {_pct(lo, 0, True)} bis {_pct(hi, 0, True)}</span>"
            "</div>",
            f'<div class="tile"><b>{_pct(bets["clv_beat_rate"])}</b>'
            f"<span>schlagen die Schlussquote (CLV Ø {_pct(bets['clv_mean'], 1, True)}, "
            f"gegen {_e(books)})</span></div>",
        ]
    else:
        tiles.append(
            f'<div class="tile"><b>0</b><span>abgerechnete Papier-Wetten '
            f'({bets.get("n_pending", 0)} offen)</span></div>'
        )
    if cal.get("n"):
        lo, hi = cal["brier_diff_ci"]
        tiles.append(
            f'<div class="tile"><b>{_num(cal["brier_model"], 3)} / '
            f'{_num(cal["brier_market"], 3)}</b><span>Brier Modell / Markt über {cal["n"]} '
            f"Spiele (kleiner = besser; Differenz {_num(lo, 3)} bis {_num(hi, 3)})</span></div>"
        )
    verdicts = [_bet_verdict(bets), _calibration_verdict(cal)]
    return (
        f'<div class="tiles">{"".join(tiles)}</div>'
        + "".join(f'<p class="verdict">{_e(v)}</p>' for v in verdicts if v)
    )


def _bet_verdict(bets: dict[str, Any]) -> str:
    n = bets.get("n_bets", 0)
    if n == 0:
        return "Noch keine Wette abgerechnet — es gibt noch nichts zu bewerten."
    if n < MIN_N:
        return (
            f"Zu wenige Wetten für ein Urteil (n = {n} < {MIN_N}). Das Intervall ist so breit, "
            "dass Gewinn und Verlust gleichermaßen Zufall sein können."
        )
    lo, hi = bets["yield_ci"]
    if lo > 0:
        return "Rendite-Intervall liegt über 0 — erst glauben, wenn auch der CLV positiv ist."
    if hi < 0:
        return "Rendite-Intervall liegt unter 0 — verliert gegen die Marge, wie erwartet."
    return "Rendite-Intervall schließt 0 ein — kein Beleg für einen Vorteil."


def _calibration_verdict(cal: dict[str, Any]) -> str:
    n = cal.get("n", 0)
    if n == 0:
        return ""
    if n < MIN_N:
        return f"Kalibrierung: zu wenige abgerechnete Prognosen für ein Urteil (n = {n})."
    lo, hi = cal["brier_diff_ci"]
    if hi < 0:
        return "Kalibrierung: Modell besser als der Markt (Intervall ohne 0) — gründlich prüfen."
    if lo > 0:
        return "Kalibrierung: Markt besser als das Modell (Intervall ohne 0) — wie erwartet."
    return "Kalibrierung: kein messbarer Unterschied zwischen Modell und Markt."


def _three(row: pd.Series, prefix: str) -> str:
    values = [row.get(f"{prefix}{s}") for s in ("H", "D", "A")]
    if any(v is None or pd.isna(v) for v in values):
        return '<span class="muted">keine Quote</span>'
    return " / ".join(_pct(v) for v in values)


def _upcoming_table(preds: pd.DataFrame, bets: pd.DataFrame, today) -> str:
    rows = []
    for row in preds.sort_values(["kickoff", "match_id"]).to_dict("records"):
        home, away = _teams(row["match_id"])
        open_bets = bets[(bets["match_id"] == row["match_id"]) & (bets["status"] == PENDING)]
        picks = "<br>".join(
            f'<span class="bet">{_e(SELECTION.get(b.selection, b.selection))} @ '
            f"{_num(float(b.odds_taken), 2)}</span> "
            f'<span class="muted">(Vorteil {_pct(b.edge, 0, True)})</span>'
            for b in open_bets.itertuples()
        )
        over = (
            f"{_pct(row['p_over'])} / {_pct(row.get('mkt_over'))}"
            if row.get("p_over") is not None
            else "–"
        )
        waiting = (
            ' <span class="muted">· Ergebnis ausstehend</span>'
            if pd.Timestamp(row["date"]).date() < today
            else ""
        )
        rows.append(
            f"<tr><td>{_kickoff_de(row.get('kickoff'), row['date'])}{waiting}</td>"
            f"<td>{_e(home)} – {_e(away)}</td>"
            f'<td class="num">{_three(pd.Series(row), "p_")}</td>'
            f'<td class="num">{_three(pd.Series(row), "mkt_")}</td>'
            f'<td class="num">{over}</td><td>{picks or "–"}</td></tr>'
        )
    return (
        '<div class="scroll"><table><thead><tr><th>Anstoß (dt. Zeit)</th><th>Spiel</th>'
        "<th>Modell 1 / X / 2</th><th>Markt 1 / X / 2</th><th>Über 2,5 Modell / Markt</th>"
        f"<th>Papier-Wette</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _settled_bets_table(bets: pd.DataFrame, limit: int = 12) -> str:
    done = bets[bets["status"] == SETTLED].sort_values(["date", "bet_id"], ascending=False)
    rows = []
    for b in done.head(limit).itertuples():
        home, away = _teams(b.match_id)
        pnl = float(b.pnl)
        clv = None if b.clv is None or pd.isna(b.clv) else float(b.clv)
        rows.append(
            f"<tr><td>{pd.Timestamp(b.date):%d.%m.}</td><td>{_e(home)} – {_e(away)}</td>"
            f"<td>{_e(SELECTION.get(b.selection, b.selection))}</td>"
            f'<td class="num">{_num(float(b.odds_taken), 2)}</td>'
            f"<td>{'gewonnen' if b.won else 'verloren'}</td>"
            f'<td class="num {"up" if pnl > 0 else "down"}">{_num(pnl, 0)}</td>'
            f'<td class="num">{_pct(clv, 1, True)}</td></tr>'
        )
    if not rows:
        return ""
    more = len(done) - limit
    note = f'<p class="muted">… und {more} ältere.</p>' if more > 0 else ""
    return (
        "<h3>Abgerechnete Papier-Wetten</h3>"
        '<div class="scroll"><table><thead><tr><th>Datum</th><th>Spiel</th><th>Wette</th>'
        "<th>Quote</th><th>Ausgang</th><th>G/V (E)</th><th>CLV</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>{note}"
    )


def _settled_predictions_table(preds: pd.DataFrame, limit: int = 12) -> str:
    done = preds[preds["status"] == SETTLED].sort_values(["date", "match_id"], ascending=False)
    rows = []
    for row in done.head(limit).to_dict("records"):
        home, away = _teams(row["match_id"])
        model_tip = max(("H", "D", "A"), key=lambda s: row[f"p_{s}"])
        market = [row.get(f"mkt_{s}") for s in ("H", "D", "A")]
        has_market = all(v is not None and not pd.isna(v) for v in market)
        fav = max(("H", "D", "A"), key=lambda s: row[f"mkt_{s}"]) if has_market else None
        hit = "✓" if model_tip == row["result"] else "✗"
        fav_cell = ("✓" if fav == row["result"] else "✗") if fav else "–"
        rows.append(
            f"<tr><td>{pd.Timestamp(row['date']):%d.%m.}</td><td>{_e(home)} – {_e(away)}</td>"
            f"<td>{int(row['ft_home_goals'])}:{int(row['ft_away_goals'])}</td>"
            f"<td>{model_tip.replace('H', '1').replace('D', 'X').replace('A', '2')} {hit}</td>"
            f"<td>{fav_cell}</td></tr>"
        )
    if not rows:
        return ""
    return (
        "<h3>Prognosen und Ergebnisse</h3>"
        '<div class="scroll"><table><thead><tr><th>Datum</th><th>Spiel</th><th>Ergebnis</th>'
        "<th>Modell-Tipp</th><th>Markt-Favorit</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def render_spieltag(
    bets: pd.DataFrame,
    predictions: pd.DataFrame,
    record: dict[str, Any],
    *,
    now: pd.Timestamp,
    backtest: dict[str, Any] | None = None,
) -> str:
    """The whole page as one HTML string."""
    now = pd.Timestamp(now)
    local_now = now.tz_convert("Europe/Berlin") if now.tzinfo else now
    sections = []
    any_upcoming = False
    for code, name in LEAGUES.items():
        league_preds = predictions[predictions["competition"] == code]
        league_bets = bets[bets["competition"] == code]
        upcoming = league_preds[league_preds["status"] == PREDICTED]
        parts = []
        if not upcoming.empty:
            any_upcoming = True
            parts.append(_upcoming_table(upcoming, league_bets, local_now.date()))
        parts.append(_settled_predictions_table(league_preds))
        parts.append(_settled_bets_table(league_bets))
        body = "".join(p for p in parts if p)
        if body:
            sections.append(f"<h2>{_e(name)}</h2>{body}")

    empty_note = (
        ""
        if any_upcoming
        else '<p class="warn">Gerade stehen keine Top-5-Spiele mit Quoten im Feed '
        "(z. B. Länderspielpause). Der nächste Lauf trägt sie ein, sobald football-data.co.uk "
        "die Quoten des Spieltags veröffentlicht — Prognosen entstehen immer vor dem Anpfiff.</p>"
    )
    since = record.get("since")
    since_text = f"seit {pd.Timestamp(since):%d.%m.%Y}" if since else "noch ohne Einträge"
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>match-scout Spieltag</title><style>{CSS}</style></head>
<body><main>
<p class="kicker">match-scout · Stand {local_now:%d.%m.%Y %H:%M} Uhr</p>
<h1>Spieltag: Modell gegen Markt</h1>
<p class="warn">{_e(DISCLAIMER)} {_e(backtest_line(backtest))}</p>
<h2>Forward-Bilanz {since_text}</h2>
{_record_tiles(record)}
{empty_note}
{"".join(sections)}
<h2>So liest du die Seite</h2>
<p><b>Modell</b> = Dixon-Coles-Tormodell, nur mit Spielen vor dem Anpfiff gefittet.
<b>Markt</b> = Bet365-Vorabquote ohne Buchmacher-Marge (Shin-Verfahren). Eine
<b>Papier-Wette</b> entsteht nur, wenn Modell × Quote − 1 ≥ 5 % ist; sie wird mit dem Zeitpunkt
gespeichert, zu dem sie feststand, und nie nachträglich geändert. <b>CLV</b> vergleicht die
genommene Quote mit der Schlussquote: wer die Schlussquote dauerhaft schlägt, hat einen echten
Vorteil — wer nicht, hatte Glück oder Pech.</p>
<footer>Daten: football-data.co.uk (nur zur Spielvorhersage genutzt, nicht weitergegeben) ·
Papier-Einsätze, keine Wettempfehlung · generiert aus data/bets.jsonl und
data/predictions.jsonl</footer>
</main></body></html>
"""
