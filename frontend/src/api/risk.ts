import { apiRequest, postJson } from './http'
import type { RiskType } from './auth'

export type RiskOption = { value: number; label: string }
export type RiskQuestion = { id: string; prompt: string; options: RiskOption[] }
export type RiskQuestionsResponse = { questions: RiskQuestion[] }

export type RiskProfile = {
  id: number
  risk_score: number
  risk_type: RiskType
  risk_type_label: string
  target_return_pct: number
  max_drawdown_pct: number
  suggested_target_return_min_pct: number
  suggested_target_return_max_pct: number | null
  suggested_drawdown_min_pct: number
  suggested_drawdown_max_pct: number
  guidance: string
  answers: Record<string, number>
  updated_at: string
}

export type RiskAssessmentPayload = {
  answers: Record<string, number>
  target_return_pct?: number
  max_drawdown_pct?: number
}

export function getRiskQuestions() {
  return apiRequest<RiskQuestionsResponse>('/api/v1/risk/questions')
}

export function getRiskProfile() {
  return apiRequest<RiskProfile>('/api/v1/risk/profile')
}

export function submitRiskAssessment(payload: RiskAssessmentPayload) {
  return postJson<RiskProfile>('/api/v1/risk/assess', payload)
}
