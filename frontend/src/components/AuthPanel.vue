<script setup lang="ts">
import { ref } from 'vue'
import { getCurrentUser, loginDemoUser, loginUser, registerUser } from '../api/auth'
import type { UserResponse } from '../api/auth'

const props = defineProps<{ notice?: string }>()
const emit = defineEmits<{ authenticated: [user: UserResponse] }>()

const mode = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')
const fullName = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  loading.value = true
  error.value = ''
  try {
    if (mode.value === 'register') {
      await registerUser({ email: email.value, password: password.value, full_name: fullName.value })
    }
    await loginUser({ email: email.value, password: password.value })
    emit('authenticated', await getCurrentUser())
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '登入失敗，請稍後再試。'
  } finally {
    loading.value = false
  }
}

async function demoLogin() {
  loading.value = true
  error.value = ''
  try {
    await loginDemoUser()
    emit('authenticated', await getCurrentUser())
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '展示登入暫時無法使用，請稍後重試。'
  } finally {
    loading.value = false
  }
}

function changeMode(nextMode: 'login' | 'register') {
  mode.value = nextMode
  error.value = ''
}
</script>

<template>
  <section class="auth-panel">
    <div class="auth-copy">
      <div class="eyebrow">PERSONAL RESEARCH SPACE</div>
      <h2>{{ mode === 'login' ? '登入你的研究帳戶' : '建立研究帳戶' }}</h2>
      <p>保存風險屬性設定；看盤分析仍可不登入使用。</p>
    </div>
    <div class="auth-card">
      <div class="auth-tabs">
        <button type="button" :class="{ active: mode === 'login' }" @click="changeMode('login')">登入</button>
        <button type="button" :class="{ active: mode === 'register' }" @click="changeMode('register')">註冊</button>
      </div>
      <p v-if="props.notice" class="auth-notice">{{ props.notice }}</p>
      <button
        v-if="mode === 'login'"
        class="demo-login-button"
        type="button"
        :disabled="loading"
        @click="demoLogin"
      >{{ loading ? '正在進入展示帳號…' : '面試官 / 訪客一鍵體驗登入' }}</button>
      <form class="auth-form" @submit.prevent="submit">
        <label v-if="mode === 'register'">姓名<input v-model.trim="fullName" required maxlength="100" autocomplete="name" /></label>
        <label>Email<input v-model.trim="email" type="email" required maxlength="254" autocomplete="email" /></label>
        <label>密碼<input v-model="password" type="password" required minlength="8" maxlength="72" autocomplete="current-password" /></label>
        <p v-if="mode === 'register'" class="auth-help">密碼至少 8 碼；請勿重複使用其他網站的密碼。</p>
        <p v-if="error" class="auth-error" role="alert">{{ error }}</p>
        <button class="auth-submit" type="submit" :disabled="loading">
          {{ loading ? '處理中…' : mode === 'login' ? '登入' : '註冊並登入' }}
        </button>
      </form>
    </div>
  </section>
</template>
