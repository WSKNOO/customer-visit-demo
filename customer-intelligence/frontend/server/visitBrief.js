function truncate(value, maxLength) {
  return String(value || '').replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, maxLength)
}

function section(markdown, current, next) {
  const start = markdown.search(new RegExp(`^##\\s+${current}`, 'm'))
  if (start < 0) return ''
  const afterHeading = markdown.indexOf('\n', start)
  const tail = markdown.slice(afterHeading + 1)
  if (!next) return tail
  const end = tail.search(new RegExp(`^##\\s+${next}`, 'm'))
  return end < 0 ? tail : tail.slice(0, end)
}

function listItems(value, maxItems, maxLength) {
  const items = []
  for (const line of value.split(/\r?\n/)) {
    const match = line.trim().match(/^(?:[-*+]\s+|\d+[.)、]\s*)(.+)$/)
    if (!match) continue
    const text = truncate(match[1].replace(/\[\d+\]/g, ''), maxLength)
    if (text && !items.includes(text)) items.push(text)
    if (items.length >= maxItems) break
  }
  return items
}

function normalizeSummaryItems(value, field, maxItems = 10) {
  if (value == null) return []
  if (!Array.isArray(value)) throw new TypeError(`${field} must be an array`)
  return value.slice(0, maxItems).map((item) => {
    if (typeof item === 'string') return truncate(item, 500)
    if (!item || typeof item !== 'object') throw new TypeError(`${field} items must be strings or objects`)
    return truncate(item.summary || item.title || item.name || '', 500)
  }).filter(Boolean)
}

function normalizeStringArray(value, field, maxItems, maxLength) {
  if (value == null) return []
  if (!Array.isArray(value)) throw new TypeError(`${field} must be an array`)
  return value.slice(0, maxItems).map(item => {
    if (typeof item !== 'string') throw new TypeError(`${field} items must be strings`)
    return truncate(item, maxLength)
  }).filter(Boolean)
}

export function normalizeVisitBrief(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new TypeError('visit_brief must be an object')
  if (value.schema_version && value.schema_version !== '1.0') throw new TypeError('unsupported schema_version')
  if (!value.customer || typeof value.customer !== 'object' || !value.visit || typeof value.visit !== 'object') {
    throw new TypeError('customer and visit must be objects')
  }
  const customerName = truncate(value.customer.name, 120)
  const visitGoal = truncate(value.visit.goal, 500)
  if (!customerName) throw new TypeError('customer.name is required')
  if (!visitGoal) throw new TypeError('visit.goal is required')
  const difficulty = ['简单', '中等', '困难'].includes(value.training_options?.difficulty)
    ? value.training_options.difficulty : '中等'
  const phase = ['contact', 'discovery', 'present', 'objection', 'close'].includes(value.training_options?.phase)
    ? value.training_options.phase : 'discovery'
  const requestedRounds = Number.isInteger(value.training_options?.round_limit)
    ? value.training_options.round_limit : 6

  const normalized = {
    schema_version: '1.0',
    brief_id: truncate(value.brief_id, 100),
    customer: {
      name: customerName,
      industry: truncate(value.customer.industry, 120),
      profile_summary: truncate(value.customer.profile_summary, 2000),
    },
    visit: {
      goal: visitGoal,
      target_role: truncate(value.visit.target_role || '业务或技术决策相关角色', 100),
      focus_areas: normalizeStringArray(value.visit.focus_areas, 'visit.focus_areas', 10, 80),
      suggested_questions: normalizeStringArray(value.visit.suggested_questions, 'visit.suggested_questions', 15, 300),
    },
    signals: {
      recent_events: normalizeSummaryItems(value.signals?.recent_events, 'signals.recent_events'),
      digital_clues: normalizeSummaryItems(value.signals?.digital_clues, 'signals.digital_clues'),
      potential_needs: normalizeSummaryItems(value.signals?.potential_needs, 'signals.potential_needs'),
      recommended_solutions: normalizeSummaryItems(value.signals?.recommended_solutions, 'signals.recommended_solutions'),
    },
    sources: [],
    training_options: {
      difficulty,
      phase,
      round_limit: Math.min(10, Math.max(3, requestedRounds)),
      voice_enabled: false,
    },
  }
  if (value.sources != null && !Array.isArray(value.sources)) throw new TypeError('sources must be an array')
  normalized.sources = (value.sources || []).slice(0, 20).map((item) => {
    if (!item || typeof item !== 'object') throw new TypeError('sources items must be objects')
    const url = truncate(item.url, 1000)
    if (!/^https?:\/\//i.test(url)) return null
    return { title: truncate(item.title, 300), url }
  }).filter(Boolean)
  if (JSON.stringify(normalized).length > 20000) throw new TypeError('visit_brief is too large')
  return normalized
}

export function mapReportToVisitBrief({ filename, company, content, sources = [] }) {
  const profile = section(content, '一、', '二、')
  const recent = section(content, '二、', '三、')
  const digital = section(content, '三、', '四、')
  const needs = section(content, '四、', '五、')
  const solutions = section(content, '五、', '六、')
  const questions = section(content, '七、', '八、')
  const goalMatch = content.match(/\*\*拜访(?:目的|目标)\*\*\s*[:：]\s*(.+)/)

  return normalizeVisitBrief({
    schema_version: '1.0',
    brief_id: truncate(filename.replace(/\.md$/i, ''), 100),
    customer: {
      name: truncate(company, 120),
      industry: '',
      profile_summary: truncate(profile.replace(/^#+.*$/gm, ''), 2000),
    },
    visit: {
      goal: truncate(goalMatch?.[1] || '了解客户需求并完成拜访准备', 500),
      target_role: '业务或技术决策相关角色',
      focus_areas: [],
      suggested_questions: listItems(questions, 15, 300),
    },
    signals: {
      recent_events: listItems(recent, 10, 500),
      digital_clues: listItems(digital, 10, 500),
      potential_needs: listItems(needs, 10, 500),
      recommended_solutions: listItems(solutions, 10, 500),
    },
    sources: sources.slice(0, 20).filter(item => item?.url).map(item => ({
      title: truncate(item.title, 300),
      url: truncate(item.url, 1000),
    })),
    training_options: {
      difficulty: '中等', phase: 'discovery', round_limit: 6, voice_enabled: false,
    },
  })
}
