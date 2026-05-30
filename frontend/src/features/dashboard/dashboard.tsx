import { type PropsWithChildren, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import Editor from '@monaco-editor/react'
import { Activity, Bot, ChevronDown, ChevronsLeftRight, Command, Copy, Cpu, Download, Gauge, LayoutDashboard, Menu, Play, Search, Sparkles, Terminal, Upload } from 'lucide-react'
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { toast } from 'sonner'
import { templates } from './data'
import { cn } from '../../lib/utils'
import { useUiStore } from '../../store/ui-store'

type CompileResponse = {
  config: {
    app_id: string
    app_name: string
    metrics?: { latency_ms: number; repair_passes: number; issue_count: number }
    runtime?: { executable: boolean; generated_files: string[] }
    validation_report: Array<{ severity: 'error' | 'warning'; message: string }>
  }
  log: Array<{ stage: string; level: 'INFO' | 'WARN' | 'ERROR'; message: string; details?: Record<string, unknown> }>
}
type CompileHistoryRow = {
  prompt: string
  success: boolean
  retries: number
  latencyMs: number
  failureType: 'validation_error' | 'runtime_failure' | null
}

type EvaluationRow = {
  kind: 'product' | 'edge'
  prompt: string
  success: boolean
  repair_passes: number
  latency_ms: number
  failure_type: 'validation_error' | 'runtime_failure' | null
}

type EvaluationResponse = {
  total: number
  success_count: number
  success_rate: number
  average_latency_ms: number
  retries_per_request: number
  failure_types: { validation_error: number; runtime_failure: number }
  rows: EvaluationRow[]
}

const STAGES = ['intent', 'design', 'schema', 'repair', 'runtime', 'metrics'] as const
const RAW_API_BASE_URL = import.meta.env.VITE_API_BASE_URL
const API_BASE_URL = RAW_API_BASE_URL
  || (typeof window !== 'undefined' && window.location.hostname.includes('vercel.app')
    ? '/backend'
    : 'http://127.0.0.1:8000')
const TESTING_PROMPTS: Array<{ kind: 'product' | 'edge'; prompt: string }> = [
  { kind: 'product', prompt: 'Build a CRM with login, contacts, dashboard, role-based access, premium plan with payments. Admins can see analytics.' },
  { kind: 'product', prompt: 'Create an ecommerce store with products, orders, customers, checkout payments, and admin analytics.' },
  { kind: 'product', prompt: 'Build an LMS for courses, lessons, students, enrollments, login, and progress dashboard.' },
  { kind: 'product', prompt: 'Make a clinic booking app with appointments, staff, services, reminders, and admin reports.' },
  { kind: 'product', prompt: 'Create a project management app with projects, tasks, teams, comments, and role permissions.' },
  { kind: 'product', prompt: 'Build a subscription SaaS dashboard with billing, user login, premium features, and admin metrics.' },
  { kind: 'product', prompt: 'Create a contact manager with companies, deals, tasks, search, and owner-only access.' },
  { kind: 'product', prompt: 'Build a store operations console with inventory, orders, customers, payments, and reports.' },
  { kind: 'product', prompt: 'Make a student course portal with login, courses, lessons, and dashboard analytics.' },
  { kind: 'product', prompt: 'Build an appointment scheduling product with customers, services, calendar dashboard, and payments.' },
  { kind: 'edge', prompt: 'Build an app.' },
  { kind: 'edge', prompt: 'Make something for my business with users and admin maybe payments or not?' },
  { kind: 'edge', prompt: 'Create a CRM but no database and also save contacts forever.' },
  { kind: 'edge', prompt: 'Build a dashboard with analytics but users should not login and admins should have private reports.' },
  { kind: 'edge', prompt: 'I need a premium free paid app for everyone and only subscribers.' },
  { kind: 'edge', prompt: 'Make a project tool with tasks, but no users, yet every task needs an owner.' },
  { kind: 'edge', prompt: 'Create a booking system for clinics or schools?' },
  { kind: 'edge', prompt: 'Build a store without products but include checkout.' },
  { kind: 'edge', prompt: 'Need login, roles, dashboards, payments, analytics, contacts, orders, appointments, courses, everything.' },
  { kind: 'edge', prompt: 'Make an app with admin analytics and role access.' },
]

export function Dashboard() {
  const { sidebarCollapsed, toggleSidebar, commandOpen, setCommandOpen, activeTab, setActiveTab } = useUiStore()
  const [prompt, setPrompt] = useState('')
  const [userPromptHistory, setUserPromptHistory] = useState<string[]>([])
  const [view, setView] = useState<'json' | 'yaml' | 'diff'>('json')
  const [compileHistory, setCompileHistory] = useState<CompileHistoryRow[]>([])
  const [previousConfig, setPreviousConfig] = useState<CompileResponse['config'] | null>(null)
  const tokenCount = Math.round(prompt.length * 1.4)
  const compile = useMutation({
    mutationFn: async (inputPrompt: string) => {
      const res = await fetch(`${API_BASE_URL}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: inputPrompt }),
      })
      if (!res.ok) throw new Error(`Compile failed (${res.status}) via ${API_BASE_URL}/generate`)
      return (await res.json()) as CompileResponse
    },
    onSuccess: () => toast.success('Compilation complete'),
    onError: (error) => toast.error(error instanceof Error ? error.message : `Compiler request failed via ${API_BASE_URL}`),
  })
  const evaluation = useQuery({
    queryKey: ['evaluation'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE_URL}/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (!res.ok) throw new Error(`Evaluation failed (${res.status}) via ${API_BASE_URL}/evaluate`)
      return (await res.json()) as EvaluationResponse
    },
    staleTime: 60_000,
  })

  const stageState = useMemo(() => {
    const done = new Set((compile.data?.log ?? []).map((x) => x.stage))
    return STAGES.map((name) => ({
      name,
      status: (compile.isPending ? (done.has(name) ? 'success' : 'active') : done.has(name) ? 'success' : 'active') as 'active' | 'success' | 'error',
    }))
  }, [compile.data?.log, compile.isPending])

  const logText = useMemo(() => {
    const entries = compile.data?.log ?? []
    return entries
      .flatMap((entry) => {
        const lines = [`[${entry.level}] ${entry.stage.toUpperCase()}  ${entry.message}`]
        const details = entry.details
        if (!details) return lines

        const errors = details.errors as Array<{ code?: string; message?: string; layer?: string }> | undefined
        const warnings = details.warnings as Array<{ code?: string; message?: string; layer?: string }> | undefined
        const fixed = details.fixed as string[] | undefined
        const remaining = details.remaining as string[] | undefined
        const unresolved = details.unresolved as Array<{ code?: string; message?: string }> | undefined

        if (errors?.length) {
          lines.push(...errors.map((e) => `  -> ISSUE [${e.code ?? 'N/A'}] (${e.layer ?? 'unknown'}): ${e.message ?? 'unknown error'}`))
        }
        if (warnings?.length) {
          lines.push(...warnings.map((w) => `  -> WARN  [${w.code ?? 'N/A'}] (${w.layer ?? 'unknown'}): ${w.message ?? 'unknown warning'}`))
        }
        if (fixed?.length) lines.push(`  -> REPAIRED: ${fixed.join(', ')}`)
        if (remaining?.length) lines.push(`  -> REMAINING: ${remaining.join(', ')}`)
        if (unresolved?.length) {
          lines.push(...unresolved.map((u) => `  -> UNRESOLVED [${u.code ?? 'N/A'}]: ${u.message ?? 'unknown issue'}`))
        }
        return lines
      })
      .join('\n')
  }, [compile.data?.log])

  const runCompile = (inputPrompt?: string) => {
    const finalPrompt = (inputPrompt ?? prompt).trim()
    if (finalPrompt.length < 3) {
      toast.error('Prompt too short')
      return
    }
    compile.mutate(finalPrompt, {
      onSuccess: (data) => {
        setUserPromptHistory((rows) => [finalPrompt, ...rows.filter((p) => p !== finalPrompt)].slice(0, 20))
        const prev = compile.data?.config
        if (prev) setPreviousConfig(prev)
        const errors = data.config.validation_report.filter((x) => x.severity === 'error')
        setCompileHistory((rows) => [
          {
            prompt: finalPrompt,
            success: errors.length === 0 && Boolean(data.config.runtime?.executable),
            retries: data.config.metrics?.repair_passes ?? 0,
            latencyMs: data.config.metrics?.latency_ms ?? 0,
            failureType: errors.length
              ? 'validation_error'
              : data.config.runtime?.executable
                ? null
                : 'runtime_failure',
          },
          ...rows,
        ])
      },
    })
  }

  const handleCommandAction = (action: 'run_compile' | 'open_logs' | 'open_compiler' | 'open_runtime' | 'toggle_sidebar') => {
    if (action === 'run_compile') runCompile()
    if (action === 'open_logs') setActiveTab('logs')
    if (action === 'open_compiler') setActiveTab('compiler')
    if (action === 'open_runtime') setActiveTab('runtime')
    if (action === 'toggle_sidebar') toggleSidebar()
    setCommandOpen(false)
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-bg text-text-primary">
      <div className="pointer-events-none absolute inset-0 bg-grid-pattern bg-grid opacity-40" />
      <div className="pointer-events-none absolute inset-0 bg-gradient-glow" />
      <Topbar onCommand={() => setCommandOpen(true)} />
      <div className="relative mx-auto flex max-w-[1680px] gap-4 px-4 pb-5 pt-24 lg:px-6">
        <Sidebar collapsed={sidebarCollapsed} onToggle={toggleSidebar} activeTab={activeTab} setActiveTab={setActiveTab} />
        <main className="grid min-h-[calc(100vh-7rem)] flex-1 grid-cols-1 gap-4">
          <EvaluationBar
            data={evaluation.data}
            loading={evaluation.isLoading || evaluation.isFetching}
            onRefresh={() => evaluation.refetch()}
            prompts={TESTING_PROMPTS}
            compileHistory={compileHistory}
            onSelectPrompt={(selectedPrompt) => {
              setPrompt(selectedPrompt)
              setActiveTab('compiler')
              runCompile(selectedPrompt)
            }}
          />
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.3fr_1fr_0.92fr]">
          {activeTab === 'overview' && (
            <>
              <section className="space-y-4 xl:col-span-2">
                <Hero appName={compile.data?.config.app_name} />
                <MetricCards metrics={compile.data?.config.metrics} />
                <RuntimeChart compileHistory={compileHistory} />
              </section>
              <section className="space-y-4">
                <Assistant issues={compile.data?.config.validation_report ?? []} runtime={compile.data?.config.runtime} />
              </section>
            </>
          )}
          {activeTab === 'compiler' && (
            <>
              <section className="space-y-4 xl:col-span-2">
                <Hero appName={compile.data?.config.app_name} />
                <PromptCenter
                  prompt={prompt}
                  setPrompt={setPrompt}
                  tokenCount={tokenCount}
                  onTemplate={setPrompt}
                  onGenerate={runCompile}
                  loading={compile.isPending}
                  userPromptHistory={userPromptHistory}
                />
                <Pipeline stages={stageState} />
                <ConfigEditor view={view} setView={setView} config={compile.data?.config} previousConfig={previousConfig} />
              </section>
              <section className="space-y-4">
                <MetricCards metrics={compile.data?.config.metrics} />
                <RuntimeChart compileHistory={compileHistory} />
                <LiveLogs lines={logText} loading={compile.isPending} />
                <Assistant issues={compile.data?.config.validation_report ?? []} runtime={compile.data?.config.runtime} />
              </section>
            </>
          )}
          {activeTab === 'runtime' && (
            <>
              <section className="space-y-4 xl:col-span-2">
                <Panel><p className="text-sm font-semibold">Runtime Monitoring</p><p className="mt-2 text-sm text-text-secondary">Execution health, generated artifacts, and route readiness from simulation.</p></Panel>
                <RuntimeChart compileHistory={compileHistory} />
              </section>
              <section className="space-y-4">
                <MetricCards metrics={compile.data?.config.metrics} />
                <Assistant issues={compile.data?.config.validation_report ?? []} runtime={compile.data?.config.runtime} />
              </section>
            </>
          )}
          {activeTab === 'logs' && (
            <>
              <section className="space-y-4 xl:col-span-2">
                <Panel><p className="text-sm font-semibold">Compiler Logs</p><p className="mt-2 text-sm text-text-secondary">Stage-by-stage output from the backend pipeline.</p></Panel>
                <LiveLogs lines={logText} loading={compile.isPending} />
              </section>
              <section className="space-y-4">
                <MetricCards metrics={compile.data?.config.metrics} />
              </section>
            </>
          )}
          {activeTab === 'agents' && (
            <>
              <section className="space-y-4 xl:col-span-2">
                <Panel><p className="text-sm font-semibold">Agent Control Plane</p><p className="mt-2 text-sm text-text-secondary">Intent, schema, repair, and runtime agents coordinating compilation.</p></Panel>
                <Pipeline stages={stageState} />
              </section>
              <section className="space-y-4">
                <Assistant issues={compile.data?.config.validation_report ?? []} runtime={compile.data?.config.runtime} />
              </section>
            </>
          )}
          </div>
        </main>
      </div>
      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} onAction={handleCommandAction} />
    </div>
  )
}

function Panel({ className, children }: PropsWithChildren<{ className?: string }>) {
  return <motion.div whileHover={{ y: -2 }} className={cn('glass-panel rounded-2xl p-4', className)}>{children}</motion.div>
}

function Topbar({ onCommand }: { onCommand: () => void }) {
  return <header className="fixed inset-x-0 top-0 z-50 border-b border-white/10 bg-black/20 backdrop-blur-2xl"><div className="mx-auto flex max-w-[1680px] items-center justify-between px-4 py-3 lg:px-6"><div className="flex items-center gap-3"><div className="rounded-xl border border-cyan-300/30 bg-cyan-400/10 p-2"><Sparkles className="h-4 w-4 text-cyan-300" /></div><div><p className="text-sm font-semibold">SOFCOM</p><p className="text-xs text-text-secondary">Autonomous Build Fabric</p></div></div><button onClick={onCommand} className="inline-flex items-center gap-2 rounded-xl border border-purple-300/30 bg-purple-400/10 px-3 py-2 text-xs text-purple-100"><Command className="h-3.5 w-3.5" />Cmd/Ctrl + K</button></div></header>
}

function Sidebar({
  collapsed,
  onToggle,
  activeTab,
  setActiveTab,
}: {
  collapsed: boolean
  onToggle: () => void
  activeTab: 'overview' | 'compiler' | 'runtime' | 'logs' | 'agents'
  setActiveTab: (tab: 'overview' | 'compiler' | 'runtime' | 'logs' | 'agents') => void
}) {
  const items = [
    { key: 'overview', label: 'Overview', Icon: LayoutDashboard },
    { key: 'compiler', label: 'Compiler', Icon: Cpu },
    { key: 'runtime', label: 'Runtime', Icon: Activity },
    { key: 'logs', label: 'Logs', Icon: Terminal },
    { key: 'agents', label: 'Agents', Icon: Bot },
  ] as const
  return <motion.aside animate={{ width: collapsed ? 72 : 252 }} className="glass-panel hidden min-h-[calc(100vh-7rem)] shrink-0 rounded-2xl p-3 md:block"><button onClick={onToggle} className="mb-3 flex w-full items-center justify-between rounded-xl border border-white/10 bg-white/5 p-2 text-xs">{collapsed ? <Menu className="h-4 w-4" /> : <><span>Collapse</span><ChevronsLeftRight className="h-4 w-4" /></>}</button><div className="space-y-2">{items.map(({ key, label, Icon }) => <button key={key} onClick={() => setActiveTab(key)} className={cn('flex w-full items-center gap-3 rounded-xl border p-2 text-sm transition', activeTab === key ? 'border-cyan-300/50 bg-cyan-400/10 text-white shadow-glow-cyan' : 'border-transparent text-text-secondary hover:bg-white/5 hover:text-white')}><Icon className="h-4 w-4" />{!collapsed && <span>{label}</span>}</button>)}</div></motion.aside>
}

function Hero({ appName }: { appName?: string }) {
  return <Panel><p className="text-xs uppercase tracking-[0.2em] text-cyan-300">Live Compilation</p><h1 className="mt-2 text-2xl font-semibold">{appName ?? 'AI software generation in cinematic real-time'}</h1><p className="mt-2 text-sm text-text-secondary">Pipeline output is now connected to the backend and validated before runtime simulation.</p></Panel>
}

function PromptCenter({
  prompt,
  setPrompt,
  tokenCount,
  onTemplate,
  onGenerate,
  loading,
  userPromptHistory,
}: {
  prompt: string
  setPrompt: (v: string) => void
  tokenCount: number
  onTemplate: (t: string) => void
  onGenerate: () => void
  loading: boolean
  userPromptHistory: string[]
}) {
  const [historyOpen, setHistoryOpen] = useState(false)

  return (
    <Panel>
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-purple-300" />
          <p className="text-sm font-semibold">AI Command Center</p>
        </div>
        <p className="text-xs text-text-secondary">{tokenCount} tokens</p>
      </div>

      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Describe the software you want to compile..."
        className="min-h-28 w-full resize-y rounded-xl border border-white/10 bg-black/30 p-3 text-sm outline-none ring-purple-300/0 transition focus:ring-2"
      />

      <div className="mt-3 flex flex-wrap gap-2">
        {templates.map((template) => (
          <button
            key={template}
            onClick={() => onTemplate(template)}
            className="rounded-xl border border-cyan-300/20 bg-cyan-400/10 px-3 py-1.5 text-xs text-cyan-100"
          >
            {template.slice(0, 48)}...
          </button>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-2 text-xs text-text-secondary">
          <span>/generate</span>
          <span>/refine</span>
          <span>/deploy</span>
        </div>
        <div className="relative flex gap-2">
          <button
            onClick={() => setHistoryOpen((v) => !v)}
            className="icon-btn"
            title="Prompt History"
          >
            <Upload className="h-4 w-4" />
          </button>
          <button
            disabled={loading || prompt.trim().length < 3}
            onClick={onGenerate}
            className="glow-btn disabled:opacity-60"
          >
            <Play className="h-4 w-4" />
            {loading ? 'Compiling...' : 'Generate'}
          </button>
          {historyOpen && (
            <div className="absolute right-0 top-11 z-20 w-80 rounded-xl border border-white/10 bg-[#0b1220] p-2 shadow-card">
              {userPromptHistory.length === 0 ? (
                <p className="px-2 py-1 text-xs text-text-secondary">No user prompt history yet.</p>
              ) : (
                userPromptHistory.map((item, idx) => (
                  <button
                    key={`${idx}-${item}`}
                    onClick={() => {
                      setPrompt(item)
                      setHistoryOpen(false)
                    }}
                    className="block w-full truncate rounded-lg px-2 py-1.5 text-left text-xs hover:bg-white/5"
                  >
                    {item}
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </Panel>
  )
}

function Pipeline({ stages }: { stages: Array<{ name: string; status: 'active' | 'success' | 'error' }> }) {
  const statusClass = { active: 'bg-cyan-400 shadow-glow-cyan', success: 'bg-emerald-400 shadow-glow-green', error: 'bg-rose-400 shadow-[0_0_20px_rgba(244,63,94,0.45)]' }
  return <Panel><p className="mb-3 text-sm font-semibold">Compilation Pipeline</p><div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">{stages.map((stage, i) => <motion.div key={stage.name} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }} className="rounded-xl border border-white/10 bg-black/30 p-3"><div className="mb-2 flex items-center justify-between"><p className="text-sm capitalize">{stage.name}</p><span className={cn('h-2.5 w-2.5 rounded-full animate-pulse', statusClass[stage.status])} /></div><div className="h-1.5 overflow-hidden rounded-full bg-white/10"><motion.div initial={{ width: 0 }} animate={{ width: stage.status === 'success' ? '100%' : '60%' }} className="h-full bg-gradient-cyber" /></div></motion.div>)}</div></Panel>
}

function toYaml(value: unknown, indent = 0): string {
  const space = '  '.repeat(indent)
  if (Array.isArray(value)) {
    return value.map((item) => `${space}- ${typeof item === 'object' && item !== null ? `\n${toYaml(item, indent + 1)}` : String(item)}`).join('\n')
  }
  if (value && typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => {
        if (v && typeof v === 'object') return `${space}${k}:\n${toYaml(v, indent + 1)}`
        return `${space}${k}: ${String(v)}`
      })
      .join('\n')
  }
  return `${space}${String(value)}`
}

function buildDiff(currentObj: unknown, previousObj: unknown): string {
  const current = JSON.stringify(currentObj ?? {}, null, 2).split('\n')
  const previous = JSON.stringify(previousObj ?? {}, null, 2).split('\n')
  const out: string[] = []
  const max = Math.max(current.length, previous.length)
  for (let i = 0; i < max; i += 1) {
    const a = previous[i]
    const b = current[i]
    if (a === b) out.push(`  ${b ?? ''}`)
    else {
      if (a !== undefined) out.push(`- ${a}`)
      if (b !== undefined) out.push(`+ ${b}`)
    }
  }
  return out.join('\n')
}

function ConfigEditor({
  view,
  setView,
  config,
  previousConfig,
}: {
  view: 'json' | 'yaml' | 'diff'
  setView: (v: 'json' | 'yaml' | 'diff') => void
  config?: CompileResponse['config']
  previousConfig?: CompileResponse['config'] | null
}) {
  const jsonObj = config ?? { message: 'Run Generate to compile config.' }
  const json = JSON.stringify(jsonObj, null, 2)
  const yaml = toYaml(jsonObj)
  const diffText = buildDiff(jsonObj, previousConfig ?? null)
  const display = view === 'json' ? json : view === 'yaml' ? yaml : diffText
  const language = view === 'yaml' ? 'yaml' : 'json'
  return <Panel className="p-0"><div className="flex items-center justify-between border-b border-white/10 p-3"><div className="flex gap-1">{(['json', 'yaml', 'diff'] as const).map((item) => <button key={item} onClick={() => setView(item)} className={cn('rounded-lg px-2 py-1 text-xs', view === item ? 'bg-white/10 text-white' : 'text-text-secondary')}>{item.toUpperCase()}</button>)}</div><div className="flex gap-2"><button onClick={() => navigator.clipboard.writeText(display)} className="icon-btn"><Copy className="h-4 w-4" /></button><button className="icon-btn"><Download className="h-4 w-4" /></button></div></div><div className="h-[310px]"><Editor theme="vs-dark" defaultLanguage={language} options={{ minimap: { enabled: true }, fontSize: 13 }} value={display} /></div></Panel>
}

function MetricCards({ metrics }: { metrics?: CompileResponse['config']['metrics'] }) {
  const cards = [{ label: 'Latency', value: metrics ? `${metrics.latency_ms}ms` : '--', icon: Gauge, glow: 'shadow-glow' }, { label: 'Repair Passes', value: metrics ? String(metrics.repair_passes) : '--', icon: Bot, glow: 'shadow-glow-cyan' }, { label: 'Issues', value: metrics ? String(metrics.issue_count) : '--', icon: Sparkles, glow: 'shadow-glow-green' }]
  return <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">{cards.map((c) => <Panel key={c.label} className={cn('p-3', c.glow)}><div className="flex items-center justify-between"><p className="text-xs text-text-secondary">{c.label}</p><c.icon className="h-4 w-4 text-cyan-300" /></div><p className="mt-2 text-xl font-semibold">{c.value}</p></Panel>)}</div>
}

function RuntimeChart({ compileHistory }: { compileHistory: CompileHistoryRow[] }) {
  const chartData = useMemo(() => {
    if (!compileHistory.length) return []
    return compileHistory
      .slice(0, 12)
      .map((row, idx, arr) => {
        const sequence = arr.length - idx
        const tokenEstimate = Math.max(200, Math.round((row.prompt.length * 1.4) + (row.retries * 80)))
        return {
          name: `Run ${sequence}`,
          tokens: tokenEstimate,
          latency: row.latencyMs,
        }
      })
      .reverse()
  }, [compileHistory])

  return (
    <Panel className="h-60">
      <p className="mb-3 text-sm font-semibold">Runtime Analytics</p>
      {chartData.length === 0 ? (
        <div className="flex h-[86%] items-center justify-center rounded-xl border border-white/10 bg-black/20 text-xs text-text-secondary">
          No live data yet. Run a compile to populate analytics.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="86%">
          <AreaChart data={chartData}>
            <defs><linearGradient id="tokens" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.7} /><stop offset="95%" stopColor="#06b6d4" stopOpacity={0} /></linearGradient></defs>
            <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ background: '#0b1220', border: '1px solid rgba(255,255,255,0.1)' }} />
            <Area type="monotone" dataKey="tokens" stroke="#22d3ee" fill="url(#tokens)" />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </Panel>
  )
}

function LiveLogs({ lines, loading }: { lines: string; loading: boolean }) {
  return <Panel><div className="mb-2 flex items-center justify-between"><p className="text-sm font-semibold">Live Compiler Logs</p><Search className="h-4 w-4 text-text-secondary" /></div><pre className="terminal h-48 overflow-y-auto rounded-xl border border-white/10 bg-black/50 p-3 text-xs leading-6 text-cyan-100">{lines || 'Waiting for compile request...'}{loading ? '\n[INFO] streaming...\n' : ''}<span className="animate-pulse">▋</span></pre></Panel>
}

function Assistant({ issues, runtime }: { issues: Array<{ severity: 'error' | 'warning'; message: string }>; runtime?: { executable: boolean; generated_files: string[] } }) {
  const errors = issues.filter((x) => x.severity === 'error')
  return <Panel><p className="text-sm font-semibold">AI Assistant</p><p className="mt-2 text-sm text-text-secondary">{errors.length ? `${errors.length} blocking issue(s) detected.` : runtime?.executable ? 'Runtime simulation passed. Config is executable.' : 'Run a compile to get validation feedback.'}</p></Panel>
}

function EvaluationBar({
  data,
  loading,
  onRefresh,
  prompts,
  compileHistory,
  onSelectPrompt,
}: {
  data?: EvaluationResponse
  loading: boolean
  onRefresh: () => void
  prompts: Array<{ kind: 'product' | 'edge'; prompt: string }>
  compileHistory: CompileHistoryRow[]
  onSelectPrompt: (prompt: string) => void
}) {
  const [tab, setTab] = useState<'summary' | 'testing_prompts'>('summary')
  const sessionSummary = useMemo(() => {
    if (!compileHistory.length) return null
    const successCount = compileHistory.filter((x) => x.success).length
    return {
      successRate: (successCount / compileHistory.length) * 100,
      retriesAvg: compileHistory.reduce((a, b) => a + b.retries, 0) / compileHistory.length,
      latencyAvg: compileHistory.reduce((a, b) => a + b.latencyMs, 0) / compileHistory.length,
      validationFailures: compileHistory.filter((x) => x.failureType === 'validation_error').length,
      runtimeFailures: compileHistory.filter((x) => x.failureType === 'runtime_failure').length,
    }
  }, [compileHistory])
  return (
    <Panel className="p-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold">Evaluation Dataset (20 Prompts)</p>
          <p className="text-xs text-text-secondary">Live backend metrics from /evaluate</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="rounded-xl border border-white/10 bg-black/20 p-1">
            <button onClick={() => setTab('summary')} className={cn('rounded-lg px-2 py-1 text-xs', tab === 'summary' ? 'bg-white/10 text-white' : 'text-text-secondary')}>Summary</button>
            <button onClick={() => setTab('testing_prompts')} className={cn('rounded-lg px-2 py-1 text-xs', tab === 'testing_prompts' ? 'bg-white/10 text-white' : 'text-text-secondary')}>Testing Prompts</button>
          </div>
          <button onClick={onRefresh} className="icon-btn text-xs">Refresh Metrics</button>
        </div>
      </div>
      {tab === 'summary' ? (
        <>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
            <MetricChip label="Success Rate" value={data ? `${(data.success_rate * 100).toFixed(1)}%` : '--'} />
            <MetricChip label="Retries / Request" value={data ? String(data.retries_per_request) : '--'} />
            <MetricChip label="Avg Latency" value={data ? `${data.average_latency_ms.toFixed(2)} ms` : '--'} />
            <MetricChip label="Validation Failures" value={data ? String(data.failure_types.validation_error) : '--'} />
            <MetricChip label="Runtime Failures" value={data ? String(data.failure_types.runtime_failure) : '--'} />
          </div>
          <div className="mt-2 rounded-xl border border-cyan-300/20 bg-cyan-400/5 p-2">
            <p className="text-xs text-cyan-100">Session Summary (includes user prompts beyond testing 20)</p>
            <div className="mt-1 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
              <MetricChip label="Success Rate" value={sessionSummary ? `${sessionSummary.successRate.toFixed(1)}%` : '--'} />
              <MetricChip label="Retries / Request" value={sessionSummary ? sessionSummary.retriesAvg.toFixed(2) : '--'} />
              <MetricChip label="Avg Latency" value={sessionSummary ? `${sessionSummary.latencyAvg.toFixed(2)} ms` : '--'} />
              <MetricChip label="Validation Failures" value={sessionSummary ? String(sessionSummary.validationFailures) : '--'} />
              <MetricChip label="Runtime Failures" value={sessionSummary ? String(sessionSummary.runtimeFailures) : '--'} />
            </div>
          </div>
          <div className="mt-3 max-h-40 space-y-2 overflow-y-auto rounded-xl border border-white/10 bg-black/20 p-2">
            {loading && <p className="px-2 py-1 text-xs text-text-secondary">Running evaluation...</p>}
            {!loading && data?.rows.map((row, idx) => (
              <div key={`${row.kind}-${idx}`} className="flex flex-wrap items-center gap-2 rounded-lg border border-white/5 bg-white/[0.02] px-2 py-1.5 text-xs">
                <span className={cn('rounded-full px-2 py-0.5', row.kind === 'product' ? 'bg-emerald-500/20 text-emerald-200' : 'bg-amber-500/20 text-amber-200')}>{row.kind}</span>
                <span className={cn('rounded-full px-2 py-0.5', row.success ? 'bg-cyan-500/20 text-cyan-200' : 'bg-rose-500/20 text-rose-200')}>{row.success ? 'success' : 'failed'}</span>
                <span className="text-text-secondary">{row.latency_ms.toFixed(2)}ms</span>
                <span className="text-text-secondary">retries: {row.repair_passes}</span>
                {row.failure_type ? <span className="text-rose-300">{row.failure_type}</span> : null}
                <span className="min-w-0 flex-1 truncate text-text-primary">{row.prompt}</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="max-h-56 space-y-2 overflow-y-auto rounded-xl border border-white/10 bg-black/20 p-2">
          {prompts.map((item, idx) => (
            <button key={`${item.kind}-${idx}`} onClick={() => onSelectPrompt(item.prompt)} className="flex w-full items-center gap-2 rounded-lg border border-white/5 bg-white/[0.02] px-2 py-1.5 text-left text-xs transition hover:border-cyan-300/30 hover:bg-cyan-400/5">
              <span className={cn('rounded-full px-2 py-0.5', item.kind === 'product' ? 'bg-emerald-500/20 text-emerald-200' : 'bg-amber-500/20 text-amber-200')}>{item.kind}</span>
              <span className="min-w-0 flex-1 truncate text-text-primary">{item.prompt}</span>
            </button>
          ))}
        </div>
      )}
    </Panel>
  )
}

function MetricChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2">
      <p className="text-[11px] text-text-secondary">{label}</p>
      <p className="text-sm font-semibold">{value}</p>
    </div>
  )
}

function CommandPalette({
  open,
  onClose,
  onAction,
}: {
  open: boolean
  onClose: () => void
  onAction: (action: 'run_compile' | 'open_logs' | 'open_compiler' | 'open_runtime' | 'toggle_sidebar') => void
}) {
  const items: Array<{ label: string; action: 'run_compile' | 'open_logs' | 'open_compiler' | 'open_runtime' | 'toggle_sidebar' }> = [
    { label: 'Run Compile', action: 'run_compile' },
    { label: 'Open Compiler', action: 'open_compiler' },
    { label: 'Open Runtime', action: 'open_runtime' },
    { label: 'Open Logs', action: 'open_logs' },
    { label: 'Toggle Sidebar', action: 'toggle_sidebar' },
  ]
  return <AnimatePresence>{open && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[70] bg-black/40 p-4 backdrop-blur-sm" onClick={onClose}><motion.div initial={{ y: -20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -20, opacity: 0 }} onClick={(e) => e.stopPropagation()} className="mx-auto mt-20 max-w-xl rounded-2xl border border-white/10 bg-[#0b1220] p-3"><div className="mb-2 flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 p-2 text-sm"><Search className="h-4 w-4 text-text-secondary" />Search commands...</div>{items.map((item) => <button key={item.label} onClick={() => onAction(item.action)} className="block w-full rounded-xl px-3 py-2 text-left text-sm hover:bg-white/5">{item.label}<ChevronDown className="float-right h-4 w-4 text-text-secondary" /></button>)}</motion.div></motion.div>}</AnimatePresence>
}
