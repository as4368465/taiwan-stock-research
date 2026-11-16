<script setup lang="ts">
import AuthPanel from '../components/AuthPanel.vue'
import type { UserResponse } from '../api/auth'

defineProps<{ notice?: string }>()
const emit = defineEmits<{ authenticated: [user: UserResponse] }>()
</script>

<template>
  <AuthPanel :notice="notice" @authenticated="emit('authenticated', $event)" />
</template>
