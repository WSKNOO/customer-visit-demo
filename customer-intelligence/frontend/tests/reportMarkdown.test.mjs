import { build } from 'esbuild'

const result = await build({
  entryPoints: ['src/utils/reportMarkdown.test.ts'],
  bundle: true,
  platform: 'node',
  format: 'esm',
  write: false,
})

const source = result.outputFiles[0].text
await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)
