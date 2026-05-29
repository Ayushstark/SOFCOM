export type StageStatus = 'active' | 'success' | 'error'

export const pipelineStages = [
  { name: 'Intent', status: 'success', ms: 82, progress: 100 },
  { name: 'Design', status: 'success', ms: 141, progress: 100 },
  { name: 'Schema', status: 'active', ms: 64, progress: 72 },
  { name: 'Repair', status: 'active', ms: 0, progress: 36 },
  { name: 'Runtime', status: 'active', ms: 0, progress: 18 },
  { name: 'Deploy', status: 'active', ms: 0, progress: 8 },
] as const

export const activityData = [
  { name: '12:00', tokens: 1800, latency: 320 },
  { name: '12:05', tokens: 2600, latency: 290 },
  { name: '12:10', tokens: 3200, latency: 270 },
  { name: '12:15', tokens: 4100, latency: 250 },
  { name: '12:20', tokens: 3600, latency: 260 },
  { name: '12:25', tokens: 4800, latency: 240 },
]

export const templates = [
  'Build a multi-tenant analytics SaaS with auth, billing, and observability.',
  'Generate a CRM with role-based permissions and AI auto-summary workflows.',
  'Create an e-commerce app with inventory sync, returns flow, and A/B tests.',
]

export const logs = [
  '[12:26:00.104] INFO Booting compiler runtime',
  '[12:26:00.481] INFO Parsing prompt directives',
  '[12:26:01.006] OK Intent inference complete in 82ms',
  '[12:26:02.114] OK Design synthesis complete in 141ms',
  '[12:26:02.844] WARN Schema mismatch in component props',
  '[12:26:03.287] INFO Repair agent patching contract',
  '[12:26:04.103] OK Hot runtime validation passed',
]
