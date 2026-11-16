import { apiRequest, postJson, saveAccessToken } from './http'

export type RiskType = 'CONSERVATIVE' | 'MODERATE' | 'AGGRESSIVE'

export type UserResponse = {
  id: number
  email: string
  full_name: string
  created_at: string
  risk_score: number | null
  risk_type: RiskType | null
  risk_type_label: string | null
}

type TokenResponse = { access_token: string; token_type: 'bearer' }
export type UserCredentials = { email: string; password: string; full_name?: string }

export function registerUser(payload: Required<UserCredentials>) {
  return postJson<UserResponse>('/api/v1/auth/register', payload)
}

export async function loginUser(payload: Pick<UserCredentials, 'email' | 'password'>) {
  const token = await postJson<TokenResponse>('/api/v1/auth/login', payload)
  saveAccessToken(token.access_token)
  return token
}

export function getCurrentUser() {
  return apiRequest<UserResponse>('/api/v1/auth/me')
}
