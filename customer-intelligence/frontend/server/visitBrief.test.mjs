import assert from 'node:assert/strict'
import { mapReportToVisitBrief } from './visitBrief.js'

const brief = mapReportToVisitBrief({
  filename: '示例客户_20260713_120000.md',
  company: '示例客户',
  content: '# 简报\n\n**拜访目的**: 了解数字化需求\n\n## 一、客户基本画像\n示例概况\n## 二、近期重点动态\n- 发布新规划\n## 三、数字化/智能化线索\n- 建设数据平台\n## 四、潜在业务痛点\n- 数据协同效率待提升\n## 五、可能匹配的产品能力\n- 数据治理服务\n## 六、拜访切入点建议\n- 从数据质量切入\n## 七、建议提问清单\n1. 当前数据协同的主要障碍是什么？\n## 八、后续商机判断\n- 待确认',
  sources: [{ title: '官网', url: 'https://example.com/news' }],
})

assert.equal(brief.schema_version, '1.0')
assert.equal(brief.customer.name, '示例客户')
assert.equal(brief.visit.goal, '了解数字化需求')
assert.equal(brief.visit.suggested_questions.length, 1)
assert.equal(brief.signals.digital_clues.length, 1)
assert.equal(brief.sources.length, 1)
assert.ok(JSON.stringify(brief).length < 20_000)
console.log('visit brief mapping tests passed')
