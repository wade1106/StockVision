<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const users = ref([])
const loading = ref(true)
const refreshing = ref(false)
const toast = ref(null)  // { msg, type: 'success'|'error' }
let toastTimer = null

function authHeaders() {
  return { Authorization: `Bearer ${localStorage.getItem('sv_token') || ''}` }
}

function showToast(msg, type = 'success') {
  clearTimeout(toastTimer)
  toast.value = { msg, type }
  toastTimer = setTimeout(() => { toast.value = null }, 3000)
}

async function loadUsers() {
  try {
    const res = await axios.get('/api/users', { headers: authHeaders() })
    users.value = res.data.users
  } catch (e) {
    if (e.response?.status === 401 || e.response?.status === 403) {
      localStorage.removeItem('sv_token')
      router.push('/login')
    } else {
      showToast('無法載入成員資料', 'error')
    }
  } finally {
    loading.value = false
  }
}

async function refreshNames() {
  refreshing.value = true
  try {
    const res = await axios.post('/api/users/refresh', {}, { headers: authHeaders() })
    await loadUsers()
    if (res.data.updated === 0) {
      showToast('名稱已是最新', 'success')
    } else {
      showToast(`已更新 ${res.data.updated} 筆名稱`, 'success')
    }
  } catch (e) {
    if (e.response?.status === 401 || e.response?.status === 403) {
      localStorage.removeItem('sv_token')
      router.push('/login')
    } else {
      showToast('重新整理失敗', 'error')
    }
  } finally {
    refreshing.value = false
  }
}

async function logout() {
  await axios.post('/api/logout', {}, { headers: authHeaders() }).catch(() => {})
  localStorage.removeItem('sv_token')
  router.push('/login')
}

onMounted(loadUsers)

const followCount = computed(() => users.value.filter(u => u.source === 'follow').length)
const groupCount = computed(() => users.value.filter(u => u.source === 'group_join').length)

const PAGE_SIZE = 10
const page = ref(1)
const totalPages = computed(() => Math.max(1, Math.ceil(users.value.length / PAGE_SIZE)))
const pagedUsers = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return users.value.slice(start, start + PAGE_SIZE)
})
const pageStart = computed(() => (page.value - 1) * PAGE_SIZE)

// 顯示的頁碼按鈕（最多顯示 5 個，超過用 ... 省略）
const pageNumbers = computed(() => {
  const total = totalPages.value
  const cur = page.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages = new Set([1, total, cur, cur - 1, cur + 1])
  return Array.from(pages)
    .filter(p => p >= 1 && p <= total)
    .sort((a, b) => a - b)
    .reduce((acc, p, i, arr) => {
      if (i > 0 && p - arr[i - 1] > 1) acc.push('...')
      acc.push(p)
      return acc
    }, [])
})

function formatDate(iso) {
  return iso ? iso.slice(0, 19).replace('T', ' ') : '—'
}
</script>

<template>
  <Transition name="toast">
    <div v-if="toast" :class="['toast', `toast-${toast.type}`]">{{ toast.msg }}</div>
  </Transition>

  <div class="header-row">
    <h1>LINE 成員列表</h1>
    <div class="btn-group">
      <button class="btn-refresh" :disabled="refreshing" @click="refreshNames">
        {{ refreshing ? '更新中...' : '重新整理名稱' }}
      </button>
      <button class="btn-logout" @click="logout">登出</button>
    </div>
  </div>

  <div v-if="loading" class="empty">載入中...</div>
  <template v-else>
    <div class="stat-grid">
      <div class="stat-box">
        <div class="value">{{ users.length }}</div>
        <div class="label">總成員數</div>
      </div>
      <div class="stat-box">
        <div class="value">{{ followCount }}</div>
        <div class="label">追蹤官方帳號</div>
      </div>
      <div class="stat-box">
        <div class="value">{{ groupCount }}</div>
        <div class="label">加入群組</div>
      </div>
    </div>

    <div class="card">
      <table v-if="users.length">
        <thead>
          <tr>
            <th>#</th>
            <th>暱稱</th>
            <th>User ID</th>
            <th>來源</th>
            <th>加入時間</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(u, i) in pagedUsers" :key="u.userId">
            <td>{{ pageStart + i + 1 }}</td>
            <td><strong>{{ u.displayName }}</strong></td>
            <td class="mono">{{ u.userId }}</td>
            <td>
              <span :class="['badge', u.source === 'follow' ? 'badge-green' : 'badge-gray']">
                {{ u.source === 'follow' ? '追蹤' : '群組加入' }}
              </span>
            </td>
            <td class="muted">{{ formatDate(u.joinedAt) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty">尚無成員資料。請確認 Webhook Server 已啟動並設定 Cloudflare Tunnel。</p>
      <div v-if="users.length" class="pagination">
        <span class="page-info">共 {{ users.length }} 筆，第 {{ page }} / {{ totalPages }} 頁</span>
        <div class="page-btns">
          <button :disabled="page === 1" @click="page = 1">«</button>
          <button :disabled="page === 1" @click="page--">‹</button>
          <template v-for="p in pageNumbers" :key="p">
            <span v-if="p === '...'" class="ellipsis">…</span>
            <button v-else :class="{ active: p === page }" @click="page = p">{{ p }}</button>
          </template>
          <button :disabled="page === totalPages" @click="page++">›</button>
          <button :disabled="page === totalPages" @click="page = totalPages">»</button>
        </div>
        <div class="page-jump">
          前往第
          <input type="number" min="1" :max="totalPages" :value="page"
            @change="e => page = Math.min(totalPages, Math.max(1, +e.target.value))" />
          頁
        </div>
      </div>
    </div>
  </template>
</template>

<style scoped>
.toast {
  position: fixed;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  z-index: 999;
  box-shadow: 0 4px 12px rgba(0,0,0,.15);
}
.toast-success { background: #1a7a42; color: #fff; }
.toast-error   { background: #c0392b; color: #fff; }
.toast-enter-active, .toast-leave-active { transition: opacity .3s, top .3s; }
.toast-enter-from, .toast-leave-to { opacity: 0; top: 12px; }

.header-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
h1 { font-size: 22px; font-weight: 700; margin: 0; }
.btn-group { display: flex; gap: 8px; }
.btn-refresh, .btn-logout { padding: 7px 16px; font-size: 13px; font-weight: 600; border: none; border-radius: 6px; cursor: pointer; }
.btn-refresh { background: #1a1a2e; color: #fff; }
.btn-refresh:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-logout { background: #e74c3c; color: #fff; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 24px; }
.stat-box { background: #fff; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.stat-box .value { font-size: 28px; font-weight: 700; }
.stat-box .label { font-size: 12px; color: #888; margin-top: 4px; }
.card { background: #fff; border-radius: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.08); padding: 24px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { background: #f0f2f5; text-align: left; padding: 10px 12px; font-weight: 600; border-bottom: 2px solid #e0e3e8; }
td { padding: 9px 12px; border-bottom: 1px solid #f0f2f5; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #fafbfc; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.badge-green { background: #e6f7ee; color: #1a7a42; }
.badge-gray  { background: #f0f2f5; color: #777; }
.mono { font-family: monospace; font-size: 12px; color: #777; }
.muted { color: #777; font-size: 13px; }
.empty { color: #999; font-size: 14px; text-align: center; padding: 40px 0; }
.pagination { display: flex; align-items: center; justify-content: space-between; padding-top: 16px; flex-wrap: wrap; gap: 8px; }
.page-info { font-size: 13px; color: #777; }
.page-btns { display: flex; align-items: center; gap: 4px; }
.page-btns button { min-width: 32px; height: 32px; padding: 0 6px; border: 1px solid #e0e3e8; border-radius: 6px; background: #fff; font-size: 13px; cursor: pointer; }
.page-btns button:disabled { opacity: 0.35; cursor: not-allowed; }
.page-btns button.active { background: #1a1a2e; color: #fff; border-color: #1a1a2e; font-weight: 700; }
.page-btns .ellipsis { padding: 0 4px; color: #999; font-size: 13px; }
.page-jump { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #555; }
.page-jump input { width: 48px; height: 30px; border: 1px solid #e0e3e8; border-radius: 6px; text-align: center; font-size: 13px; }
</style>
