export interface Match {
  id: string;
  homeTeam: string;
  awayTeam: string;
  homeProb: number;
  drawProb: number;
  awayProb: number;
  prediction: "HOME" | "DRAW" | "AWAY";
  confidence: number;
  isValueBet: boolean;
  matchDate: string;
  league: string;
  leagueId: number;
  homeForm: string;
  awayForm: string;
}
