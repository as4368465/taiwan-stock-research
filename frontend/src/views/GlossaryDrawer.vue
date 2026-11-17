<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { getGlossary } from '../api/glossary'
import type { GlossaryCategory, GlossaryTerm } from '../api/glossary'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const categories: (GlossaryCategory | '')[] = ['', '基礎交易', 'K線型態', '技術指標', '風險控管']
const categoryLabels: Record<GlossaryCategory | '', string> = {
  '': '全部',
  基礎交易: '基礎交易',
  K線型態: 'K 線型態',
  技術指標: '技術指標',
  風險控管: '風險控管',
}
const query = ref('')
const selectedCategory = ref<GlossaryCategory | ''>('')
const terms = ref<GlossaryTerm[]>([])
const loading = ref(false)
const error = ref('')
let requestSequence = 0

async function loadTerms() {
  const sequence = ++requestSequence
  loading.value = true
  error.value = ''
  try {
    const response = await getGlossary(query.value, selectedCategory.value)
    if (sequence === requestSequence) terms.value = response.terms
  } catch (cause) {
    if (sequence === requestSequence) error.value = cause instanceof Error ? cause.message : '術語資料暫時無法載入。'
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function closeOnEscape(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.open) emit('close')
}

watch([() => props.open, query, selectedCategory], ([open]) => {
  if (open) void loadTerms()
})

if (typeof window !== 'undefined') window.addEventListener('keydown', closeOnEscape)
onBeforeUnmount(() => window.removeEventListener('keydown', closeOnEscape))
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="glossary-overlay" @mousedown.self="emit('close')">
      <aside class="glossary-drawer" role="dialog" aria-modal="true" aria-labelledby="glossary-title">
        <header class="glossary-header">
          <div><div class="eyebrow">INVESTING TERMS</div><h2 id="glossary-title">投資術語小百科</h2></div>
          <button class="glossary-close" type="button" aria-label="關閉術語百科" @click="emit('close')">×</button>
        </header>
        <label class="glossary-search-label">搜尋術語
          <input v-model="query" class="form-control" type="search" placeholder="例如 RSI、停損、紅K" />
        </label>
        <div class="glossary-category-list" aria-label="術語分類">
          <button
            v-for="item in categories"
            :key="item || 'all'"
            type="button"
            :class="{ active: selectedCategory === item }"
            @click="selectedCategory = item"
          >{{ categoryLabels[item] }}</button>
        </div>
        <p v-if="loading" class="glossary-state">正在搜尋術語…</p>
        <p v-else-if="error" class="error-banner glossary-error" role="alert">{{ error }}</p>
        <p v-else-if="!terms.length" class="glossary-state">找不到符合條件的術語。</p>
        <div v-else class="glossary-term-list">
          <article v-for="term in terms" :key="term.term" class="glossary-term-card">
            <div class="glossary-term-heading"><h3>{{ term.term }}</h3><span>{{ term.category }}</span></div>
            <p>{{ term.summary }}</p>
            <div class="glossary-term-detail"><strong>看盤怎麼用</strong><p>{{ term.practical_tip }}</p></div>
            <div class="glossary-term-detail warning"><strong>常見誤區</strong><p>{{ term.risk_warning }}</p></div>
          </article>
        </div>
        <footer class="glossary-footer">術語僅作教育參考，技術指標不是獲利保證。</footer>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.glossary-overlay { position: fixed; z-index: 1000; inset: 0; display: flex; justify-content: flex-end; overflow: hidden; background: #19243b66; }
.glossary-drawer { display: flex; flex-direction: column; width: min(540px, 100%); min-width: 0; height: 100%; padding: 26px; overflow: hidden; background: #f7f8fb; box-shadow: -16px 0 48px #14213d24; }
.glossary-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 20px; }
.glossary-header h2 { margin: 7px 0 0; font-size: 25px; }
.glossary-close { width: 38px; height: 38px; border: 1px solid #e0e5ee; border-radius: 10px; color: #56627a; background: #fff; cursor: pointer; font-size: 24px; }
.glossary-search-label { display: grid; min-width: 0; gap: 8px; color: #465166; font-size: 14px; font-weight: 600; }
.glossary-search-label :deep(.form-control) { width: 100%; min-width: 0; box-sizing: border-box; }
.glossary-category-list { display: flex; flex-wrap: wrap; gap: 8px; padding: 15px 0; }
.glossary-category-list button { flex: 0 1 auto; max-width: 100%; padding: 8px 11px; border: 1px solid #e0e5ee; border-radius: 999px; color: #657188; background: #fff; cursor: pointer; font-size: 12px; white-space: nowrap; }
.glossary-category-list button.active { border-color: #b9cafa; color: #2868ee; background: #edf3ff; }
.glossary-term-list { display: grid; min-height: 0; min-width: 0; flex: 1; gap: 12px; overflow-y: auto; padding: 2px 0 18px; scrollbar-width: none; }
.glossary-term-list::-webkit-scrollbar { display: none; }
.glossary-term-card { min-width: 0; padding: 17px; border: 1px solid #e7eaf1; border-radius: 13px; background: #fff; overflow-wrap: anywhere; }
.glossary-term-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.glossary-term-heading h3 { margin: 0; color: #2d3b54; font-size: 17px; }
.glossary-term-heading span { padding: 4px 7px; border-radius: 999px; color: #5c6e8d; background: #f0f3f8; font-size: 10px; white-space: nowrap; }
.glossary-term-card > p, .glossary-term-detail p { margin: 8px 0 0; color: #687386; font-size: 13px; line-height: 1.7; }
.glossary-term-detail { margin-top: 12px; padding: 11px 12px; border-radius: 9px; background: #f5f8ff; }
.glossary-term-detail strong { color: #47689f; font-size: 11px; }
.glossary-term-detail.warning { background: #fff8ef; }
.glossary-term-detail.warning strong { color: #98642e; }
.glossary-state { padding: 30px 10px; color: #788397; text-align: center; font-size: 13px; }
.glossary-error { width: 100%; margin: 0; }
.glossary-footer { margin-top: auto; padding-top: 14px; border-top: 1px solid #e5e9f0; color: #8a94a6; font-size: 11px; }
@media (max-width: 600px) { .glossary-drawer { padding: 20px 16px; } }
</style>
