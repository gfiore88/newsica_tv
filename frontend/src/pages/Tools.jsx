import { useEffect, useState } from 'react'
import { FileAudio, Music, MessageSquare, Play, Check, X, Cpu, RefreshCw, Server } from 'lucide-react'
import { useDialog } from '../context/useDialog'

export default function Tools() {
  const [manualFormats, setManualFormats] = useState([])
  const [selectedFormatId, setSelectedFormatId] = useState('news')
  const [manualTitle, setManualTitle] = useState('')
  const [manualBrief, setManualBrief] = useState('')
  const [manualLoading, setManualLoading] = useState(false)
  const [musicMode, setMusicMode] = useState({ mode: 'mixed', counts: {} })
  const [telegramVoices, setTelegramVoices] = useState([])
  const [aiJobs, setAiJobs] = useState([])
  const [generationSummary, setGenerationSummary] = useState({
    counts: {},
    active_workers: [],
    latest_jobs: [],
  })
  const [generationMaxUploadMb, setGenerationMaxUploadMb] = useState(0)
  const { showAlert } = useDialog()

  useEffect(() => {
    fetchMusicMode()
    fetchManualFormats()
    fetchTelegramVoices()
    fetchAiJobs()
    fetchGenerationSummary()
    const telegramInterval = setInterval(fetchTelegramVoices, 10000)
    const jobsInterval = setInterval(fetchAiJobs, 10000)
    const generationInterval = setInterval(fetchGenerationSummary, 10000)
    return () => {
      clearInterval(telegramInterval)
      clearInterval(jobsInterval)
      clearInterval(generationInterval)
    }
    // Initial dashboard polling only; fetch functions are declarations and do not capture mutable request state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const selectedFormat = manualFormats.find((item) => item.id === selectedFormatId) || null

  async function fetchManualFormats() {
    try {
      const res = await fetch('/api/manual-event-formats')
      if (!res.ok) return
      const data = await res.json()
      const formats = data.formats || []
      setManualFormats(formats)
      if (formats.length > 0 && !formats.some((item) => item.id === selectedFormatId)) {
        setSelectedFormatId(formats[0].id)
      }
    } catch (error) {
      console.error(error)
    }
  }

  async function fetchMusicMode() {
    try {
      const res = await fetch('/api/music_mode')
      if (res.ok) setMusicMode(await res.json())
    } catch (error) {
      console.error(error)
    }
  }

  const changeMusicMode = async (mode) => {
    try {
      const res = await fetch('/api/music_mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode })
      })
      if (res.ok) setMusicMode(await res.json())
    } catch (error) {
      console.error(error)
    }
  }

  const triggerMusicGen = async () => {
    try {
      await fetch('/api/music/generate', { method: 'POST' })
      await showAlert('Generazione musica AI avviata in background.', 'Traccia in lavorazione')
      fetchAiJobs()
    } catch (e) {
      console.error(e)
    }
  }

  const launchManualEvent = async () => {
    if (!selectedFormat) {
      await showAlert('Nessun format disponibile.', 'Errore')
      return
    }
    if (selectedFormat.requires_brief && !manualBrief.trim()) {
      await showAlert('Questo format richiede un tema o un brief.', 'Attenzione')
      return
    }

    setManualLoading(true)
    try {
      const res = await fetch('/api/manual_event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          character_id: selectedFormat.id,
          title: manualTitle,
          brief: manualBrief,
        })
      })
      const data = await res.json()
      if (res.ok) {
        await showAlert(`Generazione avviata: ${data.title}`, 'Format in Lavorazione')
        setManualTitle('')
        setManualBrief('')
      } else {
        await showAlert(data.message || 'Errore nella generazione del format.', 'Errore Server')
      }
    } catch (error) {
      console.error(error)
      await showAlert('Errore nell\'invio della richiesta.', 'Errore Rete')
    } finally {
      setManualLoading(false)
    }
  }

  async function fetchTelegramVoices() {
    try {
      const res = await fetch('/api/telegram-voices')
      if (res.ok) {
        const data = await res.json()
        setTelegramVoices(data.voices || [])
      }
    } catch (error) {
      console.error(error)
    }
  }

  const handleTgVoice = async (id, action) => {
    try {
      await fetch(`/api/telegram-voices/${action}/${id}`, { method: 'POST' })
      fetchTelegramVoices()
    } catch (error) {
      console.error(error)
    }
  }

  async function fetchAiJobs() {
    try {
      const res = await fetch('/api/ai_music_jobs')
      if (res.ok) {
        const data = await res.json()
        setAiJobs(data.jobs || [])
      }
    } catch (error) {
      console.error(error)
    }
  }

  async function fetchGenerationSummary() {
    try {
      const res = await fetch('/api/generation/summary')
      if (res.ok) {
        const data = await res.json()
        setGenerationSummary(data.summary || { counts: {}, active_workers: [], latest_jobs: [] })
        setGenerationMaxUploadMb(data.max_upload_mb || 0)
      }
    } catch (error) {
      console.error(error)
    }
  }

  const formatAiJobLabel = (job) => {
    const shortId = (job.id || '').substring(0, 8)
    const status = (job.status || '').toLowerCase()
    const title = (job.generated_title || '').trim()
    if ((status === 'done' || status === 'completed') && title) {
      return `${title} (${shortId})`
    }
    return shortId
  }

  const generationCounts = generationSummary.counts || {}
  const generationWorkers = generationSummary.active_workers || []
  const generationJobs = generationSummary.latest_jobs || []
  const generationTotal = Object.values(generationCounts).reduce((sum, value) => sum + Number(value || 0), 0)
  const statusClass = (status) => {
    const normalized = (status || '').toLowerCase()
    if (normalized === 'ready' || normalized === 'done' || normalized === 'completed') return 'bg-green-900/30 text-green-400 border-green-500/30'
    if (normalized === 'failed' || normalized === 'expired') return 'bg-red-900/30 text-red-400 border-red-500/30'
    if (normalized === 'running' || normalized === 'uploading') return 'bg-sky-900/30 text-sky-300 border-sky-500/30'
    if (normalized === 'claimed') return 'bg-purple-900/30 text-purple-300 border-purple-500/30'
    return 'bg-amber-900/30 text-amber-400 border-amber-500/30'
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pb-6">
      <div className="glass rounded-xl p-6 border border-amber-900/50 flex flex-col lg:col-span-2">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h2 className="text-sm uppercase tracking-widest text-amber-400 font-bold flex items-center gap-2 mb-2">
              <FileAudio size={18} /> Genera Evento al Volo
            </h2>
            <p className="text-sm text-slate-400">
              Un solo pannello per provare i prompt editoriali supportati dalla regia immediata, incluso `Flash 60 Secondi`.
            </p>
          </div>
          {selectedFormat && (
            <span className="text-[10px] px-3 py-1 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 font-bold uppercase tracking-wide">
              Voce: {selectedFormat.display_name}
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_1fr] gap-4 mb-4">
          <div>
            <label className="block text-[11px] uppercase tracking-wider text-slate-500 font-bold mb-2">
              Format
            </label>
            <select
              value={selectedFormatId}
              onChange={(e) => setSelectedFormatId(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 focus:border-amber-500 rounded-lg px-3 py-3 text-sm text-slate-200 focus:outline-none transition"
            >
              {manualFormats.map((format) => (
                <option key={format.id} value={format.id}>
                  {format.label}
                </option>
              ))}
            </select>
          </div>

          <div className="rounded-lg bg-slate-900/60 border border-slate-800 px-4 py-3">
            <div className="text-[11px] uppercase tracking-wider text-slate-500 font-bold mb-2">
              Profilo selezionato
            </div>
            <div className="text-sm text-slate-200 font-semibold">
              {selectedFormat?.label || '...'}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              {selectedFormat?.description || 'Nessuna descrizione disponibile.'}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-[11px] uppercase tracking-wider text-slate-500 font-bold mb-2">
              Titolo editoriale
            </label>
            <input
              value={manualTitle}
              onChange={(e) => setManualTitle(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 focus:border-amber-500 rounded-lg px-3 py-3 text-sm text-slate-200 placeholder-slate-500 focus:outline-none transition"
              placeholder={selectedFormat?.title_placeholder || 'Titolo opzionale'}
            />
          </div>
          <div>
            <label className="block text-[11px] uppercase tracking-wider text-slate-500 font-bold mb-2">
              Brief / Focus
            </label>
            <textarea
              value={manualBrief}
              onChange={(e) => setManualBrief(e.target.value)}
              rows={3}
              className="w-full bg-slate-900 border border-slate-700 focus:border-amber-500 rounded-lg p-3 text-sm text-slate-200 placeholder-slate-500 focus:outline-none transition resize-none"
              placeholder={selectedFormat?.brief_placeholder || 'Brief opzionale'}
            />
          </div>
        </div>

        <button
          onClick={launchManualEvent}
          disabled={manualLoading || !selectedFormat}
          className="mt-auto w-full bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-bold text-sm py-3 px-4 rounded-lg transition-all shadow-[0_0_15px_rgba(245,158,11,0.3)] flex justify-center items-center gap-2"
        >
          <Play size={16} /> {manualLoading ? 'Generazione in corso...' : 'Genera e Manda in Onda'}
        </button>
      </div>

      <div className="glass rounded-xl p-6 border border-sky-900/50 flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm uppercase tracking-widest text-sky-400 font-bold flex items-center gap-2">
            <MessageSquare size={18} /> Vocali Telegram
          </h2>
          <span className="text-[10px] px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 font-bold uppercase border border-sky-500/30">
            {telegramVoices.length} In Coda
          </span>
        </div>
        <div className="flex-1 overflow-y-auto max-h-64 space-y-3 pr-2">
          {telegramVoices.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-8">Nessun vocale in attesa.</p>
          ) : (
            telegramVoices.map((v) => (
              <div key={v.id} className="bg-slate-900/80 p-3 rounded-lg border border-slate-700 flex flex-col gap-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-bold text-slate-200">{v.author || 'Ascoltatore'}</span>
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${
                      v.status === 'pending' ? 'bg-amber-900/30 text-amber-400 border-amber-500/40' :
                      v.status === 'approved' ? 'bg-sky-900/30 text-sky-300 border-sky-500/40' :
                      v.status === 'playing' ? 'bg-purple-900/30 text-purple-300 border-purple-500/40' :
                      v.status === 'played' ? 'bg-green-900/30 text-green-400 border-green-500/40' :
                      'bg-red-900/30 text-red-400 border-red-500/40'
                    }`}>
                      {v.status}
                    </span>
                    <span className="text-xs text-slate-500">{v.duration}s</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {v.is_playable ? (
                    <audio controls src={`/api/telegram-voices/play/${v.id}`} className="h-8 flex-1" />
                  ) : (
                    <div className="h-8 flex-1 flex items-center px-3 rounded bg-slate-950 border border-slate-800 text-xs text-slate-500">
                      Anteprima non disponibile
                    </div>
                  )}
                  {v.can_approve && (
                    <button onClick={() => handleTgVoice(v.id, 'approve')} className="p-2 bg-green-600/20 text-green-400 hover:bg-green-600/40 rounded-lg transition border border-green-500/30">
                      <Check size={16} />
                    </button>
                  )}
                  {v.can_reject && (
                    <button onClick={() => handleTgVoice(v.id, 'reject')} className="p-2 bg-red-600/20 text-red-400 hover:bg-red-600/40 rounded-lg transition border border-red-500/30">
                      <X size={16} />
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="glass rounded-xl p-6 border border-pink-900/50 flex flex-col">
        <h2 className="text-sm uppercase tracking-widest text-pink-400 font-bold flex items-center gap-2 mb-4">
          <Music size={18} /> Musica AI (ACE-Step)
        </h2>

        <div className="mb-6 p-4 rounded-lg bg-slate-900/50 border border-slate-800">
          <div className="flex justify-between text-xs mb-3">
            <span className="text-slate-400 font-bold uppercase tracking-wide">Modalita Rotazione</span>
            <span className="text-slate-500 font-mono">Dischi: {musicMode.counts?.library || 0} | AI: {musicMode.counts?.ai || 0}</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button onClick={() => changeMusicMode('mixed')} className={`px-3 py-2 rounded-lg text-xs font-bold transition border ${musicMode.mode === 'mixed' ? 'bg-pink-600/80 border-pink-500 text-white shadow-lg shadow-pink-500/20' : 'bg-slate-800 border-slate-700 text-slate-400'}`}>
              MIX CARTELLE + AI
            </button>
            <button onClick={() => changeMusicMode('ai_only')} className={`px-3 py-2 rounded-lg text-xs font-bold transition border ${musicMode.mode === 'ai_only' ? 'bg-pink-600/80 border-pink-500 text-white shadow-lg shadow-pink-500/20' : 'bg-slate-800 border-slate-700 text-slate-400'}`}>
              SOLO MUSICA AI
            </button>
          </div>
        </div>

        <button onClick={triggerMusicGen} className="mb-4 w-full bg-slate-800 hover:bg-slate-700 text-pink-400 font-bold py-3 px-4 rounded-lg border border-pink-900/50 transition">
          Genera Traccia AI Ora
        </button>

        <div className="flex-1 overflow-y-auto max-h-40 space-y-2 pr-2">
          {aiJobs.length === 0 ? (
            <p className="text-xs text-slate-500 text-center py-4">Nessun job in corso.</p>
          ) : (
            aiJobs.map((job) => (
              <div key={job.id} className="bg-slate-900/80 px-3 py-2 rounded border border-slate-800 flex justify-between items-center">
                <span className="text-[11px] text-slate-300 truncate mr-2">{formatAiJobLabel(job)}</span>
                <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${
                  (job.status === 'completed' || job.status === 'done') ? 'bg-green-900/30 text-green-400' :
                  job.status === 'failed' ? 'bg-red-900/30 text-red-400' :
                  'bg-amber-900/30 text-amber-400 animate-pulse'
                }`}>{job.status}</span>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="glass rounded-xl p-6 border border-indigo-900/50 flex flex-col lg:col-span-2">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <h2 className="text-sm uppercase tracking-widest text-indigo-300 font-bold flex items-center gap-2 mb-2">
              <Cpu size={18} /> Generation Queue
            </h2>
            <div className="text-xs text-slate-400">
              Job remoti/co-located per audio slot, musica AI e artifact validati.
            </div>
          </div>
          <button
            onClick={fetchGenerationSummary}
            className="h-9 w-9 inline-flex items-center justify-center rounded-lg bg-slate-900 border border-slate-700 text-slate-300 hover:text-white hover:border-indigo-500 transition"
            title="Aggiorna"
          >
            <RefreshCw size={15} />
          </button>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3 mb-5">
          {['pending', 'claimed', 'running', 'uploading', 'ready', 'failed', 'expired'].map((status) => (
            <div key={status} className="bg-slate-900/70 border border-slate-800 rounded-lg px-3 py-3">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-1">{status}</div>
              <div className="text-xl font-black text-slate-100">{generationCounts[status] || 0}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-[0.8fr_1.2fr] gap-4">
          <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-4 min-h-[180px]">
            <div className="flex items-center justify-between mb-3">
              <div className="text-[11px] uppercase tracking-wider text-slate-500 font-bold flex items-center gap-2">
                <Server size={14} /> Worker attivi
              </div>
              <span className="text-[10px] text-slate-500 font-mono">Max upload {generationMaxUploadMb || '--'} MB</span>
            </div>
            {generationWorkers.length === 0 ? (
              <div className="text-sm text-slate-500 py-8 text-center">
                Nessun worker remoto attivo.
              </div>
            ) : (
              <div className="space-y-2">
                {generationWorkers.map((worker) => (
                  <div key={worker.worker_id} className="flex items-center justify-between gap-3 rounded border border-slate-800 bg-slate-950/60 px-3 py-2">
                    <div className="min-w-0">
                      <div className="text-sm font-bold text-slate-200 truncate">{worker.worker_id}</div>
                      <div className="text-[11px] text-slate-500 truncate">{worker.last_heartbeat_at || 'heartbeat non disponibile'}</div>
                    </div>
                    <span className="text-xs font-mono text-indigo-300">{worker.active_jobs || 0} job</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-slate-900/70 border border-slate-800 rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
              <div className="text-[11px] uppercase tracking-wider text-slate-500 font-bold">
                Ultimi job
              </div>
              <span className="text-[10px] text-slate-500 font-mono">{generationTotal} totali</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/70 text-slate-500 uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-2 font-bold">Job</th>
                    <th className="px-4 py-2 font-bold">Tipo</th>
                    <th className="px-4 py-2 font-bold">Titolo/tema</th>
                    <th className="px-4 py-2 font-bold">Worker</th>
                    <th className="px-4 py-2 font-bold">Stato</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {generationJobs.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                        Nessun job di generazione registrato.
                      </td>
                    </tr>
                  ) : (
                    generationJobs.map((job) => (
                      <tr key={job.id} className="hover:bg-slate-800/40">
                        <td className="px-4 py-3 font-mono text-slate-400">{(job.id || '').slice(0, 8)}</td>
                        <td className="px-4 py-3 text-slate-300">{job.job_type || '--'}</td>
                        <td className="px-4 py-3 text-slate-300 max-w-[260px] truncate">{job.title || job.theme || job.source || '--'}</td>
                        <td className="px-4 py-3 text-slate-400 max-w-[160px] truncate">{job.worker_id || '--'}</td>
                        <td className="px-4 py-3">
                          <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${statusClass(job.status)}`}>
                            {job.status || 'pending'}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

    </div>
  )
}
