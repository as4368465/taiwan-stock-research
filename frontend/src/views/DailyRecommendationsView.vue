<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { getAiQuota } from '../api/advisory'
import type { AiQuota } from '../api/advisory'
import { addRecommendedStockToPortfolio, createDailyRecommendations, getRecommendationRiskProfile } from '../api/recommendation'
import type { DailyRecommendationResponse, StockRecommendation } from '../api/recommendation'

const props = defineProps<{ riskTypeLabel: string | null }>()
const conditions = reactive({ investment_budget: 100000, target_return_pct: 12.5, max_loss_pct: 10 })
const result = ref<DailyRecommendationResponse | null>(null)
const loading = ref(false)
const profileLoading = ref(true)
const error = ref('')
const success = ref('')
const addingSymbol = ref('')
const hasProfile = ref(false)
const aiQuota = ref<AiQuota | null>(null)

async function loadAiQuota() {
  try {
    aiQuota.value = await getAiQuota()
  } catch {
    aiQuota.value = null
  }
}

async function loadProfileDefaults() {
  profileLoading.value = true
  try {
    const profile = await getRecommendationRiskProfile()
    conditions.target_return_pct = profile.target_return_pct
    conditions.max_loss_pct = profile.max_drawdown_pct
    hasProfile.value = true
  } catch {
    hasProfile.value = false
  } finally {
    profileLoading.value = false
  }
}

async function generate() {
  loading.value = true
  error.value = ''
  success.value = ''
  try {
    result.value = await createDailyRecommendations({ ...conditions })
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '目前無法產生推薦，請稍後再試。'
    result.value = null
  } finally {
    loading.value = false
    await loadAiQuota()
  }
}

async function addToPortfolio(stock: StockRecommendation) {
  addingSymbol.value = stock.symbol
  error.value = ''
  success.value = ''
  try {
    await addRecommendedStockToPortfolio({
      stock_symbol: stock.symbol,
      average_cost: Number(stock.current_price),
      shares: stock.suggested_shares,
    })
    success.value = `已將 ${stock.name}（${stock.symbol}）加入庫存，成本以最近收盤價試算。`
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '加入庫存失敗。'
  } finally {
    addingSymbol.value = ''
  }
}

function money(value: number | string) {
  return Number(value).toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

onMounted(() => {
  void loadProfileDefaults()
  void loadAiQuota()
})
</script>

<template>
  <section class="recommendation-page">
    <header class="recommendation-intro">
      <div class="eyebrow">PERSONALIZED DAILY IDEAS / 每日研究</div>
      <h1>每日 AI 選股推薦</h1>
      <p>先以固定量化條件篩出候選股，再由 AI 根據你的風險屬性與可查證資料整理理由。系統不會下單。</p>
    </header>
    <div class="ai-quota-row">
      <span v-if="aiQuota" class="ai-quota-badge">今日剩餘 AI 體驗次數：{{ aiQuota.user_remaining }} / {{ aiQuota.user_limit }} 次（全站 {{ aiQuota.global_remaining }} / {{ aiQuota.global_limit }}）</span>
      <span v-else class="ai-quota-badge muted">正在讀取今日額度…</span>
    </div>

    <section class="recommendation-conditions">
      <div class="recommendation-risk-row">
        <div><span class="form-caption">目前風險屬性</span><strong>{{ props.riskTypeLabel ?? '尚未完成風險測驗' }}</strong></div>
        <span class="form-hint">{{ profileLoading ? '讀取風險設定中…' : hasProfile ? '預期報酬與虧損上限已帶入問卷設定，可自行調整本次條件。' : '使用穩健型預設值，可自行調整本次條件。' }}</span>
      </div>
      <div class="recommendation-form-grid">
        <label class="form-field-label">本次預計投入資金（元）
          <input v-model.number="conditions.investment_budget" class="form-control" type="number" min="1000" step="1000" />
        </label>
        <label class="form-field-label">預期報酬率（%）
          <input v-model.number="conditions.target_return_pct" class="form-control" type="number" min="0.1" max="200" step="0.1" />
        </label>
        <label class="form-field-label">最多能接受虧損（%）
          <input v-model.number="conditions.max_loss_pct" class="form-control" type="number" min="0.1" max="50" step="0.1" />
        </label>
        <button class="auth-submit" type="button" :disabled="loading || profileLoading" @click="generate">
          {{ loading ? '正在初篩行情並整理來源…' : '產生今日 AI 買進清單' }}
        </button>
      </div>
      <p class="form-hint">預算會平均拆成三份估算零股股數；實際成交價格、手續費及稅費可能不同。</p>
    </section>

    <p v-if="error" class="error-banner" role="alert">{{ error }}</p>
    <p v-if="success" class="recommendation-success" role="status">{{ success }}</p>

    <section v-if="result" class="recommendation-results">
      <div class="recommendation-result-heading">
        <div><div class="eyebrow">TOP 3 / 來源佐證</div><h2>為你整理的三檔觀察標的</h2></div>
        <div class="recommendation-audit-status">
          <span class="audit-badge" :class="result.audit_approved ? 'approved' : 'review-needed'">
            {{ result.audit_approved ? '✓ 通過 AI 風控合規審查' : '需人工覆核' }}
          </span>
          <small>{{ result.user_risk_type }} · {{ new Date(result.generated_at).toLocaleString('zh-TW') }}</small>
        </div>
      </div>
      <p v-if="result.audit_note" class="recommendation-audit-note">{{ result.audit_note }}</p>
      <p class="recommendation-market-summary">{{ result.market_summary }}</p>

      <article v-for="(stock, index) in result.recommendations" :key="stock.symbol" class="recommendation-card">
        <div class="recommendation-card-top">
          <div><span class="recommendation-rank">0{{ index + 1 }}</span><span class="recommendation-symbol">{{ stock.symbol }}</span><h3>{{ stock.name }}</h3></div>
          <button class="account-button recommendation-add" type="button" :disabled="addingSymbol === stock.symbol || stock.suggested_shares < 1" @click="addToPortfolio(stock)">
            {{ addingSymbol === stock.symbol ? '加入中…' : stock.suggested_shares < 1 ? '預算不足以分配股數' : '加入我的庫存' }}
          </button>
        </div>
        <div class="recommendation-metrics">
          <div><span>最新收盤</span><strong>{{ money(stock.current_price) }} 元</strong></div>
          <div><span>建議進場區間</span><strong>{{ money(stock.suggested_buy_price_min) }} – {{ money(stock.suggested_buy_price_max) }}</strong></div>
          <div><span>建議股數（零股）</span><strong>{{ stock.suggested_shares.toLocaleString('zh-TW') }} 股</strong></div>
        </div>
        <div class="recommendation-price-track">
          <div><span>停損參考</span><strong>{{ money(stock.stop_loss_price) }}</strong></div>
          <div class="price-track-line"><span></span></div>
          <div class="price-track-current"><span>最近收盤</span><strong>{{ money(stock.current_price) }}</strong></div>
          <div class="price-track-line"><span></span></div>
          <div><span>目標停利參考</span><strong>{{ money(stock.target_sell_price) }}</strong></div>
        </div>
        <div v-if="stock.technical_snapshot" class="technical-highlight-strip">
          <span class="technical-pattern">{{ stock.technical_snapshot.candles.at(-1)?.pattern }}</span>
          <span>RSI14 <strong>{{ stock.technical_snapshot.rsi14 ?? '—' }}</strong> {{ stock.technical_snapshot.rsi_signal }}</span>
          <span>量比 <strong>{{ stock.technical_snapshot.volume_ratio ?? '—' }}x</strong> {{ stock.technical_snapshot.volume_signal }}</span>
          <span>MACD <strong>{{ stock.technical_snapshot.macd_signal }}</strong></span>
        </div>
        <p class="recommendation-reasoning">{{ stock.reasoning }}</p>
        <details class="recommendation-sources">
          <summary>可靠來源與數據佐證（{{ stock.sources.length }}）</summary>
          <article v-for="(source, sourceIndex) in stock.sources" :key="`${source.title}-${sourceIndex}`">
            <span class="source-type">{{ source.source_type === 'NEWS' ? '新聞' : '技術指標' }}</span>
            <a v-if="source.url" :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.title }}</a>
            <strong v-else>{{ source.title }}</strong>
            <time v-if="source.published_at">{{ new Date(source.published_at).toLocaleString('zh-TW') }}</time>
            <p>{{ source.detail }}</p>
          </article>
        </details>
      </article>
      <p class="risk-disclaimer">{{ result.disclaimer }}</p>
    </section>
  </section>
</template>

<style scoped>
.recommendation-page { width: min(1120px, calc(100% - 40px)); margin: 0 auto 72px; }
.recommendation-intro { padding: 36px 0 24px; }
.recommendation-intro p, .form-hint { color: #687386; line-height: 1.7; }
.recommendation-conditions, .recommendation-card { padding: 24px; border: 1px solid #e8ebf2; border-radius: 18px; background: #fff; box-shadow: 0 8px 28px #1b2d4a0a; }
.recommendation-risk-row, .recommendation-result-heading, .recommendation-card-top { display: flex; align-items: center; justify-content: space-between; gap: 18px; }
.recommendation-risk-row strong { display: block; margin-top: 6px; }
.form-caption, .recommendation-metrics span, .recommendation-price-track span { display: block; color: #788397; font-size: 13px; }
.form-hint { font-size: 13px; }
.recommendation-form-grid { display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)) auto; align-items: end; gap: 14px; margin: 22px 0 8px; }
.recommendation-form-grid label { display: grid; gap: 8px; color: #465166; font-size: 14px; font-weight: 600; }
.recommendation-form-grid input { min-width: 0; padding: 12px; border: 1px solid #dce1eb; border-radius: 10px; font: inherit; }
.recommendation-results { margin-top: 36px; }
.recommendation-result-heading h2 { margin: 6px 0; }
.recommendation-result-heading > span { color: #778196; font-size: 13px; }
.recommendation-audit-status { display: grid; justify-items: end; gap: 6px; }
.recommendation-audit-status small { color: #778196; font-size: 12px; }
.audit-badge { padding: 7px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.audit-badge.approved { color: #267044; background: #eaf8f0; }
.audit-badge.review-needed { color: #9a5a25; background: #fff4e8; }
.recommendation-audit-note { margin: 8px 0 14px; color: #687386; font-size: 13px; line-height: 1.7; }
.recommendation-market-summary, .recommendation-success { padding: 14px 16px; border-radius: 12px; background: #eef5ff; color: #36527e; line-height: 1.7; }
.recommendation-success { background: #eaf8f0; color: #267044; }
.recommendation-card { margin-top: 16px; }
.recommendation-card-top > div { display: flex; align-items: baseline; gap: 10px; }
.recommendation-card-top h3 { margin: 0; font-size: 22px; }
.recommendation-rank { color: #8b95a8; font-size: 13px; }
.recommendation-symbol { color: #3569d4; font-weight: 700; }
.recommendation-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 22px 0; }
.recommendation-metrics > div { padding: 14px; border-radius: 12px; background: #f7f8fb; }
.recommendation-metrics strong { display: block; margin-top: 6px; font-size: 16px; }
.recommendation-price-track { display: grid; grid-template-columns: auto 1fr auto 1fr auto; align-items: center; gap: 12px; padding: 16px; border-radius: 12px; background: #fbfcfe; }
.recommendation-price-track strong { display: block; margin-top: 4px; }
.price-track-line { height: 3px; background: linear-gradient(90deg, #e65e67, #d9dee8, #27a978); }
.price-track-current { text-align: center; }
.recommendation-reasoning { line-height: 1.9; color: #37445a; }
.technical-highlight-strip { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; margin: 15px 0; padding: 12px 14px; border: 1px solid #e7ecf5; border-radius: 11px; color: #637088; background: #f8faff; font-size: 12px; }
.technical-highlight-strip strong { color: #37445a; }
.technical-pattern { padding: 5px 8px; border-radius: 999px; color: #31589f; background: #eaf1ff; font-weight: 700; }
.recommendation-sources { padding-top: 12px; border-top: 1px solid #edf0f5; }
.recommendation-sources summary { cursor: pointer; font-weight: 700; }
.recommendation-sources article { margin-top: 14px; padding: 14px; border-radius: 10px; background: #f7f8fb; }
.recommendation-sources article > * { margin-right: 10px; }
.recommendation-sources a { color: #2868d7; }
.recommendation-sources time { color: #8992a2; font-size: 12px; }
.recommendation-sources p { margin: 9px 0 0; color: #596579; line-height: 1.7; }
.risk-disclaimer { color: #768094; font-size: 13px; line-height: 1.7; }
@media (max-width: 820px) { .recommendation-form-grid { grid-template-columns: 1fr 1fr; } .recommendation-form-grid button { grid-column: 1 / -1; } }
@media (max-width: 600px) { .recommendation-page { width: min(100% - 24px, 1120px); } .recommendation-conditions, .recommendation-card { padding: 18px; } .recommendation-risk-row, .recommendation-result-heading, .recommendation-card-top { align-items: flex-start; flex-direction: column; } .recommendation-audit-status { justify-items: start; }.recommendation-form-grid, .recommendation-metrics { grid-template-columns: 1fr; } .recommendation-form-grid button { grid-column: auto; } .recommendation-price-track { grid-template-columns: 1fr; text-align: left; } .price-track-line { width: 100%; } .recommendation-price-track .price-track-current { text-align: left; } }
</style>
