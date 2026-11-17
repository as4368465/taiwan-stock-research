<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ApiError } from '../api/http'
import {
  getRiskProfile,
  getRiskQuestions,
  submitRiskAssessment,
} from '../api/risk'
import type { RiskProfile, RiskQuestion } from '../api/risk'

const emit = defineEmits<{ profileUpdated: [profile: RiskProfile] }>()

const questions = ref<RiskQuestion[]>([])
const resultElement = ref<HTMLElement | null>(null)
const answers = reactive<Record<string, number>>({})
const profile = ref<RiskProfile | null>(null)
const targetReturn = ref<number | null>(null)
const maxDrawdown = ref<number | null>(null)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const answeredCount = computed(() => Object.keys(answers).length)
const allQuestionsAnswered = computed(() => questions.value.length > 0 && answeredCount.value === questions.value.length)

onMounted(async () => {
  try {
    const response = await getRiskQuestions()
    questions.value = response.questions
    try {
      profile.value = await getRiskProfile()
      Object.assign(answers, profile.value.answers)
      targetReturn.value = profile.value.target_return_pct
      maxDrawdown.value = profile.value.max_drawdown_pct
    } catch (cause) {
      if (!(cause instanceof ApiError) || cause.status !== 404) throw cause
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '無法載入風險問卷。'
  } finally {
    loading.value = false
  }
})

async function saveAssessment() {
  if (!allQuestionsAnswered.value) return
  saving.value = true
  error.value = ''
  try {
    const payload: {
      answers: Record<string, number>
      target_return_pct?: number
      max_drawdown_pct?: number
    } = { answers: { ...answers } }
    if (targetReturn.value !== null) payload.target_return_pct = targetReturn.value
    if (maxDrawdown.value !== null) payload.max_drawdown_pct = maxDrawdown.value

    profile.value = await submitRiskAssessment(payload)
    targetReturn.value = profile.value.target_return_pct
    maxDrawdown.value = profile.value.max_drawdown_pct
    emit('profileUpdated', profile.value)
    await nextTick()
    resultElement.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '無法儲存評估結果。'
  } finally {
    saving.value = false
  }
}

function recommendedReturnRange(result: RiskProfile): string {
  const min = result.suggested_target_return_min_pct
  const max = result.suggested_target_return_max_pct
  return max === null ? `${min}% 以上（問卷參考）` : `${min}%–${max}%（問卷參考）`
}

function recommendedDrawdownRange(result: RiskProfile): string {
  return `${result.suggested_drawdown_min_pct}%–${result.suggested_drawdown_max_pct}%`
}
</script>

<template>
  <section class="risk-page">
    <div class="risk-intro">
      <div class="eyebrow">INVESTOR PROFILE</div>
      <h2>投資風險屬性測驗</h2>
      <p>依你的投資經驗、虧損承受度、目標、下跌反應與資金期限，整理一份可調整的參考設定。</p>
    </div>

    <p v-if="loading" class="market-message">正在載入問卷…</p>
    <p v-if="error" class="error-banner" role="alert">{{ error }}</p>

    <template v-if="!loading && questions.length">
      <section v-if="profile" ref="resultElement" class="risk-result">
        <div class="risk-result-top">
          <div>
            <div class="eyebrow">YOUR PROFILE</div>
            <h3>{{ profile.risk_type_label }}</h3>
          </div>
          <div class="risk-score"><strong>{{ profile.risk_score }}</strong><span>/ 25 分</span></div>
        </div>
        <p class="risk-guidance">{{ profile.guidance }}</p>
        <div class="risk-recommendations">
          <div><span>問卷報酬參考</span><strong>{{ recommendedReturnRange(profile) }}</strong></div>
          <div><span>問卷回撤參考</span><strong>{{ recommendedDrawdownRange(profile) }}</strong></div>
        </div>
        <div class="risk-adjustments">
          <label class="form-field-label">我的預期年化報酬率 (%)
            <small>記錄你希望追求的年報酬目標，供個人研究設定參考。</small>
            <input v-model.number="targetReturn" class="form-control" type="number" min="0.01" max="100" step="0.01" />
          </label>
          <label class="form-field-label">我能接受的最大虧損 (%)
            <small>記錄你可接受的虧損幅度，供個人風險控管參考。</small>
            <input v-model.number="maxDrawdown" class="form-control" type="number" min="0.01" max="100" step="0.01" />
          </label>
        </div>
        <p class="risk-disclaimer">這兩項目前會儲存在你的風險屬性資料中，作為個人研究與後續風險控管功能的參考；不會改變目前的個股分析，也不會自動下單。問卷結果不代表投資建議或報酬保證。</p>
        <button class="auth-submit risk-save-button" type="button" :disabled="saving" @click="saveAssessment">
          {{ saving ? '儲存中…' : '儲存我的風險設定' }}
        </button>
      </section>

      <form class="risk-questionnaire" @submit.prevent="saveAssessment">
        <fieldset v-for="(question, index) in questions" :key="question.id" class="risk-question">
          <legend><span>0{{ index + 1 }}</span>{{ question.prompt }}</legend>
          <label v-for="option in question.options" :key="option.value" class="risk-option choice-option">
            <input v-model.number="answers[question.id]" type="radio" :name="question.id" :value="option.value" />
            <span>{{ option.label }}</span>
          </label>
        </fieldset>
        <p class="risk-progress">已完成 {{ answeredCount }} / {{ questions.length }} 題</p>
        <button class="auth-submit" type="submit" :disabled="!allQuestionsAnswered || saving">
          {{ saving ? '儲存中…' : profile ? '重新計算問卷並儲存' : '計算我的風險屬性' }}
        </button>
      </form>
    </template>
  </section>
</template>
