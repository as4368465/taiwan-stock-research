import { apiRequest } from './http'

export type GlossaryCategory = '基礎交易' | 'K線型態' | '技術指標' | '風險控管'
export type GlossaryTerm = {
  term: string
  category: GlossaryCategory
  summary: string
  practical_tip: string
  risk_warning: string
}
export type GlossaryResponse = { terms: GlossaryTerm[]; total: number }

export function getGlossary(q: string, category: GlossaryCategory | '') {
  const params = new URLSearchParams()
  if (q.trim()) params.set('q', q.trim())
  if (category) params.set('category', category)
  const suffix = params.size ? `?${params.toString()}` : ''
  return apiRequest<GlossaryResponse>(`/api/v1/glossary${suffix}`)
}
