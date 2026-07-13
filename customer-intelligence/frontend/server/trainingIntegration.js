import http from 'http'
import https from 'https'
import { randomUUID } from 'crypto'
import { normalizeVisitBrief } from './visitBrief.js'

export class TrainingIntegrationError extends Error {
  constructor(code, message, status = 503) {
    super(message)
    this.name = 'TrainingIntegrationError'
    this.code = code
    this.status = status
  }
}

function positiveInt(value, fallback, minimum = 100, maximum = 120000) {
  const parsed = Number.parseInt(value || '', 10)
  return Number.isFinite(parsed) ? Math.min(maximum, Math.max(minimum, parsed)) : fallback
}

export function getTrainingIntegrationConfig(env = process.env) {
  return {
    enabled: String(env.TRAINING_INTEGRATION_ENABLED || 'false').toLowerCase() === 'true',
    serviceBaseUrl: String(env.TRAINING_SERVICE_BASE_URL || '').replace(/\/+$/, ''),
    publicUrl: String(env.TRAINING_PUBLIC_URL || '/training/'),
    connectTimeoutMs: positiveInt(env.TRAINING_CONNECT_TIMEOUT_MS, 2000),
    readTimeoutMs: positiveInt(env.TRAINING_READ_TIMEOUT_MS, 10000),
  }
}

function trainingPageUrl(publicUrl, sessionId) {
  if (!publicUrl.startsWith('/') && !/^https?:\/\//i.test(publicUrl)) {
    throw new TrainingIntegrationError('TRAINING_PUBLIC_URL_INVALID', '陪练页面配置无效', 503)
  }
  const separator = publicUrl.includes('?') ? '&' : '?'
  return `${publicUrl}${separator}session_id=${encodeURIComponent(sessionId)}`
}

export function postJson(urlValue, payload, { connectTimeoutMs, readTimeoutMs }) {
  return new Promise((resolve, reject) => {
    let target
    try { target = new URL(urlValue) } catch {
      reject(new TrainingIntegrationError('TRAINING_SERVICE_CONFIG_INVALID', '陪练服务配置无效', 503))
      return
    }
    if (!['http:', 'https:'].includes(target.protocol)) {
      reject(new TrainingIntegrationError('TRAINING_SERVICE_CONFIG_INVALID', '陪练服务配置无效', 503))
      return
    }
    const body = JSON.stringify(payload)
    const transport = target.protocol === 'https:' ? https : http
    let settled = false
    const finish = (fn, value) => {
      if (settled) return
      settled = true
      clearTimeout(connectTimer)
      fn(value)
    }
    const request = transport.request(target, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
      },
    }, (response) => {
      clearTimeout(connectTimer)
      let text = ''
      response.setEncoding('utf8')
      response.on('data', (chunk) => {
        text += chunk
        if (text.length > 64 * 1024) request.destroy(new Error('response too large'))
      })
      response.on('end', () => {
        let data
        try { data = text ? JSON.parse(text) : {} } catch {
          finish(reject, new TrainingIntegrationError('TRAINING_BAD_RESPONSE', '陪练服务返回异常', 502))
          return
        }
        if ((response.statusCode || 500) >= 400) {
          const status = response.statusCode === 400 ? 422 : 503
          const code = response.statusCode === 400 ? 'VISIT_BRIEF_REJECTED' : 'TRAINING_SERVICE_UNAVAILABLE'
          finish(reject, new TrainingIntegrationError(code, status === 422 ? '客户情报数据校验失败' : '陪练服务暂不可用', status))
          return
        }
        finish(resolve, data)
      })
    })
    const connectTimer = setTimeout(() => {
      request.destroy(new TrainingIntegrationError('TRAINING_CONNECT_TIMEOUT', '连接陪练服务超时', 504))
    }, connectTimeoutMs)
    request.setTimeout(readTimeoutMs, () => {
      request.destroy(new TrainingIntegrationError('TRAINING_READ_TIMEOUT', '陪练服务响应超时', 504))
    })
    request.on('socket', (socket) => {
      const event = target.protocol === 'https:' ? 'secureConnect' : 'connect'
      if (socket.connecting) socket.once(event, () => clearTimeout(connectTimer))
      else clearTimeout(connectTimer)
    })
    request.on('error', (error) => {
      if (error instanceof TrainingIntegrationError) finish(reject, error)
      else finish(reject, new TrainingIntegrationError('TRAINING_SERVICE_UNAVAILABLE', '陪练服务暂不可用', 503))
    })
    request.end(body)
  })
}

export async function startTrainingFromBrief(brief, { env = process.env, requestId = randomUUID(), requestFn = postJson } = {}) {
  const config = getTrainingIntegrationConfig(env)
  if (!config.enabled) throw new TrainingIntegrationError('TRAINING_INTEGRATION_DISABLED', '陪练集成功能暂未启用', 503)
  if (!config.serviceBaseUrl) throw new TrainingIntegrationError('TRAINING_SERVICE_NOT_CONFIGURED', '陪练服务暂未配置', 503)
  let normalized
  try { normalized = normalizeVisitBrief(brief) } catch {
    throw new TrainingIntegrationError('VISIT_BRIEF_INVALID', '客户情报数据校验失败', 422)
  }
  const result = await requestFn(`${config.serviceBaseUrl}/api/training/session/init`, normalized, config)
  if (!result || !/^[0-9a-f]{32}$/.test(result.session_id || '')) {
    throw new TrainingIntegrationError('TRAINING_BAD_RESPONSE', '陪练服务返回异常', 502)
  }
  return {
    request_id: requestId,
    session_id: result.session_id,
    customer_name: String(result.customer_name || normalized.customer.name).slice(0, 120),
    opening_question: String(result.opening_question || '').slice(0, 500),
    training_url: trainingPageUrl(config.publicUrl, result.session_id),
    status: result.status || 'ready',
  }
}
