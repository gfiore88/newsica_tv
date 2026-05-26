import React, { useEffect, useState } from 'react'
import { FileAudio, Music, MessageSquare, Play, Check, X } from 'lucide-react'

export default function Tools() {
  const [manualFormats, setManualFormats] = useState([])
  const [selectedFormatId, setSelectedFormatId] = useState('news')
  const [manualTitle, setManualTitle] = useState('')
  const [manualBrief, setManualBrief] = useState('')
  const [manualLoading, setManualLoading] = useState(false)
  const [musicMode, setMusicMode] = useState({ mode: 'mixed', counts: {} })
  const [telegramVoices, setTelegramVoices] = useState([])
  const [aiJobs, setAiJobs] = useState([])

  useEffect(() => {
    fetchMusicMode()
    fetchManualFormats()
    fetchTelegramVoices()
    fetchAiJobs()
    const telegramInterval = setInterval(fetchTelegramVoices, 10000)
    const jobsInterval = setInterval(fetchAiJobs, 10000)
    return () => {
      clearInterval(telegramInterval)
      clearInterval(jobsInterval)
    }
  }, [])

  const selectedFormat = manualFormats.find((item) => item.id === selectedFormatId) || null

  const fetchManualFormats = async () => {
    try {
      const res = await fetch('/api/manual-event-formats')
      if (!res.ok) return
      const data = await res.json()
      const formats = data.formats || []
      setManualFormats(formats)
      if (formats.length > 0 && !formats.some((item) => item.id === selectedFormatId)) {
        setSelectedFormatId(formats[0].id)
      }
    } catch (e) {}
  }

  const fetchMusicMode = async () => {
    try {
      const res = await fetch('/api/music_mode')
      if (res.ok) setMusicMode(await res.json())
    } catch (e) {}
  }

  const changeMusicMode = async (mode) => {
    try {
      const res = await fetch('/api/music_mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode })
      })
      if (res.ok) setMusicMode(await res.json())
    } catch (e) {}
  }

  const triggerMusicGen = async () => {
    try {
      await fetch('/api/music_gen', { method: 'POST' })
      alert('Generazione musica AI avviata in background.')
      fetchAiJobs()
    } catch (e) {}
  }

  const launchManualEvent = async () => {
    if (!selectedFormat) {
      alert('Nessun format disponibile.')
      return
    }
    if (selectedFormat.requires_brief && !manualBrief.trim()) {
      alert('Questo format richiede un tema o un brief.')
      return
    }

    setManualLoading(true)
    try {
      const res = await fetch('/api/manual-event', {
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
        alert(`Generazione avviata: ${data.title}`)
        setManualTitle('')
        setManualBrief('')
      } else {
        alert(data.message || 'Errore nella generazione del format.')
      }
    } catch (e) {
      alert('Errore nell\'invio della richiesta.')
    } finally {
      setManualLoading(false)
    }
  }

  const fetchTelegramVoices = async () => {
    try {
      const res = await fetch('/api/telegram-voices')
      if (res.ok) {
        const data = await res.json()
        setTelegramVoices(data.voices || [])
      }
    } catch (e) {}
  }

  const handleTgVoice = async (id, action) => {
    try {
      await fetch(`/api/telegram-voices/${action}/${id}`, { method: 'POST' })
      fetchTelegramVoices()
    } catch (e) {}
  }

  const fetchAiJobs = async () => {
    try {
      const res = await fetch('/api/ai_music_jobs')
      if (res.ok) {
        const data = await res.json()
        setAiJobs(data.jobs || [])
      }
    } catch (e) {}
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
                <span className="text-[11px] text-slate-300 font-mono truncate mr-2">{job.id.substring(0, 8)}</span>
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
    </div>
  )
}
