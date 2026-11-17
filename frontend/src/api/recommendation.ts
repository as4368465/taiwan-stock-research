import { apiRequest, postJson } from './http'
import type { SourceReference } from './advisory'

export type DailyRecommendationRequest = {
  investment_budget: number
  target_return_pct?: number
  max_loss_pct?: number
}

export type StockRecommendation = {
  symbol: string
  name: string
  current_price: number | string
  suggested_buy_price_min: number | string
  suggested_buy_price_max: number | string
  suggested_shares: number
  target_sell_price: number | string
  stop_loss_price: number | string
  reasoning: string
  sources: SourceReference[]
}

export type DailyRecommendationResponse = {
  generated_at: string
  user_risk_type: string
  market_summary: string
  recommendations: StockRecommendation[]
  disclaimer: string
}

export function createDailyRecommendations(payload: DailyRecommendationRequest) {
  return postJson<DailyRecommendationResponse>('/api/v1/advisory/daily-recommendations', payload)
}

export function addRecommendedStockToPortfolio(payload: {
  stock_symbol: string
  average_cost: number
  shares: number
}) {
  return postJson('/api/v1/portfolio', payload)
}

export function getRecommendationRiskProfile() {
  return apiRequest<{
    risk_type: string
    risk_type_label: string
    target_return_pct: number
    max_drawdown_pct: number
  }>('/api/v1/risk/profile')
}
