import assert from 'node:assert/strict'
import { validateResearchRequest } from './validation.js'

assert.equal(validateResearchRequest({ company_name: '示例科技有限公司' }).company_name, '示例科技有限公司')

for (const company_name of [
  '示例;id', '示例&&id', '示例|id', '示例$(id)', '示例`id`',
  '示例\nid', '../../etc/passwd', '..\\..\\Windows\\win.ini',
]) {
  assert.throws(() => validateResearchRequest({ company_name }), /unsupported|invalid/)
}

console.log('research request validation tests passed')
