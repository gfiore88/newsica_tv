import { useState, useEffect, useCallback } from 'react'
import { Database as DbIcon, RefreshCw, Clock, CheckCircle, XCircle, AlertCircle, Loader, UploadCloud, Hourglass } from 'lucide-react'

// ─── Configurazione stati ──────────────────────────────────────────────
const STATUS_CONFIG = {
  all:       { label: 'Tutti',      color: 'text-slate-300',  bg: 'bg-slate-700',       border: 'border-slate-600',       icon: DbIcon },
  pending:   { label: 'Pending',    color: 'text-amber-300',  bg: 'bg-amber-900/30',    border: 'border-amber-500/50',    icon: Hourglass },
  claimed:   { label: 'Claimed',    color: 'text-sky-300',    bg: 'bg-sky-900/30',      border: 'border-sky-500/50',      icon: Loader },
  running:   { label: 'Running',    color: 'text-blue-300',   bg: 'bg-blue-900/30',     border: 'border-blue-500/50',     icon: Loader },
  uploading: { label: 'Uploading',  color: 'text-violet-300', bg: 'bg-violet-900/30',   border: 'border-violet-500/50',   icon: UploadCloud },
  ready:     { label: 'Ready',      color: 'text-emerald-300',bg: 'bg-emerald-900/30',  border: 'border-emerald-500/50',  icon: CheckCircle },
  failed:    { label: 'Failed',     color: 'text-red-300',    bg: 'bg-red-900/30',      border: 'border-red-500/50',      icon: XCircle },
  expired:   { label: 'Expired',    color: 'text-slate-400',  bg: 'bg-slate-800/50',    border: 'border-slate-600',       icon: AlertCircle },
}

const ACTIVE_STATUSES = new Set(['pending', 'claimed', 'running', 'uploading'])

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.all
  const Icon = cfg.icon
  const isActive = ACTIVE_STATUSES.has(status)
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-bold uppercase ${cfg.color} ${cfg.bg} ${cfg.border}`}>
      <Icon size={10} className={isActive ? 'animate-spin' : ''} />
      {cfg.label}
    </span>
  )
}

function formatDt(iso) {
  if (!iso) return '--'
  const d = new Date(iso)
  return d.toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'medium' })
}

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return '--'
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}

function JobTypeChip({ type }) {
  const colors = {
    ai_music:     'text-purple-300 bg-purple-900/30 border-purple-500/40',
    tts_audio:    'text-sky-300 bg-sky-900/30 border-sky-500/40',
    slot_audio:   'text-indigo-300 bg-indigo-900/30 border-indigo-500/40',
    hourly_chime: 'text-amber-300 bg-amber-900/30 border-amber-500/40',
    breaking_news:'text-red-300 bg-red-900/30 border-red-500/40',
    short_tts:    'text-teal-300 bg-teal-900/30 border-teal-500/40',
    llm_generate: 'text-orange-300 bg-orange-900/30 border-orange-500/40',
  }
  return (
    <span className={`px-2 py-0.5 rounded border text-[10px] font-bold uppercase ${colors[type] || 'text-slate-400 bg-slate-800 border-slate-600'}`}>
      {type?.replace(/_/g, ' ') || '--'}
    </span>
  )
}

// ─── Componente tab Generation Jobs ──────────────────────────────────
function GenerationJobsTab({ autoRefresh }) {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState('all')
  const [counts, setCounts] = useState({})

  const fetchJobs = useCallback(async (filter) => {
    setLoading(true)
    try {
      const url = filter && filter !== 'all'
        ? `/api/db/generation-jobs?status=${filter}&limit=200`
        : `/api/db/generation-jobs?limit=200`
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        setJobs(data.data || [])
      }
    } catch (e) {
      console.error('Errore generation jobs:', e)
    }
    setLoading(false)
  }, [])

  // Conta i job per status dal dataset completo (solo quando filtro = all)
  const updateCounts = useCallback(async () => {
    try {
      const res = await fetch('/api/db/generation-jobs?limit=500')
      if (res.ok) {
        const data = await res.json()
        const all = data.data || []
        const c = {}
        all.forEach(j => { c[j.status] = (c[j.status] || 0) + 1 })
        c.all = all.length
        setCounts(c)
      }
    } catch (e) {}
  }, [])

  useEffect(() => {
    fetchJobs(statusFilter)
    updateCounts()
  }, [statusFilter, fetchJobs, updateCounts])

  useEffect(() => {
    if (!autoRefresh) return
    const iv = setInterval(() => {
      fetchJobs(statusFilter)
      updateCounts()
    }, 5000)
    return () => clearInterval(iv)
  }, [autoRefresh, statusFilter, fetchJobs, updateCounts])

  const filterButtons = Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
    <button
      key={key}
      onClick={() => setStatusFilter(key)}
      className={`px-3 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-wide transition flex items-center gap-1.5 border shrink-0 ${
        statusFilter === key
          ? `${cfg.color} ${cfg.bg} ${cfg.border}`
          : 'text-slate-500 border-slate-700 hover:text-slate-300 hover:bg-slate-800/60'
      }`}
    >
      {cfg.label}
      {counts[key] !== undefined && (
        <span className={`text-[10px] font-mono px-1 rounded ${statusFilter === key ? 'opacity-80' : 'text-slate-500'}`}>
          {counts[key]}
        </span>
      )}
    </button>
  ))

  return (
    <div className="flex flex-col h-full">
      {/* Filter strip */}
      <div className="px-4 py-3 border-b border-slate-800 bg-slate-900/60 flex gap-2 overflow-x-auto shrink-0">
        {filterButtons}
      </div>

      {/* Jobs count + loading */}
      <div className="px-5 py-2 border-b border-slate-800 flex items-center gap-2 shrink-0">
        <span className="text-xs text-slate-500">
          {loading ? 'Aggiornamento...' : `${jobs.length} job${jobs.length !== 1 ? 's' : ''}`}
        </span>
        {loading && <RefreshCw size={12} className="text-slate-500 animate-spin" />}
      </div>

      {/* Scrollable table */}
      <div className="flex-1 overflow-auto">
        {jobs.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-slate-500 text-sm">
            {loading ? 'Caricamento...' : 'Nessun job trovato per questo filtro.'}
          </div>
        ) : (
          <table className="w-full text-left text-sm text-slate-300 min-w-[900px]">
            <thead className="bg-slate-900 sticky top-0 border-b border-slate-800 shadow-md z-10">
              <tr>
                <th className="px-4 py-3 font-bold text-slate-400 text-xs w-24">ID</th>
                <th className="px-4 py-3 font-bold text-slate-400 text-xs">Tipo</th>
                <th className="px-4 py-3 font-bold text-slate-400 text-xs">Titolo / Dedupe</th>
                <th className="px-4 py-3 font-bold text-slate-400 text-xs w-16 text-center">Pri</th>
                <th className="px-4 py-3 font-bold text-slate-400 text-xs">Creato</th>
                <th className="px-4 py-3 font-bold text-slate-400 text-xs">
                  <div className="flex items-center gap-1"><Clock size={12} /> Inizio</div>
                </th>
                <th className="px-4 py-3 font-bold text-slate-400 text-xs">
                  <div className="flex items-center gap-1"><Clock size={12} /> Fine</div>
                </th>
                <th className="px-4 py-3 font-bold text-slate-400 text-xs w-20">Durata</th>
                <th className="px-4 py-3 font-bold text-slate-400 text-xs w-28">Stato</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {jobs.map((job) => {
                const isActive = ACTIVE_STATUSES.has(job.status)
                return (
                  <tr
                    key={job.id}
                    className={`transition hover:bg-slate-900/60 ${isActive ? 'bg-slate-900/30' : ''}`}
                  >
                    {/* ID (short) */}
                    <td className="px-4 py-3">
                      <span className="font-mono text-[11px] text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
                        {job.id?.slice(0, 8) || '--'}
                      </span>
                    </td>

                    {/* Tipo */}
                    <td className="px-4 py-3">
                      <JobTypeChip type={job.job_type} />
                    </td>

                    {/* Titolo / dedupe */}
                    <td className="px-4 py-3 max-w-[240px]">
                      <div className="font-semibold text-slate-200 truncate text-xs">
                        {job.title || job.theme || '--'}
                      </div>
                      {job.dedupe_key && (
                        <div className="text-[10px] text-slate-600 font-mono truncate mt-0.5">
                          {job.dedupe_key}
                        </div>
                      )}
                      {job.error && (
                        <div className="text-[10px] text-red-400 mt-1 truncate" title={job.error}>
                          ⚠ {job.error}
                        </div>
                      )}
                    </td>

                    {/* Priorità */}
                    <td className="px-4 py-3 text-center">
                      <span className={`text-xs font-mono font-bold ${
                        job.priority >= 200 ? 'text-red-400' :
                        job.priority >= 100 ? 'text-amber-400' :
                        'text-slate-500'
                      }`}>
                        {job.priority ?? '--'}
                      </span>
                    </td>

                    {/* Creato */}
                    <td className="px-4 py-3 text-[11px] text-slate-400 whitespace-nowrap">
                      {formatDt(job.created_at)}
                    </td>

                    {/* Inizio (started_at) */}
                    <td className="px-4 py-3 text-[11px] text-slate-400 whitespace-nowrap">
                      {job.started_at ? (
                        <span className="text-sky-400">{formatDt(job.started_at)}</span>
                      ) : (
                        <span className="text-slate-600">--</span>
                      )}
                    </td>

                    {/* Fine (ended_at) */}
                    <td className="px-4 py-3 text-[11px] whitespace-nowrap">
                      {job.ended_at ? (
                        <span className={job.status === 'failed' || job.status === 'expired' ? 'text-red-400' : 'text-emerald-400'}>
                          {formatDt(job.ended_at)}
                        </span>
                      ) : isActive ? (
                        <span className="text-amber-400 animate-pulse text-[10px] font-bold">IN CORSO</span>
                      ) : (
                        <span className="text-slate-600">--</span>
                      )}
                    </td>

                    {/* Durata */}
                    <td className="px-4 py-3 text-[11px] font-mono">
                      {job.duration_seconds !== null ? (
                        <span className="text-slate-300">{formatDuration(job.duration_seconds)}</span>
                      ) : (
                        <span className="text-slate-600">--</span>
                      )}
                    </td>

                    {/* Stato */}
                    <td className="px-4 py-3">
                      <StatusBadge status={job.status} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ─── Componente principale Database ──────────────────────────────────
export default function Database() {
  const [activeTab, setActiveTab] = useState('jobs')
  const [data, setData] = useState({
    history: [],
    memory: [],
    assets: [],
    rotation: { recent_tracks: [], block_events: [], configured_window: 0, tracked_count: 0 }
  })
  const [loading, setLoading] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [histRes, memRes, assetsRes, rotationRes] = await Promise.all([
        fetch('/api/db/history'),
        fetch('/api/db/memory'),
        fetch('/api/db/assets'),
        fetch('/api/db/music-rotation')
      ])
      const [hist, mem, assets, rotation] = await Promise.all([
        histRes.json(), memRes.json(), assetsRes.json(), rotationRes.json()
      ])
      setData({
        history: hist.data || [],
        memory: mem.data || [],
        assets: assets.data || [],
        rotation: rotation.data || { recent_tracks: [], block_events: [], configured_window: 0, tracked_count: 0 }
      })
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  useEffect(() => {
    if (activeTab !== 'jobs') {
      Promise.resolve().then(fetchData)
    }
  }, [activeTab])

  useEffect(() => {
    if (activeTab !== 'jobs') {
      const int = setInterval(fetchData, 10000)
      return () => clearInterval(int)
    }
  }, [activeTab])

  const formatDateTime = (iso) => {
    if (!iso) return '--'
    return new Date(iso).toLocaleString()
  }

  const tabs = [
    { key: 'jobs',     label: 'Generation Jobs' },
    { key: 'history',  label: 'Trasmissioni' },
    { key: 'memory',   label: 'Memoria Editoriale' },
    { key: 'assets',   label: 'Stato Asset' },
    { key: 'rotation', label: 'Rotazione Musica' },
  ]

  return (
    <div className="flex flex-col h-full bg-slate-950/50 rounded-xl border border-slate-800 shadow-xl overflow-hidden">
      {/* Header & Tabs */}
      <div className="p-4 lg:p-5 border-b border-slate-800 bg-slate-900/80 flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="flex items-center gap-2 shrink-0">
          <DbIcon className="text-indigo-500" size={22} />
          <h1 className="text-base font-black text-white">Registro &amp; Audit</h1>
        </div>
        <div className="flex gap-1.5 overflow-x-auto flex-1">
          {tabs.map(t => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={`px-3 py-1.5 text-[11px] font-bold uppercase tracking-wide rounded-lg transition shrink-0 ${
                activeTab === t.key ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        {activeTab !== 'jobs' && (
          <button
            onClick={fetchData}
            className={`text-slate-400 hover:text-white p-2 rounded-lg bg-slate-800 hover:bg-slate-700 transition shrink-0 ${loading ? 'animate-spin' : ''}`}
          >
            <RefreshCw size={16} />
          </button>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto bg-slate-950">

        {/* ── Generation Jobs ── */}
        {activeTab === 'jobs' && (
          <GenerationJobsTab autoRefresh={true} />
        )}

        {/* ── Storico Trasmissioni ── */}
        {activeTab === 'history' && (
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-900 sticky top-0 border-b border-slate-800 shadow-md">
              <tr>
                <th className="px-5 py-4 font-bold text-slate-400 text-xs">Inizio</th>
                <th className="px-5 py-4 font-bold text-slate-400 text-xs">Tipo</th>
                <th className="px-5 py-4 font-bold text-slate-400 text-xs">Titolo / Segmento</th>
                <th className="px-5 py-4 font-bold text-slate-400 text-xs">Asset Path</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {data.history.map((row, i) => (
                <tr key={i} className="hover:bg-slate-900/50 transition">
                  <td className="px-5 py-3 whitespace-nowrap text-xs">{formatDateTime(row.started_at)}</td>
                  <td className="px-5 py-3">
                    <span className="px-2 py-1 rounded-full bg-slate-800 border border-slate-700 text-[10px] font-bold text-slate-300 uppercase">
                      {row.event_type}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <div className="font-semibold text-white text-sm">{row.display_title || row.title}</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">{row.display_detail || row.segment || row.block_type || '--'}</div>
                  </td>
                  <td className="px-5 py-3 text-slate-500 font-mono text-xs">{row.asset_path ? row.asset_path.split('/').pop() : '--'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* ── Memoria Editoriale ── */}
        {activeTab === 'memory' && (
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-900 sticky top-0 border-b border-slate-800 shadow-md">
              <tr>
                <th className="px-5 py-4 font-bold text-slate-400 text-xs w-1/5">Tipo</th>
                <th className="px-5 py-4 font-bold text-slate-400 text-xs w-2/5">Sintesi</th>
                <th className="px-5 py-4 font-bold text-slate-400 text-xs w-2/5">Valore</th>
                <th className="px-5 py-4 font-bold text-slate-400 text-xs w-1/5">Creazione</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {data.memory.map((row, i) => (
                <tr key={i} className="hover:bg-slate-900/50 transition">
                  <td className="px-5 py-3">
                    <span className="px-2 py-1 rounded-full bg-purple-900/30 border border-purple-500/30 text-[10px] font-bold text-purple-300 uppercase">
                      {row.memory_type}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-xs text-slate-300 align-top">{row.value_summary || '--'}</td>
                  <td className="px-5 py-3 align-top">
                    {row.value_is_json ? (
                      <pre className="max-w-[520px] overflow-auto rounded-lg border border-slate-800 bg-slate-950/80 p-3 text-[11px] leading-5 text-slate-300 whitespace-pre-wrap">
                        {row.value_pretty}
                      </pre>
                    ) : (
                      <div className="max-w-[520px] whitespace-pre-wrap text-xs font-semibold text-white">{row.value}</div>
                    )}
                  </td>
                  <td className="px-5 py-3 whitespace-nowrap text-slate-400 align-top text-xs">{formatDateTime(row.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* ── Stato Asset ── */}
        {activeTab === 'assets' && (
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-900 sticky top-0 border-b border-slate-800 shadow-md">
              <tr>
                <th className="px-5 py-4 font-bold text-slate-400 text-xs">Slot</th>
                <th className="px-5 py-4 font-bold text-slate-400 text-xs">Character / Titolo</th>
                <th className="px-5 py-4 font-bold text-slate-400 text-xs">Stato</th>
                <th className="px-5 py-4 font-bold text-slate-400 text-xs">Aggiornato</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {data.assets.map((row, i) => {
                let statusColor = 'text-slate-400 bg-slate-800 border-slate-600'
                if (row.status === 'ready') statusColor = 'text-green-400 bg-green-900/30 border-green-500/50'
                if (row.status === 'preparing') statusColor = 'text-amber-400 bg-amber-900/30 border-amber-500/50 animate-pulse'
                if (row.status === 'failed') statusColor = 'text-red-400 bg-red-900/30 border-red-500/50'
                if (row.status === 'played') statusColor = 'text-blue-400 bg-blue-900/30 border-blue-500/50'
                return (
                  <tr key={i} className="hover:bg-slate-900/50 transition">
                    <td className="px-5 py-3 font-mono text-slate-400 text-xs">{row.slot_time}</td>
                    <td className="px-5 py-3">
                      <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">{row.character}</div>
                      <div className="font-semibold text-white mt-0.5 text-sm">{row.title}</div>
                    </td>
                    <td className="px-5 py-3">
                      <span className={`px-2 py-1 rounded-full border text-[10px] font-bold uppercase ${statusColor}`}>{row.status}</span>
                      {row.error && <div className="text-[10px] text-red-400 mt-1 font-mono">{row.error}</div>}
                    </td>
                    <td className="px-5 py-3 text-slate-400 text-xs">{formatDateTime(row.updated_at)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}

        {/* ── Rotazione Musica ── */}
        {activeTab === 'rotation' && (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 p-4 lg:p-6">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-800 bg-slate-900">
                <div className="text-xs uppercase tracking-widest font-bold text-sky-400">Finestra Recente</div>
                <div className="text-xs text-slate-400 mt-1">
                  Limite: {data.rotation.configured_window || 0} brani. Tracciati: {data.rotation.tracked_count || 0}.
                </div>
              </div>
              <div className="divide-y divide-slate-800/60 max-h-80 overflow-y-auto">
                {data.rotation.recent_tracks.length === 0 ? (
                  <div className="px-5 py-8 text-xs text-slate-500">Nessuna history runtime.</div>
                ) : data.rotation.recent_tracks.map((track, i) => (
                  <div key={`${track.path}-${i}`} className="px-5 py-3">
                    <div className="text-xs font-semibold text-white">{track.display_title || track.filename}</div>
                    <div className="text-[11px] text-slate-500 mt-0.5 font-mono break-all">{track.filename}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-800 bg-slate-900">
                <div className="text-xs uppercase tracking-widest font-bold text-amber-400">Candidati Scartati</div>
                <div className="text-xs text-slate-400 mt-1">Ultimi eventi in cui la rotazione ha escluso brani recenti.</div>
              </div>
              <div className="divide-y divide-slate-800/60 max-h-80 overflow-y-auto">
                {data.rotation.block_events.length === 0 ? (
                  <div className="px-5 py-8 text-xs text-slate-500">Ancora nessun candidato escluso.</div>
                ) : data.rotation.block_events.map((event, i) => (
                  <div key={`${event.timestamp}-${i}`} className="px-5 py-4">
                    <div className="flex items-center justify-between gap-4">
                      <div className="text-xs font-semibold text-white">{formatDateTime(event.timestamp)}</div>
                      <div className="text-[11px] text-slate-500">{event.blocked_count} esclusi su {event.candidate_count}</div>
                    </div>
                    <div className="text-[10px] text-amber-300 mt-1 uppercase tracking-wider font-bold">
                      {event.reason} | finestra={event.recent_window}
                    </div>
                    <div className="mt-2 space-y-1.5">
                      {event.blocked_tracks.map((track, idx) => (
                        <div key={`${track.path}-${idx}`} className="rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2">
                          <div className="text-xs text-slate-200">{track.display_title || track.filename}</div>
                          <div className="text-[11px] text-slate-500 mt-0.5 font-mono break-all">{track.filename}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
