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

export interface TipsData {
  competition: string;
  n_trained_on?: number;
  tips: Tip[];
  combo?: Combo;
  error?: string;
}

export interface BacktestSummary {
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

export interface BacktestData {
  league: string;
  seasons: string[];
  summary: BacktestSummary;
  verdict: string;
  bankroll_curve: { date: string; bankroll: number }[];
}

export interface Meta {
  generated_at: string;
  disclaimer: string;
}
