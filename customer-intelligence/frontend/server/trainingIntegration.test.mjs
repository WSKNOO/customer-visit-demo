import assert from 'node:assert/strict'
import http from 'node:http'
import { once } from 'node:events'
import { startTrainingFromBrief } from './trainingIntegration.js'

const brief = {
  schema_version: '1.0',
  customer: { name: '演示客户', profile_summary: '甲'.repeat(5000) },
  visit: { goal: '验证集成', suggested_questions: Array(30).fill('问题'.repeat(200)) },
  signals: { potential_needs: Array(30).fill('需求') },
}

async function withServer(handler, test) {
  const server = http.createServer(handler)
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  try { await test(`http://127.0.0.1:${server.address().port}`) } finally { server.close() }
}

await withServer((req, res) => {
  let raw = ''
  req.on('data', chunk => { raw += chunk })
  req.on('end', () => {
    const data = JSON.parse(raw)
    assert.equal(data.customer.profile_summary.length, 2000)
    assert.equal(data.visit.suggested_questions.length, 15)
    res.writeHead(201, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ session_id: 'a'.repeat(32), customer_name: data.customer.name, opening_question: '您好', status: 'ready' }))
  })
}, async (baseUrl) => {
  const result = await startTrainingFromBrief(brief, { env: {
    TRAINING_INTEGRATION_ENABLED: 'true', TRAINING_SERVICE_BASE_URL: baseUrl,
    TRAINING_PUBLIC_URL: '/training/', TRAINING_CONNECT_TIMEOUT_MS: '500', TRAINING_READ_TIMEOUT_MS: '500',
  } })
  assert.equal(result.session_id, 'a'.repeat(32))
  assert.equal(result.training_url, `/training/?session_id=${'a'.repeat(32)}`)
})

await assert.rejects(() => startTrainingFromBrief({ customer: {}, visit: {} }, { env: {
  TRAINING_INTEGRATION_ENABLED: 'true', TRAINING_SERVICE_BASE_URL: 'http://127.0.0.1:1',
} }), error => error.code === 'VISIT_BRIEF_INVALID')

await assert.rejects(() => startTrainingFromBrief(brief, { env: {
  TRAINING_INTEGRATION_ENABLED: 'true', TRAINING_SERVICE_BASE_URL: 'http://127.0.0.1:1',
  TRAINING_CONNECT_TIMEOUT_MS: '100', TRAINING_READ_TIMEOUT_MS: '100',
} }), error => error.code === 'TRAINING_SERVICE_UNAVAILABLE' || error.code === 'TRAINING_CONNECT_TIMEOUT')

await withServer((_req, _res) => {}, async (baseUrl) => {
  await assert.rejects(() => startTrainingFromBrief(brief, { env: {
    TRAINING_INTEGRATION_ENABLED: 'true', TRAINING_SERVICE_BASE_URL: baseUrl,
    TRAINING_CONNECT_TIMEOUT_MS: '100', TRAINING_READ_TIMEOUT_MS: '100',
  } }), error => error.code === 'TRAINING_READ_TIMEOUT')
})

console.log('training integration tests passed')
