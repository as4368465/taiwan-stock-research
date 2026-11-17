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

export type CandleFeature = {
  date: string
  open: number | string
  high: number | string
  low: number | string
  close: number | string
  body_ratio_pct: number | string
  upper_shadow_ratio_pct: number | string
  lower_shadow_ratio_pct: number | string
  candle_color: string
  pattern: string
}

export type TechnicalIndicatorSnapshot = {
  latest_date: string
  candles: CandleFeature[]
  volume_ratio: number | string | null
  volume_signal: string
  rsi14: number | string | null
  rsi_signal: string
  macd_dif: number | string | null
  macd_dea: number | string | null
  macd_histogram: number | string | null
  macd_signal: string
}

export type SellDiagnosis = {
  action: SellAction
  suggested_sell_price_min: number
  suggested_sell_price_max: number
  confidence_level: ConfidenceLevel
  reasoning: string
  sources: SourceReference[]
  technical_snapshot: TechnicalIndicatorSnapshot | null
  audit_approved: boolean
  disclaimer: string
}

export function getSellDiagnosis(itemId: number) {
  return apiRequest<SellDiagnosis>(`/api/v1/advisory/sell-diagnosis/${itemId}`, {
    method: 'POST',
  })
}
