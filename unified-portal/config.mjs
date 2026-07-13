function publicUrl(value, fallback = '') {
  const text = String(value || fallback).trim().slice(0, 1000)
  if (!text) return ''
  if (text.startsWith('/') || /^https?:\/\//i.test(text)) return text
  return ''
}

export function getPortalConfig(env = process.env) {
  return {
    intelligence_url: publicUrl(env.PORTAL_INTELLIGENCE_URL, '/intelligence/'),
    training_url: publicUrl(env.PORTAL_TRAINING_URL, '/training/'),
    solution_url: publicUrl(env.PORTAL_SOLUTION_URL),
  }
}
