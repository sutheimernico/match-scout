export interface Tip {
  match_id: string;
  date: string;
  home: string;
  away: string;
  p_H: number;
  p_D: number;
  p_A: number;
  p_over05: number;
  p_over15: number;
  p_over25: number;
  p_over35: number;
  p_btts: number;
  p_home_adv: number;
  p_away_adv: number;
  tip_1x2: string;
  most_likely_score: string;
  top_scores: string;
}

export interface Combo {
  legs: { match: string; pick: string; p: number }[];
  combined_prob: number;
  n_legs: number;
}

export interface CompetitionTips {
  code: string;
  name: string;
  kind: "cup" | "league";
  n_scheduled: number;
  n_trained_on: number;
  tips: Tip[];
  combo?: Combo;
}

export interface UpcomingData {
  generated_at?: string;
  season?: string;
  competitions: CompetitionTips[];
  error?: string;
}

export interface Summary {
  n_bets: number;
  yield: number;
  yield_ci: [number, number];
  clv_mean: number;
  clv_beat_rate: number;
  final_bankroll: number;
  max_drawdown: number;
  total_staked: number;
  profit: number;
}

export interface Scheme {
  summary: Summary;
  curve: { date: string; profit: number }[];
  verdict: string;
}

export interface LeagueStat {
  league: string;
  n_bets: number;
  yield: number;
  clv_beat_rate: number;
  final_bankroll: number;
}

export interface BacktestData {
  competitions: string[];
  seasons: string[];
  start_bankroll: number;
  date_range: [string, string];
  clv_beat_rate: number;
  clv_mean: number;
  headline_verdict: string;
  schemes: { flat: Scheme; kelly: Scheme };
  per_league: LeagueStat[];
}

export interface Meta {
  generated_at: string;
  disclaimer: string;
}

export interface ForwardData {
  generated_at: string;
  state: "empty" | "pending" | "settled";
  since: string | null;
  bets: {
    n_bets: number;
    n_won: number;
    n_pending: number;
    yield: number | null;
    yield_ci?: [number | null, number | null];
    clv_beat_rate: number | null;
    clv_books: Record<string, number>;
    verdict: string;
    curve: { date: string; profit: number }[];
  };
  calibration: { n: number; brier_model?: number; brier_market?: number; verdict: string };
}
