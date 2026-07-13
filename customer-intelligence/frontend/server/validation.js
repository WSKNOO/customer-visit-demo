const COMPANY_PATTERN = /^[\p{Script=Han}A-Za-z0-9（）()·&＆.\-\s]{1,120}$/u

function singleLine(value, field, maxLength) {
  if (value == null) return ''
  if (typeof value !== 'string') throw new TypeError(`${field} must be a string`)
  const result = value.trim()
  if (/[\r\n]/.test(result) || result.length > maxLength) {
    throw new TypeError(`${field} is invalid or too long`)
  }
  return result
}

export function validateResearchRequest(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    throw new TypeError('request body must be an object')
  }
  const company_name = singleLine(body.company_name, 'company_name', 120)
  if (!company_name || company_name.includes('&&') || !COMPANY_PATTERN.test(company_name)) {
    throw new TypeError('company_name contains unsupported characters')
  }
  return {
    company_name,
    visit_purpose: singleLine(body.visit_purpose, 'visit_purpose', 500),
    focus_areas: singleLine(body.focus_areas, 'focus_areas', 200),
  }
}
