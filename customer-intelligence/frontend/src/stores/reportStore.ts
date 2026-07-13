import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchReports, fetchReport, startResearch, type ReportInfo, type ReportContent } from '@/api'

export const useReportStore = defineStore('report', () => {
  const reports = ref<ReportInfo[]>([])
  const currentReport = ref<ReportContent | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadReports() {
    loading.value = true
    error.value = null
    try {
      reports.value = await fetchReports()
    } catch (e: any) {
      error.value = e.message || '加载报告列表失败'
    } finally {
      loading.value = false
    }
  }

  async function loadReport(filename: string) {
    loading.value = true
    error.value = null
    currentReport.value = null
    try {
      currentReport.value = await fetchReport(filename)
    } catch (e: any) {
      error.value = e.message || '加载报告失败'
    } finally {
      loading.value = false
    }
  }

  async function research(params: { company_name: string; visit_purpose?: string; focus_areas?: string }) {
    loading.value = true
    error.value = null
    try {
      const result = await startResearch(params)
      return result
    } catch (e: any) {
      error.value = e.message || '启动研究失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  return { reports, currentReport, loading, error, loadReports, loadReport, research }
})