import React, { useState, useEffect } from 'react'
import { Mic, Music, MessageSquare, Play, Check, X } from 'lucide-react'

export default function Tools() {
  const [podcastTopic, setPodcastTopic] = useState('')
  const [musicMode, setMusicMode] = useState({ mode: 'mixed', counts: {} })
  const [telegramVoices, setTelegramVoices] = useState([])
  const [aiJobs, setAiJobs] = useState([])
  
  // Chat Overlay state
  const [ytVideoId, setYtVideoId] = useState('')
  const [mockMessage, setMockMessage] = useState('')
  const [mockAuthor, setMockAuthor] = useState('')
  const [mockRole, setMockRole] = useState('regular')

  useEffect(() => {
    fetchMusicMode()
    const int1 = setInterval(fetchTelegramVoices, 10000)
    const int2 = setInterval(fetchAiJobs, 10000)
    fetchTelegramVoices()
    fetchAiJobs()
    return () => { clearInterval(int1); clearInterval(int2) }
  }, [])

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
      alert("Generazione musica AI avviata in background.")
      fetchAiJobs()
    } catch (e) {}
  }

  const launchPodcast = async () => {
    if (!podcastTopic.trim()) {
      alert("Inserisci un topic per il podcast!")
      return
    }
    try {
      await fetch('/api/podcast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: podcastTopic })
      })
      alert("Richiesta Podcast inviata!")
      setPodcastTopic('')
    } catch (e) {}
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
      
      {/* Podcast */}
      <div className="glass rounded-xl p-6 border border-purple-900/50 flex flex-col">
        <h2 className="text-sm uppercase tracking-widest text-purple-400 font-bold flex items-center gap-2 mb-4">
          <Mic size={18} /> Newsica Podcast al Volo
        </h2>
        <p className="text-sm text-slate-400 mb-4">
          Digita una tematica. Ollama formulerà il copione e Chatterbox darà voce a Giulia & Marco. Verrà accodato alla fine del blocco corrente.
        </p>
        <textarea 
          value={podcastTopic}
          onChange={e => setPodcastTopic(e.target.value)}
          rows={3} 
          className="w-full bg-slate-900 border border-slate-700 focus:border-purple-500 rounded-lg p-3 text-sm text-slate-200 placeholder-slate-500 focus:outline-none transition resize-none mb-4"
          placeholder="Es: il futuro del lavoro remoto..."/>
        <button onClick={launchPodcast} className="mt-auto w-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-sm py-3 px-4 rounded-lg transition-all shadow-[0_0_15px_rgba(147,51,234,0.3)] flex justify-center items-center gap-2">
          <Play size={16} /> Genera e Manda in Onda
        </button>
      </div>

      {/* Telegram Voices */}
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
            telegramVoices.map(v => (
              <div key={v.id} className="bg-slate-900/80 p-3 rounded-lg border border-slate-700 flex flex-col gap-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-bold text-slate-200">{v.author}</span>
                  <span className="text-xs text-slate-500">{v.duration}s</span>
                </div>
                <div className="flex items-center gap-2">
                  <audio controls src={`/api/telegram-voices/play/${v.id}`} className="h-8 flex-1" />
                  <button onClick={() => handleTgVoice(v.id, 'approve')} className="p-2 bg-green-600/20 text-green-400 hover:bg-green-600/40 rounded-lg transition border border-green-500/30">
                    <Check size={16} />
                  </button>
                  <button onClick={() => handleTgVoice(v.id, 'reject')} className="p-2 bg-red-600/20 text-red-400 hover:bg-red-600/40 rounded-lg transition border border-red-500/30">
                    <X size={16} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Musica AI */}
      <div className="glass rounded-xl p-6 border border-pink-900/50 flex flex-col">
        <h2 className="text-sm uppercase tracking-widest text-pink-400 font-bold flex items-center gap-2 mb-4">
          <Music size={18} /> Musica AI (ACE-Step)
        </h2>
        
        <div className="mb-6 p-4 rounded-lg bg-slate-900/50 border border-slate-800">
          <div className="flex justify-between text-xs mb-3">
            <span className="text-slate-400 font-bold uppercase tracking-wide">Modalità Rotazione</span>
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
            aiJobs.map(job => (
              <div key={job.id} className="bg-slate-900/80 px-3 py-2 rounded border border-slate-800 flex justify-between items-center">
                <span className="text-[11px] text-slate-300 font-mono truncate mr-2">{job.id.substring(0,8)}</span>
                <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${
                  job.status === 'completed' ? 'bg-green-900/30 text-green-400' :
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
