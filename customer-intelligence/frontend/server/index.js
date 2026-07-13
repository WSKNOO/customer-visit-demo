import express from 'express'
import cors from 'cors'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { spawn } from 'child_process'
import { randomUUID } from 'crypto'
import { validateResearchRequest } from './validation.js'
import { mapReportToVisitBrief } from './visitBrief.js'
import { startTrainingFromBrief, TrainingIntegrationError } from './trainingIntegration.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const app = express()
const PORT = Number.parseInt(process.env.INTELLIGENCE_API_PORT || '3001', 10)
const HOST = process.env.INTELLIGENCE_API_HOST || '127.0.0.1'
const allowedOrigins = (process.env.INTELLIGENCE_CORS_ORIGINS || 'http://localhost:8006')
  .split(',').map(v => v.trim()).filter(Boolean)

app.use(cors({ origin: allowedOrigins }))
app.use(express.json({ limit: `${Number.parseInt(process.env.INTELLIGENCE_MAX_BODY_KB || '128', 10)}kb` }))

const REPORTS_DIR = path.resolve(__dirname, '..', '..', 'tmp', 'reports')
const DEMO_DATA_DIR = path.resolve(__dirname, '..', '..', 'demo-data')
const intelligenceMockMode = String(process.env.INTELLIGENCE_MOCK_MODE || process.env.MOCK_MODE || '').toLowerCase() === 'true'
const researchJobs = new Map()
const researchTimeoutMs = Math.min(30 * 60 * 1000, Math.max(10 * 1000,
  Number.parseInt(process.env.INTELLIGENCE_RESEARCH_TIMEOUT_SECONDS || '600', 10) * 1000))

function cleanResearchJobs() {
  const cutoff = Date.now() - 24 * 60 * 60 * 1000
  for (const [id, job] of researchJobs) if (job.updated_at_ms < cutoff) researchJobs.delete(id)
  if (researchJobs.size > 100) {
    const oldest = [...researchJobs.entries()].sort((a, b) => a[1].updated_at_ms - b[1].updated_at_ms)
    for (const [id] of oldest.slice(0, researchJobs.size - 100)) researchJobs.delete(id)
  }
}

function publicJob(job) {
  return {
    task_id: job.task_id,
    status: job.status,
    message: job.message,
    report_filename: job.report_filename || null,
    result_mode: job.result_mode || null,
    error_code: job.error_code || null,
    request_id: job.request_id,
  }
}

app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', service: 'customer-intelligence-api', mock: intelligenceMockMode, training_integration: process.env.TRAINING_INTEGRATION_ENABLED === 'true' })
})

// Ensure reports directory exists
if (!fs.existsSync(REPORTS_DIR)) {
  fs.mkdirSync(REPORTS_DIR, { recursive: true })
}

// Parse company name from filename: 公司名_20260622_093011.md
function parseReportFilename(filename) {
  const match = filename.match(/^(.+)_(\d{8})_(\d{6})\.md$/)
  if (match) {
    const company = match[1]
    const dateStr = `${match[2].slice(0,4)}-${match[2].slice(4,6)}-${match[2].slice(6,8)}`
    return { company, date: dateStr }
  }
  return { company: filename.replace('.md', ''), date: '' }
}

function validReportFilename(filename) {
  return typeof filename === 'string' && filename.endsWith('.md')
    && !filename.includes('..') && !filename.includes('/') && !filename.includes('\\')
}

function loadVisitBrief(filename) {
  if (!validReportFilename(filename)) throw Object.assign(new Error('Invalid report identifier'), { status: 400 })
  const reportPath = path.join(REPORTS_DIR, filename)
  if (!fs.existsSync(reportPath)) throw Object.assign(new Error('Report not found'), { status: 404 })
  const content = fs.readFileSync(reportPath, 'utf-8')
  const sourcePath = path.join(REPORTS_DIR, `${filename.replace(/\.md$/i, '')}_sources.json`)
  let sources = []
  if (fs.existsSync(sourcePath)) {
    try { sources = JSON.parse(fs.readFileSync(sourcePath, 'utf-8')) } catch { sources = [] }
  }
  const { company } = parseReportFilename(filename)
  return mapReportToVisitBrief({ filename, company, content, sources })
}

function readDemoReports() {
  if (!fs.existsSync(DEMO_DATA_DIR)) return []
  return fs.readdirSync(DEMO_DATA_DIR).filter(name => /^[a-z0-9_-]+\.json$/i.test(name)).sort().map((name) => {
    try {
      const data = JSON.parse(fs.readFileSync(path.join(DEMO_DATA_DIR, name), 'utf-8'))
      return {
        id: name.replace(/\.json$/i, ''),
        customer_name: String(data.customer_name || '').slice(0, 120),
        visit_goal: String(data.visit_goal || '').slice(0, 200),
      }
    } catch { return null }
  }).filter(item => item?.customer_name)
}

// GET /api/reports - List all report files
app.get('/api/reports', (req, res) => {
  try {
    const files = fs.readdirSync(REPORTS_DIR)
      .filter(f => f.endsWith('.md') && !f.endsWith('_sources.md'))
      .sort()
      .reverse()

    const reports = files.map(filename => {
      const filePath = path.join(REPORTS_DIR, filename)
      const stat = fs.statSync(filePath)
      const content = fs.readFileSync(filePath, 'utf-8')
      const { company, date } = parseReportFilename(filename)
      const lines = content.split('\n').length

      return {
        filename,
        company,
        date,
        size_kb: Math.round(stat.size / 1024),
        lines,
      }
    })

    res.json(reports)
  } catch (err) {
    console.error('Error listing reports:', err)
    res.status(500).json({ error: err.message })
  }
})

// GET /api/reports/:filename - Get full report content
app.get('/api/reports/:filename', (req, res) => {
  try {
    const filename = req.params.filename
    // Sanitize: prevent directory traversal
    if (filename.includes('..') || filename.includes('/') || filename.includes('\\')) {
      return res.status(400).json({ error: 'Invalid filename' })
    }

    const filePath = path.join(REPORTS_DIR, filename)
    if (!fs.existsSync(filePath)) {
      return res.status(404).json({ error: 'Report not found' })
    }

    const content = fs.readFileSync(filePath, 'utf-8')
    const { company } = parseReportFilename(filename)
    const lines = content.split('\n').length
    const chars = content.length

    // Try to find associated sources JSON
    const sourceBase = filename.replace('.md', '')
    const sourcePath = path.join(REPORTS_DIR, `${sourceBase}_sources.json`)
    let sources = 0
    if (fs.existsSync(sourcePath)) {
      try {
        const sourceData = JSON.parse(fs.readFileSync(sourcePath, 'utf-8'))
        sources = Array.isArray(sourceData) ? sourceData.length : 0
      } catch {}
    }

    res.json({
      filename,
      company,
      content,
      lines,
      chars,
      sources,
    })
  } catch (err) {
    console.error('Error reading report:', err)
    res.status(500).json({ error: err.message })
  }
})

app.get('/api/reports/:filename/visit-brief', (req, res) => {
  try {
    return res.json(loadVisitBrief(req.params.filename))
  } catch (error) {
    return res.status(error.status || 500).json({ success: false, error: error.status ? error.message : 'Unable to build visit brief' })
  }
})

app.get('/api/demo-reports', (_req, res) => {
  return res.json(readDemoReports())
})

app.post('/api/demo-reports/:id/load', (req, res) => {
  const requestId = randomUUID()
  try {
    const id = req.params.id
    if (!/^[a-z0-9_-]{1,60}$/i.test(id)) return res.status(400).json({ success: false, error: '演示数据标识无效', request_id: requestId })
    const sourceFile = path.join(DEMO_DATA_DIR, `${id}.json`)
    if (!fs.existsSync(sourceFile)) return res.status(404).json({ success: false, error: '演示数据不存在', request_id: requestId })
    const data = JSON.parse(fs.readFileSync(sourceFile, 'utf-8'))
    const timestamp = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)
    const safeCustomer = String(data.customer_name || '').replace(/[^\u4e00-\u9fffA-Za-z0-9._-]+/g, '_').slice(0, 80)
    if (!safeCustomer || typeof data.report_markdown !== 'string' || data.report_markdown.length > 100000) {
      return res.status(422).json({ success: false, error: '演示数据校验失败', request_id: requestId })
    }
    const filename = `${safeCustomer}_${timestamp.slice(0, 8)}_${timestamp.slice(8, 14)}.md`
    fs.writeFileSync(path.join(REPORTS_DIR, filename), data.report_markdown, 'utf-8')
    const sources = Array.isArray(data.sources) ? data.sources.slice(0, 20) : []
    fs.writeFileSync(path.join(REPORTS_DIR, `${filename.replace(/\.md$/, '')}_sources.json`), `${JSON.stringify(sources, null, 2)}\n`, 'utf-8')
    console.log(`[demo-report] request_id=${requestId} status=loaded demo_id=${id}`)
    return res.json({ success: true, status: 'success', result_mode: 'cached', report_filename: filename, request_id: requestId })
  } catch {
    console.error(`[demo-report] request_id=${requestId} error_code=DEMO_LOAD_FAILED`)
    return res.status(500).json({ success: false, error: '加载缓存演示结果失败', error_code: 'DEMO_LOAD_FAILED', request_id: requestId })
  }
})

app.post('/api/visit-brief/start-training', async (req, res) => {
  const requestId = randomUUID()
  try {
    const filename = req.body?.report_filename
    const brief = loadVisitBrief(filename)
    const result = await startTrainingFromBrief(brief, { requestId })
    console.log(`[training-init] request_id=${requestId} status=ready`)
    return res.json(result)
  } catch (error) {
    const known = error instanceof TrainingIntegrationError || error.status
    const status = known ? (error.status || 500) : 500
    const code = error instanceof TrainingIntegrationError ? error.code : (error.status === 404 ? 'REPORT_NOT_FOUND' : 'TRAINING_INIT_FAILED')
    const message = error instanceof TrainingIntegrationError ? error.message
      : (error.status === 404 ? '客户情报报告不存在' : error.status === 400 ? '客户情报标识无效' : '创建陪练会话失败')
    console.error(`[training-init] request_id=${requestId} error_code=${code}`)
    return res.status(status).json({ success: false, error: message, error_code: code, request_id: requestId })
  }
})

// POST /api/research - Start a new research task
app.post('/api/research', (req, res) => {
  let payload
  try {
    payload = validateResearchRequest(req.body)
  } catch (err) {
    return res.status(400).json({ success: false, error: err.message })
  }

  cleanResearchJobs()
  const taskId = randomUUID()
  const requestId = randomUUID()
  const job = {
    task_id: taskId, request_id: requestId, status: 'generating',
    message: intelligenceMockMode ? '正在生成Mock客户情报' : '正在生成客户情报',
    updated_at_ms: Date.now(),
  }
  researchJobs.set(taskId, job)

  // Run the research command in background
  const projectRoot = path.resolve(__dirname, '..', '..')
  const scriptPath = path.join(projectRoot, 'research_cli.py')
  const pythonExecutable = process.env.PYTHON_EXECUTABLE || 'python3'
  const child = spawn(pythonExecutable, [scriptPath], {
    cwd: projectRoot,
    shell: false,
    stdio: ['pipe', 'pipe', 'pipe'],
  })

  let output = ''
  let errorOutput = ''
  let timedOut = false
  const timeout = setTimeout(() => {
    timedOut = true
    child.kill('SIGTERM')
  }, researchTimeoutMs)
  child.stdout.on('data', (data) => {
    if (output.length < 64 * 1024) output += data.toString()
  })
  child.stderr.on('data', (data) => {
    if (errorOutput.length < 16 * 1024) errorOutput += data.toString()
  })

  child.stdin.end(JSON.stringify(payload))

  child.on('error', () => {
    clearTimeout(timeout)
    Object.assign(job, { status: 'service_error', error_code: 'RESEARCH_PROCESS_UNAVAILABLE', message: '研究服务暂不可用，请稍后重试', updated_at_ms: Date.now() })
    console.error(`[research] request_id=${requestId} error_code=RESEARCH_PROCESS_UNAVAILABLE`)
  })

  child.on('close', (code) => {
    clearTimeout(timeout)
    if (timedOut) {
      Object.assign(job, { status: 'timeout', error_code: 'RESEARCH_TIMEOUT', message: '情报生成超时，可稍后重试或加载缓存演示结果', updated_at_ms: Date.now() })
      console.error(`[research] request_id=${requestId} error_code=RESEARCH_TIMEOUT`)
      return
    }
    let result = null
    try {
      const outputLines = output.trim().split(/\r?\n/).filter(Boolean)
      result = JSON.parse(outputLines[outputLines.length - 1] || '{}')
    } catch {}
    if (code === 0 && result?.success) {
      const reportFilename = path.basename(String(result.report_path || ''))
      Object.assign(job, {
        status: 'success', message: result.mock ? 'Mock客户情报生成成功' : '客户情报生成成功',
        report_filename: validReportFilename(reportFilename) ? reportFilename : null,
        result_mode: result.mock ? 'mock' : 'live', updated_at_ms: Date.now(),
      })
      console.log(`[research] request_id=${requestId} status=success mode=${job.result_mode}`)
      return
    }
    const reason = String(result?.error || errorOutput || '').toLowerCase()
    const isModel = /model|api key|chat|token|模型/.test(reason)
    const isSearch = /search|crawl|baidu|fetch|搜索|抓取/.test(reason)
    Object.assign(job, {
      status: isModel ? 'model_error' : isSearch ? 'search_error' : 'generation_error',
      error_code: isModel ? 'MODEL_SERVICE_ERROR' : isSearch ? 'SEARCH_SERVICE_ERROR' : 'RESEARCH_FAILED',
      message: isModel ? '模型服务异常，可稍后重试或加载缓存演示结果'
        : isSearch ? '搜索服务异常，可稍后重试或加载缓存演示结果'
          : '情报生成失败，可稍后重试或加载缓存演示结果',
      updated_at_ms: Date.now(),
    })
    console.error(`[research] request_id=${requestId} error_code=${job.error_code}`)
  })

  res.json({
    success: true,
    task_id: taskId,
    request_id: requestId,
    status: 'generating',
    message: `研究任务已启动: ${payload.company_name}`,
    note: '可通过任务状态查看生成进度；已有报告不会受本次任务失败影响。',
  })
})

app.get('/api/research/:taskId', (req, res) => {
  const taskId = req.params.taskId
  if (!/^[0-9a-f-]{36}$/.test(taskId)) return res.status(400).json({ success: false, error: '任务标识无效' })
  const job = researchJobs.get(taskId)
  if (!job) return res.status(404).json({ success: false, error: '研究任务不存在或已过期' })
  return res.json(publicJob(job))
})

app.listen(PORT, HOST, () => {
  console.log(`✅ AI4Search API Server running at http://localhost:${PORT}`)
  console.log(`📁 Reports directory: ${REPORTS_DIR}`)
})
