<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { getSellDiagnosis } from '../api/advisory'
import type { SellDiagnosis } from '../api/advisory'
import {
  addPortfolioItem,
  deletePortfolioItem,
  getPortfolio,
  updatePortfolioItem,
} from '../api/portfolio'
import type { PortfolioItem } from '../api/portfolio'

const items = ref<PortfolioItem[]>([])
const diagnoses = ref<Record<number, SellDiagnosis>>({})
const loading = ref(false)
const saving = ref(false)
const diagnosisLoadingId = ref<number | null>(null)
const error = ref('')
const form = reactive({ stock_symbol: '', average_cost: 0, shares: 0 })
const editingId = ref<number | null>(null)
const editForm = reactive({ average_cost: 0, shares: 0 })

async function loadPortfolio() {
  loading.value = true
  error.value = ''
  try {
    items.value = await getPortfolio()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '無法讀取持股清單。'
  } finally {
    loading.value = false
  }
}

async function addItem() {
  if (!form.stock_symbol.trim() || form.average_cost <= 0 || form.shares <= 0) return
  saving.value = true
  error.value = ''
  try {
    await addPortfolioItem({
      stock_symbol: form.stock_symbol.trim(),
      average_cost: form.average_cost,
      shares: form.shares,
    })
    form.stock_symbol = ''
    form.average_cost = 0
    form.shares = 0
    await loadPortfolio()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '新增持股失敗。'
  } finally {
    saving.value = false
  }
}

function beginEdit(item: PortfolioItem) {
  editingId.value = item.id
  editForm.average_cost = Number(item.average_cost)
  editForm.shares = item.shares
}

async function saveEdit(itemId: number) {
  try {
    error.value = ''
    await updatePortfolioItem(itemId, { ...editForm })
    editingId.value = null
    await loadPortfolio()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '更新持股失敗。'
  }
}

async function removeItem(itemId: number) {
  try {
    error.value = ''
    await deletePortfolioItem(itemId)
    delete diagnoses.value[itemId]
    await loadPortfolio()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '刪除持股失敗。'
  }
}

async function diagnose(itemId: number) {
  diagnosisLoadingId.value = itemId
  error.value = ''
  try {
    diagnoses.value[itemId] = await getSellDiagnosis(itemId)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'AI 診斷暫時無法使用。'
  } finally {
    diagnosisLoadingId.value = null
  }
}

function actionLabel(action: SellDiagnosis['action']) {
  return {
    TAKE_PROFIT: '建議分批獲利了結',
    STOP_LOSS: '建議執行停損',
    HOLD: '建議續抱觀察波段',
  }[action]
}

function confidenceLabel(level: SellDiagnosis['confidence_level']) {
  return { HIGH: '高', MEDIUM: '中', LOW: '低' }[level]
}

function formatMoney(value: number | string) {
  return Number(value).toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

onMounted(loadPortfolio)
</script>

<template>
  <section class="portfolio-page">
    <div class="portfolio-intro">
      <div class="eyebrow">MY PORTFOLIO / SELL DIAGNOSIS</div>
      <h2>我的庫存與 AI 診斷</h2>
      <p>持倉損益以資料來源最近提供的盤後收盤價試算；AI 診斷僅供研究參考，不會下單。</p>
    </div>

    <p v-if="error" class="error-banner portfolio-error" role="alert">{{ error }}</p>

    <section class="portfolio-form-card">
      <h3>新增持股</h3>
      <form class="portfolio-form" @submit.prevent="addItem">
        <label class="form-field-label">股票代號
          <input v-model="form.stock_symbol" class="form-control" required pattern="\d{4,6}" placeholder="例如 2330" />
        </label>
        <label class="form-field-label">買進均價（元）
          <input v-model.number="form.average_cost" class="form-control" required type="number" min="0.01" step="0.01" />
        </label>
        <label class="form-field-label">持有股數
          <input v-model.number="form.shares" class="form-control" required type="number" min="1" step="1" />
        </label>
        <button class="auth-submit" type="submit" :disabled="saving">{{ saving ? '新增中…' : '加入庫存' }}</button>
      </form>
    </section>

    <div class="portfolio-heading">
      <h3>持股總覽 <span>{{ items.length }} 檔</span></h3>
      <button class="news-more-button" type="button" :disabled="loading" @click="loadPortfolio">{{ loading ? '更新中…' : '更新行情' }}</button>
    </div>
    <p v-if="loading && !items.length" class="market-message">正在讀取持股與行情…</p>
    <p v-else-if="!items.length" class="portfolio-empty">目前沒有持股，請使用上方表單新增。</p>

    <article v-for="item in items" :key="item.id" class="portfolio-item-card">
      <div class="portfolio-item-heading">
        <div><span class="portfolio-symbol">{{ item.stock_symbol }}</span><strong>{{ item.stock_name }}</strong></div>
        <span class="portfolio-pnl" :class="Number(item.unrealized_pnl) > 0 ? 'trend-up' : Number(item.unrealized_pnl) < 0 ? 'trend-down' : 'trend-neutral'">
          {{ Number(item.unrealized_pnl) > 0 ? '+' : '' }}{{ formatMoney(item.unrealized_pnl) }}（{{ Number(item.unrealized_return_pct).toFixed(2) }}%）
        </span>
      </div>

      <div v-if="editingId === item.id" class="portfolio-edit-form">
        <label class="form-field-label">買進均價<input v-model.number="editForm.average_cost" class="form-control" type="number" min="0.01" step="0.01" /></label>
        <label class="form-field-label">持有股數<input v-model.number="editForm.shares" class="form-control" type="number" min="1" step="1" /></label>
        <button class="account-button" type="button" @click="saveEdit(item.id)">儲存</button>
        <button class="account-button" type="button" @click="editingId = null">取消</button>
      </div>
      <div v-else class="portfolio-metrics">
        <div><span>買進均價</span><strong>{{ formatMoney(item.average_cost) }}</strong></div>
        <div><span>最近收盤價</span><strong>{{ formatMoney(item.current_price) }}</strong></div>
        <div><span>持有股數</span><strong>{{ item.shares.toLocaleString('zh-TW') }}</strong></div>
        <div><span>目前市值</span><strong>{{ formatMoney(item.market_value) }}</strong></div>
      </div>
      <p class="portfolio-source">行情日期 {{ item.price_as_of }} · {{ item.data_source }} · 非即時報價</p>

      <div class="portfolio-actions">
        <button class="auth-submit diagnosis-button" type="button" :disabled="diagnosisLoadingId === item.id" @click="diagnose(item.id)">
          {{ diagnosisLoadingId === item.id ? '正在整理行情與新聞…' : 'AI 賣出診斷' }}
        </button>
        <button v-if="editingId !== item.id" class="account-button" type="button" @click="beginEdit(item)">編輯成本／股數</button>
        <button v-if="editingId !== item.id" class="account-button delete-button" type="button" @click="removeItem(item.id)">刪除</button>
      </div>

      <section v-if="diagnoses[item.id]" class="diagnosis-card">
        <div class="diagnosis-result-heading">
          <span class="diagnosis-action" :class="diagnoses[item.id].action.toLowerCase()">{{ actionLabel(diagnoses[item.id].action) }}</span>
          <span>參考賣出區間：{{ formatMoney(diagnoses[item.id].suggested_sell_price_min) }}–{{ formatMoney(diagnoses[item.id].suggested_sell_price_max) }} 元</span>
          <small>信心程度：{{ confidenceLabel(diagnoses[item.id].confidence_level) }}</small>
        </div>
        <p class="diagnosis-reasoning">{{ diagnoses[item.id].reasoning }}</p>
        <div class="diagnosis-sources">
          <h4>參考依據與數據來源</h4>
          <article v-for="(source, index) in diagnoses[item.id].sources" :key="`${source.title}-${index}`" class="diagnosis-source">
            <div><span class="source-type">{{ source.source_type === 'NEWS' ? '新聞' : source.source_type === 'MARKET' ? '大盤' : source.source_type === 'INDUSTRY' ? '同業比較' : '技術指標' }}</span>
              <a v-if="source.url" :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.title }}</a>
              <strong v-else>{{ source.title }}</strong>
              <time v-if="source.published_at">{{ new Date(source.published_at).toLocaleString('zh-TW') }}</time>
            </div>
            <p>{{ source.detail }}</p>
          </article>
        </div>
        <p class="risk-disclaimer">{{ diagnoses[item.id].disclaimer }}</p>
      </section>
    </article>
  </section>
</template>
