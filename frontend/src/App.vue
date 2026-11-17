<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import AuthView from './views/AuthView.vue'
import RiskAssessmentView from './views/RiskAssessmentView.vue'
import PortfolioView from './views/PortfolioView.vue'
import DailyRecommendationsView from './views/DailyRecommendationsView.vue'
import GlossaryDrawer from './views/GlossaryDrawer.vue'
import { ApiError, clearAccessToken, getAccessToken, apiRequest } from './api/http'
import { getCurrentUser } from './api/auth'
import type { UserResponse } from './api/auth'
import type { RiskProfile } from './api/risk'

type PriceRow = {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  ma5: number | null
  ma20: number | null
  ma60: number | null
}

type Analysis = {
  symbol: string
  name: string
  is_demo_data: boolean
  data_source: string
  latest_data_date: string | null
  is_realtime: boolean
  notice: string
  latest_close: number | null
  data: PriceRow[]
}
type MarketPoint = { time: string; value: number }
type MarketOverview = {
  symbol: string
  name: string
  is_demo_data: boolean
  data_source: string
  latest_data_date: string | null
  latest_value: number
  session_open: number
  session_high: number
  session_low: number
  data: MarketPoint[]
  notice: string
}

type StockMatch = { stock_id: string; stock_name: string }
type NewsItem = {
  id: number
  stock_id: string
  title: string
  source: string
  published_at: string
  url: string
  summary: string
}
type NewsPage = { news: NewsItem[]; next_cursor: string | null; has_more: boolean; data_source: string }

const symbol = ref('2330')
const selectedStockId = ref('')
const suggestions = ref<StockMatch[]>([])
const showSuggestions = ref(false)
const analysis = ref<Analysis | null>(null)
const activeSection = ref<'market' | 'risk' | 'portfolio' | 'daily' | 'auth'>('market')
const currentUser = ref<UserResponse | null>(null)
const authNotice = ref('')
const glossaryOpen = ref(false)
const viewMode = ref<'market' | 'stock'>('market')
const market = ref<MarketOverview | null>(null)
const marketLoading = ref(false)
const marketError = ref('')
const loading = ref(false)
const error = ref('')
const chartElement = ref<HTMLDivElement | null>(null)
const newsItems = ref<NewsItem[]>([])
const newsCursor = ref<string | null>(null)
const newsHasMore = ref(false)
const newsLoading = ref(false)
const newsError = ref('')
const newsLoadSentinel = ref<HTMLDivElement | null>(null)
const newsAutoPaused = ref(false)
const newsSource = ref('')
let chart: echarts.ECharts | undefined
let suggestTimer: number | undefined
let newsObserver: IntersectionObserver | undefined

const latest = computed(() => analysis.value?.data.at(-1))
const previous = computed(() => analysis.value?.data.at(-2))
const marketChange = computed(() => {
  if (!market.value) return null
  const change = market.value.latest_value - market.value.session_open
  return { value: change, percent: market.value.session_open ? change / market.value.session_open * 100 : 0 }
})
const stockChange = computed(() => {
  if (!latest.value || !previous.value) return null
  const change = latest.value.close - previous.value.close
  return { value: change, percent: previous.value.close ? change / previous.value.close * 100 : 0 }
})

function trendClass(value: number | null | undefined, reference: number | null | undefined): string {
  if (value == null || reference == null || value === reference) return 'trend-neutral'
  return value > reference ? 'trend-up' : 'trend-down'
}

function formatChange(change: { value: number; percent: number } | null): string {
  if (!change) return '漲跌資料不足'
  const arrow = change.value > 0 ? '▲' : change.value < 0 ? '▼' : '－'
  const sign = change.value > 0 ? '+' : ''
  return `${arrow} ${sign}${change.value.toFixed(2)} (${sign}${change.percent.toFixed(2)}%)`
}

async function findStocks(query: string): Promise<StockMatch[]> {
  const body = await apiRequest<{ results: StockMatch[] }>(
    `/api/stocks/search?q=${encodeURIComponent(query)}`,
  )
  return body.results
}

async function loadMarket() {
  marketLoading.value = true
  marketError.value = ''
  try {
    const body = await apiRequest<MarketOverview>('/api/market/taiex')
    market.value = body
    await nextTick()
    if (viewMode.value === 'market') drawMarketChart()
  } catch (cause) {
    marketError.value = cause instanceof Error ? cause.message : '無法載入大盤指數，請確認後端已啟動。'
  } finally {
    marketLoading.value = false
  }
}

function goHome() {
  chart?.dispose()
  chart = undefined
  newsObserver?.disconnect()
  analysis.value = null
  viewMode.value = 'market'
  activeSection.value = 'market'
  error.value = ''
  void loadMarket()
}

async function loadNewsPage() {
  const currentSymbol = analysis.value?.symbol
  if (!currentSymbol || newsLoading.value || !newsHasMore.value && newsCursor.value) return

  newsLoading.value = true
  newsError.value = ''
  newsAutoPaused.value = false
  try {
    const params = new URLSearchParams({ limit: '10' })
    if (newsCursor.value) params.set('cursor', newsCursor.value)
    const body = await apiRequest<NewsPage>(
      `/api/stocks/${encodeURIComponent(currentSymbol)}/news?${params}`,
    )

    // 以 URL 去重，前端再做一次保護，避免重新查詢或分頁時重複顯示。
    const existingUrls = new Set(newsItems.value.map((item) => item.url))
    const newItems = body.news.filter((item) => !existingUrls.has(item.url))
    newsItems.value = [...newsItems.value, ...newItems]
    newsCursor.value = body.next_cursor
    newsHasMore.value = body.has_more
    newsSource.value = body.data_source
    // API 可能為了找舊新聞掃描了日期，但該區間沒有新文章；停下自動觸發，讓使用者按鈕決定是否繼續。
    if (newItems.length === 0 && body.has_more) newsAutoPaused.value = true
  } catch (cause) {
    newsError.value = cause instanceof Error ? cause.message : '新聞載入失敗，請稍後重試。'
    newsAutoPaused.value = true
  } finally {
    newsLoading.value = false
  }
}

function observeNewsSentinel() {
  newsObserver?.disconnect()
  if (!newsLoadSentinel.value || !newsHasMore.value || newsAutoPaused.value) return
  newsObserver = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) void loadNewsPage()
  }, { rootMargin: '120px' })
  newsObserver.observe(newsLoadSentinel.value)
}

function handleSearchInput() {
  selectedStockId.value = ''
  showSuggestions.value = true
  if (suggestTimer !== undefined) window.clearTimeout(suggestTimer)

  const query = symbol.value.trim()
  if (!query) {
    suggestions.value = []
    showSuggestions.value = false
    return
  }

  suggestTimer = window.setTimeout(async () => {
    try {
      const matches = await findStocks(query)
      if (symbol.value.trim() === query) suggestions.value = matches
    } catch {
      if (symbol.value.trim() === query) suggestions.value = []
    }
  }, 250)
}

function chooseStock(stock: StockMatch) {
  symbol.value = stock.stock_name
  selectedStockId.value = stock.stock_id
  suggestions.value = []
  showSuggestions.value = false
  void searchStock()
}

async function searchStock() {
  const query = symbol.value.trim()
  if (!query) return

  loading.value = true
  viewMode.value = 'stock'
  error.value = ''
  suggestions.value = []
  showSuggestions.value = false
  // 查詢時會先移除舊圖表的 v-if 區塊；先釋放 ECharts，避免綁在已移除的 DOM 上。
  chart?.dispose()
  chart = undefined
  analysis.value = null
  newsItems.value = []
  newsCursor.value = null
  newsHasMore.value = false
  newsError.value = ''
  newsAutoPaused.value = false
  newsObserver?.disconnect()
  try {
    let requestedSymbol = selectedStockId.value || query
    if (!selectedStockId.value && !/^\d{4,6}$/.test(query)) {
      const matches = await findStocks(query)
      const normalizedQuery = query.toLocaleLowerCase()
      const exactName = matches.find((stock) => stock.stock_name.toLocaleLowerCase() === normalizedQuery)
      if (exactName) {
        requestedSymbol = exactName.stock_id
      } else if (matches.length === 1) {
        requestedSymbol = matches[0].stock_id
      } else if (matches.length > 1) {
        suggestions.value = matches
        showSuggestions.value = true
        throw new Error('找到多檔相符股票，請從下拉清單選擇。')
      } else {
        throw new Error(`找不到「${query}」，請確認股票代號或名稱。`)
      }
    }

    const result = await apiRequest<Analysis>(
      `/api/stocks/${encodeURIComponent(requestedSymbol)}/analysis`,
    )
    selectedStockId.value = requestedSymbol
    analysis.value = result
    newsHasMore.value = true
    void loadNewsPage()
    await nextTick()
    drawChart()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '無法連線到 API，請確認後端已啟動。'
  } finally {
    loading.value = false
  }
}

watch([newsItems, newsHasMore, newsAutoPaused, newsLoading], async () => {
  await nextTick()
  observeNewsSentinel()
})

async function loadCurrentUser() {
  if (!getAccessToken()) return
  try {
    currentUser.value = await getCurrentUser()
  } catch (cause) {
    if (!(cause instanceof ApiError) || cause.status !== 401) {
      authNotice.value = cause instanceof Error ? cause.message : '無法讀取登入狀態。'
    }
  }
}

function handleUnauthorized() {
  currentUser.value = null
  activeSection.value = 'auth'
  authNotice.value = '登入狀態已過期，請重新登入。'
}

function openRiskAssessment() {
  if (!currentUser.value) {
    activeSection.value = 'auth'
    authNotice.value = '請先登入，才能保存個人風險評估。'
    return
  }
  authNotice.value = ''
  activeSection.value = 'risk'
}

function openPortfolio() {
  if (!currentUser.value) {
    activeSection.value = 'auth'
    authNotice.value = '請先登入，才能管理個人持股。'
    return
  }
  authNotice.value = ''
  activeSection.value = 'portfolio'
}

function openDailyRecommendations() {
  if (!currentUser.value) {
    activeSection.value = 'auth'
    authNotice.value = '請先登入，才能使用個人化每日推薦。'
    return
  }
  authNotice.value = ''
  activeSection.value = 'daily'
}

function onAuthenticated(user: UserResponse) {
  currentUser.value = user
  authNotice.value = ''
  activeSection.value = 'market'
}

function onRiskProfileUpdated(profile: RiskProfile) {
  if (!currentUser.value) return
  currentUser.value = {
    ...currentUser.value,
    risk_score: profile.risk_score,
    risk_type: profile.risk_type,
    risk_type_label: profile.risk_type_label,
  }
}

function logout() {
  clearAccessToken()
  currentUser.value = null
  authNotice.value = ''
  activeSection.value = 'market'
}

function drawChart() {
  if (!chartElement.value || !analysis.value) return
  chart ??= echarts.init(chartElement.value)
  const rows = analysis.value.data
  chart.setOption({
    color: ['#246bfe', '#f59e0b', '#8b5cf6', '#16a394'],
    tooltip: { trigger: 'axis' },
    legend: { top: 4, right: 8, textStyle: { color: '#667085' } },
    grid: { left: 52, right: 24, top: 48, bottom: 42 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: rows.map((row) => row.date),
      axisLabel: { color: '#8a94a6' },
      axisLine: { lineStyle: { color: '#e8ebf2' } },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { color: '#8a94a6' },
      splitLine: { lineStyle: { color: '#eef0f5' } },
    },
    series: [
      { name: '收盤價', type: 'line', smooth: true, showSymbol: false, lineStyle: { width: 3 }, data: rows.map((row) => row.close) },
      { name: 'MA5', type: 'line', smooth: true, showSymbol: false, lineStyle: { width: 1.5 }, data: rows.map((row) => row.ma5) },
      { name: 'MA20', type: 'line', smooth: true, showSymbol: false, lineStyle: { width: 1.5 }, data: rows.map((row) => row.ma20) },
      { name: 'MA60', type: 'line', smooth: true, showSymbol: false, lineStyle: { width: 1.5 }, data: rows.map((row) => row.ma60) },
    ],
  })
}

function drawMarketChart() {
  if (!chartElement.value || !market.value) return
  chart ??= echarts.init(chartElement.value)
  chart.setOption({
    color: ['#2868ee'],
    tooltip: { trigger: 'axis' },
    grid: { left: 68, right: 24, top: 24, bottom: 36 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: market.value.data.map((point) => point.time),
      axisLabel: { color: '#8a94a6', interval: 29 },
      axisLine: { lineStyle: { color: '#e8ebf2' } },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { color: '#8a94a6' },
      splitLine: { lineStyle: { color: '#eef0f5' } },
    },
    series: [{ name: '加權指數', type: 'line', smooth: true, showSymbol: false, lineStyle: { width: 2.5 }, areaStyle: { opacity: 0.08 }, data: market.value.data.map((point) => point.value) }],
  })
}

function resizeChart() { chart?.resize() }
watch(analysis, async () => { await nextTick(); drawChart() })
watch(market, async () => { await nextTick(); if (viewMode.value === 'market') drawMarketChart() })
watch([activeSection, viewMode], async ([section, mode]) => {
  // Vue 切頁會卸載圖表 DOM；釋放舊 ECharts 實例，回到看盤頁時再綁定新 DOM。
  chart?.dispose()
  chart = undefined
  if (section !== 'market') return

  await nextTick()
  if (mode === 'market' && market.value) drawMarketChart()
  if (mode === 'stock' && analysis.value) drawChart()
})
onMounted(() => {
  window.addEventListener('resize', resizeChart)
  window.addEventListener('auth:unauthorized', handleUnauthorized)
  void loadCurrentUser()
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  window.removeEventListener('auth:unauthorized', handleUnauthorized)
  chart?.dispose()
})

void loadMarket()
</script>

<template>
  <main class="page-shell">
    <header class="topbar">
      <a class="brand" href="#" aria-label="返回大盤總覽" @click.prevent="goHome">
        <span class="brand-mark">Q</span>
        <span>QuantGuard <span class="brand-light">TW</span><small>個人化台股 Multi-Agent 量化分析師團隊</small></span>
      </a>
      <nav class="primary-nav" aria-label="主要導覽">
        <button type="button" :class="{ active: activeSection === 'market' }" @click="activeSection = 'market'">看盤分析</button>
        <button type="button" :class="{ active: activeSection === 'risk' }" @click="openRiskAssessment">風險測驗</button>
        <button type="button" :class="{ active: activeSection === 'portfolio' }" @click="openPortfolio">庫存診斷</button>
        <button type="button" :class="{ active: activeSection === 'daily' }" @click="openDailyRecommendations">每日推薦</button>
        <button type="button" :class="{ active: glossaryOpen }" @click="glossaryOpen = true">術語百科</button>
      </nav>
      <span class="topbar-note"><span class="status-dot"></span>研究模式 · 不連接券商</span>
      <div class="account-nav">
        <template v-if="currentUser">
          <span class="account-name">{{ currentUser.full_name }}</span>
          <span class="account-risk" :class="currentUser.risk_type?.toLowerCase()">
            {{ currentUser.risk_type_label ?? '尚未完成測驗' }}
          </span>
          <button type="button" class="account-button" @click="logout">登出</button>
        </template>
        <button v-else type="button" class="account-button" @click="activeSection = 'auth'; authNotice = ''">登入 / 註冊</button>
      </div>
    </header>

    <AuthView
      v-if="activeSection === 'auth'"
      :notice="authNotice"
      @authenticated="onAuthenticated"
    />
    <RiskAssessmentView
      v-else-if="activeSection === 'risk' && currentUser"
      @profile-updated="onRiskProfileUpdated"
    />
    <PortfolioView v-else-if="activeSection === 'portfolio' && currentUser" />
    <DailyRecommendationsView
      v-else-if="activeSection === 'daily' && currentUser"
      :risk-type-label="currentUser.risk_type_label"
    />
    <template v-else>
    <section class="intro">
      <div class="eyebrow">MARKET RESEARCH / 台灣市場</div>
      <h1>QuantGuard <span>TW</span></h1>
      <p>你的個人化台股 Multi-Agent 量化分析師團隊</p>
    </section>

    <section class="search-card" aria-label="股票查詢">
      <div class="search-label">搜尋台股</div>
      <div class="search-input-wrap">
        <form class="search-row" @submit.prevent="searchStock">
          <span class="search-icon">⌕</span>
          <input v-model="symbol" aria-label="股票代號或名稱" placeholder="輸入股票代號或名稱，例如 台積電" autocomplete="off" @input="handleSearchInput" />
          <button type="submit" :disabled="loading">{{ loading ? '分析中…' : '開始分析' }} <span>→</span></button>
        </form>
        <div v-if="showSuggestions && suggestions.length" class="search-suggestions">
          <button v-for="stock in suggestions" :key="stock.stock_id" type="button" class="search-suggestion" @mousedown.prevent @click="chooseStock(stock)">
            <span>{{ stock.stock_name }}</span><small>{{ stock.stock_id }}</small>
          </button>
        </div>
      </div>
      <div class="quick-hint">輸入股票代號或名稱；離線示範資料：<button class="text-button" @click="symbol = '2330'; selectedStockId = '2330'; searchStock()">2330 台積電</button></div>
    </section>

    <p v-if="error" class="error-banner">{{ error }}</p>

    <template v-if="viewMode === 'market'">
      <div class="section-heading">
        <div><div class="eyebrow">TAIWAN MARKET</div><h2>市場總覽 <span>加權指數（TAIEX）</span></h2></div>
        <div class="demo-pill live-source"><span></span>最近交易日</div>
      </div>
      <p v-if="marketError" class="error-banner">{{ marketError }} <button class="text-button" @click="loadMarket">重新載入</button></p>
      <p v-else-if="marketLoading && !market" class="market-message">正在載入大盤指數…</p>
      <template v-if="market">
        <section class="metrics-grid market-metrics">
          <article class="metric-card primary-metric">
            <div class="metric-label">加權指數 <span>TAIEX</span></div>
            <div class="metric-value" :class="trendClass(market.latest_value, market.session_open)">{{ market.latest_value.toLocaleString('zh-TW', { maximumFractionDigits: 2 }) }}</div>
            <div class="metric-foot">資料日期 {{ market.latest_data_date }} <span class="trend-change" :class="trendClass(market.latest_value, market.session_open)">{{ formatChange(marketChange) }}（較開盤）</span></div>
          </article>
          <article class="metric-card"><div class="metric-label">當日開盤 <span>指數點</span></div><div class="metric-value compact">{{ market.session_open.toLocaleString('zh-TW', { maximumFractionDigits: 2 }) }}</div><div class="metric-foot">盤中第一筆指數</div></article>
          <article class="metric-card"><div class="metric-label">當日最高 <span>指數點</span></div><div class="metric-value compact" :class="trendClass(market.session_high, market.session_open)">{{ market.session_high.toLocaleString('zh-TW', { maximumFractionDigits: 2 }) }}</div><div class="metric-foot">相較當日開盤</div></article>
          <article class="metric-card"><div class="metric-label">當日最低 <span>指數點</span></div><div class="metric-value compact" :class="trendClass(market.session_low, market.session_open)">{{ market.session_low.toLocaleString('zh-TW', { maximumFractionDigits: 2 }) }}</div><div class="metric-foot">相較當日開盤</div></article>
        </section>
        <section class="chart-card">
          <div class="chart-heading"><div><h3>加權指數走勢</h3><p>最近交易日盤中變化（每分鐘取樣）</p></div><span class="chart-period">{{ market.latest_data_date }}</span></div>
          <div ref="chartElement" class="chart"></div>
          <div class="chart-note">資料來源：{{ market.data_source }}。此為指數資料，不是個股價格，也不代表即時報價。</div>
        </section>
        <div class="notice"><span class="notice-icon">i</span><span>{{ market.notice }}</span></div>
      </template>
    </template>

    <template v-else-if="analysis">
      <div class="section-heading">
        <div><div class="eyebrow">STOCK OVERVIEW</div><h2>{{ analysis.symbol }} <span>{{ analysis.name }}</span></h2></div>
        <div class="demo-pill" :class="{ 'live-source': !analysis.is_demo_data }"><span></span>{{ analysis.is_demo_data ? '示範資料' : '歷史日線' }}</div>
      </div>

      <section class="metrics-grid">
        <article class="metric-card primary-metric">
          <div class="metric-label">最新收盤價 <span>新台幣</span></div>
          <div class="metric-value" :class="trendClass(latest?.close, previous?.close)">{{ latest?.close?.toLocaleString('zh-TW') }}<small>.00</small></div>
          <div class="metric-foot">資料日期 {{ analysis.latest_data_date }} <span class="trend-change" :class="trendClass(latest?.close, previous?.close)">{{ formatChange(stockChange) }}</span> <span class="neutral-change">{{ analysis.is_realtime ? '即時行情' : '盤後資料' }}</span></div>
        </article>
        <article class="metric-card"><div class="metric-label">MA5 <span>短期趨勢</span></div><div class="metric-value compact" :class="trendClass(latest?.ma5, previous?.ma5)">{{ latest?.ma5?.toFixed(2) ?? '—' }}</div><div class="metric-foot">近 5 個交易日平均</div></article>
        <article class="metric-card"><div class="metric-label">MA20 <span>中期趨勢</span></div><div class="metric-value compact" :class="trendClass(latest?.ma20, previous?.ma20)">{{ latest?.ma20?.toFixed(2) ?? '—' }}</div><div class="metric-foot">近 20 個交易日平均</div></article>
        <article class="metric-card"><div class="metric-label">MA60 <span>長期趨勢</span></div><div class="metric-value compact" :class="trendClass(latest?.ma60, previous?.ma60)">{{ latest?.ma60?.toFixed(2) ?? '—' }}</div><div class="metric-foot">近 60 個交易日平均</div></article>
      </section>

      <section class="chart-card">
        <div class="chart-heading"><div><h3>價格與均線</h3><p>收盤價走勢及移動平均線</p></div><span class="chart-period">{{ analysis.is_demo_data ? '示範樣本' : '近一年日線' }}</span></div>
        <div ref="chartElement" class="chart"></div>
        <div class="chart-note">均線需累積足夠交易日才會顯示；成交量欄位以股為單位。</div>
      </section>
      <section class="news-card" aria-label="相關新聞">
        <div class="news-heading">
          <div><div class="eyebrow">RELATED NEWS</div><h3>相關新聞</h3><p>由新到舊 · 每次最多載入 10 則 · 僅保留一年</p></div>
          <span v-if="newsSource" class="news-source-pill">{{ newsSource }}</span>
        </div>
        <p v-if="newsItems.length === 0 && newsLoading" class="news-empty">正在搜尋相關新聞…</p>
        <p v-else-if="newsItems.length === 0 && !newsLoading && !newsError" class="news-empty">目前找不到這檔股票的新聞資料。</p>
        <article v-for="item in newsItems" :key="item.url" class="news-item">
          <div class="news-meta"><span>{{ item.source }}</span><time :datetime="item.published_at">{{ new Date(item.published_at).toLocaleString('zh-TW') }}</time></div>
          <a class="news-title" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.title }}</a>
          <p class="news-summary">{{ item.summary || '來源未提供摘要，請點選標題閱讀原文。' }}</p>
        </article>
        <p v-if="newsError" class="news-error">{{ newsError }}</p>
        <button v-if="newsHasMore && newsAutoPaused && !newsLoading" class="news-more-button" @click="loadNewsPage">繼續搜尋較舊新聞</button>
        <p v-else-if="newsLoading && newsItems.length" class="news-status">正在載入更多新聞…</p>
        <p v-else-if="!newsHasMore && newsItems.length" class="news-status">已顯示目前可取得的新聞。</p>
        <div ref="newsLoadSentinel" class="news-sentinel" aria-hidden="true"></div>
      </section>
      <div class="notice"><span class="notice-icon">i</span><span>{{ analysis.notice }}資料來源：{{ analysis.data_source }}。來源資料可能延遲或更正，請自行核對。</span></div>
    </template>

    <footer>QuantGuard TW · 個人化台股量化研究 <span>資料為研究用途</span></footer>
    </template>
    <GlossaryDrawer :open="glossaryOpen" @close="glossaryOpen = false" />
  </main>
</template>
