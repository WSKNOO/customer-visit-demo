import assert from 'node:assert/strict'
import { once } from 'node:events'
import { createPortalServer } from './server.mjs'
import { getPortalConfig } from './config.mjs'

assert.deepEqual(getPortalConfig({
  PORTAL_INTELLIGENCE_URL: '/intelligence/', PORTAL_TRAINING_URL: '/training/',
  PORTAL_SOLUTION_URL: 'javascript:alert(1)',
}), { intelligence_url: '/intelligence/', training_url: '/training/', solution_url: '' })

const server = createPortalServer({
  PORTAL_INTELLIGENCE_URL: '/intelligence/', PORTAL_TRAINING_URL: '/training/', PORTAL_SOLUTION_URL: 'https://solution.example.com/',
})
server.listen(0, '127.0.0.1')
await once(server, 'listening')
try {
  const base = `http://127.0.0.1:${server.address().port}`
  const health = await fetch(`${base}/health`).then(r => r.json())
  const config = await fetch(`${base}/config`).then(r => r.json())
  const page = await fetch(base).then(r => r.text())
  assert.equal(health.status, 'ok')
  assert.equal(config.solution_url, 'https://solution.example.com/')
  assert.match(page, /政企客户智能拜访助手/)
} finally { server.close() }

console.log('unified portal tests passed')
