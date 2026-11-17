import { apiRequest, postJson } from './http'

export type PortfolioItem = {
  id: number
  stock_symbol: string
  stock_name: string
  average_cost: number | string
  shares: number
  current_price: number | string
  market_value: number | string
  unrealized_pnl: number | string
  unrealized_return_pct: number | string
  price_as_of: string
  data_source: string
  created_at: string
  updated_at: string
}

export type PortfolioCreate = {
  stock_symbol: string
  average_cost: number
  shares: number
}

export function getPortfolio() {
  return apiRequest<PortfolioItem[]>('/api/v1/portfolio')
}

export function addPortfolioItem(payload: PortfolioCreate) {
  return postJson<PortfolioItem>('/api/v1/portfolio', payload)
}

export function updatePortfolioItem(id: number, payload: Partial<Pick<PortfolioItem, 'average_cost' | 'shares'>>) {
  return apiRequest<PortfolioItem>(`/api/v1/portfolio/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deletePortfolioItem(id: number) {
  return apiRequest<void>(`/api/v1/portfolio/${id}`, { method: 'DELETE' })
}
