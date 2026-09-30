<template>
  <section class="page" data-module="pipe">
    <header class="page-head">
      <div>
        <h2>管段档案管理</h2>
        <p class="page-desc">维护管段，围绕管段编号、管道类别、起点井号、终点井号做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记管段</button>
        <button class="btn" type="button" @click="exportRows">导出管段档案清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyText }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条管段档案记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type Summary = Record<string, number>

const ENDPOINT = '/api/pipe'
const columns = ["管段编号", "管道类别", "起点井号", "终点井号", "管径规格", "管材类型", "埋设深度", "管段状态"]
const actions = ["办理移交", "标记观测", "封闭管段"]
const statuses = ["待移交", "正常运行", "重点观测", "封闭施工"]

// 筛选项与后端查询参数一一对应；三项同时给出时由后端取交集，条件并列不覆盖。
const QUERY_KEYS: Record<string, string> = {
  管段编号: 'keyword',
  管道类别: 'category',
  起点井号: 'start_manhole',
}

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const stats = ref([
  { label: '在册管段', value: 0 },
  { label: '重点观测管段', value: 0 },
  { label: '管网总长', value: 0 },
])

const hasActiveFilters = computed(() =>
  filterFields.some((field) => filters.value[field]?.trim()),
)

const emptyText = computed(() =>
  hasActiveFilters.value
    ? '没有符合当前条件的管段，请调整筛选条件后重试'
    : '暂无管段档案数据，可先登记管段',
)

function buildQuery() {
  const params = new URLSearchParams()
  for (const field of filterFields) {
    const value = filters.value[field]?.trim()
    if (value) {
      params.set(QUERY_KEYS[field], value)
    }
  }
  return params.toString()
}

function applySummary(summary?: Summary) {
  // 统计卡片与列表同一次请求、同一批过滤后的管段，条数口径保持一致。
  stats.value[0].value = summary?.['在册管段'] ?? total.value
  stats.value[1].value = summary?.['重点观测管段'] ?? 0
}

function resetStats() {
  stats.value[0].value = 0
  stats.value[1].value = 0
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '管段登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('管段档案动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '管段档案操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}?${buildQuery()}`)
    if (!response.ok) {
      throw new Error('管段列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    applySummary(payload.summary as Summary | undefined)
  } catch (error) {
    // 取数失败时清空旧数据，避免界面继续展示上一批管段误导判断；已填条件保留在输入框里。
    rows.value = []
    total.value = 0
    resetStats()
    errorMessage.value = error instanceof Error ? error.message : '管段档案列表读取失败'
  }
}

onMounted(reload)
</script>
