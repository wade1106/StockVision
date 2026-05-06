<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const username = ref('')
const password = ref('')
const showPassword = ref(false)
const error = ref(null)
const loading = ref(false)

async function login() {
  error.value = null
  loading.value = true
  try {
    const res = await axios.post('/api/login', {
      username: username.value,
      password: password.value,
    })
    localStorage.setItem('sv_token', res.data.token)
    router.push('/users')
  } catch (e) {
    error.value = e.response?.data?.detail || '登入失敗'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <div class="login-box">
      <h1>StockVision</h1>
      <p class="subtitle">後台管理</p>
      <form @submit.prevent="login">
        <label>帳號</label>
        <input v-model="username" type="text" autocomplete="username" required />
        <label>密碼</label>
        <div class="input-wrap">
          <input v-model="password" :type="showPassword ? 'text' : 'password'"
            autocomplete="current-password" required />
          <button type="button" class="eye-btn" @click="showPassword = !showPassword">
            <svg v-if="!showPassword" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
            </svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
              <line x1="1" y1="1" x2="23" y2="23"/>
            </svg>
          </button>
        </div>
        <div v-if="error" class="error">{{ error }}</div>
        <button type="submit" :disabled="loading">
          {{ loading ? '登入中...' : '登入' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f2f5;
}
.login-box {
  background: #fff;
  border-radius: 12px;
  padding: 40px 36px;
  width: 340px;
  box-shadow: 0 4px 20px rgba(0,0,0,.1);
}
h1 { font-size: 22px; font-weight: 700; margin: 0 0 4px; color: #1a1a2e; }
.subtitle { font-size: 13px; color: #999; margin: 0 0 28px; }
label { display: block; font-size: 13px; font-weight: 600; color: #555; margin-bottom: 6px; }
input {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid #e0e3e8;
  border-radius: 6px;
  font-size: 14px;
  margin-bottom: 16px;
  box-sizing: border-box;
}
input:focus { outline: none; border-color: #1a1a2e; }
.input-wrap { position: relative; margin-bottom: 16px; }
.input-wrap input { margin-bottom: 0; padding-right: 40px; }
.eye-btn { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; color: #999; padding: 0; width: auto; margin: 0; }
button {
  width: 100%;
  padding: 10px;
  background: #1a1a2e;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 4px;
}
button:disabled { opacity: 0.5; cursor: not-allowed; }
.error { color: #c0392b; font-size: 13px; margin-bottom: 12px; }
</style>
