import { apiRequest } from './http'

export type SellAction = 'TAKE_PROFIT' | 'STOP_LOSS' | 'HOLD'
export type ConfidenceLevel = 'HIGH' | 'MEDIUM' | 'LOW'
export type SourceReference = {
  source_type: 'NEWS' | 'TECHNICAL' | 'MARKET' | 'INDUSTRY'
  title: string
  detail: string
  url: string | null
  published_at: string | null
}

export type SellDiagnosis = {
  action: SellAction
  suggested_sell_price_min: number
  suggested_sell_price_max: number
  confidence_level: ConfidenceLevel
  reasoning: string
  sources: SourceReference[]
  disclaimer: string
}

export function getSellDiagnosis(itemId: number) {
  return apiRequest<SellDiagnosis>(`/api/v1/advisory/sell-diagnosis/${itemId}`, {
    method: 'POST',
  })
}
