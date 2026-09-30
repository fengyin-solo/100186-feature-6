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
      <label class="filter-item">
        <span>管段编号</span>
        <input v-model="filters.keyword" placeholder="按管段编号检索" />
      </label>
      <label class="filter-item">
        <span>管道类别</span>
        <input v-model="filters.category" placeholder="按管道类别过滤" />
      </label>
      <label class="filter-item">
        <span>起点井号</span>
        <input v-model="filters.startManhole" placeholder="按起点井号过滤" />
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
          <td :colspan="columns.length + 1" class="empty-state">
            {{ hasActiveFilters ? '没有符合当前条件的管段，可调整或重置条件后再查' : '暂无管段档案数据，可先登记管段' }}
          </td>
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
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type Filters = { keyword: string; category: string; startManhole: string }

const ENDPOINT = '/api/pipe'
const columns = ["管段编号", "管道类别", "起点井号", "终点井号", "管径规格", "管材类型", "埋设深度", "管段状态"]
const actions = ["办理移交", "标记观测", "封闭管段"]

const rows = ref<Row[]>([])
const total = ref(0)
const observedTotal = ref(0)
const errorMessage = ref('')
const filters = reactive<Filters>({ keyword: '', category: '', startManhole: '' })
// 只认最后一次查询：快速重复提交时，早回来的旧响应不能覆盖新条件下的结果
let requestSeq = 0

const hasActiveFilters = computed(() =>
  Boolean(filters.keyword.trim() || filters.category.trim() || filters.startManhole.trim()),
)

const stats = computed(() => [
  { label: "在册管段", value: total.value },
  { label: "重点观测管段", value: observedTotal.value },
  { label: "管网总长", value: '—' },
])

function buildQuery() {
  const params = new URLSearchParams()
  const keyword = filters.keyword.trim()
  const category = filters.category.trim()
  const startManhole = filters.startManhole.trim()
  // 条件并列传给后端，由后端逐个收窄，而不是互相覆盖
  if (keyword) params.set('keyword', keyword)
  if (category) params.set('category', category)
  if (startManhole) params.set('start_manhole', startManhole)
  return params.toString()
}

function resetFilters() {
  filters.keyword = ''
  filters.category = ''
  filters.startManhole = ''
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
  const seq = ++requestSeq
  const query = buildQuery()
  try {
    const listRes = await request(`${ENDPOINT}?${query}`)
    if (!listRes.ok) {
      throw new Error('管段列表读取失败')
    }
    const payload = await listRes.json()
    // 旧批次响应晚到时直接丢弃，避免覆盖最新条件下的数据
    if (seq !== requestSeq) return
    const nextRows: Row[] = payload.items ?? []
    rows.value = nextRows
    // 列表条数是唯一数据源；概览统计共用同一筛选口径（同一份后端过滤）
    total.value = payload.total ?? nextRows.length

    // 重点观测数走统计接口；失败不影响已拿到的列表，只让该卡片归零并提示
    try {
      const statsRes = await request(`${ENDPOINT}/stats?${query}`)
      if (statsRes.ok && seq === requestSeq) {
        const statsPayload = await statsRes.json()
        observedTotal.value = Number(statsPayload.observed ?? 0)
      }
    } catch {
      if (seq === requestSeq) {
        observedTotal.value = 0
        errorMessage.value = '管段统计概览暂不可用'
      }
    }
  } catch (error) {
    if (seq !== requestSeq) return
    // 取数失败时清空上一批旧数据，避免把旧结果误当成当前条件的命中结果；已填条件保留不动
    rows.value = []
    total.value = 0
    observedTotal.value = 0
    errorMessage.value = error instanceof Error ? error.message : '管段档案列表读取失败'
  }
}

onMounted(reload)
</script>
