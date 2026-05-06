<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'
import { Line, Bar, Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, BarElement, ArcElement, Title, Tooltip, Legend, Filler
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, ArcElement, Title, Tooltip, Legend, Filler)

// 預設日期範圍：最近 30 天
function toDateStr(d) { return d.toISOString().slice(0, 10) }
const today = new Date()
const thirtyDaysAgo = new Date(today); thirtyDaysAgo.setDate(today.getDate() - 30)

const start = ref(toDateStr(thirtyDaysAgo))
const end = ref(toDateStr(today))
const rows = ref([])
const loading = ref(false)
const error = ref(null)

async function fetchData() {
  loading.value = true
  error.value = null
  try {
    const res = await axios.get('/api/performance', { params: { start: start.value, end: end.value } })
    rows.value = res.data.rows
  } catch (e) {
    error.value = '無法載入資料'
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)

// 統計
const decided = computed(() => rows.value.filter(r => r.correct !== null))
const accuracy = computed(() => {
  if (!decided.value.length) return null
  return (decided.value.filter(r => r.correct).length / decided.value.length * 100).toFixed(1)
})
const bullDecided = computed(() => decided.value.filter(r => r.direction === 'bullish'))
const bearDecided = computed(() => decided.value.filter(r => r.direction === 'bearish'))
const bullAcc = computed(() => bullDecided.value.length
  ? (bullDecided.value.filter(r => r.correct).length / bullDecided.value.length * 100).toFixed(1) : null)
const bearAcc = computed(() => bearDecided.value.length
  ? (bearDecided.value.filter(r => r.correct).length / bearDecided.value.length * 100).toFixed(1) : null)

// 每日準確率（折線圖）
const dailyChartData = computed(() => {
  const byDate = {}
  rows.value.forEach(r => {
    if (r.correct === null) return
    if (!byDate[r.date]) byDate[r.date] = { correct: 0, total: 0 }
    byDate[r.date].total++
    if (r.correct) byDate[r.date].correct++
  })
  const dates = Object.keys(byDate).sort()
  return {
    labels: dates,
    datasets: [{
      label: '準確率 (%)',
      data: dates.map(d => +(byDate[d].correct / byDate[d].total * 100).toFixed(1)),
      borderColor: '#4a90d9',
      backgroundColor: 'rgba(74,144,217,0.1)',
      tension: 0.3,
      fill: true,
      pointRadius: 4,
    }]
  }
})

const lineOptions = { responsive: true, maintainAspectRatio: false,
  scales: { y: { min: 0, max: 100, ticks: { callback: v => v + '%' } } },
  plugins: { legend: { display: false } } }

// 看好 vs 看淡（長條圖）
const directionChartData = computed(() => ({
  labels: ['看好', '看淡'],
  datasets: [{
    label: '準確率 (%)',
    data: [bullAcc.value ?? 0, bearAcc.value ?? 0],
    backgroundColor: ['rgba(39,174,96,0.7)', 'rgba(231,76,60,0.7)'],
    borderRadius: 6,
  }]
}))

const barOptions = { responsive: true, maintainAspectRatio: false,
  scales: { y: { min: 0, max: 100, ticks: { callback: v => v + '%' } } },
  plugins: { legend: { display: false } } }

// 結果分佈（甜甜圈）
const donutData = computed(() => ({
  labels: ['正確', '錯誤', '待定'],
  datasets: [{
    data: [
      rows.value.filter(r => r.correct === true).length,
      rows.value.filter(r => r.correct === false).length,
      rows.value.filter(r => r.correct === null).length,
    ],
    backgroundColor: ['rgba(39,174,96,0.8)', 'rgba(231,76,60,0.8)', 'rgba(200,200,200,0.6)'],
    borderWidth: 2,
  }]
}))

const donutOptions = { responsive: true, maintainAspectRatio: false,
  plugins: { legend: { position: 'bottom' } } }

// 排序
const sortKey = ref('date')
const sortDir = ref('desc')
function toggleSort(key) {
  if (sortKey.value === key) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else { sortKey.value = key; sortDir.value = 'desc' }
}
const sortedRows = computed(() => {
  return [...rows.value].sort((a, b) => {
    const av = a[sortKey.value], bv = b[sortKey.value]
    if (av === null) return 1; if (bv === null) return -1
    return sortDir.value === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
  })
})

function sortIcon(key) {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? ' ▲' : ' ▼'
}
</script>

<template>
  <h1>預測 vs 實際比對</h1>

  <form class="filter" @submit.prevent="fetchData">
    <label>開始日期 <input type="date" v-model="start" /></label>
    <label>結束日期 <input type="date" v-model="end" /></label>
    <button type="submit">套用</button>
  </form>

  <div v-if="loading" class="empty">載入中...</div>
  <div v-else-if="error" class="empty error">{{ error }}</div>
  <template v-else-if="rows.length">

    <!-- 統計數字 -->
    <div class="stat-grid">
      <div class="stat-box">
        <div class="value">{{ accuracy ?? '—' }}{{ accuracy ? '%' : '' }}</div>
        <div class="label">整體準確率</div>
      </div>
      <div class="stat-box">
        <div class="value" style="color:#27ae60">{{ bullAcc ?? '—' }}{{ bullAcc ? '%' : '' }}</div>
        <div class="label">看好準確率</div>
      </div>
      <div class="stat-box">
        <div class="value" style="color:#e74c3c">{{ bearAcc ?? '—' }}{{ bearAcc ? '%' : '' }}</div>
        <div class="label">看淡準確率</div>
      </div>
      <div class="stat-box">
        <div class="value">{{ decided.length }}</div>
        <div class="label">已有結果筆數</div>
      </div>
      <div class="stat-box">
        <div class="value">{{ rows.length }}</div>
        <div class="label">總預測筆數</div>
      </div>
    </div>

    <!-- 圖表 -->
    <div class="card">
      <h2>每日準確率趨勢</h2>
      <div class="chart-wrap">
        <Line :data="dailyChartData" :options="lineOptions" />
      </div>
    </div>

    <div class="chart-row">
      <div class="card">
        <h2>看好 vs 看淡準確率</h2>
        <div class="chart-wrap chart-sm">
          <Bar :data="directionChartData" :options="barOptions" />
        </div>
      </div>
      <div class="card">
        <h2>預測結果分佈</h2>
        <div class="chart-wrap chart-sm">
          <Doughnut :data="donutData" :options="donutOptions" />
        </div>
      </div>
    </div>

    <!-- 明細表格 -->
    <div class="card">
      <h2>個股明細</h2>
      <table>
        <thead>
          <tr>
            <th @click="toggleSort('date')" class="sortable">日期{{ sortIcon('date') }}</th>
            <th>股票</th>
            <th>代號</th>
            <th @click="toggleSort('direction')" class="sortable">預測{{ sortIcon('direction') }}</th>
            <th @click="toggleSort('prob')" class="sortable">信心度{{ sortIcon('prob') }}</th>
            <th @click="toggleSort('actual_return')" class="sortable">實際漲跌{{ sortIcon('actual_return') }}</th>
            <th @click="toggleSort('correct')" class="sortable">結果{{ sortIcon('correct') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in sortedRows" :key="r.date + r.ticker">
            <td class="muted">{{ r.date }}</td>
            <td><strong>{{ r.name }}</strong></td>
            <td class="mono">{{ r.ticker }}</td>
            <td>
              <span :class="['badge', r.direction === 'bullish' ? 'badge-green' : 'badge-red']">
                {{ r.direction === 'bullish' ? '看好' : '看淡' }}
              </span>
            </td>
            <td>{{ r.prob }}%</td>
            <td :style="{ color: r.actual_return > 0 ? '#27ae60' : r.actual_return < 0 ? '#e74c3c' : '#777' }">
              <span v-if="r.actual_return !== null">{{ r.actual_return > 0 ? '+' : '' }}{{ r.actual_return }}%</span>
              <span v-else class="muted">待結算</span>
            </td>
            <td>
              <span v-if="r.correct === null" class="badge badge-gray">待定</span>
              <span v-else-if="r.correct" class="badge badge-green">✓ 正確</span>
              <span v-else class="badge badge-red">✗ 錯誤</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>

  <div v-else class="card">
    <p class="empty">選定日期範圍內無預測資料。請先執行 daily_run.py 產生預測快照。</p>
  </div>
</template>

<style scoped>
h1 { font-size: 22px; font-weight: 700; margin-bottom: 24px; }
h2 { font-size: 16px; font-weight: 600; margin-bottom: 12px; color: #444; }
.filter { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 20px; }
.filter label { font-size: 13px; color: #555; display: flex; flex-direction: column; gap: 4px; }
.filter input[type=date] { padding: 6px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; }
.filter button { padding: 7px 18px; background: #1a1a2e; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; align-self: flex-end; }
.filter button:hover { background: #2d2d4e; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 24px; }
.stat-box { background: #fff; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.stat-box .value { font-size: 28px; font-weight: 700; }
.stat-box .label { font-size: 12px; color: #888; margin-top: 4px; }
.card { background: #fff; border-radius: 10px; box-shadow: 0 1px 4px rgba(0,0,0,.08); padding: 24px; margin-bottom: 24px; }
.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.chart-wrap { position: relative; height: 280px; }
.chart-sm { height: 220px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { background: #f0f2f5; text-align: left; padding: 10px 12px; font-weight: 600; border-bottom: 2px solid #e0e3e8; }
th.sortable { cursor: pointer; user-select: none; }
th.sortable:hover { background: #e8eaed; }
td { padding: 9px 12px; border-bottom: 1px solid #f0f2f5; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #fafbfc; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.badge-green { background: #e6f7ee; color: #1a7a42; }
.badge-red   { background: #fdecea; color: #c0392b; }
.badge-gray  { background: #f0f2f5; color: #777; }
.mono { font-family: monospace; font-size: 12px; color: #777; }
.muted { color: #777; font-size: 13px; }
.empty { color: #999; font-size: 14px; text-align: center; padding: 40px 0; }
.error { color: #c0392b; }
</style>