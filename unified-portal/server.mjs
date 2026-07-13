import http from 'http'
import { readFile } from 'fs/promises'
import { fileURLToPath, pathToFileURL } from 'url'
import path from 'path'
import { getPortalConfig } from './config.mjs'

const directory = path.dirname(fileURLToPath(import.meta.url))

function json(res, status, data) {
  const body = JSON.stringify(data)
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Content-Length': Buffer.byteLength(body), 'Cache-Control': 'no-store' })
  res.end(body)
}

export function createPortalServer(env = process.env) {
  return http.createServer(async (req, res) => {
    const url = new URL(req.url || '/', 'http://portal.local')
    if (req.method !== 'GET') return json(res, 405, { error: 'Method not allowed' })
    if (url.pathname === '/health') return json(res, 200, { status: 'ok', service: 'unified-portal' })
    if (url.pathname === '/config') return json(res, 200, getPortalConfig(env))
    if (url.pathname !== '/' && url.pathname !== '/index.html') return json(res, 404, { error: 'Not found' })
    try {
      const body = await readFile(path.join(directory, 'index.html'))
      res.writeHead(200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Content-Length': body.length,
        'Cache-Control': 'no-store',
        'Content-Security-Policy': "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
      })
      res.end(body)
    } catch {
      json(res, 500, { error: 'Portal unavailable' })
    }
  })
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const host = process.env.PORTAL_HOST || '127.0.0.1'
  const port = Number.parseInt(process.env.PORTAL_PORT || '8080', 10)
  createPortalServer().listen(port, host, () => console.log(`Unified portal listening on http://${host}:${port}`))
}
