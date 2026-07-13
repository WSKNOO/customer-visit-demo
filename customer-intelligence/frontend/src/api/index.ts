import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
})

export interface ReportInfo {
  filename: string
  company: string
  date: string
  size_kb: number
  lines: number
}

export interface ReportContent {
  filename: string
  company: string
  content: string
  lines: number
  chars: number
  sources: number
}

export async function fetchReports(): Promise<ReportInfo[]> {
  const { data } = await api.get<ReportInfo[]>('/reports')
  return data
}

export async function fetchReport(filename: string): Promise<ReportContent> {
  const { data } = await api.get<ReportContent>(`/reports/${encodeURIComponent(filename)}`)
  return data
}

export interface ResearchRequest {
  company_name: string
  visit_purpose?: string
  focus_areas?: string
}

export async function startResearch(params: ResearchRequest) {
  const { data } = await api.post('/research', params)
  return data
}

export interface ResearchStatus {
  task_id: string
  status: 'generating' | 'success' | 'search_error' | 'model_error' | 'generation_error' | 'service_error' | 'timeout'
  message: string
  report_filename: string | null
  result_mode: 'mock' | 'live' | null
  error_code: string | null
  request_id: string
}

export async function fetchResearchStatus(taskId: string): Promise<ResearchStatus> {
  const { data } = await api.get<ResearchStatus>(`/research/${encodeURIComponent(taskId)}`)
  return data
}

export interface TrainingStartResponse {
  request_id: string
  session_id: string
  customer_name: string
  opening_question: string
  training_url: string
  status: string
}

export async function startTrainingFromReport(reportFilename: string): Promise<TrainingStartResponse> {
  const { data } = await api.post<TrainingStartResponse>('/visit-brief/start-training', {
    report_filename: reportFilename,
  })
  return data
}

export interface DemoReportOption {
  id: string
  customer_name: string
  visit_goal: string
}

export async function fetchDemoReports(): Promise<DemoReportOption[]> {
  const { data } = await api.get<DemoReportOption[]>('/demo-reports')
  return data
}

export async function loadDemoReport(id: string): Promise<{ report_filename: string; request_id: string }> {
  const { data } = await api.post(`/demo-reports/${encodeURIComponent(id)}/load`)
  return data
}

export default api
